"""Deterministic grader harness. No LLM judge anywhere in the core score.

An env supplies Rule objects. The Grader parses the submission, runs every rule that applies to the task,
and returns a Score. It never raises on garbage input (a bad submission scores 0), never trusts claimed
fields (total_cost, score, solved: the rules recompute from the world), and never mutates its inputs.
"""
from __future__ import annotations
import copy, json
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass
class RuleResult:
    passed: bool
    detail: str = ""

class Rule:
    id = "R-?"
    description = ""
    gate = False          # a failed gate rule makes the whole submission score 0 (e.g. invalid format)
    def check(self, ctx: "Ctx") -> RuleResult:
        raise NotImplementedError

@dataclass
class Ctx:
    task: Any
    world: Any
    sub: dict              # parsed submission (deep copy: rules may not change the caller's data)
    cache: dict = field(default_factory=dict)

@dataclass
class Score:
    score: float = 0.0
    solved: bool = False
    valid: bool = False
    rules: dict = field(default_factory=dict)       # rule_id -> bool
    details: dict = field(default_factory=dict)     # rule_id -> why
    soft: dict = field(default_factory=dict)        # reported separately, never part of `solved`
    verdict: str = ""
    meta: dict = field(default_factory=dict)        # set by the runner: repaired, turns, turns_exhausted, error (never read by the grader)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 6), "solved": self.solved, "valid": self.valid, "rules": dict(self.rules),
                "details": dict(self.details), "soft": dict(self.soft), "verdict": self.verdict, "meta": dict(self.meta)}

class Grader:
    """Subclass or instantiate with: rules (id -> Rule), parse(sub) -> dict|None, soft(ctx) -> dict, world_factory(task)."""
    def __init__(self, rules: dict[str, Rule], world_factory: Callable, parse: Callable, soft: Callable | None = None,
                 infeasible_check: Callable | None = None):
        self.rules, self.world_factory, self.parse, self.soft = rules, world_factory, parse, soft
        self.infeasible_check = infeasible_check

    def grade(self, task, submission: Any) -> Score:
        try:
            return self._grade(task, submission)
        except Exception as e:   # the contract: garbage in = score 0, never an exception
            return Score(verdict=f"unscorable: {type(e).__name__}")

    def _grade(self, task, submission) -> Score:
        sub = self.parse(copy.deepcopy(submission))
        if not isinstance(sub, dict):
            return Score(verdict="not a valid submission")
        world = self.world_factory(task)
        ctx = Ctx(task=task, world=world, sub=sub)
        status = sub.get("status")
        applicable = [self.rules[r] for r in task.rules if r in self.rules]
        out = Score(valid=True)
        if status == "infeasible":
            ok, why = self.infeasible_check(ctx) if self.infeasible_check else (False, "")
            out.rules = {"R-INFEASIBLE": bool((not task.expected_feasible) and ok)}
            out.solved = (not task.expected_feasible) and ok
            out.score = 1.0 if out.solved else 0.0
            out.verdict = "correct infeasible claim" if out.solved else ("false infeasible claim: " + why)
            out.details = {"claim": why}
            return out
        if status != "plan":
            return Score(verdict="status must be 'plan' or 'infeasible'")
        passed = 0
        gate_fail = False
        applicable = sorted(applicable, key=lambda r: not r.gate)     # gates first
        for r in applicable:
            try:
                res = r.check(ctx)
            except Exception as e:   # a rule that cannot evaluate fails; it never crashes the grade
                res = RuleResult(False, f"could not evaluate: {type(e).__name__}")
            out.rules[r.id] = bool(res.passed); out.details[r.id] = res.detail
            passed += bool(res.passed)
            if r.gate and not res.passed:
                gate_fail = True
                break                     # the plan cannot even be read: other rules would be meaningless
        if gate_fail:
            out.valid = False
            out.verdict = "invalid format (gate failed)"
            return out
        out.solved = task.expected_feasible and all(out.rules.values()) and bool(out.rules)
        # Partial credit counts the scored rules only. The format gate is a precondition, not a reward: an empty but well-formed answer scores 0.
        scored = [r for r in applicable if not r.gate]
        passed_scored = sum(1 for r in scored if out.rules.get(r.id))
        out.score = 1.0 if out.solved else (passed_scored / len(scored) if scored and task.expected_feasible else 0.0)
        # An infeasible task has no valid plan: any plan scores 0 whatever rules it happens to satisfy.
        if not task.expected_feasible:
            out.solved, out.score = False, 0.0
            out.verdict = "plan given for an infeasible task"
        else:
            out.verdict = "solved" if out.solved else "failed: " + ", ".join(k for k, v in out.rules.items() if not v)
        if self.soft:
            try: out.soft = self.soft(ctx)
            except Exception: out.soft = {}
        return out

