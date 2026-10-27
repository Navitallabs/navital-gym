"""Per-adapter leak test (qa, T-099). The agent may see ONLY: the task prompt, the env instructions/policy text, the task id and language,
the tool specs, and tool outputs. Never raw task params, meta, rules, binding, traps, feasibility, gold answers or forbidden actions.

1. RUNTIME (dependency-free): everything the OpenEnv session (the adapters' shared reset/step path) hands out, for every task of every env:
   reset observation, tool specs, every tool called with no/junk args, and the finalize reply. Scanned for hidden keys, designer-note text
   (core leak.find_leaks) and a gold answer pair or the whole gold answer inside tool output (a gold VALUE alone is not a leak: states, PANs and dates are legitimately in the inputs).
2. STATIC (works without verifiers / inspect-ai / openenv installed): AST audit of every adapter module. Any read of a hidden Task field
   (.params .meta .rules .binding .traps .expected_feasible .snapshot_date, .to_dict()) must sit in a host-side function (scoring or world
   building). Anything else is reported as a LEAK RISK. The list of allowed host-side readers is printed so a human can eyeball it.
3. Packages not installed -> the live check for that adapter is reported SKIPPED (never silently green).
Usage: python3 -I adapter_leak_check.py [env ...]"""
import importlib.util
import ast, importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, ".."))
from navital_gym.core import leak
from navital_gym.adapters.openenv_env import NavitalSession

ENVS = sys.argv[1:] or [e for e in ["trip", "gst", "form", "form_multidoc", "support", "upi"] if __import__("importlib").util.find_spec("navital_gym.envs." + e)]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import splitpatch; ENVS = splitpatch.apply_from_env(ENVS)
HIDDEN_KEYS = ("gold_answer", "forbidden_actions", "expected_feasible", "binding_constraint", "binding", "traps", "meta", "params", "grader_notes", "snapshot_date", "review_status", "oracle")
fails, skips = [], []

def fail(msg): fails.append(msg); print("LEAK/FAIL", msg)

