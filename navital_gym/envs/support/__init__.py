"""Env #5 Bhasha Support Desk: online-shop customer support in Hindi and Hinglish (core) plus an experimental Tamil / Bengali / Marathi split.
State is graded from the actions the agent lists (replayed against the shop's invented policy by an independent oracle); the reply language is a
hard rule for the core only. The policy is invented for this env: it is not Indian consumer law and not any real store's policy. All orders are synthetic.
EXPERIMENTAL SPLIT: machine-assisted, not native-reviewed; corrections welcome.
    from navital_gym.envs.support import load_env, grade
    env = load_env()                      # core only (Hindi + Hinglish)
    env = load_env(include_experimental=True)
"""
import os
from ...core import Env, load_tasks
from .world import SupportWorld
from .rules import make_grader, RULES
from . import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.jsonl")
EASY_PATH = os.path.join(HERE, "tasks_easy.jsonl")

INSTRUCTIONS = """You are a customer-support agent for an online shop, talking to ONE customer in their language. Everything is synthetic; the shop's policy is invented.
Use the tools to read the policy and the order (get_policy, get_order, return_window_status, get_photo_status, get_customer_bank, validate_ifsc). Nothing changes until you finish.
Finish with ONE JSON object and nothing else after it:
{"status": "plan", "actions": [ {"tool": "issue_refund", "args": {"order_id": ..., "amount": rupees, "mode": "original_source" | "bank_transfer"}},
                                {"tool": "cancel_order" | "schedule_pickup" | "request_photo" | "request_address_change", "args": {"order_id": ...}},
                                {"tool": "escalate_to_human", "args": {"reason": ...}} ],
 "decision": one of refund | decline_return | cancel | decline_cancel | request_photo | ask_ifsc | refuse_privacy | escalate | address_change | decline_address_change,
 "reason": one of eligible | outside_return_window | non_returnable_category | outside_report_window | not_shipped | already_shipped | damaged_with_photo | no_photo | bad_ifsc | not_owner | customer_requests_human,
 "reply": "your message to the customer, in the customer's language"}
The decision and the reason are graded against what the policy requires for THIS order, so read the order before deciding. List only the actions the policy allows (an empty list is valid). Never reveal another customer's data. If a refund is due, say the amount in your reply."""

def load_env(seed: int = 0, tasks_path: str = TASKS_PATH, include_experimental: bool = False, splits=("core",)) -> Env:
    """splits: "core" (the standard Hindi/Hinglish 50, plus the experimental 26 with include_experimental) and/or "easy" (tasks_easy.jsonl, 18 one-decision Hinglish tasks)."""
    tasks = [t for t in load_tasks(tasks_path) if "core" in splits and (include_experimental or t.meta.get("split") == "core")]
    if "easy" in splits:
        tasks += load_tasks(EASY_PATH)
    env = Env(tasks, SupportWorld, make_grader(lambda task: SupportWorld(task, seed)), seed)
    env.name, env.instructions = "support", INSTRUCTIONS
    return env

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract (qa harness). Never raises. Uses all tasks, experimental split included."""
    global _ENV
    if _ENV is None:
        _ENV = load_env(include_experimental=True, splits=("core", "easy"))
    return _ENV.contract_grade(task, submission)

def check_gold(tasks) -> list:
    """Tasks whose stored gold_answer disagrees with the oracle's expected actions/amount (a task bug or an oracle bug: fix before shipping)."""
    kinds = {"refund": "refund", "decline_return": "decline_return", "cancel": "cancel", "decline_cancel": "decline_cancel", "request_photo": "request_photo",
             "ask_ifsc": "ask_correct_ifsc", "privacy": "refuse_other_customer_data", "escalate": "escalate_to_human",
             "address_ok": "request_address_change", "address_no": "decline_address_change",
             "decline_return_early": "decline_return", "decline_cancel_delivered": "decline_cancel", "own_address": "answer_own_order"}
    bad = []
    for t in tasks:
        o = oracle.solve(t.meta["kind"], t.params["world"], t.params["policy"]); gold = t.meta.get("gold_answer") or {}
        if kinds[o["reply"]] != gold.get("action") or ("amount" in gold and gold["amount"] != o["amount"]):
            bad.append({"id": t.id, "oracle": o["reply"], "gold": gold})
    return bad

from .baselines import get_baselines  # noqa: E402
