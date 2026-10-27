"""python -m navital_gym.cli --env trip --agent heuristic [--k 1] [--tasks IN-TRIP-002,IN-TRIP-003] [--out runs/x.json]
Agents: the env's scripted baselines (see envs/<env>/baselines.py) or  <provider>:<model>  with provider in ollama, openai, groq, openrouter, gemini, cerebras, mistral, cloudflare, anthropic
(keys are read from OPENAI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY, never from the command line). Prints a markdown table; --out writes per-task scores as JSON."""
import argparse, importlib, json, os, sys
from .core.runner import run_suite, format_report
from .core.agents import make_agent, redact, load_env_file

def _commit():
    from .core.version import code_id
    return code_id()

def stratified(env, n):
    """Deterministic stratified subset: tasks grouped by (split, kind, family); take one from each group in turn (first by id) until n."""
    from .core.grader import task_split, task_kind
    groups = {}
    for tid in sorted(env.tasks):
        t = env.tasks[tid]
        groups.setdefault((task_split(t), task_kind(t), t.family or ""), []).append(tid)
    order, out, i = sorted(groups), [], 0
    while len(out) < min(n, len(env.tasks)):
        for g in order:
            if i < len(groups[g]) and len(out) < n:
                out.append(groups[g][i])
        i += 1
    return sorted(out)

def _load_prior(path, env):
    """Finished tasks from an earlier --out file: {agent: {task_id: [Score]}} plus their transcripts. A task that ended in a provider error / cap is NOT finished."""
    from .core.grader import Score
    if not path or not os.path.exists(path):
        return {}, {}
    data = json.load(open(path))
    tpath = path.replace(".json", ".transcripts.json")
    tr = json.load(open(tpath)) if os.path.exists(tpath) else {}
    out = {}
    for agent, d in data.items():
        out[agent] = {tid: [Score(score=r["score"], solved=r["solved"], valid=r["valid"], rules=r["rules"], details=r["details"], soft=r["soft"], verdict=r["verdict"], meta=r.get("meta", {})) for r in runs]
                      for tid, runs in d["tasks"].items() if not any(r.get("meta", {}).get("error") for r in runs)}
    return out, tr

