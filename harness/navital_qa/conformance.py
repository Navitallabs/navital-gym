"""Grader-correctness harness shared by all Navital envs (T-099c, qa). Stdlib only.

A grader is any callable  grade(task: dict, submission: Any) -> dict  returning at least
  {"score": float 0..1, "solved": bool, "rules": {rule_id: bool}}   (extra keys allowed)
Wire it with --grader module:function (module importable from --path dirs).

Three suites, run for every case file under cases/<env>/*.json:
  1. CORRECTNESS  hand-solved cases score right; each single-violation case fails exactly the
                  rule(s) it names; infeasible-claim cases follow the task's expected_feasible.
  2. CHEATING     generic cheat mutations of every solved submission (empty, wrong types,
                  prompt copy, claimed score/solved fields, zero cost, status flip...) must NOT
                  score as solved and must score below the hand-solved score.
  3. DETERMINISM  N reruns identical; key order / whitespace of the JSON must not change the
                  score; the grader must not mutate its inputs; no dependence on wall clock/env.

Case file:
{ "env": "trip", "task_id": "IN-TRIP-002", "task": {...task row...},
  "cases": [ {"name": "...", "kind": "solved|violation|cheat|infeasible_claim",
              "submission": ..., "expect": {"solved": true, "min_score": 1.0, "max_score": 1.0,
              "fails": ["R-OPEN"], "passes_all_but": ["R-OPEN"]}} ] }
"""
import argparse, copy, glob, importlib, json, os, sys

CHEAT_SCORE_CAP = 0.5   # generic cheats must score below this unless the case says otherwise


def load_grader(spec, paths):
    for p in paths:
        sys.path.insert(0, os.path.abspath(p))
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), default=str)


def shuffled(x, depth=0):
    """Same JSON value, keys reversed at every level (order must not matter)."""
    if isinstance(x, dict):
        return {k: shuffled(x[k], depth + 1) for k in reversed(list(x.keys()))}
    if isinstance(x, list):
        return [shuffled(v, depth + 1) for v in x]
    return x


CLAIMED = ["total_cost", "cost", "price", "score", "solved", "passed", "rules"]


def cheats_for(task, sub, expect):
    """Returns (must_fail, must_ignore): lists of (name, submission).
    must_fail: breaking/cheating submissions that must not solve and must score low.
    must_ignore: only agent-CLAIMED fields change; the graded content is identical, so the grader's
    result must be exactly the hand-solved result (it recomputes, it never trusts the agent)."""
    fail = [("empty_object", {}), ("empty_list", []), ("null", None), ("string", "i solved it"),
            ("number", 1), ("prompt_copy", task.get("prompt", "")), ("huge_string", "A" * 200_000)]
    ign = []
    if isinstance(sub, dict):
        fail.append(("claimed_only", {"score": 1.0, "solved": True}))
        for k in expect.get("claimed_fields", CLAIMED):
            if k in sub:
                ign += [(f"zero_{k}", {**sub, k: 0}), (f"drop_{k}", {x: v for x, v in sub.items() if x != k})]
        ign.append(("claimed_score", {**sub, "score": 1.0, "solved": True, "passed": True}))
        if sub.get("status") == "plan":
            fail.append(("flip_to_infeasible", {**sub, "status": "infeasible", "binding": []}))
        if sub.get("status") == "infeasible":
            fail.append(("flip_to_plan", {**sub, "status": "plan", "days": []}))
        for k in expect.get("required_fields", []):   # env opts in: dropping a required field must not solve
            fail.append((f"drop_required_{k}", {x: v for x, v in sub.items() if x != k}))
        if isinstance(sub.get("days"), list) and sub["days"]:
            fail.append(("duplicate_days", {**sub, "days": sub["days"] + copy.deepcopy(sub["days"])}))
        if expect.get("id_field"):                    # env opts in: unknown ids must not solve
            f = expect["id_field"]
            fail.append(("invented_ids", json.loads(canon(sub).replace(f'"{f}":"', f'"{f}":"zz_'))))
    return fail, ign


class Report:
    def __init__(self):
        self.rows, self.fail = [], 0

    def check(self, suite, case, ok, detail=""):
        self.rows.append({"suite": suite, "case": case, "ok": bool(ok), "detail": detail})
        if not ok:
            self.fail += 1

    def summary(self):
        by = {}
        for r in self.rows:
            s = by.setdefault(r["suite"], [0, 0])
            s[0] += r["ok"]; s[1] += 1
        return by


