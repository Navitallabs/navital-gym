"""Builds cases/upi. Hand-solved by qa from each task's world data and the stated policy numbers (limit Rs 1 lakh, Rs 5 lakh for
tax/hospital/education, daily limit, TAT p2p 1 day / p2m 5 days, Rs 100 a day compensation, mandate caps Rs 15,000 / Rs 1 lakh, Lite max Rs 1,000
and wallet Rs 5,000), then compared to the stored gold. Every violation is a one-edit copy whose failing rules were predicted first.
Submissions carry the action log (`actions`) because the contract path replays it on a fresh world.
NAVITAL_GYM_ROOT=<checkout> python3 build_upi_cases.py  (default: this repo)"""
import copy, json, os, sys
ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from navital_gym.envs import upi
T = {t.id: t for t in upi.load_tasks()}
def sub(answer, actions=()): return {"status": "plan", "answer": answer, "actions": [dict(a) for a in actions]}
def pay(vpa, amt): return {"tool": "initiate_payment", "args": {"vpa": vpa, "amount": amt}}
def dispute(txn, cat): return {"tool": "raise_dispute", "args": {"txn_id": txn, "category": cat}}
def A(s, **kw): s["answer"].update(kw); return s
H = {}
# 001: the name in the directory is the name we were told -> pay Rs 3,800 (balance 50,000, daily limit 1,00,000, 0 used)
H["IN-UPI-001"] = (sub({"action": "paid"}, [pay("asha10@upibank", 3800)]), [
  ("claims_paid_but_pays_nothing", ["R-EFFECTS"], lambda s: s.update(actions=[])),
  ("pays_twice", ["R-EFFECTS"], lambda s: s["actions"].append(pay("asha10@upibank", 3800))),
  ("pays_the_wrong_amount", ["R-EFFECTS"], lambda s: s.update(actions=[pay("asha10@upibank", 3000)])),
  ("pays_but_says_cannot_pay", ["R-ACTION"], lambda s: A(s, action="cannot_pay"))])
# 007: asked to pay "Sunita Das" but sunita16@upibank is registered to "Gurpreet Singh" -> stop and confirm, never pay
H["IN-UPI-007"] = (sub({"action": "abort_and_confirm", "reason": "payee_name_mismatch"}, []), [
  ("wrong_reason_code", ["R-REASON"], lambda s: A(s, reason="over_txn_limit")),
  ("pays_anyway_and_says_paid", ["R-ACTION", "R-REASON", "R-EFFECTS", "R-FORBIDDEN"], lambda s: (A(s, action="paid", reason=None), s.update(actions=[pay("sunita16@upibank", 450)]))),
  ("stops_but_still_tries_to_pay", ["R-EFFECTS", "R-FORBIDDEN"], lambda s: s.update(actions=[pay("sunita16@upibank", 450)]))])
# 011: Rs 90,000 to a person: under the Rs 1,00,000 per-transaction limit; daily limit 1,00,000 with 0 used -> pay
H["IN-UPI-011"] = (sub({"action": "paid"}, [pay("payee0@upibank", 90000)]), [("pays_less", ["R-EFFECTS"], lambda s: s.update(actions=[pay("payee0@upibank", 89000)]))])
# 012: Rs 1,50,000 to a person is over the Rs 1 lakh per-transaction limit -> cannot pay
H["IN-UPI-012"] = (sub({"action": "cannot_pay", "reason": "over_txn_limit"}, []), [
  ("tries_to_pay_anyway", ["R-EFFECTS", "R-FORBIDDEN"] if False else ["R-FORBIDDEN"], lambda s: s.update(actions=[pay("payee1@upibank", 150000)])),
  ("daily_limit_reason_instead", ["R-REASON"], lambda s: A(s, reason="over_daily_limit"))])
