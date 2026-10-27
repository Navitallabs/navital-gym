#!/usr/bin/env python3
"""Rebuild runs/spend-ledger.json from the saved run files (each task's meta.usd / meta.tokens). Use after parallel runs by older code that could overwrite
each other's ledger updates. Smoke-test calls that did not write a run file are not included (they are cents). Usage: python3 scripts/rebuild_ledger.py [runs_dir] [--ledger path] [--write]   (dry run unless --write)"""
import glob, json, os, sys, time
args = [a for a in sys.argv[1:] if not a.startswith("--")]
runs = args[0] if args else "runs"
ledger_path = sys.argv[sys.argv.index("--ledger") + 1] if "--ledger" in sys.argv else os.path.join(runs, "spend-ledger.json")
led = {}
for path in sorted(glob.glob(os.path.join(runs, "*-s*.json"))):
    if path.endswith(".transcripts.json") or "ledger" in path:
        continue
    for agent, d in json.load(open(path)).items():
        prov = (d.get("settings") or {}).get("provider")
        if not prov or prov == "openai-compatible":
            prov = (d.get("settings") or {}).get("base_url", "")
            prov = "openai" if "openai.com" in prov else "groq" if "groq" in prov else "gemini" if "generativelanguage" in prov else "openrouter" if "openrouter" in prov else "other"
        model = (d.get("settings") or {}).get("model", agent)
        usd = sum(sc.get("meta", {}).get("usd", 0) for r in d["tasks"].values() for sc in r)
        tok = sum(sc.get("meta", {}).get("tokens", 0) for r in d["tasks"].values() for sc in r)
        e = led.setdefault(prov, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "models": {}})
        e["usd"] = round(e["usd"] + usd, 6); e["input_tokens"] += tok     # in+out combined here; the split is not kept per task
        m = e["models"].setdefault(model, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0}); m["usd"] = round(m["usd"] + usd, 6); m["input_tokens"] += tok
        e["updated"] = time.strftime("%Y-%m-%d %H:%M:%S") + " (rebuilt from run files)"
json.dump(led, open(ledger_path if "--write" in sys.argv else os.devnull, "w"), indent=1, sort_keys=True)
print({k: round(v["usd"], 4) for k, v in led.items()}, "(dry: pass --write to replace runs/spend-ledger.json)" if "--write" not in sys.argv else "(written)")
