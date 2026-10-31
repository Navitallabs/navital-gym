#!/usr/bin/env python3
"""Check an outside submission (see SUBMITTING.md) offline: no model is called and nothing is trusted from the file except the model's own words and tool calls.
usage: python3 scripts/verify_submission.py submissions/<model-slug>/<env>-<slug>-<full|easy|sN>.json [--allow-incomplete]
Next to the run file: <same name>.transcripts.json and submission.json ({"model", "provider", "date": "YYYY-MM-DD", "submitter", "notes"}).
Checks, each with a reason on failure:
  1 files and schema   run file, transcripts and submission.json parse; exactly one model; settings.model/provider; submission.json names that model
  2 task ids           exactly the public task ids of that split (full / easy) or the deterministic stratified sample (sN); nothing else, nothing hidden or held out
  3 prompts            every transcript starts with the public prompt of its task
  4 replay             every tool call is replayed on a fresh world (worlds are deterministic): each recorded tool result must equal the replayed one,
                       then the final answer is graded by the CURRENT grader; solved/score/rules must equal the claimed ones, and so must the summary pass@1
  5 grader id          graded_with / the run's own commit is compared with the current grader id: a different id is reported, and the replay decides
  6 complete           every task answered (a task that ended in a provider error is 'not run'); --allow-incomplete only lists them
Prints PASS or FAIL with every reason; exit code 0 / 1. A PASS means the file is internally consistent and reproducible by the public grader. It cannot prove WHICH model produced
the words (rows are labelled 'community, self-reported')."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
from navital_gym.core.agents import extract_json
from navital_gym.core.grader import summarize
from navital_gym.core.version import code_id
from navital_gym.cli import stratified
import runfiles

ENV_RE = re.compile(r"^(?P<env>[a-z_]+)-.+-(?P<kind>full|easy|s\d+)$")

def _load(path, reasons, what):
    try:
        with open(path) as f: return json.load(f)
    except (OSError, ValueError) as e:
        reasons.append(f"{what}: cannot read {os.path.basename(path)} ({type(e).__name__})"); return None

REPAIR_PREFIX = "Your answer did not parse:"       # the runner's format-repair and forced-final prompts (core/agents.py REPAIR / FINAL): meta is derived from them, never taken from the file
FINAL_PROMPT = "You have used all your tool calls."

def _same(claimed, mine, path, bad):
    """Every number the file claims must equal the recomputed one, recursively (a missing key counts as different)."""
    if isinstance(claimed, dict):
        for k, v in claimed.items():
            if not isinstance(mine, dict) or k not in mine: bad.append(f"{path}/{k}: missing in the recomputed summary")
            else: _same(v, mine[k], f"{path}/{k}", bad)
    elif isinstance(claimed, bool) or not isinstance(claimed, (int, float)):
        if claimed != mine: bad.append(f"{path}: claimed {claimed!r}, recomputed {mine!r}")
    elif not isinstance(mine, (int, float)) or abs(float(claimed) - float(mine)) > 1e-6: bad.append(f"{path}: claimed {claimed}, recomputed {mine}")

def verify(path, allow_incomplete=False):
    """-> (ok, reasons, notes). reasons are failures, notes are information."""
    return check(path, allow_incomplete)[:3]

def check(path, allow_incomplete=False):
    """-> (ok, reasons, notes, summary). `summary` is RECOMPUTED from the replay: publish this, never the file's own summary."""
    ok, reasons, notes, summary = _check(path, allow_incomplete)
    return ok, reasons, notes, (summary if ok else None)

