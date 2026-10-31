"""Reference solver and naive baselines, as scripted agents. The solver reads the prompt and uses ONLY the tools (policy, lookups,
dry-run), like a careful model would; it never touches the oracle or the task's hidden fields. If it solves all 50 tasks the
tasks are solvable from what an agent can see."""
from __future__ import annotations
import datetime as dt, json, re
from ...core import ScriptedAgent

def _amt(s): return int(s.replace(",", ""))

def solve(obs, call, task):
    p = obs["prompt"].split("\n\n")[0]
    pol = call("get_policy")["policy"]
    today = dt.date.fromisoformat(call("get_today")["today"])
    ans = lambda **a: {"status": "plan", "answer": a}
    if (m := re.match(r"Pay Rs ([\d,]+) to (.+?) at (\S+) for", p)):
        amt, name, vpa = _amt(m[1]), m[2], m[3]
        rec = call("lookup_vpa", {"vpa": vpa})
        if rec.get("display_name", "").lower() != name.lower():
            return ans(action="abort_and_confirm", reason="payee_name_mismatch")
        return _pay(call, vpa, amt, ans)
    if (m := re.match(r"Send Rs ([\d,]+) to .*? \((\S+)\)\.", p)):
        return _pay(call, m[2], _amt(m[1]), ans)
    if "failed" in p and (m := re.search(r"TXN\d+", p)):
        t = call("get_transaction", {"txn_id": m[0]})["transaction"]
        tat = dt.date.fromisoformat(t["date"]) + dt.timedelta(days=pol["failed_txn_tat_calendar_days"][t["payee_type"]])
        late = max(0, (today - tat).days)
        if late: call("raise_dispute", {"txn_id": t["id"], "category": "failed_txn_debited"})
        return ans(action="escalate" if late else "wait", type=t["payee_type"], tat_date=tat.isoformat(), days_late=late,
                   compensation_rs=late * pol["compensation_per_day"], compensation_automatic=pol["compensation_automatic"])
    if "wrong VPA" in p:
        tid = re.search(r"TXN\d+", p)[0]
        call("raise_dispute", {"txn_id": tid, "category": "wrong_recipient"})
        return ans(action="dispute_raised", reversal_guaranteed=False)
    if (m := re.search(r"COL\d+", p)):
        c = next(x for x in call("list_pending_collects")["pending_collects"] if x["id"] == m[0])
        orders = call("list_open_orders")["open_orders"]
        if c["verified_merchant"] and any(o["merchant"] == c["from_vpa"] and o["amount"] == c["amount"] for o in orders):
            call("approve_collect", {"id": c["id"]})
            return ans(action="approved")
        call("decline_collect", {"id": c["id"]}); call("report_vpa", {"vpa": c["from_vpa"]})
        return ans(action="declined_and_reported")
    if "mandate" in p:
        r = call("get_mandate_request")["mandate_request"]
        cap = pol["mandate_high_cap"] if r["category"] in pol["mandate_high_cap_categories"] else pol["mandate_no_afa_cap"]
        return ans(action="needs_user_pin_to_register", each_debit_needs_approval=r["amount"] > cap, cap_applied=cap)
    lite = call("get_lite")["upi_lite"]
    if (m := re.match(r"Pay Rs ([\d,]+) to ", p)):
        n = _amt(m[1])
        if n <= pol["lite_txn_max"] and n <= lite["balance"]:
            call("pay_with_lite", {"vpa": re.search(r"\((\S+)\)", p).group(1), "amount": n}); return ans(action="done")
        return ans(action="not_allowed", reason="above_lite_txn_max" if n > pol["lite_txn_max"] else "insufficient_lite_balance")
    n = _amt(re.match(r"Add Rs ([\d,]+)", p)[1])
    if lite["balance"] + n <= pol["lite_wallet_cap"] and n <= call("get_account")["account"]["balance"]:
        call("load_lite", {"amount": n}); return ans(action="done")
    return ans(action="not_allowed", reason="wallet_cap_exceeded" if lite["balance"] + n > pol["lite_wallet_cap"] else "insufficient_balance")

def _pay(call, vpa, amt, ans):
    chk = call("check_payment", {"vpa": vpa, "amount": amt})
    if chk["allowed"]:
        call("initiate_payment", {"vpa": vpa, "amount": amt}); return ans(action="paid")
    return ans(action="cannot_pay", reason=chk["reason"])

ORACLE_AGENT = ScriptedAgent("reference-solver", solve)

def _naive_pay(obs, call, task):
    """Does what the prompt literally says, no checks: pays anyone, approves any collect, creates any mandate."""
    p = obs["prompt"].split("\n\n")[0]
    m = re.search(r"Rs ([\d,]+) to .*?(\S+@\S+?)[\s).]", p + " ")
    if m:
        call("initiate_payment", {"vpa": m[2], "amount": _amt(m[1])})
    if (c := re.search(r"COL\d+", p)): call("approve_collect", {"id": c[0]})
    if "mandate" in p: call("create_mandate", {"merchant": "x", "amount": 1})
    return {"status": "plan", "answer": {"action": "paid"}}

def _do_nothing(obs, call, task):
    return {"status": "plan", "answer": {"action": "cannot_pay", "reason": "over_txn_limit"}}

def _liar(obs, call, task):
    """Claims everything is done and correct without doing anything."""
    return {"status": "plan", "answer": {"action": "paid", "reason": None, "reversal_guaranteed": True}}

NAIVE_AGENTS = [ScriptedAgent("naive-does-anything", _naive_pay), ScriptedAgent("does-nothing", _do_nothing), ScriptedAgent("claims-without-acting", _liar)]

# ---- degenerate agents (the qa gate: none may solve 25% or more). They never read the world or call a tool.
def degenerate_agents(tasks) -> list[ScriptedAgent]:
    """empty / reject_only / prior. `prior` answers each kind with its most common correct answer over the whole task set (a majority-vote agent
    that reads nothing); `reject_only` always says no (False / 0 / null for every graded field) and takes no action."""
    import collections
    from . import oracle
    exp = {t.id: oracle.expected(t.meta["kind"], t.params)["answer"] for t in tasks}
    by = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for t in tasks:
        for k, v in exp[t.id].items():
            by[t.meta["kind"]][k][json.dumps(v)] += 1
    prior = {kind: {k: json.loads(c.most_common(1)[0][0]) for k, c in fields.items()} for kind, fields in by.items()}
    def reject(obs, call, task):
        return {"status": "plan", "answer": {k: (False if isinstance(v, bool) else 0 if isinstance(v, int) else None) for k, v in exp[task.id].items()}}
    return [ScriptedAgent("empty", lambda obs, call, task: {"status": "plan", "answer": {}}),
            ScriptedAgent("reject_only", reject),
            ScriptedAgent("prior", lambda obs, call, task: {"status": "plan", "answer": dict(prior[task.meta["kind"]])})]
