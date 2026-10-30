#!/usr/bin/env python3
"""leaderboard.json for the website, built ONLY from the saved (regraded) run files. One entry per model x env x split x sample.
Fields: model, provider, tier (small|large), env, split, sample ("stratified-15", "stratified-5", "full"), n (tasks), pass_at_1, strict_pass_at_1, pass_pow_k (+ k), format_fail,
errors, partial_credit, harness_commit (id of the grading code: git tree id of navital_gym/, verify with `git rev-parse v1.0.1:navital_gym`), date, source (run file), origin (navital = our own runs, community = a verified outside submission under submissions/<model-slug>/, with submitter and self_reported=true). Rows where at least half the tasks hit provider errors are
left out and listed under `excluded`; so are incomplete runs (fewer tasks than their sample size) and, with --commit, runs graded at another commit.
usage: python3 scripts/export_leaderboard.py [out.json] [--runs DIR] [--submissions DIR] [--commit SHA] [--require-single-commit]
  out.json   default docs/leaderboard.json            --runs DIR   default <repo>/runs (read only)     --submissions DIR   default <repo>/submissions; each */*.json is verified (scripts/verify_submission.py) before it is counted
  --commit SHA            keep only run files whose graded_with is SHA (use the launch commit after scripts/regrade.py); others go to `excluded`
  --require-single-commit exit 2 unless every published row was graded by ONE commit (the site says so; this makes it true)
Each entry carries rule_failures ({rule id: count}, per task at k=1; a task can fail several rules; answered tasks only; null when k>1, where counts would be runs, not tasks); top level rule_names maps env -> rule id -> the rule's `description` from rules.py verbatim ("" if it has none).
Top level also carries grader_commits, ungraded (run files with no graded_with), single_grader_commit, and task_counts (tasks per env and split) so the site need not hand-keep them.
`date` is the run file's modification time (date_basis says so): scripts/regrade.py rewrites files, so after a regrade it is the regrade date, not the day the model ran."""
import glob, importlib, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import runfiles
LARGE = ("sonnet", "opus", "fable", "-pro")
argv = sys.argv[1:]
if "-h" in argv or "--help" in argv:
    print(__doc__); sys.exit(0)
def opt(name, default=None, flag=False):
    if name in argv:
        i = argv.index(name); argv.pop(i)
        return True if flag else argv.pop(i)
    return default
RUNS = opt("--runs", os.path.join(ROOT, "runs")); SUBS = opt("--submissions", os.path.join(ROOT, "submissions")); ONLY_COMMIT = opt("--commit"); REQUIRE_ONE = opt("--require-single-commit", flag=True)
out_path = argv[0] if argv else os.path.join(ROOT, "docs", "leaderboard.json")
entries, excluded = [], []
ours = sorted(p for p in glob.glob(os.path.join(RUNS, "*.json")) if not p.endswith((".transcripts.json", ".stale.json", "spend-ledger.json")) and "scripted" not in p and "smoke" not in p)
theirs = sorted(p for p in glob.glob(os.path.join(SUBS, "*", "*.json")) if not p.endswith((".transcripts.json", "submission.json")))
if theirs:
    import verify_submission
