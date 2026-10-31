"""Env #2 UPI Desk: payments and disputes in a simulated bank (payee-name check, limits, failed-but-debited, wrong recipient,
collect-request scams, AutoPay mandates, UPI Lite). Rules are simplified env rules, not live NPCI/RBI rules (see README).
    from navital_gym.envs.upi import load_env, grade
    env = load_env(); obs = env.reset("IN-UPI-001")     # obs = prompt + tool specs; the agent never sees hidden task fields
    grade(task_dict, submission)                          # shared grader contract: {"score", "solved", "rules"}; never raises
Tasks come from the task authors' tasks_upi.jsonl (copied to tasks_source.jsonl); `row_to_task` adapts a row to the core Task."""
from __future__ import annotations
import json, os, re
from typing import Any
from ...core import Env, Task
from .world import UpiWorld, ACTIONS
from . import oracle, rules

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks_source.jsonl")
EASY_TASKS_PATH = os.path.join(HERE, "tasks_easy.jsonl")
SPLIT_PATHS = {"core": TASKS_PATH, "easy": EASY_TASKS_PATH}

def _n(s: str) -> int:
    return int(s.replace(",", ""))

def facts_from_prompt(kind: str, prompt: str) -> dict:
    """The few things only the prompt states (who to pay, how much, which transaction). The oracle reads these, not the gold."""
    if kind == "pay_verify":
        m = re.match(r"Pay Rs ([\d,]+) to (.+?) at (\S+) for", prompt)
        return {"amount": _n(m.group(1)), "payee_name": m.group(2), "vpa": m.group(3)}
    if kind == "limits":
        m = re.match(r"Send Rs ([\d,]+) to .*? \((\S+)\)\.", prompt)
        return {"amount": _n(m.group(1)), "vpa": m.group(2)}
    if kind in ("failed_debited", "wrong_recipient"):
        return {"txn_id": re.search(r"TXN\d+", prompt).group(0)}
    if kind == "collect_request":
        return {"collect_id": re.search(r"COL\d+", prompt).group(0)}
    if kind == "upi_lite":
        m = re.match(r"Pay Rs ([\d,]+) to .*?\((\S+)\)", prompt)
        if m: return {"op": "pay", "amount": _n(m.group(1)), "vpa": m.group(2)}
        return {"op": "load", "amount": _n(re.match(r"Add Rs ([\d,]+)", prompt).group(1))}
    if kind == "mandate":
        return {}
    raise ValueError(kind)

def row_to_task(row: dict) -> Task:
    kind = row["kind"]
    params = {"world": row["world"], "rules": row["rules"], "facts": facts_from_prompt(kind, row["prompt"])}
    if "policy_keys" in row: params["policy_keys"] = row["policy_keys"]
    return Task(id=row["id"], family=kind, difficulty=int(row.get("difficulty", 1)), lang=row.get("lang", "en"), prompt=row["prompt"],
                params=params, rules=rules.rule_ids_for(kind, params), expected_feasible=True,
                meta={"kind": kind, "gold_answer": row.get("gold_answer"), "gold_actions": row.get("gold_actions", []),
                      "forbidden_actions": row.get("forbidden_actions", []),
                      "split": (row.get("meta") or {}).get("split", "core")})

def _read(path: str) -> list[Task]:
    with open(path, encoding="utf-8") as f:
        return [row_to_task(json.loads(l)) for l in f if l.strip() and not l.startswith("#")]

def load_tasks(path: str | None = None, splits: tuple = ("core",)) -> list[Task]:
    """`path` loads one file as given; otherwise the files of `splits` ("core" = the 50 standard tasks, "easy" = IN-UPI-E01..)."""
    if path is not None:
        return _read(path)
    unknown = [x for x in splits if x not in SPLIT_PATHS]
    if unknown:
        raise ValueError(f"unknown split {unknown[0]!r}; choose from {sorted(SPLIT_PATHS)}")
    return [t for x in splits for t in _read(SPLIT_PATHS[x])]

