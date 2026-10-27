"""Env #4 Form Desk: KYC fields, addresses and PIN codes, Indian number idioms, financial-year dates. Exact-match grading from an independent oracle.
Rules are env rules (simplified), not claims about live systems. All identities are synthetic; no Aadhaar numbers exist anywhere in this env.
    from navital_gym.envs.form import load_env, grade
    env = load_env(); obs = env.reset("IN-FORM-001")
"""
import os
from ...core import Env, load_tasks
from .world import FormWorld
from .rules import make_grader, RULES
from . import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.jsonl")

INSTRUCTIONS = """You are filling or checking Indian forms in a fixed simulated setting. Everything is synthetic.
Use the tools if they help (get_input, get_policy, validate_pan, validate_ifsc, validate_mobile, pin_zone). Finish with ONE JSON object and nothing else after it:
{"status": "plan", "answer": {<the answer fields named in the request>}}
Dates as YYYY-MM-DD; yes/no as true/false; whole numbers as numbers. A value that fails its format rule must be null, never repaired or guessed.
There is no infeasible answer in this env. The grader recomputes every field from the input; claimed scores or extra fields are ignored."""

def load_env(seed: int = 0, tasks_path: str = TASKS_PATH, include_pending: bool = True) -> Env:
    tasks = load_tasks(tasks_path)
    env = Env(tasks, FormWorld, make_grader(lambda task: FormWorld(task, seed)), seed)
    env.name, env.instructions = "form", INSTRUCTIONS
    return env

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract (qa harness): grade(task: dict, submission) -> {"score", "solved", "rules"}. Never raises."""
    global _ENV
    if _ENV is None:
        _ENV = load_env()
    return _ENV.contract_grade(task, submission)

def check_gold(tasks) -> list:
    """Tasks whose stored gold_answer disagrees with the oracle (a task bug or an oracle bug: fix before shipping)."""
    bad = []
    for t in tasks:
        want = oracle.solve(t.meta["kind"], t.params["world"])
        gold = t.meta.get("gold_answer") or {}
        diff = {k: (gold[k], v) for k, v in want.items() if k in gold and gold[k] != v}
        if diff:
            bad.append({"id": t.id, "diff": diff})
    return bad

from .baselines import get_baselines  # noqa: E402