for path, origin in [(p, "navital") for p in ours] + [(p, "community") for p in theirs]:
    name = os.path.basename(path)[:-5]
    parts = name.split("-")
    env = parts[0]
    easy = name.endswith("-easy")
    sample = "full" if name.endswith("-full") else "easy" if easy else ("stratified-" + name.rsplit("-s", 1)[1]) if "-s" in name and name.rsplit("-s", 1)[1].isdigit() else None
    if sample is None:
        continue
    date = time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(path)))
    extra = {"origin": origin}
    if origin == "community":        # only a submission that scripts/verify_submission.py passes reaches the table; its verdicts were replayed at the CURRENT grader
        ok, reasons, _, recomputed = verify_submission.check(path)
        meta = json.load(open(os.path.join(os.path.dirname(path), "submission.json")))
        if not ok:
            excluded.append({"model": meta.get("model", name), "provider": meta.get("provider", "unknown"), "env": env, "sample": sample, "reason": "submission failed verification: " + "; ".join(reasons)[:300],
                             "source": os.path.relpath(path, ROOT) if path.startswith(ROOT) else os.path.basename(path), "origin": origin})
            continue
        date, extra = meta["date"], {"origin": origin, "submitter": meta["submitter"], "self_reported": True}
    for agent, d in json.load(open(path)).items():
        if d.get("partial"):
            continue
        if origin == "community":
            from navital_gym.core.version import code_id
            d["graded_with"] = code_id()
            extra = {**extra, "graded_by": f"replayed at {code_id()}"}
            d["summary"] = recomputed          # published numbers come from the replay, never from the submitter's own summary
        st, s = d.get("settings", {}), d["summary"]
        model, provider = st.get("model", agent), st.get("provider", "unknown")
        base = {"model": model, "provider": provider, "tier": "large" if any(x in model.lower() for x in LARGE) else "small", "env": env, "sample": sample,
                "harness_commit": d.get("graded_with"), "date": date, "date_basis": "submission.json" if origin == "community" else "file-modified", "source": os.path.basename(path), **extra}
        if easy and s.get("answered", s["tasks"]) < len(runfiles.env_tasks(env, easy=True)):
            excluded.append({**base, "reason": f"incomplete run: {s.get('answered', s['tasks'])} answered of {len(runfiles.env_tasks(env, easy=True))} easy tasks", "n": s["tasks"]})
            continue
        if sample == "full" and s.get("answered", s["tasks"]) < len(importlib.import_module(f"navital_gym.envs.{env}").load_env().tasks):
            continue                 # a full-set run still in progress is not published as a result
        want = int(sample.split("-")[1]) if sample.startswith("stratified-") else None
        if want is not None and s.get("answered", s["tasks"]) < want:
            excluded.append({**base, "reason": f"incomplete run: {s.get('answered', s['tasks'])} of {want} tasks answered ({s.get('not_run', 0)} not run)", "n": s["tasks"]})
            continue
        if ONLY_COMMIT and d.get("graded_with") != ONLY_COMMIT:
            excluded.append({**base, "reason": f"graded at {d.get('graded_with') or 'no recorded commit'}, not {ONLY_COMMIT}: run scripts/regrade.py", "n": s["tasks"]})
            continue
        if s["errors"] >= 0.5:
            excluded.append({**base, "reason": f"{s['errors']:.0%} of tasks ended in provider errors", "n": s["tasks"]})
            continue
        groups = {"all": s}
        for split, sub in (s.get("by_split") or {}).items():
            if len(s["by_split"]) > 1:
                groups[split] = sub
        if easy:
            groups = {"easy": s}
        for split, g in groups.items():
            ids = None if split in ("all", "easy") else {tid for tid, t in runfiles.env_tasks(base["env"]).items() if t.meta.get("split", "core") == split}
            entries.append({**base, "split": split, "n": g.get("answered", g["tasks"]), "pass_at_1": round(g["pass@1"], 4), "strict_pass_at_1": round(g["strict_pass@1"], 4),
                            "k": g["k"], "pass_pow_k": round(g["pass^k"], 4), "format_fail": round(g["format_fail"], 4), "errors": round(g["errors"], 4),
                            "truncated_tasks": runfiles.truncated_tasks(d["tasks"], ids),
                            "rule_failures": dict(sorted((g.get("rule_failures") or {}).items())) if g["k"] == 1 else None,
                            "partial_credit": round(runfiles.first_run_partial(d["tasks"], g) if g["k"] > 1 and split == "all" else g["mean_score"], 4)})
entries.sort(key=lambda e: (e["env"], e["split"], e["sample"], e["model"]))
commits = sorted({e["harness_commit"] for e in entries if e["harness_commit"]})
ungraded = sorted({e["source"] for e in entries if not e["harness_commit"]})
single = len(commits) == 1 and not ungraded
task_counts = {}
for env in sorted({e["env"] for e in entries}):
    envo = importlib.import_module(f"navital_gym.envs.{env}")
    try: allt = envo.load_env(include_experimental=True).tasks
    except TypeError: allt = envo.load_env().tasks
    from navital_gym.core.grader import task_split
    counts = {"all": len(allt)}
    for sp in sorted({task_split(t) for t in allt.values()}):
        if len({task_split(t) for t in allt.values()}) > 1: counts[sp] = sum(1 for t in allt.values() if task_split(t) == sp)
    task_counts[env] = counts
rule_names = {}                      # verbatim `description` of each rule, "" when rules.py has none (never filled in here: editing navital_gym/ changes the grader id)
for env in sorted({e["env"] for e in entries}):
    rules = importlib.import_module(f"navital_gym.envs.{env}").load_env().grader.rules
    rule_names[env] = {rid: getattr(r, "description", "") or "" for rid, r in sorted(rules.items())}
    for e in entries:
        if e["env"] == env:
            for rid in e["rule_failures"] or {}:
                rule_names[env].setdefault(rid, "")
doc = {"generated": time.strftime("%Y-%m-%d"), "note": "Small samples: with n=15 one task is 6.7 points. Built from run files; see docs/RESULTS.md. Small and mid-size models are marked tier=small; tier=large rows have fewer tasks unless sample=full.",
       "grader_commits": commits, "ungraded": ungraded, "single_grader_commit": single, "task_counts": task_counts,
       "rule_failures_note": "per task at k=1; a task can fail several rules; answered tasks only", "rule_names": rule_names, "entries": entries, "excluded": excluded}
json.dump(doc, open(out_path, "w"), indent=1, ensure_ascii=False)
print(f"wrote {out_path}: {len(entries)} entries, {len(excluded)} excluded; grader commits: {commits or 'none'}; run files without graded_with: {len(ungraded)}")
if REQUIRE_ONE and not single:
    sys.exit(f"--require-single-commit: rows come from {len(commits)} grader commits ({', '.join(commits) or 'none'}) and {len(ungraded)} run files have none: run scripts/regrade.py on them first")