def _headline(results: dict) -> dict:
    """pass@1 counts the first run of each task (a format-repair retry, if the agent used one, is allowed).
    strict_pass@1 counts only first runs solved with NO repair retry. format_fail = runs whose answer was not a readable, valid-format submission
    (reported on its own so a harness/format problem is never mistaken for lack of task skill). turns_exhausted / errors come from the runner.
    A task whose run ended in a PROVIDER error (rate limit, quota, outage, spend cap) was not answered by the model: it is NOT RUN, left out of every rate
    (the denominator is `answered`) and counted in `not_run`; `tasks` is still every task attempted."""
    errored = {tid for tid, runs in results.items() if any(s.meta.get("error") for s in runs)}
    ans = {tid: runs for tid, runs in results.items() if tid not in errored}
    n = len(ans)
    p1 = sum(1 for runs in ans.values() if runs and runs[0].solved)
    strict = sum(1 for runs in ans.values() if runs and runs[0].solved and not runs[0].meta.get("repaired"))
    pk = sum(1 for runs in ans.values() if runs and all(s.solved for s in runs))
    fails: dict[str, int] = {}
    for runs in ans.values():
        for s in runs:
            for r, ok in s.rules.items():
                if not ok: fails[r] = fails.get(r, 0) + 1
    allruns = [s for runs in ans.values() for s in runs]
    m = len(allruns) or 1
    every = [s for runs in results.values() for s in runs]
    return {"tasks": len(results), "answered": n, "not_run": len(errored),
            "pass@1": p1 / n if n else 0.0, "strict_pass@1": strict / n if n else 0.0, "pass^k": pk / n if n else 0.0,
            "k": max((len(r) for r in results.values()), default=0),
            "mean_score": sum(s.score for s in allruns) / len(allruns) if allruns else 0.0,
            "format_fail": sum(1 for s in allruns if not s.valid) / m,
            "turns_exhausted": sum(1 for s in allruns if s.meta.get("turns_exhausted")) / m,
            "errors": sum(1 for s in every if s.meta.get("error")) / (len(every) or 1),
            "rule_failures": dict(sorted(fails.items()))}


def task_split(task) -> str:
    """'core' unless the task says otherwise in meta['split'] (e.g. 'experimental'). Core and experimental scores are never mixed."""
    return str((getattr(task, "meta", None) or {}).get("split") or "core")

def task_kind(task) -> str:
    """meta['kind'] if the env sets one, else 'feasible' / 'infeasible' from the task's expected_feasible."""
    k = (getattr(task, "meta", None) or {}).get("kind")
    return str(k) if k else ("feasible" if getattr(task, "expected_feasible", True) else "infeasible")

def summarize(results: dict, tasks: dict | None = None) -> dict:
    """results: {task_id: [Score, ...k runs]} -> pass@1, pass^k (all k runs solved), mean rule score, per-rule failures.
    With `tasks` ({task_id: Task}) it also returns by_split and by_kind: the same numbers per split (core / experimental) and per kind
    (feasible / infeasible, or the env's own kinds), so a mixed headline can never be the only number reported."""
    out = _headline(results)
    if tasks is not None:
        for key, fn in (("by_split", task_split), ("by_kind", task_kind)):
            groups: dict[str, dict] = {}
            for tid, runs in results.items():
                if tid in tasks:
                    groups.setdefault(fn(tasks[tid]), {})[tid] = runs
            out[key] = {g: _headline(r) for g, r in sorted(groups.items())}
    return out