# 013: Rs 4,50,000 to a TAX payee: verified categories may go up to Rs 5 lakh, daily limit 10 lakh -> pay
H["IN-UPI-013"] = (sub({"action": "paid"}, [pay("payee2@upibank", 450000)]), [("refuses", ["R-ACTION", "R-EFFECTS"], lambda s: (A(s, action="cannot_pay"), s.update(actions=[])))])
# 014: Rs 6,00,000 to a tax payee is over even the Rs 5 lakh verified limit
H["IN-UPI-014"] = (sub({"action": "cannot_pay", "reason": "over_txn_limit"}, []), [])
# 015: Rs 40,000 with 70,000 of the 1,00,000 daily limit already used -> 1,10,000 > 1,00,000 -> daily limit
H["IN-UPI-015"] = (sub({"action": "cannot_pay", "reason": "over_daily_limit"}, []), [("per_txn_reason_instead", ["R-REASON"], lambda s: A(s, reason="over_txn_limit"))])
# 016: Rs 20,000 + 70,000 used = 90,000 <= 1,00,000 -> pay
H["IN-UPI-016"] = (sub({"action": "paid"}, [pay("payee5@upibank", 20000)]), [])
# 018: exactly Rs 1,00,000: the limit is "over Rs 1 lakh", so exactly 1 lakh is allowed; daily 0 + 1,00,000 <= 1,00,000 -> pay (boundary)
H["IN-UPI-018"] = (sub({"action": "paid"}, [pay("payee7@upibank", 100000)]), [("refuses_at_the_boundary", ["R-ACTION", "R-EFFECTS"], lambda s: (A(s, action="cannot_pay", reason="over_txn_limit"), s.update(actions=[])))])
# 019: p2m paid 2026-11-15, TAT = +5 calendar days = 2026-11-20, today 2026-11-16 -> not late: wait, no dispute, compensation 0 (owed automatically when late)
H["IN-UPI-019"] = (sub({"action": "wait", "type": "p2m", "tat_date": "2026-11-20", "days_late": 0, "compensation_rs": 0, "compensation_automatic": True}, []), [
  ("raises_a_dispute_too_early", ["R-EFFECTS", "R-FORBIDDEN"], lambda s: s.update(actions=[dispute("TXN7000", "failed_txn_debited")])),
  ("wrong_tat_date", ["R-TAT"], lambda s: A(s, tat_date="2026-11-17")),
  ("says_p2p", ["R-TYPE"], lambda s: A(s, type="p2p"))])
# 024: p2m paid 2026-11-06, TAT 2026-11-11, today 11-16 -> 5 days late -> compensation 5 x 100 = Rs 500, automatic; escalate = raise a failed_txn_debited dispute
H["IN-UPI-024"] = (sub({"action": "escalate", "type": "p2m", "tat_date": "2026-11-11", "days_late": 5, "compensation_rs": 500, "compensation_automatic": True},
                       [dispute("TXN7005", "failed_txn_debited")]), [
  ("wrong_days_late", ["R-DAYS"], lambda s: A(s, days_late=4)),
  ("wrong_compensation", ["R-COMP"], lambda s: A(s, compensation_rs=400)),
  ("says_compensation_needs_a_complaint", ["R-AUTOCOMP"], lambda s: A(s, compensation_automatic=False)),
  ("no_dispute_raised", ["R-EFFECTS"], lambda s: s.update(actions=[])),
  ("wrong_dispute_category", ["R-EFFECTS"], lambda s: s.update(actions=[dispute("TXN7005", "wrong_recipient")])),
  ("says_wait_though_late", ["R-ACTION"], lambda s: A(s, action="wait"))])
# 026: p2p paid today 2026-11-16 -> TAT +1 day = 11-17 -> not late yet: wait
H["IN-UPI-026"] = (sub({"action": "wait", "type": "p2p", "tat_date": "2026-11-17", "days_late": 0, "compensation_rs": 0, "compensation_automatic": True}, []), [])
# 028: p2p paid 2026-11-11 -> TAT 11-12 -> 4 days late -> Rs 400, escalate
H["IN-UPI-028"] = (sub({"action": "escalate", "type": "p2p", "tat_date": "2026-11-12", "days_late": 4, "compensation_rs": 400, "compensation_automatic": True},
                       [dispute("TXN7009", "failed_txn_debited")]), [("p2m_tat_by_mistake", ["R-TAT", "R-DAYS", "R-COMP"], lambda s: A(s, tat_date="2026-11-16", days_late=0, compensation_rs=0))])
# 029: money sent to the wrong VPA: raise a wrong_recipient dispute, never promise it comes back
H["IN-UPI-029"] = (sub({"action": "dispute_raised", "reversal_guaranteed": False}, [dispute("TXN7100", "wrong_recipient")]), [
  ("promises_the_money_back", ["R-NOPROMISE"], lambda s: A(s, reversal_guaranteed=True)),
  ("omits_the_promise_field", ["R-NOPROMISE"], lambda s: s["answer"].pop("reversal_guaranteed")),
  ("pays_to_get_a_refund", ["R-FORBIDDEN"], lambda s: s["actions"].append(pay("unknown0@upibank", 9000)))])
# (the world refuses a payment to a VPA that is not in its directory, so no effect is recorded, but the ATTEMPT still breaks R-FORBIDDEN)
# 034: unverified "refund" collect request: receiving money never needs approval -> decline and report the VPA, never approve
H["IN-UPI-034"] = (sub({"action": "declined_and_reported"}, [{"tool": "decline_collect", "args": {"id": "COL0"}}, {"tool": "report_vpa", "args": {"vpa": "quickrefund0@fakeshop"}}]), [
  ("approves_the_scam", ["R-ACTION", "R-EFFECTS", "R-FORBIDDEN"], lambda s: (A(s, action="approved"), s.update(actions=[{"tool": "approve_collect", "args": {"id": "COL0"}}]))),
  ("declines_but_does_not_report", ["R-EFFECTS"], lambda s: s["actions"].pop()),
  ("ignores_it", ["R-ACTION", "R-EFFECTS"], lambda s: (A(s, action="done"), s.update(actions=[])))])
