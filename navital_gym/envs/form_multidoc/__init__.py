"""Form Desk: hard (experimental split, calibrated only after baseline runs): multi-document KYC consistency, PAN structure vs name, conflicting fields in one record,
OCR repair where the fix is unique, and batches of records. Exact-match grading from an independent oracle. Rules are env rules (simplified). All identities are synthetic; no Aadhaar numbers.
    from navital_gym.envs.form_multidoc import load_env, grade
    env = load_env(); obs = env.reset("IN-FORMMD-001")
"""
import os
from ...core import Env, load_tasks
from .world import FormMultidocWorld
from .rules import make_grader, RULES
from . import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.jsonl")

INSTRUCTIONS = """You are checking Indian forms in a fixed simulated setting. Everything is synthetic. Every answer field is defined in the request.
Use the tools if they help (get_input, get_policy, validate_pan, validate_ifsc, pin_zone). Finish with ONE JSON object and nothing else after it:
{"status": "plan", "answer": {<the answer fields named in the request>}}
Dates as YYYY-MM-DD; yes/no as true/false; whole numbers as numbers; lists as JSON arrays of strings with each item at most once ([] when empty). Do not repair or guess a value unless the policy says how.
There is no infeasible answer in this env. The grader recomputes every field from the input; claimed scores or extra fields are ignored."""

def load_env(seed: int = 0, tasks_path: str = TASKS_PATH, include_pending: bool = True) -> Env:
    tasks = load_tasks(tasks_path)
    env = Env(tasks, FormMultidocWorld, make_grader(lambda task: FormMultidocWorld(task, seed)), seed)
    env.name, env.instructions = "form_multidoc", INSTRUCTIONS
    return env

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract (qa harness): grade(task: dict, submission) -> {"score", "solved", "rules"}. Never raises."""
    global _ENV
    if _ENV is None: _ENV = load_env()
    return _ENV.contract_grade(task, submission)

def check_gold(tasks) -> list:
    """Tasks whose stored gold_answer disagrees with the oracle (a task bug or an oracle bug: fix before shipping)."""
    bad = []
    for t in tasks:
        want = oracle.solve(t.meta["kind"], t.params["world"]); gold = t.meta.get("gold_answer") or {}
        diff = {k: (gold[k], v) for k, v in want.items() if k in gold and gold[k] != v}
        if diff: bad.append({"id": t.id, "diff": diff})
    return bad

from .baselines import get_baselines  # noqa: E402