def _check(path, allow_incomplete):
    reasons, notes = [], []
    base = os.path.basename(path)[:-5] if path.endswith(".json") else os.path.basename(path)
    m = ENV_RE.match(base)
    if not m:
        return False, [f"file name must be <env>-<model-slug>-<full|easy|sN>.json, got {os.path.basename(path)}"], notes, None
    env_name, kind = m["env"], m["kind"]
    data = _load(path, reasons, "run file")
    tr_all = _load(path[:-5] + ".transcripts.json", reasons, "transcripts")
    meta = _load(os.path.join(os.path.dirname(path), "submission.json"), reasons, "submission.json")
    if reasons or data is None or meta is None: return False, reasons or ["unreadable files"], notes, None
    # 1 schema
    if not isinstance(data, dict) or len(data) != 1:
        return False, ["run file must hold exactly one model"], notes, None
    agent, d = next(iter(data.items()))
    for key in ("settings", "summary", "tasks"):
        if key not in d: reasons.append(f"run file: missing '{key}'")
    st = d.get("settings") or {}
    for key in ("model", "provider"):
        if not st.get(key): reasons.append(f"run file settings: missing '{key}'")
    for key in ("model", "provider", "date", "submitter"):
        if not isinstance(meta.get(key), str) or not meta[key].strip(): reasons.append(f"submission.json: missing '{key}'")
    if isinstance(meta.get("date"), str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]): reasons.append("submission.json: date must be YYYY-MM-DD")
    if st.get("model") and meta.get("model") and meta["model"] not in (st["model"], agent): reasons.append(f"submission.json model '{meta['model']}' is not the run's model '{st['model']}'")
    if reasons: return False, reasons, notes, None
    # 2 task ids
    easy = kind == "easy"
    try:
        env = runfiles.load_env_for(path)
    except Exception as e:
        return False, [f"unknown environment '{env_name}' ({type(e).__name__})"], notes, None
    public = set(env.tasks)
    expected = set(stratified(env, int(kind[1:]))) if kind.startswith("s") else public
    if kind.startswith("s") and not easy and set(d["tasks"]) != expected:      # the CLI draws a sample from the default split; support's default is the 50 core tasks
        import importlib
        core_env = importlib.import_module(f"navital_gym.envs.{env_name}").load_env()
        if set(d["tasks"]) == set(stratified(core_env, int(kind[1:]))): expected = set(d["tasks"])
    if kind == "full" and not easy:        # support: the 50 core tasks alone, or core + the 26 labelled-experimental ones (both are 'the standard split')
        import importlib
        core = set(importlib.import_module(f"navital_gym.envs.{env_name}").load_env().tasks)
        if set(d["tasks"]) == core: expected = core
    got = set(d["tasks"])
    if got - public: reasons.append(f"task ids outside the public split: {sorted(got - public)[:5]} (held-out or invented tasks are not accepted)")
    elif got != expected: reasons.append(f"task ids are not the {'stratified sample' if kind.startswith('s') else 'full ' + ('easy' if easy else 'standard') + ' split'}: missing {sorted(expected - got)[:5]}, extra {sorted(got - expected)[:5]}")
    if reasons: return False, reasons, notes, None
    # 3-4 prompts and replay
    tr_all = tr_all or {}
    tr = tr_all.get(agent) or (next(iter(tr_all.values())) if len(tr_all) == 1 else {})
    empty = sorted(tid for tid, runs in d["tasks"].items() if not isinstance(runs, list) or not runs)
    if empty: reasons.append(f"{len(empty)} task(s) have no run recorded ({', '.join(empty[:5])}{', ...' if len(empty) > 5 else ''}): every task needs at least one attempt and its transcript")
    ks = {len(runs) for runs in d["tasks"].values() if isinstance(runs, list) and runs}
    if len(ks) > 1: reasons.append(f"tasks have different numbers of runs ({sorted(ks)}): every task needs the same k")
    if reasons: return False, reasons, notes, None
    replayed = {}
    for tid, runs in d["tasks"].items():
        runs_msgs = tr.get(tid, [])
        out = []
        for i, old in enumerate(runs):
            if (old.get("meta") or {}).get("error"):                          # a task the submission calls "not run": never believed when it has a transcript
                if i < len(runs_msgs) and runs_msgs[i]: reasons.append(f"{tid} run {i}: marked as a provider error but the transcript has an answer: errors are not accepted from the file")
                elif allow_incomplete: out.append(old)                        # local check only: listed as incomplete below, never published
                else: reasons.append(f"{tid} run {i}: marked not run (provider error): re-run with --resume until every task is answered")
                continue
            if i >= len(runs_msgs) or not runs_msgs[i]:
                reasons.append(f"{tid} run {i}: no transcript"); continue
            msgs = runs_msgs[i]
            prompt = env.reset(tid)["prompt"]                      # the prompt the agent is shown NOW (GST standard prompts name the answer fields): a run from an older prompt is rejected
            first = next((x for x in msgs if x.get("role") == "user"), None)
            if not first or prompt not in (first.get("content") or ""):
                reasons.append(f"{tid} run {i}: transcript does not start with the public prompt"); continue
            results_by_id = {x.get("tool_call_id"): x.get("content") for x in msgs if x.get("role") == "tool"}
            bad_tool = None
            for x in msgs:
                for c in (x.get("tool_calls") or []) if x.get("role") == "assistant" else []:
                    res = env.world.call(c["name"], c.get("args"))
                    rec = results_by_id.get(c.get("id"))
                    try:
                        same = json.loads(rec or "null") == json.loads(json.dumps(res))
                    except (TypeError, ValueError):
                        same = False
                    if not same and bad_tool is None: bad_tool = c["name"]
            if bad_tool:
                reasons.append(f"{tid} run {i}: recorded result of tool '{bad_tool}' differs from the replayed world (edited transcript)"); continue
            final = [x for x in msgs if x.get("role") == "assistant" and not x.get("tool_calls")]
            sub = extract_json(final[-1].get("content") or "") if final else None
            sc = env.grade(env.task, sub)
            users = [(x.get("content") or "") for x in msgs if x.get("role") == "user"]     # meta is derived from the transcript, not copied from the file
            sc.meta = {"error": None, "repaired": any(u.startswith(REPAIR_PREFIX) for u in users), "turns_exhausted": any(u.startswith(FINAL_PROMPT) for u in users),
                       "turns": sum(1 for x in msgs if x.get("role") == "assistant")}
            claimed_meta = old.get("meta") or {}
            for key in ("repaired", "turns_exhausted"):
                if key in claimed_meta and bool(claimed_meta[key]) != sc.meta[key]:
                    reasons.append(f"{tid} run {i}: claims {key}={claimed_meta[key]}, the transcript shows {sc.meta[key]}")
            mine = sc.to_dict()
            if (mine["solved"], mine["score"], mine["rules"], mine["valid"]) != (old.get("solved"), old.get("score"), old.get("rules"), old.get("valid")):
                reasons.append(f"{tid} run {i}: claims solved={old.get('solved')} score={old.get('score')}, the public grader gives solved={mine['solved']} score={mine['score']}")
            out.append(sc)
        replayed[tid] = out
    if reasons: return False, reasons, notes, None
    from navital_gym.core.grader import Score
    scored = {tid: [r if isinstance(r, Score) else Score(score=r.get("score", 0.0), solved=r.get("solved", False), valid=r.get("valid", False), rules=r.get("rules", {}), details=r.get("details", {}),
                                                         soft=r.get("soft", {}), verdict=r.get("verdict", ""), meta=r.get("meta", {})) for r in runs] for tid, runs in replayed.items()}
    mine = summarize(scored, env.tasks); claimed = d["summary"]
    bad = []; _same(claimed, mine, "summary", bad)
    reasons.extend(bad[:8] + ([f"... {len(bad) - 8} more summary differences"] if len(bad) > 8 else []))
    # 5 grader id
    now = code_id() or ""; was = d.get("graded_with") or d.get("navital_gym_commit")
    if now.endswith("-dirty"): notes.append(f"this checkout's navital_gym/ has uncommitted edits ({now}): verify on a clean checkout")
    if was != now: notes.append(f"graded/run at grader id {was}, current is {now}")
    # 6 complete
    n_ans, n_all = mine.get("answered", 0), mine.get("tasks", 0)
    if n_ans < n_all:
        (notes if allow_incomplete else reasons).append(f"incomplete: {n_ans} of {n_all} tasks answered (the rest ended in provider errors)")
    notes.append("rows from submissions are labelled 'community, self-reported': the file cannot prove which model wrote the answers")
    if not reasons: notes.append(f"replayed at {now}: every verdict is recomputed by replay at the current grader id and matches")
    return not reasons, reasons, notes, mine

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__); sys.exit(2)
    ok, reasons, notes = verify(args[0], allow_incomplete="--allow-incomplete" in sys.argv)
    for r in reasons: print("  FAIL:", r)
    for n in notes: print("  note:", n)
    print(("PASS" if ok else "FAIL"), os.path.basename(args[0]))
    sys.exit(0 if ok else 1)