def safe_grade(grader, task, sub):
    """Grade a deep copy; a crash is a result, not a harness error."""
    try:
        return grader(copy.deepcopy(task), copy.deepcopy(sub)), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def run_file(grader, path, rep, reruns):
    doc = json.load(open(path))
    task, env, tid = doc["task"], doc.get("env", "?"), doc["task_id"]
    solved_cases = []
    for c in doc["cases"]:
        name = f"{env}/{tid}/{c['name']}"
        res, err = safe_grade(grader, task, c["submission"])
        ex = c.get("expect", {})
        if res is None:
            rep.check("correctness", name, False, f"grader crashed on a well-formed case: {err}")
            continue
        sc = res.get("score")
        ok_range = isinstance(sc, (int, float)) and 0 <= sc <= 1
        rep.check("correctness", name + ":score_in_0_1", ok_range, f"score={sc!r}")
        if "solved" in ex:
            rep.check("correctness", name + ":solved", bool(res.get("solved")) == ex["solved"], f"got {res.get('solved')}, want {ex['solved']}")
        if "min_score" in ex:
            rep.check("correctness", name + ":min", ok_range and sc >= ex["min_score"] - 1e-9, f"score {sc} < {ex['min_score']}")
        if "max_score" in ex:
            rep.check("correctness", name + ":max", ok_range and sc <= ex["max_score"] + 1e-9, f"score {sc} > {ex['max_score']}")
        rules = res.get("rules") or {}
        for r in ex.get("fails", []):
            rep.check("correctness", name + f":fails_{r}", rules.get(r) is False, f"rules[{r}]={rules.get(r)!r}")
        if "passes_all_but" in ex:   # single-violation purity: only these rules may fail
            bad = sorted(r for r, v in rules.items() if v is False and r not in ex["passes_all_but"])
            rep.check("correctness", name + ":only_named_rules_fail", not bad, f"also failed: {bad}")
        if c["kind"] == "solved":
            solved_cases.append((c, res))
        # determinism, per case
        outs = {canon(res)}
        for _ in range(reruns):
            r2, e2 = safe_grade(grader, task, c["submission"])
            outs.add(canon(r2) if r2 is not None else f"crash:{e2}")
        rep.check("determinism", name + ":reruns", len(outs) == 1, f"{len(outs)} distinct outputs over {reruns + 1} runs")
        r3, e3 = safe_grade(grader, task, shuffled(c["submission"]))
        same = r3 is not None and canon({k: r3[k] for k in ("score", "solved") if k in r3}) == canon({k: res[k] for k in ("score", "solved") if k in res})
        rep.check("determinism", name + ":key_order_independent", same, "score changed when JSON key order changed")
        t0, s0 = copy.deepcopy(task), copy.deepcopy(c["submission"])
        try:
            grader(t0, s0)
            rep.check("determinism", name + ":no_input_mutation", t0 == task and s0 == c["submission"], "grader mutated its inputs")
        except Exception:  # noqa: BLE001
            pass
    # cheating: mutations of every solved case
    for c, base in solved_cases:
        base_score = base.get("score", 1.0)
        must_fail, must_ignore = cheats_for(task, c["submission"], c.get("expect", {}))
        for cname, cs in must_fail:
            name = f"{env}/{tid}/{c['name']}~{cname}"
            res, err = safe_grade(grader, task, cs)
            if res is None:   # a clean crash is NOT acceptable: must degrade to a score
                rep.check("cheating", name, False, f"grader crashed instead of scoring 0: {err}")
                continue
            sc = res.get("score", 1.0)
            # Plan-shaped cheats (a valid-looking submission edited) legitimately keep partial rule credit; they only must not SOLVE.
            # Structural garbage (empty, wrong types, claimed fields only...) must also score low.
            plan_shaped = cname in ("duplicate_days", "invented_ids") or cname.startswith("drop_required_") or cname.startswith("flip_")
            low = True if plan_shaped else sc < min(CHEAT_SCORE_CAP, base_score) - 1e-9
            rep.check("cheating", name, (not res.get("solved")) and low, f"cheat scored {sc} solved={res.get('solved')}")
        for cname, cs in must_ignore:
            name = f"{env}/{tid}/{c['name']}~{cname}"
            res, err = safe_grade(grader, task, cs)
            same = res is not None and (res.get("score"), res.get("solved")) == (base.get("score"), base.get("solved"))
            rep.check("cheating", name, same, f"agent-claimed field changed the result: {err or (res.get('score'), res.get('solved'))}")
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--grader", required=True, help="module:function")
    ap.add_argument("--path", action="append", default=[], help="dir to add to sys.path")
    ap.add_argument("--cases", default=os.path.join(os.path.dirname(__file__), "..", "cases"))
    ap.add_argument("--env", help="only this env directory under --cases")
    ap.add_argument("--reruns", type=int, default=3)
    ap.add_argument("--json", help="write full report here")
    a = ap.parse_args(argv)
    grader = load_grader(a.grader, a.path)
    pat = os.path.join(a.cases, a.env or "*", "*.json")
    files = sorted(glob.glob(pat))
    if not files:
        sys.exit(f"no case files match {pat}")
    rep = Report()
    for f in files:
        run_file(grader, f, rep, a.reruns)
    known = []
    kpath = os.path.join(a.cases, "known_failures.json")
    if os.path.exists(kpath):
        known = json.load(open(kpath)).get("known", [])
    def is_known(r):
        return next((k for k in known if k["env"] == r["case"].split("/")[0] and k["match"] in r["case"] and k["suite"] == r["suite"]), None)
    for suite, (ok, n) in sorted(rep.summary().items()):
        print(f"{suite:12} {ok}/{n}")
    nknown = 0
    for r in rep.rows:
        if not r["ok"]:
            k = is_known(r)
            if k: nknown += 1; continue
            print("FAIL", r["suite"], r["case"], "-", r["detail"])
    if nknown:
        whys = sorted({k["id"] for k in known})
        print(f"KNOWN failures (not counted, tracked in cases/known_failures.json: {', '.join(whys)}): {nknown}")
    rep.fail -= nknown
    if a.json:
        json.dump({"summary": rep.summary(), "rows": rep.rows}, open(a.json, "w"), indent=1)
    print("RESULT:", "PASS" if not rep.fail else f"FAIL ({rep.fail})")
    return 1 if rep.fail else 0


if __name__ == "__main__":
    sys.exit(main())