def list_envs():
    import os, pkgutil
    from . import envs as envs_pkg
    base = os.path.dirname(envs_pkg.__file__)
    import glob
    for name in sorted(d for d in os.listdir(base) if glob.glob(os.path.join(base, d, "tasks*.jsonl")) and os.path.exists(os.path.join(base, d, "__init__.py"))):
        try:
            mod = importlib.import_module(f"navital_gym.envs.{name}")
            env = mod.load_env()
            n = len(env.tasks); inf = sum(1 for t in env.tasks.values() if not t.expected_feasible)
            gb = getattr(mod, "get_baselines", None)
            print(f"{name:10} {n:4} tasks ({inf} infeasible)  baselines: {', '.join(sorted(gb())) if gb else '-'}")
        except Exception as e:
            print(f"{name:10} (could not load: {type(e).__name__})")

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "list":
        return list_envs()
    if argv and argv[0] == "run":
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog="navital-gym", description="navital-gym list | navital-gym run --env trip --agent oracle")
    ap.add_argument("--env", default="trip"); ap.add_argument("--agent", action="append", required=True)
    ap.add_argument("--k", type=int, default=1); ap.add_argument("--tasks"); ap.add_argument("--tasks-file", help="run a different tasks JSONL (e.g. a private held-out set); the env must accept tasks_path"); ap.add_argument("--sample", type=int, help="run a deterministic stratified subset of N tasks (round-robin over split/kind/family, task-id order); say so when you report it"); ap.add_argument("--out"); ap.add_argument("--max-turns", type=int, default=40); ap.add_argument("--no-repair", action="store_true", help="no format-repair retry (strict)"); ap.add_argument("--no-json-mode", action="store_true"); ap.add_argument("--token-cap", type=int, default=None, help="stop a model agent once input+output tokens reach N (spend guard)"); ap.add_argument("--env-file", default=".env.local"); ap.add_argument("--split", choices=["core", "easy", "all"], default=None, help="which task split to load (envs that have an easy split): core = the standard tasks (default), easy, or all"); ap.add_argument("--env-kw", action="append", default=[], help="keyword for the env's load_env, KEY=VALUE (true/false/int/str), e.g. include_experimental=true for support"); ap.add_argument("--resume", action="store_true", help="if --out exists, keep its finished tasks and run only the rest (tasks that ended in a provider error are retried); safe to repeat daily within a free tier"); ap.add_argument("--spend-cap-usd", type=float, default=None, help="stop before this many USD are spent with this provider (your own limit; a project cap in ~/.navital-gym/caps.json can only be lowered by it)"); ap.add_argument("--price-in", type=float, default=None, help="USD per million input tokens (paid providers; defaults are conservative)"); ap.add_argument("--price-out", type=float, default=None); ap.add_argument("--ledger", default="runs/spend-ledger.json"); ap.add_argument("--pause", type=float, default=0.0, help="seconds between tool turns (free-tier rate limits)"); ap.add_argument("--temperature", type=float, default=None, help="default 0 for k=1, 0.7 for k>1 (pass^k needs sampling)");
    a = ap.parse_args(argv)
    load_env_file(a.env_file)      # API keys for hosted providers; nothing is printed
    mod = importlib.import_module(f"navital_gym.envs.{a.env}")
    kw = {}
    for item in a.env_kw:
        k, _, v = item.partition("=")
        kw[k] = True if v.lower() == "true" else False if v.lower() == "false" else int(v) if v.lstrip("-").isdigit() else v
    if a.tasks_file:
        kw["tasks_path"] = a.tasks_file
    if a.split:
        import inspect
        if "splits" not in inspect.signature(mod.load_env).parameters:
            sys.exit(f"env {a.env!r} has no easy split (its load_env takes no `splits`)")
        kw["splits"] = {"core": ("core",), "easy": ("easy",), "all": ("core", "easy")}[a.split]
    env = mod.load_env(**kw)
    ids = a.tasks.split(",") if a.tasks else (stratified(env, a.sample) if a.sample else None)
    reports, dump, transcripts_all, quota_stop = [], {}, {}, None
    for name in a.agent:
        if name in getattr(mod, "get_baselines", lambda: {})():
            agent = mod.get_baselines()[name]
        else:
            temp = a.temperature if a.temperature is not None else (0.0 if a.k == 1 else 0.7)
            agent = make_agent(name, spend_cap_usd=a.spend_cap_usd, price_in=a.price_in, price_out=a.price_out, ledger_path=a.ledger, max_turns=a.max_turns, temperature=temp, repair=not a.no_repair, json_mode=not a.no_json_mode, pause=a.pause)
            agent.token_cap = a.token_cap
        tr = {} if a.out else None
        prior, prior_tr = _load_prior(a.out, env) if a.resume else ({}, {})
        pk = name if name in prior else (getattr(agent, "name", None) if getattr(agent, "name", None) in prior else (next(iter(prior)) if len(prior) == 1 else None))   # same agent, even if the spec string changed (e.g. a different port)
        prior_here = dict(prior.get(pk, {}))
        todo = [t for t in (ids or env.task_ids()) if t not in prior_here]
        if a.resume and not todo:
            print(f"  [{name}] nothing to do: all requested tasks are already finished in {a.out}", file=sys.stderr)
        live = {}
        def progress(tid, runs, _name=name):
            print(f"  [{_name}] {tid}: " + ", ".join(f"{s.verdict} ({s.score:.2f})" for s in runs), file=sys.stderr, flush=True)
            if a.out:      # checkpoint after every task: a killed or crashed run keeps everything finished so far (resume with --resume)
                from .core.grader import summarize
                live[tid] = runs
                merged_now = {**{t: r for t, r in prior_here.items() if t in (ids or env.task_ids())}, **live}
                part = {_name: {"settings": getattr(agent, "settings", lambda: {})(), "navital_gym_commit": _commit(), "k": a.k, "summary": summarize(merged_now, env.tasks),
                                "tasks": {t: [s_.to_dict() for s_ in r] for t, r in merged_now.items()}, "partial": True}}
                tmp_tr = {**{t: v for t, v in (prior_tr.get(pk, {}) if (a.resume and pk) else {}).items() if t in prior_here}, **(tr or {})}
                with open(a.out + ".tmp", "w") as f_:
                    f_.write(redact(json.dumps(part, indent=1, sort_keys=True)))
                os.replace(a.out + ".tmp", a.out)
                with open(a.out.replace(".json", ".transcripts.json") + ".tmp", "w") as f_:
                    f_.write(redact(json.dumps({_name: tmp_tr})))
                os.replace(a.out.replace(".json", ".transcripts.json") + ".tmp", a.out.replace(".json", ".transcripts.json"))
        rep = run_suite(env, agent, todo, a.k, transcripts=tr, progress=progress)
        if prior_here:           # merge finished tasks from the earlier file with the new ones, keep one summary
            from .core.grader import summarize
            merged = {**{t: r for t, r in prior_here.items() if t in (ids or env.task_ids())}, **rep["results"]}
            rep = {**rep, "results": merged, "summary": summarize(merged, env.tasks)}
        reports.append(rep)
        if rep.get("quota_exhausted"): quota_stop = rep["quota_exhausted"]
        old_tr = prior_tr.get(pk, {}) if (a.resume and pk) else {}
        transcripts_all[name] = {**{t: v for t, v in old_tr.items() if t in prior_here}, **(tr or {})}
        dump[name] = {"settings": getattr(agent, "settings", lambda: {})(), "navital_gym_commit": _commit(), "k": a.k, "summary": rep["summary"], "tasks": {t: [s.to_dict() for s in runs] for t, runs in rep["results"].items()}}
    print(format_report(reports))
    if a.out:
        with open(a.out, "w") as f:
            f.write(redact(json.dumps(dump, indent=1, sort_keys=True)))
        if any(transcripts_all.values()):
            with open(a.out.replace(".json", ".transcripts.json"), "w") as f:
                f.write(redact(json.dumps(transcripts_all)))
    if quota_stop:       # tell the resume loop: daily quota gone, wait for the reset (exit code 75, wait seconds on the last line)
        print(f"QUOTA_EXHAUSTED: {quota_stop['message']}", file=sys.stderr)
        print(f"QUOTA_WAIT={int(quota_stop['wait']) if quota_stop.get('wait') else 0}", file=sys.stderr)
        sys.exit(75)

if __name__ == "__main__":
    main()