INSTRUCTIONS = """You are an assistant for the account owner in a simulated bank and UPI app (all names, balances and rules are synthetic). Use the tools to look things up, read the policy, and act. Some actions move money or cannot be undone: check first. Do only what the request and the policy allow.
Finish with ONE JSON object and nothing after it: {"status": "plan", "answer": {...}}. The answer always has "action", one of:
  paid | abort_and_confirm (the payee does not match what you were told: stop and ask) | cannot_pay | wait | escalate | dispute_raised |
  approved | declined_and_reported | needs_user_pin_to_register | done | not_allowed
and these fields where they apply:
  "reason": payee_name_mismatch | over_txn_limit | over_daily_limit | above_lite_txn_max | insufficient_lite_balance | wallet_cap_exceeded | insufficient_balance (when you stop or refuse)
  failed-but-debited money: "type" (p2p | p2m), "tat_date" (YYYY-MM-DD, the last day the bank has to return it), "days_late", "compensation_rs", "compensation_automatic" (true/false)
  wrong recipient: "reversal_guaranteed" (true/false)
  AutoPay mandate: "each_debit_needs_approval" (true/false), "cap_applied" (rupees)
What you did is checked from the actions you took, not from what you say."""

class UpiEnv(Env):
    """Env whose grader also needs the action log. The log comes from the live world, so an agent cannot edit it;
    on the contract path (no live world) the caller supplies `actions` in the submission."""
    def _with_log(self, task, sub):
        if self.world is not None and self.task is task and isinstance(sub, dict):
            sub = dict(sub)
            sub["actions"] = [{"tool": c["tool"], "args": c["args"]} for c in self.world.calls]
        return sub

    def step(self, action: dict) -> dict:
        if self.done or "finalize" not in action:
            return super().step(action)
        sc = self.grader.grade(self.task, self._with_log(self.task, action["finalize"]))
        self.done = True
        return {"obs": {"graded": True}, "done": True, "reward": sc.score, "info": sc.to_dict()}

    def grade(self, task, submission: Any):
        return self.grader.grade(task, self._with_log(task, submission))

def load_env(seed: int = 0, tasks_path: str | None = None, splits: tuple = ("core",)) -> Env:
    env = UpiEnv(load_tasks(tasks_path, splits), UpiWorld, rules.make_grader(lambda task: UpiWorld(task, seed)), seed)
    env.name, env.instructions = "upi", INSTRUCTIONS
    return env

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract: grade(task: dict, submission) -> {"score", "solved", "rules"}. Never raises."""
    global _ENV
    if _ENV is None:
        _ENV = UpiEnv([], UpiWorld, rules.make_grader(lambda t: UpiWorld(t, 0)), 0)
        _ENV.name = "upi"
    try:
        t = row_to_task(task) if "kind" in task and "world" in task else Task.from_dict(task)
    except Exception:
        return {"score": 0.0, "solved": False, "rules": {}}
    sc = _ENV.grader.grade(t, submission).to_dict()
    return {"score": sc["score"], "solved": sc["solved"], "rules": sc["rules"], "verdict": sc["verdict"]}

def check_gold(tasks: list[Task]) -> list[dict]:
    """Tasks whose stored gold disagrees with the oracle: a task bug or a rules bug. Compares the answer fields and the
    set of required actions and forbidden tools."""
    bad = []
    for t in tasks:
        e = oracle.expected(t.meta["kind"], t.params)
        g = t.meta["gold_answer"] or {}
        diffs = {k: (g.get(k), v) for k, v in e["answer"].items() if k in g and g[k] != v}
        gold_fx = sorted(map(str, [(a["tool"], *[a["args"].get(k) for k in __import__("navital_gym.envs.upi.world", fromlist=["x"]).EFFECT_KEYS[a["tool"]]]) for a in t.meta["gold_actions"]]))
        if gold_fx != sorted(map(str, e["effects"])): diffs["effects"] = (gold_fx, e["effects"])
        if sorted(t.meta["forbidden_actions"]) != sorted(e["forbidden"]): diffs["forbidden"] = (t.meta["forbidden_actions"], e["forbidden"])
        if diffs: bad.append({"id": t.id, "kind": t.meta["kind"], "diff": diffs})
    return bad

def get_baselines() -> dict:
    """name -> scripted agent, for `navital-gym run --env upi --agent <name>`. None of them calls a model.
    oracle      the reference solver: reads the prompt and uses only the tools (an upper bound, not a fair baseline)
    empty / reject_only / prior   the degenerate agents behind the 25% gate: they read nothing and call no tool."""
    from .solver import ORACLE_AGENT, degenerate_agents
    agents = {"oracle": ORACLE_AGENT}
    agents.update({a.name: a for a in degenerate_agents(load_tasks(splits=("core", "easy")))})
    return agents
