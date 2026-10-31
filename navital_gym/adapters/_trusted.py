"""Grading for the adapters (Inspect, verifiers): the verdict comes from what the rollout EXECUTED, never from what the final answer claims.

An adapter records the tool calls the model really made (name and arguments, in order). `grade_executed` replays them on a fresh world of the task (worlds are
deterministic, as in scripts/regrade.py) and grades the final answer with the env's own `grade`. For an env whose grader reads the action log (UPI), the log is
the replayed world's, and any `actions` list the answer carries is overridden; for the others the answer is graded as the harness grades it."""
from __future__ import annotations
import copy, json
from typing import Any, Iterable


def parse_arguments(arguments: Any) -> dict:
    """Tool-call arguments as a dict (providers hand over a dict or a JSON string; anything else is an empty call)."""
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            v = json.loads(arguments or "{}")
        except ValueError:
            return {}
        return v if isinstance(v, dict) else {}
    return {}


def grade_executed(env, task_id: str, submission: Any, calls: Iterable[tuple[str, dict]]) -> dict:
    """{"score", "solved", "rules", "verdict", "soft"} for `submission`, graded on a world where `calls` have been executed in order."""
    e = copy.copy(env)                      # own task/world; tasks and grader are shared and stateless
    e.reset(task_id)
    for name, args in calls:
        e.world.call(str(name), parse_arguments(args))
    sc = e.grade(e.task, submission).to_dict()
    return {"score": sc["score"], "solved": sc["solved"], "rules": sc["rules"], "verdict": sc["verdict"], "soft": sc["soft"]}
