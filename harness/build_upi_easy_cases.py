"""cases/upi_easy for frontend's UPI easy split. Hand solves by qa from each prompt, get_policy and the world data; the build asserts they equal the stored gold
and gold actions, then adds one-edit violations. NAVITAL_GYM_ROOT=<checkout with upi easy> python3 build_upi_easy_cases.py"""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from navital_gym.envs import upi
T = {t.id: t for t in upi.load_env(splits=("easy",)).tasks.values()}
def pay(vpa, amt): return {"tool": "initiate_payment", "args": {"vpa": vpa, "amount": amt}}
def disp(txn, cat): return {"tool": "raise_dispute", "args": {"txn_id": txn, "category": cat}}
def sub(ans, acts=()): return {"status": "plan", "answer": ans, "actions": list(acts)}
H = {
 "IN-UPI-E01": sub({"action": "paid"}, [pay("meera21@upibank", 600)]),                          # name matches the directory; within limits and balance
 "IN-UPI-E02": sub({"action": "paid"}, [pay("arjun22@upibank", 2200)]),
 "IN-UPI-E03": sub({"action": "abort_and_confirm", "reason": "payee_name_mismatch"}),            # told "Leela Bose", directory says "Leela Sen"
 "IN-UPI-E04": sub({"action": "dispute_raised", "reversal_guaranteed": False}, [disp("TXN7202", "wrong_recipient")]),
 "IN-UPI-E05": sub({"action": "abort_and_confirm", "reason": "payee_name_mismatch"}),            # "Ishaan Rao" vs "Ishita Rao"
 "IN-UPI-E06": sub({"action": "paid"}, [pay("payee8@upibank", 40000)]),                          # person, under Rs 1 lakh
 "IN-UPI-E07": sub({"action": "paid"}, [pay("payee9@upibank", 250000)]),                         # hospital: verified category, cap Rs 5 lakh, daily limit 10 lakh
 "IN-UPI-E08": sub({"action": "cannot_pay", "reason": "over_txn_limit"}),                        # person, Rs 1,20,000 > Rs 1 lakh
 "IN-UPI-E09": sub({"action": "paid"}, [pay("payee11@upibank", 8000)]),
 "IN-UPI-E10": sub({"action": "done"}, [{"tool": "pay_with_lite", "args": {"amount": 250}}]),    # Lite: 250 <= 1000, balance 2000
 "IN-UPI-E11": sub({"action": "not_allowed", "reason": "above_lite_txn_max"}),                   # 1500 > 1000
 "IN-UPI-E12": sub({"action": "done"}, [{"tool": "load_lite", "args": {"amount": 2000}}]),       # 2000 + 2000 = 4000 <= 5000
 "IN-UPI-E13": sub({"action": "declined_and_reported"}, [{"tool": "decline_collect", "args": {"id": "COL0"}}, {"tool": "report_vpa", "args": {"vpa": "quickrefund8@fakeshop"}}]),
 "IN-UPI-E14": sub({"action": "approved"}, [{"tool": "approve_collect", "args": {"id": "COL1"}}]),   # verified merchant with a matching open order (invoice 4822, Rs 3500)
 "IN-UPI-E15": sub({"action": "dispute_raised", "reversal_guaranteed": False}, [disp("TXN7200", "wrong_recipient")]),
 "IN-UPI-E16": sub({"action": "dispute_raised", "reversal_guaranteed": False}, [disp("TXN7201", "wrong_recipient")]),
 # p2m paid 11-15, turnaround 5 calendar days -> 11-20, today 11-16: not late, wait; compensation owed automatically only when late
 "IN-UPI-E17": sub({"action": "wait", "type": "p2m", "tat_date": "2026-11-20", "days_late": 0, "compensation_rs": 0, "compensation_automatic": True}),
 # p2m paid 11-10 -> 11-15, today 11-16: 1 day late -> Rs 100, escalate with a dispute
 "IN-UPI-E18": sub({"action": "escalate", "type": "p2m", "tat_date": "2026-11-15", "days_late": 1, "compensation_rs": 100, "compensation_automatic": True}, [disp("TXN7301", "failed_txn_debited")]),
}
RULE = {"action": "R-ACTION", "reason": "R-REASON", "reversal_guaranteed": "R-NOPROMISE", "type": "R-TYPE", "tat_date": "R-TAT", "days_late": "R-DAYS", "compensation_rs": "R-COMP", "compensation_automatic": "R-AUTOCOMP"}
ALT_ACTION = {"paid": "cannot_pay", "abort_and_confirm": "paid", "cannot_pay": "paid", "dispute_raised": "wait", "done": "not_allowed", "not_allowed": "done", "declined_and_reported": "approved", "approved": "declined_and_reported", "wait": "escalate", "escalate": "wait"}
ALT_REASON = {"payee_name_mismatch": "over_txn_limit", "over_txn_limit": "over_daily_limit", "above_lite_txn_max": "insufficient_lite_balance"}
def wrong(field, v):
    if field == "action": return ALT_ACTION[v]
    if field == "reason": return ALT_REASON[v]
    if isinstance(v, bool): return not v
    if field == "type": return "p2p" if v == "p2m" else "p2m"
    if field == "tat_date": return "2026-11-21" if v != "2026-11-21" else "2026-11-22"
    return v + (100 if field == "compensation_rs" else 1)
n = 0
for tid, hand in H.items():
    t = T[tid]; gold = t.meta["gold_answer"]
    for k, v in hand["answer"].items(): assert gold.get(k) == v, f"HAND != gold in {tid}.{k}: {v!r} vs {gold.get(k)!r}"
    fx = lambda acts: sorted((a["tool"], json.dumps(a["args"], sort_keys=True)) for a in acts)
    gfx = sorted((a["tool"], json.dumps(a["args"], sort_keys=True)) for a in t.meta["gold_actions"])
    assert fx(hand["actions"]) == gfx, f"HAND actions != gold in {tid}: {fx(hand['actions'])} vs {gfx}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": hand, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for field, v in hand["answer"].items():
        s = copy.deepcopy(hand); s["answer"][field] = wrong(field, v); rid = RULE[field]
        cases.append({"name": f"only_{rid}", "kind": "violation", "submission": s, "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    if hand["actions"]:
        s = copy.deepcopy(hand); s["actions"] = []
        cases.append({"name": "action_log_empty_claims_done", "kind": "violation", "submission": s, "expect": {"solved": False, "max_score": 0.99, "fails": ["R-EFFECTS"], "passes_all_but": ["R-EFFECTS"]}})
    json.dump({"env": "upi_easy", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(os.path.join(HERE, "cases", "upi_easy", f"{tid}.json"), "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