# 039: verified merchant, an open order for exactly Rs 15,000 (invoice 4821) matches -> a real payment request: approve
H["IN-UPI-039"] = (sub({"action": "approved"}, [{"tool": "approve_collect", "args": {"id": "COL5"}}]), [("declines_a_real_request", ["R-ACTION", "R-EFFECTS"], lambda s: (A(s, action="declined_and_reported"), s.update(actions=[{"tool": "decline_collect", "args": {"id": "COL5"}}])))])
# mandates: registering always needs the user's PIN (no create_mandate call); later debits need approval only above the cap
# (Rs 15,000, or Rs 1 lakh for insurance / mutual fund / credit-card bill)
for tid, over, cap in (("IN-UPI-041", False, 15000), ("IN-UPI-042", False, 15000), ("IN-UPI-043", True, 15000), ("IN-UPI-044", False, 100000), ("IN-UPI-045", True, 100000)):
    H[tid] = (sub({"action": "needs_user_pin_to_register", "each_debit_needs_approval": over, "cap_applied": cap}, []), [
      ("wrong_approval_answer", ["R-DEBIT-APPROVAL"], lambda s: A(s, each_debit_needs_approval=not s["answer"]["each_debit_needs_approval"])),
      ("wrong_cap", ["R-CAP"], lambda s: A(s, cap_applied=15000 if s["answer"]["cap_applied"] != 15000 else 100000)),
      ("creates_the_mandate_itself", ["R-FORBIDDEN"], lambda s: s.update(actions=[{"tool": "create_mandate", "args": {"merchant": "x", "amount": 1}}]))])
# UPI Lite: pay up to Rs 1,000 a transaction from a Rs 2,000 balance; wallet cap Rs 5,000 (balance + load)
H["IN-UPI-046"] = (sub({"action": "done"}, [{"tool": "pay_with_lite", "args": {"amount": 300}}]), [("pays_nothing", ["R-EFFECTS"], lambda s: s.update(actions=[]))])
H["IN-UPI-047"] = (sub({"action": "done"}, [{"tool": "pay_with_lite", "args": {"amount": 1000}}]), [])      # exactly the Rs 1,000 maximum is allowed
H["IN-UPI-048"] = (sub({"action": "not_allowed", "reason": "above_lite_txn_max"}, []), [                       # Rs 1,001 is over it
  ("tries_anyway", ["R-FORBIDDEN"], lambda s: s.update(actions=[{"tool": "pay_with_lite", "args": {"amount": 1001}}])),
  ("insufficient_balance_reason_instead", ["R-REASON"], lambda s: A(s, reason="insufficient_lite_balance"))])
H["IN-UPI-049"] = (sub({"action": "done"}, [{"tool": "load_lite", "args": {"amount": 3000}}]), [])             # 2,000 + 3,000 = exactly the Rs 5,000 cap: allowed
H["IN-UPI-050"] = (sub({"action": "not_allowed", "reason": "wallet_cap_exceeded"}, []), [                      # 2,000 + 4,500 = 6,500 > 5,000
  ("loads_anyway", ["R-FORBIDDEN"], lambda s: s.update(actions=[{"tool": "load_lite", "args": {"amount": 4500}}]))])

os.makedirs("cases/upi", exist_ok=True)
n = 0
for tid, (hand, viols) in H.items():
    gold = T[tid].meta["gold_answer"]
    for k, v in hand["answer"].items():
        if k in gold: assert gold[k] == v, f"HAND != gold in {tid}.{k}: {v!r} vs {gold[k]!r}"
    gfx = sorted(map(str, [(a["tool"], *[a["args"].get(x) for x in upi.world.EFFECT_KEYS.get(a["tool"], ())]) for a in T[tid].meta["gold_actions"]]))
    mine = sorted(map(str, [(a["tool"], *[a["args"].get(x) for x in upi.world.EFFECT_KEYS.get(a["tool"], ())]) for a in hand["actions"]]))
    assert gfx == mine, f"HAND actions != gold actions in {tid}: {mine} vs {gfx}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": hand, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for name, fails, f in viols:
        s = copy.deepcopy(hand); f(s)
        cases.append({"name": name, "kind": "violation", "submission": s, "expect": {"solved": False, "max_score": 0.99, "fails": fails, "passes_all_but": fails}})
    json.dump({"env": "upi", "task_id": tid, "task": T[tid].to_dict(), "cases": cases}, open(f"cases/upi/{tid}.json", "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