def leaves(x, out):
    if isinstance(x, dict):
        for v in x.values(): leaves(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x: leaves(v, out)
    elif isinstance(x, str) and len(x) >= 8: out.add(x)
    elif isinstance(x, int) and not isinstance(x, bool) and abs(x) >= 100000: out.add(str(x))
    return out

def policy_pairs(task):
    """"key": value pairs of the env's published rules (task.params['rules'], shown through get_policy on purpose)."""
    r = task.params.get("rules")
    return {f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in r.items()} if isinstance(r, dict) else set()

def blob(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)

# ---------------------------------------------------------------- 1. runtime
for name in ENVS:
    try:
        sess = NavitalSession(name)
    except Exception as e:
        fail(f"{name}: cannot load env: {type(e).__name__}: {e}"); continue
    for tid in sess.env.task_ids():
        task = sess.env.tasks[tid]
        seen = []
        o = sess.reset(tid)
        seen.append(("reset", blob({k: o[k] for k in ("prompt", "tools", "task_id", "lang")})))
        if set(o) - {"prompt", "tools", "task_id", "lang", "result", "done", "reward"}:
            fail(f"{name}/{tid}: reset returns unexpected keys {sorted(set(o))}")
        for spec in o["tools"]:
            tn = spec["function"]["name"]; props = spec["function"]["parameters"].get("properties", {})
            for args in ({}, {"x": 1}, {k: "A" for k in props}, {k: "" for k in props}, {k: "999999" for k in props}):
                r = sess.step({"tool": tn, "args": args})
                seen.append((f"tool:{tn}{args}", blob(r)))
                if set(r) - {"result", "done", "reward"}:
                    fail(f"{name}/{tid}: step returns unexpected keys {sorted(r)}")
        # robustness probe: call every tool with real-looking values drawn from the task's own data (ids, names, dates, codes). A tool must answer or return an
        # {"error": ...}; an exception here would crash an agent's run (the Support easy split once crashed on a trimmed policy this way).
        pool = []
        def _leaves(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if isinstance(k, str) and 0 < len(k) <= 40 and k not in pool: pool.append(k)     # ids are often dict keys (a VPA directory, a ledger)
                    _leaves(v)
            elif isinstance(x, list):
                for v in x: _leaves(v)
            elif isinstance(x, str) and 0 < len(x) <= 40 and x not in pool: pool.append(x)
        _leaves(task.params.get("world")); pool = pool[:30]
        for spec in o["tools"]:
            tn = spec["function"]["name"]; pschema = spec["function"]["parameters"].get("properties", {}); props = list(pschema)
            for v in (pool if props else []):
                try:
                    # numeric parameters get a plain number (a string would be refused before the tool's own logic runs)
                    r = sess.step({"tool": tn, "args": {k: (100 if pschema[k].get("type") in ("integer", "number") else v) for k in props}})
                    seen.append((f"tool:{tn}(pool)", blob(r)))
                except Exception as ex:
                    fail(f"{name}/{tid}: tool {tn} RAISED {type(ex).__name__}: {str(ex)[:80]} on args {v!r}")
                    break
        fin = sess.step({"finalize": {"status": "plan", "answer": {}, "actions": [], "reply": "x"}})
        seen.append(("finalize", blob(fin)))
        if set(fin) - {"result", "done", "reward"} or "info" in fin or "rules" in blob(fin).lower().replace("rules of", ""):
            fail(f"{name}/{tid}: finalize reply carries grader detail: {blob(fin)[:200]}")
        agent_text = {w: t for w, t in seen}
        gold = set()
        leaves(task.meta.get("gold_answer"), gold); leaves(task.meta.get("forbidden_actions"), gold)
        prompt = o["prompt"]
        for where, text in agent_text.items():
            for key in HIDDEN_KEYS:
                if f'"{key}"' in text and key not in ("params", "rules", "meta"):
                    fail(f"{name}/{tid} [{where}]: hidden key {key!r} in agent-visible text")
            for key in ("params", "meta"):
                if f'"{key}"' in text and where != "reset":
                    fail(f"{name}/{tid} [{where}]: hidden key {key!r} in tool output")
            if where == "reset":   # env instructions may legitimately say "infeasible"; only the task prompt part is scanned
                for l in leak.leaks_in_observation(task, o):
                    fail(f"{name}/{tid}: {l}")
            else:
                for l in leak.find_leaks(task, text, where):
                    fail(f"{name}/{tid}: {l}")
            for gk, gv in (task.meta.get("gold_answer") or {}).items():
                pair = f'"{gk}": {json.dumps(gv, ensure_ascii=False)}'
                if pair in policy_pairs(task): continue   # the answer restates a rule that get_policy states on purpose
                if pair in text and where != "reset":
                    fail(f"{name}/{tid} [{where}]: gold pair {pair[:80]} appears in agent-visible tool output")
            gtext = blob(task.meta.get("gold_answer") or {})
            if len(gtext) > 6 and gtext in text:
                fail(f"{name}/{tid} [{where}]: the whole gold answer appears in agent-visible text")
    print(f"runtime {name}: {len(sess.env.task_ids())} tasks scanned")

# ---------------------------------------------------------------- 2. static audit
HIDDEN_ATTRS = {"params", "meta", "rules", "binding", "traps", "expected_feasible", "snapshot_date", "to_dict", "HIDDEN"}
HOST_SIDE = {"_grade", "score", "setup_task", "make_world", "navital_score", "solved", "grade", "contract_grade", "reset", "step",
             "_pick", "__init__", "_grade_one", "run_suite"}
ADAPTERS = ["inspect_task.py", "verifiers_env.py", "openenv_env.py"]
adir = os.path.join(HERE, "..", "navital_gym", "adapters")
for fn in ADAPTERS:
    src = open(os.path.join(adir, fn)).read(); tree = ast.parse(src)
    reads = []
    class V(ast.NodeVisitor):
        stack = []
        def visit_FunctionDef(self, n):
            self.stack.append(n.name); self.generic_visit(n); self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_Attribute(self, n):
            if n.attr in HIDDEN_ATTRS and isinstance(n.value, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                reads.append((n.attr, n.lineno, self.stack[-1] if self.stack else "<module>"))
            self.generic_visit(n)
    V().visit(tree)
    risky = [r for r in reads if r[2] not in HOST_SIDE]
    # task.to_dict()/meta reads are fine in the scorer; flag any in the module scope or in functions that build agent-facing data
    print(f"static {fn}: hidden-field reads {[(a, l, f) for a, l, f in reads]}")
    for a, l, f in risky:
        if a == "HIDDEN": continue
        fail(f"{fn}:{l} reads hidden field .{a} in `{f}` (not a known host-side function)")
    # agent-facing constructors must be fed only public data
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fname = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if fname in ("Sample", "NavitalData", "NavitalObservation"):
                text = ast.unparse(node)
                for bad in (".params", ".meta", ".rules", ".binding", ".traps", "gold", "expected_feasible", "to_dict"):
                    if bad in text:
                        fail(f"{fn}:{node.lineno} {fname}(...) is built from `{bad}`: {text[:160]}")

# ---------------------------------------------------------------- 3. live adapters
for pkg, label in (("verifiers", "verifiers"), ("inspect_ai", "Inspect"), ("openenv", "OpenEnv")):
    try:
        importlib.import_module(pkg); print(f"live {label}: package present (live rollout leak test NOT implemented yet; static audit above applies)")
        skips.append(f"{label}: package present but live rollout check not implemented")
    except ImportError:
        skips.append(f"{label}: package not installed, live check SKIPPED (static audit only)")
for s in skips: print("SKIPPED", s)
print("adapter_leak_check:", "PASS" if not fails else f"FAIL ({len(fails)})", f"(+{len(skips)} adapter(s) static-only)")
sys.exit(1 if fails else 0)
