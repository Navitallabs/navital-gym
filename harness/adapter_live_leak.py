"""LIVE per-adapter leak check (qa, T-099): drives the real adapter objects with the packages installed.
Run with the repo venv:  .venv/bin/python -I harness/adapter_live_leak.py [env ...]
Everything each adapter hands the agent (task data, prompts, tool lists, tool outputs, observations, state, the graded reply) is serialised
and scanned for hidden keys, designer-note text, gold pairs or the whole gold answer. Adapters whose package is missing are reported SKIPPED."""
import importlib.util
import asyncio, importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, ".."))
from navital_gym.core import leak
ENVS = sys.argv[1:] or [e for e in ["trip", "gst", "form", "form_multidoc", "support", "upi"] if __import__("importlib").util.find_spec("navital_gym.envs." + e)]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import splitpatch; ENVS = splitpatch.apply_from_env(ENVS)
HIDDEN = ("gold_answer", "forbidden_actions", "expected_feasible", "binding_constraint", "traps", "grader_notes", "review_status", "snapshot_date", "oracle", "meta", "params")
fails = []; ran = {}; skipped = []
def fail(m): fails.append(m); print("LEAK/FAIL", m)
def policy_pairs(task):
    """"key": value pairs of the env's published rules (task.params['rules'], shown through get_policy on purpose)."""
    r = task.params.get("rules")
    return {f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in r.items()} if isinstance(r, dict) else set()

def blob(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
def scan(label, task, text, prompt_ok=False):
    text = text.replace('"meta": null', '').replace('"_meta": null', '')   # MCP Tool objects carry an empty protocol-level meta field
    for k in HIDDEN:
        if f'"{k}"' in text: fail(f"{label} {task.id}: hidden key {k!r} in agent-visible data")
    for l in leak.find_leaks(task, text, label):
        if not (prompt_ok and "tell" in l and "impossible" in l.lower()): fail(f"{label} {task.id}: {l}")
    for gk, gv in (task.meta.get("gold_answer") or {}).items():
        pair = f'"{gk}": {json.dumps(gv, ensure_ascii=False)}'
        if pair in policy_pairs(task): continue   # the answer restates a rule that get_policy states on purpose
        if pair in text: fail(f"{label} {task.id}: gold pair {gk!r} visible")
    g = blob(task.meta.get("gold_answer") or {})
    if len(g) > 6 and g in text: fail(f"{label} {task.id}: whole gold answer visible")

def tool_calls(world):
    """Call every tool with no / junk / blank args; return the outputs."""
    out = []
    for spec in world.tool_specs():
        f = spec["function"]; props = f["parameters"].get("properties", {})
        for args in ({}, {"x": 1}, {k: "A" for k in props}, {k: "" for k in props}):
            out.append(world.call(f["name"], args))
    return out

for name in ENVS:
    pkg = importlib.import_module(f"navital_gym.envs.{name}")
    env = pkg.load_env()   # exactly what the adapters load (Support: core split only)
    # ---------------- OpenEnv
    try:
        oe = importlib.import_module("navital_gym.adapters.openenv_env")
        if not oe.OPENENV_AVAILABLE: raise ImportError("openenv")
        for tid in env.task_ids():
            t = env.tasks[tid]; e = oe.NavitalOpenEnv(name)
            o = e.reset(task_id=tid); d = o.model_dump()
            if d.get("metadata"): fail(f"OpenEnv {tid}: metadata not empty {d['metadata']}")
            scan("OpenEnv.reset", t, blob({k: d[k] for k in ("tools", "task_id", "lang")}))
            scan("OpenEnv.reset.prompt", t, blob(d["prompt"].split("\n\n")[0]), prompt_ok=False)
            for spec in d["tools"]:
                tn = spec["function"]["name"]
                for args in ({}, {"x": 1}):
                    r = e.step(oe.NavitalAction(tool=tn, args=args)).model_dump()
                    scan(f"OpenEnv.step({tn})", t, blob(r))
            fin = e.step(oe.NavitalAction(finalize={"status": "plan", "answer": {}, "actions": [], "reply": "x"})).model_dump()
            scan("OpenEnv.final", t, blob(fin))
            if fin["result"] != {"graded": True}: fail(f"OpenEnv {tid}: finalize result is {fin['result']!r}, expected only {{'graded': True}}")
            scan("OpenEnv.state", t, blob(e.state.model_dump()))
        ran["OpenEnv"] = ran.get("OpenEnv", 0) + len(env.task_ids())
    except ImportError:
        if "OpenEnv" not in skipped: skipped.append("OpenEnv")
    # ---------------- Inspect
    try:
        it = importlib.import_module("navital_gym.adapters.inspect_task")
        itask = it.navital_task(name)
        for s in itask.dataset:
            t = env.tasks[str(s.id)]
            if set((s.metadata or {})) - {"lang"}: fail(f"Inspect {s.id}: sample metadata has {sorted(s.metadata)}")
            if s.target not in ("", None, []): fail(f"Inspect {s.id}: sample target is {s.target!r} (must be empty)")
            if s.input != t.prompt + "\n\n" + env.instructions: fail(f"Inspect {s.id}: sample input is not exactly prompt + env instructions")
            scan("Inspect.sample", t, blob({"input": s.input.split("\n\n")[0], "metadata": s.metadata, "target": s.target}))
            w = env.make_world(t)
            for td in it._tools_for(w):
                scan("Inspect.tool", t, blob(str(getattr(td, "__dict__", td))[:2000]))
            for o in tool_calls(w): scan("Inspect.tool_output", t, blob(o))
        ran["Inspect"] = ran.get("Inspect", 0) + len(itask.dataset)
    except ImportError:
        if "Inspect" not in skipped: skipped.append("Inspect")
    # ---------------- verifiers
    try:
        ve = importlib.import_module("navital_gym.adapters.verifiers_env")
        ts = ve.NavitalTaskset(ve.NavitalConfig(env_name=name))
        for vt in ts.load():
            t = env.tasks[vt.data.id]; d = vt.data.model_dump()
            if d["prompt"] != t.prompt + "\n\n" + env.instructions: fail(f"verifiers {t.id}: prompt is not exactly prompt + env instructions")
            scan("verifiers.data", t, blob({k: v for k, v in d.items() if k != "prompt"}))
            scan("verifiers.data.prompt", t, blob(d["prompt"].split("\n\n")[0]))
            tool = ve.NavitalToolset(ve.vf.ToolsetConfig()); asyncio.run(tool.setup_task(vt.data))
            for x in asyncio.run(tool.list_tools()):
                scan("verifiers.tool", t, blob(x.model_dump() if hasattr(x, "model_dump") else str(x)))
            for tn in [x.name for x in asyncio.run(tool.list_tools())]:
                for args in ({}, {"x": 1}):
                    r = asyncio.run(tool.call_tool(tn, args))
                    scan(f"verifiers.call({tn})", t, blob([c.text for c in r.content]))
        ran["verifiers"] = ran.get("verifiers", 0) + len(env.task_ids())
    except ImportError:
        if "verifiers" not in skipped: skipped.append("verifiers")
    print(f"{name}: scanned {len(env.task_ids())} tasks through the live adapters")
print("live adapters exercised:", ran or "none")
for s in skipped: print("SKIPPED", s, "(package not installed)")
print("adapter_live_leak:", "PASS" if not fails and ran else ("FAIL" if fails else "NOTHING RAN"))
sys.exit(1 if fails or not ran else 0)
