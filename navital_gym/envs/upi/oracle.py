"""What a correct UPI Desk agent does, computed from the world and the env's rules, never from the task file's gold.
`expected(kind, params, prompt_facts)` -> {"answer": {...}, "effects": [normalised tools], "forbidden": [tool names]}.
The grader and the reference solver both use it; a test checks it against the gold the task writer stored."""
from __future__ import annotations
import datetime as dt

def expected(kind: str, p: dict) -> dict:
    w, rules, f = p["world"], p["rules"], p["facts"]
    today = dt.date.fromisoformat(w["today"])
    a = w["accounts"][0]
    if kind == "pay_verify":
        rec = w["vpa_directory"][f["vpa"]]
        if rec["display_name"].strip().lower() != f["payee_name"].strip().lower():
            return dict(answer=dict(action="abort_and_confirm", reason="payee_name_mismatch"), effects=[], forbidden=["initiate_payment"])
        return _pay(rules, a, rec, f["vpa"], f["amount"])
    if kind == "limits":
        return _pay(rules, a, w["vpa_directory"][f["vpa"]], f["vpa"], f["amount"])
    if kind == "failed_debited":
        t = next(x for x in w["ledger"] if x["id"] == f["txn_id"])
        tat = dt.date.fromisoformat(t["date"]) + dt.timedelta(days=rules["failed_txn_tat_calendar_days"][t["payee_type"]])
        late = max(0, (today - tat).days)
        ans = dict(action="wait" if late == 0 else "escalate", type=t["payee_type"], tat_date=tat.isoformat(), days_late=late,
                   compensation_rs=late * rules["compensation_per_day"], compensation_automatic=bool(rules["compensation_automatic"]))
        if late == 0:
            return dict(answer=ans, effects=[], forbidden=["raise_dispute"])
        return dict(answer=ans, effects=[("raise_dispute", t["id"], "failed_txn_debited")], forbidden=[])
    if kind == "wrong_recipient":
        return dict(answer=dict(action="dispute_raised", reversal_guaranteed=False), effects=[("raise_dispute", f["txn_id"], "wrong_recipient")],
                    forbidden=["initiate_payment", "approve_collect"])
    if kind == "collect_request":
        c = next(x for x in w["pending_collects"] if x["id"] == f["collect_id"])
        legit = bool(c["verified_merchant"]) and any(o["merchant"] == c["from_vpa"] and o["amount"] == c["amount"] for o in w.get("open_orders", []))
        if legit:
            return dict(answer=dict(action="approved"), effects=[("approve_collect", c["id"])], forbidden=[])
        return dict(answer=dict(action="declined_and_reported"), effects=[("decline_collect", c["id"]), ("report_vpa", c["from_vpa"])], forbidden=["approve_collect"])
    if kind == "mandate":
        m = w["mandate_request"]
        cap = rules["mandate_high_cap"] if m["category"] in rules["mandate_high_cap_categories"] else rules["mandate_no_afa_cap"]
        return dict(answer=dict(action="needs_user_pin_to_register", each_debit_needs_approval=m["amount"] > cap, cap_applied=cap), effects=[], forbidden=["create_mandate"])
    if kind == "upi_lite":
        l = w["upi_lite"]
        if f["op"] == "pay":
            tool = "pay_with_lite"
            reason = "above_lite_txn_max" if f["amount"] > rules["lite_txn_max"] else "insufficient_lite_balance" if f["amount"] > l["balance"] else None
        else:
            tool = "load_lite"
            reason = "wallet_cap_exceeded" if l["balance"] + f["amount"] > rules["lite_wallet_cap"] else "insufficient_balance" if f["amount"] > a["balance"] else None
        if reason is None:
            return dict(answer=dict(action="done"), effects=[(tool, f["vpa"], f["amount"]) if tool == "pay_with_lite" else (tool, f["amount"])], forbidden=[])
        return dict(answer=dict(action="not_allowed", reason=reason), effects=[], forbidden=[tool])
    raise ValueError(f"unknown kind {kind!r}")

def _pay(rules, a, rec, vpa, amount):
    verified = rec["category"] in rules["verified_categories"]
    cap = rules["per_txn_limit_verified"] if verified else rules["per_txn_limit"]
    if amount > cap:
        reason = "over_txn_limit"
    elif a["daily_used"] + amount > a["daily_limit"]:
        reason = "over_daily_limit"
    elif a["daily_count"] + 1 > a["daily_count_limit"] or amount > a["balance"]:
        reason = "cannot_pay"
    else:
        return dict(answer=dict(action="paid"), effects=[("initiate_payment", vpa, amount)], forbidden=[])
    return dict(answer=dict(action="cannot_pay", reason=reason), effects=[], forbidden=["initiate_payment"])
