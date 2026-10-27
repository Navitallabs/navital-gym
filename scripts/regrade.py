#!/usr/bin/env python3
"""Re-grade saved runs with the CURRENT grader, without calling any model again. Needs runs/<env>-<slug>-s<N>.json and its .transcripts.json (the final
answer is the last assistant message). Use it after a grader fix so that every table row is graded by one commit. Originals are kept in runs/orig/.
Note: tool calls from the transcript are replayed before grading (state-based envs).
usage: python3 scripts/regrade.py runs/trip-openai-gpt-4o-mini-s15.json [more files...]"""
import importlib, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navital_gym.core.agents import extract_json
from navital_gym.core.grader import summarize, Score

from navital_gym.core.version import code_id as commit    # graded_with = git tree id of navital_gym/ (see core/version.py)

def regrade(path):
    env_name = os.path.basename(path).split("-")[0]
    data = json.load(open(path))
    tr_path = path.replace(".json", ".transcripts.json")
    transcripts = json.load(open(tr_path)) if os.path.exists(tr_path) else {}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import runfiles
    env = runfiles.load_env_for(path)
    for agent, d in data.items():
        results = {}
        for tid, runs in d["tasks"].items():
            msgs_runs = transcripts.get(agent, {}).get(tid, [])
            out = []
            for i, old in enumerate(runs):
                sub = None
                if i < len(msgs_runs):
                    last = [m for m in msgs_runs[i] if m.get("role") == "assistant" and not m.get("tool_calls")]
                    sub = extract_json(last[-1].get("content") or "") if last else None
                env.reset(tid)
                # envs whose grade depends on world state (UPI/support actions taken through tools) need the tool calls replayed on a fresh world;
                # the worlds are deterministic, so this reproduces the state the agent left behind
                if i < len(msgs_runs):
                    for m in msgs_runs[i]:
                        for c in (m.get("tool_calls") or []) if m.get("role") == "assistant" else []:
                            env.world.call(c["name"], c.get("args"))
                sc = env.grade(env.task, sub)
                sc.meta = old.get("meta", {})
                out.append(sc)
            results[tid] = out
        d["tasks"] = {tid: [s.to_dict() for s in runs] for tid, runs in results.items()}
        d["summary"] = summarize(results, env.tasks)
        d["graded_with"] = commit()
    os.makedirs(os.path.join(os.path.dirname(path), "orig"), exist_ok=True)
    if not os.path.exists(os.path.join(os.path.dirname(path), "orig", os.path.basename(path))):
        shutil.copy(path, os.path.join(os.path.dirname(path), "orig", os.path.basename(path)))
    json.dump(data, open(path, "w"), indent=1, sort_keys=True)
    return {a: (round(d["summary"]["pass@1"], 3), round(d["summary"]["format_fail"], 3)) for a, d in data.items()}

if __name__ == "__main__":
    for p in sys.argv[1:]:
        if any(k in os.path.basename(p) for k in ("transcripts", "stale", "ledger", "smoke", "scripted")):
            print(p, "skipped (not a run file)"); continue       # a loose glob must not crash the regrade
        print(p, regrade(p))
