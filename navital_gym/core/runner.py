"""Baseline runner: model-agnostic. An Agent gets the observation and a call_tool function and returns a submission."""
from __future__ import annotations
import json, urllib.request, urllib.error
from typing import Any, Callable, Protocol
from .grader import summarize

class Agent(Protocol):
    name: str
    def solve(self, obs: dict, call_tool: Callable[[str, dict], dict], task) -> Any: ...

class ScriptedAgent:
    """Wrap a function (obs, call_tool, task) -> submission. Used for oracle / naive / cheating baselines."""
    def __init__(self, name: str, fn: Callable):
        self.name, self.fn = name, fn
    def solve(self, obs, call_tool, task):
        return self.fn(obs, call_tool, task)

def run_suite(env, agent, task_ids=None, k: int = 1, progress=None, transcripts: dict | None = None) -> dict:
    """Run `agent` on each task k times (fresh world each time) and return {"results": {id: [Score..]}, "summary": {...}}."""
    results, bad_streak, quota = {}, 0, None
    for tid in (env.task_ids() if task_ids is None else task_ids):
        if bad_streak >= 3:       # a persistent rate limit, dead key or spent cap: stop instead of burning the rest of the list
            break
        runs = []
        for _ in range(k):
            obs = env.reset(tid)
            if hasattr(agent, "validator"):
                agent.validator = getattr(env, "format_check", None)
            try:
                sub = agent.solve(obs, lambda name, args=None: env.world.call(name, args), env.task)
            except Exception as e:     # an agent crash is a failed run, not a harness crash
                sub = {"error": f"agent crashed: {type(e).__name__}"}
                if hasattr(agent, "meta"):
                    agent.meta = {**getattr(agent, "meta", {}), "error": f"agent crashed: {type(e).__name__}"}
            sc = env.grade(env.task, sub)
            sc.meta = dict(getattr(agent, "meta", {}) or {})
            if sc.meta.get("quota_exhausted"):      # a daily free quota is gone: this task is NOT RUN (not stored), and the suite stops
                quota = {"wait": sc.meta.get("quota_wait"), "message": sc.meta.get("error")}
                break
            runs.append(sc)
            if transcripts is not None and getattr(agent, "transcript", None) is not None:
                transcripts.setdefault(tid, []).append(agent.transcript)
        if quota:
            transcripts and transcripts.pop(tid, None)
            break
        results[tid] = runs
        bad_streak = bad_streak + 1 if all(r.meta.get("error") for r in runs) else 0
        if progress:
            progress(tid, runs)
    out = {"results": results, "summary": summarize(results, env.tasks), "agent": agent.name}
    if quota: out["quota_exhausted"] = quota
    return out

def format_report(reports: list[dict]) -> str:
    """Headline table, then one table per split/kind when the env has more than one (never only a mixed number)."""
    out = [_table(reports, lambda r: r["summary"], "all")]
    for r in reports:       # say WHY runs errored (provider text, already credential-scrubbed), so an infrastructure problem is never read as a wrong answer
        seen: dict[str, int] = {}
        for runs in r.get("results", {}).values():
            for sc in runs:
                if sc.meta.get("error"):
                    seen[sc.meta["error"][:160]] = seen.get(sc.meta["error"][:160], 0) + 1
        for msg, n in sorted(seen.items(), key=lambda kv: -kv[1])[:3]:
            out.append(f"  [{r['agent']}] error x{n}: {msg}")
    for key in ("by_split", "by_kind"):
        groups = sorted({g for r in reports for g in r["summary"].get(key, {})})
        if 1 < len(groups) <= (6 if key == "by_kind" else 99):
            for g in groups:
                out.append(f"\n{key[3:]} = {g}\n" + _table(reports, lambda r, g=g: r["summary"][key].get(g), g))
    return "\n".join(out)

def _table(reports, pick, label) -> str:
    lines = ["| agent | tasks | pass@1 | strict pass@1 (no repair) | pass^k | format fail | turns out | errors | partial credit (mean rule score) | worst rules |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in reports:
        s = pick(r)
        if s is None:
            continue
        worst = ", ".join(f"{k}:{v}" for k, v in sorted(s["rule_failures"].items(), key=lambda kv: -kv[1])[:3]) or "-"
        lines.append(f"| {r['agent']} | {s['tasks']} | {s['pass@1']:.2f} | {s['strict_pass@1']:.2f} | {s['pass^k']:.2f} (k={s['k']}) | {s['format_fail']:.0%} | {s['turns_exhausted']:.0%} | {s['errors']:.0%} | {s['mean_score']:.2f} | {worst} |")
    return "\n".join(lines)

from .agents import extract_json, OpenAIChatAgent as OpenAICompatAgent, AnthropicChatAgent, make_agent  # noqa: E402,F401  (kept here for older imports)
