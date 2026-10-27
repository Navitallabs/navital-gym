"""Scripted agents for Bhasha Support Desk: empty, refund_all (always refunds, answers in English), english (right actions, wrong language), oracle."""
import re
from ...core.runner import ScriptedAgent
from . import oracle, data as D

def _o(task): return oracle.solve(task.meta["kind"], task.params["world"], task.params["policy"])

def _actions(o):
    out = []
    for t, oid, amt, mode in o["actions"]:
        args = {k: v for k, v in (("order_id", oid), ("amount", amt), ("mode", mode)) if v is not None}
        out.append({"tool": t, "args": args} if t != "escalate_to_human" else {"tool": t, "args": {"reason": "customer asked for a manager"}})
    return out

def reply_for(task, o) -> str:
    lang = task.lang; kind = o["reply"]
    amount = o["amount"]; eta = task.params["policy"].get("refund_eta_workdays", 5)
    tmpl = D.REPLIES[kind][lang]
    tail = D.REFUND_TAILS[lang].format(amount=amount, eta=eta) if amount else ""
    tmpl = re.sub(r"\{refund_\w+\}", lambda m: tail, tmpl)
    return tmpl.format(amount=amount, eta=eta, address=task.params["world"]["order"].get("ship_address", ""))

def empty(obs, call, task): return {"status": "plan", "actions": [], "reply": "Okay.", "decision": "decline_return", "reason": "eligible"}

def noop_lang(obs, call, task):
    """The gaming floor: never reads the order, takes no action, answers with one fixed sentence in the right language and a fixed guess."""
    return {"status": "plan", "actions": [], "reply": D.REPLIES["decline_return"][task.lang], "decision": "decline_return", "reason": "outside_return_window"}

def refund_all(obs, call, task):
    o = task.params["world"]["order"]
    return {"status": "plan", "actions": [{"tool": "issue_refund", "args": {"order_id": o["id"], "amount": o["price"], "mode": "original_source"}}], "reply": "Your refund has been issued.", "decision": "refund", "reason": "eligible"}

def english(obs, call, task):
    o = _o(task)
    return {"status": "plan", "actions": _actions(o), "reply": "Your request has been handled as per our policy. Refund amount, if any: " + str(o["amount"] or 0) + ".", "decision": o["decision"], "reason": o["reason"]}

def oracle_agent(obs, call, task):
    o = _o(task)
    return {"status": "plan", "actions": _actions(o), "reply": reply_for(task, o), "decision": o["decision"], "reason": o["reason"]}

def get_baselines():
    return {n: ScriptedAgent(n, f) for n, f in [("empty", empty), ("noop_lang", noop_lang), ("refund_all", refund_all), ("english", english), ("oracle", oracle_agent)]}
