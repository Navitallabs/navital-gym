"""Env #3 GST Desk. Tasks come from the task authors' tasks_gst.jsonl as rows
{id, kind, difficulty, lang, prompt, rules(values), world, gold_answer}; load_tasks adapts them to the core Task."""
from __future__ import annotations
import json, os
from decimal import Decimal as Dc
from ...core.schema import Task
from ...core.env import Env
from .world import GstWorld
from . import oracle, rules

def row_to_task(row: dict) -> Task:
    kind = row["kind"]
    return Task(id=row["id"], family=kind, difficulty=int(row.get("difficulty", 1)), lang=row.get("lang", "en"),
                prompt=row["prompt"], params={"world": row["world"], "rules": row["rules"]},
                rules=rules.rule_ids_for(kind, row["prompt"]), expected_feasible=True,
                meta={"kind": kind, "gold_answer": row.get("gold_answer"), "forbidden_actions": row.get("forbidden_actions", []), "split": row.get("split", "core")})

def load_tasks(path: str) -> list[Task]:
    with open(path, encoding="utf-8") as f:
        return [row_to_task(json.loads(l)) for l in f if l.strip() and not l.startswith("#")]

INSTRUCTIONS = ("Use the tools to read the documents and the policy. Finish with a JSON object "
                '{"status": "plan", "answer": {...}} containing exactly the fields the question asks for. '
                "Money as a decimal string or number in rupees; dates as YYYY-MM-DD; yes/no as true/false.")

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.jsonl")
EASY_PATH = os.path.join(HERE, "tasks_easy.jsonl")

# The standard questions do not name the fields the grader scores, so each standard prompt ends with the answer fields for ITS question type (the easy prompts already end
# with "Answer field: ...", so they are left exactly as they were).
ANSWER_FIELDS = {
    "invoice": "Answer fields: taxable_value, cgst, sgst, igst, round_off and invoice_total (rupees), and tax_type = exactly CGST+SGST or IGST.",
    "place_of_supply": "Answer field: tax_type = exactly CGST+SGST or IGST.",
    "itc_reconciliation": "Answer fields: eligible_itc (rupees) and eligible_invoices (a list of the invoice ids, as written in the register, whose credit can be claimed).",
    "late_filing": "Answer fields: due_date (YYYY-MM-DD), days_late (whole number), late_fee (rupees) and interest (rupees).",
}

def answer_fields_text(task: Task) -> str:
    kind = task.meta["kind"]
    if kind == "threshold":
        return "Answer field: " + ("eligible" if "R-ELIGIBLE" in task.rules else "required") + " = true or false."
    return ANSWER_FIELDS[kind]

class GstEnv(Env):
    def reset(self, task_id: str) -> dict:
        obs = super().reset(task_id)
        if (self.task.meta or {}).get("split", "core") == "core":
            obs["prompt"] += "\n" + answer_fields_text(self.task)
        return obs

def make_env(tasks: list[Task], seed: int = 0) -> Env:
    e = GstEnv(tasks, GstWorld, rules.make_grader(lambda task: GstWorld(task, seed)), seed)
    e.instructions = INSTRUCTIONS
    e.name = "gst"
    return e

def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool): return a == b
    if isinstance(a, (int, float, str, Dc)) and isinstance(b, (int, float, str, Dc)):
        try: return Dc(str(a)) == Dc(str(b))
        except Exception: return str(a) == str(b)
    return a == b

def check_gold(tasks: list[Task]) -> list[dict]:
    """Tasks whose stored gold_answer disagrees with the oracle (a task bug or a rules bug: fix before shipping)."""
    bad = []
    for t in tasks:
        want = oracle.solve(t.meta["kind"], t.params["world"], t.params["rules"], t.prompt)
        gold = t.meta["gold_answer"] or {}
        diff = {k: (gold.get(k), str(v)) for k, v in want.items() if k in gold and not (
            sorted(map(str, gold[k])) == sorted(map(str, v)) if isinstance(v, list) else _same(gold[k], v))}
        if diff: bad.append({"id": t.id, "kind": t.meta["kind"], "diff": diff})
    return bad


def load_env(seed: int = 0, tasks_path: str = TASKS_PATH, splits=("core",)) -> Env:
    """Entry point shared by every adapter: navital_gym.envs.<name>.load_env().
    splits: "core" (the standard 50, the default so existing results never change) and/or "easy" (tasks_easy.jsonl, 18 one-rule tasks)."""
    tasks = (load_tasks(tasks_path) if "core" in splits else []) + (load_tasks(EASY_PATH) if "easy" in splits else [])
    return make_env(tasks, seed)

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract (qa harness): grade(task: dict, submission) -> {"score", "solved", "rules"}. Never raises."""
    global _ENV
    if _ENV is None:
        _ENV = load_env(splits=("core", "easy"))
    return _ENV.contract_grade(task, submission)


from .baselines import get_baselines  # noqa: E402
