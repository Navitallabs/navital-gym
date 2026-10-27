#!/usr/bin/env python3
"""A regrade cannot fix a prompt the model already saw. This compares, for every saved run, the first user message in the transcript (the prompt the model actually
received: task prompt + the env's policy text) with what the CURRENT env would send. Tasks whose prompt changed since the run are STALE: reported, and with --drop
moved out of the run file (kept in <file>.stale.json) so `navital-gym run ... --resume` re-runs them.
usage: python3 scripts/check_run_prompts.py [--drop] [runs/*.json ...]   (default: every sampled/full run file)"""
import glob, importlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
drop = "--drop" in sys.argv
files = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(p for p in glob.glob(os.path.join(ROOT, "runs", "*.json")) if not p.endswith((".transcripts.json", "spend-ledger.json", ".stale.json")) and ("-s" in p or "-full" in p or "-easy" in p) and "scripted" not in p)
envs = {}
def env_for(name, kw):
    key = (name, tuple(sorted(kw.items())))
    if key not in envs:
        envs[key] = importlib.import_module(f"navital_gym.envs.{name}").load_env(**kw)
    return envs[key]
total = 0
for path in files:
    name = os.path.basename(path).split("-")[0]
    data = json.load(open(path))
    tpath = path.replace(".json", ".transcripts.json")
    tr = json.load(open(tpath)) if os.path.exists(tpath) else {}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import runfiles
    env = runfiles.load_env_for(path)
    stale = {}
    for agent, d in data.items():
        for tid in d["tasks"]:
            runs = tr.get(agent, {}).get(tid)
            if not runs or not runs[0]:
                continue
            seen = runs[0][0].get("content", "")
            if tid in env.tasks and seen != env.reset(tid)["prompt"]:
                stale.setdefault(agent, []).append(tid)
    n = sum(len(v) for v in stale.values()); total += n
    print(f"{os.path.basename(path)}: {n} stale" + (f" {sorted({t for v in stale.values() for t in v})}" if n else ""))
    if drop and n:
        old = {"data": {}, "tr": {}}
        for agent, ids in stale.items():
            old["data"][agent] = {t: data[agent]["tasks"].pop(t) for t in ids}
            old["tr"][agent] = {t: tr.get(agent, {}).pop(t, None) for t in ids}
            from navital_gym.core.grader import summarize, Score
            res = {t: [Score(score=r["score"], solved=r["solved"], valid=r["valid"], rules=r["rules"], details=r["details"], soft=r["soft"], verdict=r["verdict"], meta=r.get("meta", {})) for r in runs]
                   for t, runs in data[agent]["tasks"].items()}
            data[agent]["summary"] = summarize(res, env.tasks)
        json.dump(old, open(path.replace(".json", ".stale.json"), "w"))
        json.dump(data, open(path, "w"), indent=1, sort_keys=True)
        json.dump(tr, open(tpath, "w"))
print("total stale:", total, "(dropped: they will re-run on --resume)" if drop else "(report only; pass --drop to move them out)")
