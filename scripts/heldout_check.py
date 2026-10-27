#!/usr/bin/env python3
"""Gates for a PRIVATE held-out task set (kept outside the repo, e.g. ~/.navital-gym/heldout/<env>.jsonl; never commit it). Same gates as the public sets:
  1 disjoint   no task id and no prompt equals one in ANY public split of that env (core, easy, experimental)
  2 oracle     the reference solver solves every task (100%)
  3 degenerate every non-oracle baseline of the env (empty, reject_only, prior, shotgun ...) solves < 25% of the set
  4 leak       no hidden field, trap text or tell in a prompt or tool specs; and a robustness call of every tool on every task does not crash
usage: python3 scripts/heldout_check.py <env> <heldout.jsonl>       exit 0 = all gates pass
The set is loaded the way `navital-gym run --env <env> --tasks-file <heldout.jsonl>` loads it (the env's load_env(tasks_path=...))."""
import importlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from navital_gym.core import leak
from navital_gym.core.runner import run_suite

def load(env_name, path=None, **kw):
    mod = importlib.import_module(f"navital_gym.envs.{env_name}")
    if path: kw["tasks_path"] = path
    return mod.load_env(**kw)

def public_tasks(env_name):
    """Every public task of the env: core, easy and experimental splits."""
    out = {}
    mod = importlib.import_module(f"navital_gym.envs.{env_name}")
    import inspect
    params = inspect.signature(mod.load_env).parameters
    variants = [{}]
    if "splits" in params: variants += [{"splits": ("easy",)}, {"splits": ("core", "easy")}]
    if "include_experimental" in params: variants += [{"include_experimental": True}]
    for kw in variants:
        try: out.update({t.id: t for t in mod.load_env(**kw).tasks.values()})
        except Exception: pass
    return out

def check(env_name, path):
    problems, notes = [], []
    env = load(env_name, path)
    tasks = env.tasks
    if not tasks: return ["no tasks loaded"], notes
    pub = public_tasks(env_name)
    pub_prompts = {t.prompt for t in pub.values()}
    dup_ids = sorted(set(tasks) & set(pub)); dup_prompts = sorted(t for t, x in tasks.items() if x.prompt in pub_prompts)
    if dup_ids: problems.append(f"ids also in the public set: {dup_ids[:5]}")
    if dup_prompts: problems.append(f"prompts identical to a public prompt: {dup_prompts[:5]} ({len(dup_prompts)} total)")
    if len({x.prompt for x in tasks.values()}) < len(tasks): problems.append("duplicate prompts inside the held-out set")
    base = env.baselines() if callable(getattr(env, "baselines", None)) else None
    mod = importlib.import_module(f"navital_gym.envs.{env_name}")
    base = base or mod.get_baselines()
    n = len(tasks)
    for name, agent in sorted(base.items()):
        rep = run_suite(env, agent)
        s = rep["summary"]; rate = s["pass@1"]
        if name == "oracle":
            if rate < 1.0: problems.append(f"oracle solves {rate:.0%} ({round(rate * n)}/{n}); failing: {[t for t, r in rep['results'].items() if not r[0].solved][:6]}")
        else:
            notes.append(f"{name}: {rate:.0%}")
            if rate >= 0.25: problems.append(f"degenerate agent '{name}' solves {rate:.0%} (gate: < 25%)")
    for tid, t in tasks.items():
        obs = env.reset(tid)
        for msg in leak.leaks_in_observation(t, obs): problems.append(f"{tid}: {msg}")
        for spec in env.world.tool_specs():
            name = spec["function"]["name"] if "function" in spec else spec["name"]
            try: res = env.world.call(name, {})
            except Exception as e: problems.append(f"{tid}: tool {name} crashed on empty arguments ({type(e).__name__})"); continue
            for msg in leak.find_leaks(t, json.dumps(res, default=str), f"tool {name}"): problems.append(f"{tid}: {msg}")
    notes.insert(0, f"{n} tasks, kinds: " + ", ".join(f"{k} {v}" for k, v in sorted(_count(tasks).items())))
    return problems, notes

def _count(tasks):
    c = {}
    for t in tasks.values():
        k = (t.meta or {}).get("kind") or getattr(t, "kind", "") or "-"
        c[k] = c.get(k, 0) + 1
    return c

if __name__ == "__main__":
    if len(sys.argv) != 3: print(__doc__); sys.exit(2)
    probs, notes = check(sys.argv[1], os.path.expanduser(sys.argv[2]))
    for n in notes: print("  ", n)
    for p in probs[:40]: print("  FAIL:", p)
    if len(probs) > 40: print(f"  ... {len(probs) - 40} more")
    print(("PASS" if not probs else "FAIL"), sys.argv[1], os.path.basename(sys.argv[2]))
    sys.exit(0 if not probs else 1)
