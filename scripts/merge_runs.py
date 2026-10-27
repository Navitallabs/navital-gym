#!/usr/bin/env python3
"""Merge two run files of the SAME agent/env (e.g. a 5-task run and the other 10 tasks of the same 15-task sample) into one, with transcripts, and recompute the summary.
usage: python3 scripts/merge_runs.py a.json b.json --out merged.json     (grades are kept as run; use scripts/regrade.py afterwards to re-grade the whole file)"""
import importlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navital_gym.core.grader import summarize, Score

def load(p):
    t = p.replace(".json", ".transcripts.json")
    return json.load(open(p)), (json.load(open(t)) if os.path.exists(t) else {})

def main(a, b, out):
    (da, ta), (db, tb) = load(a), load(b)
    env_name = os.path.basename(a).split("-")[0]
    env = importlib.import_module(f"navital_gym.envs.{env_name}").load_env()
    merged, mt = {}, {}
    for agent in da:
        if agent not in db:
            sys.exit(f"agent {agent} not in both files")
        tasks = {**da[agent]["tasks"], **db[agent]["tasks"]}
        dup = set(da[agent]["tasks"]) & set(db[agent]["tasks"])
        if dup:
            sys.exit(f"task ids in both files: {sorted(dup)[:3]}")
        results = {tid: [Score(score=r["score"], solved=r["solved"], valid=r["valid"], rules=r["rules"], details=r["details"], soft=r["soft"], verdict=r["verdict"], meta=r.get("meta", {})) for r in runs] for tid, runs in tasks.items()}
        merged[agent] = {**da[agent], "tasks": tasks, "summary": summarize(results, env.tasks), "merged_from": [os.path.basename(a), os.path.basename(b)]}
        mt[agent] = {**ta.get(agent, {}), **tb.get(agent, {})}
    json.dump(merged, open(out, "w"), indent=1, sort_keys=True)
    json.dump(mt, open(out.replace(".json", ".transcripts.json"), "w"))
    print(out, {k: v["summary"]["tasks"] for k, v in merged.items()})

if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(args[0], args[1], sys.argv[sys.argv.index("--out") + 1])
