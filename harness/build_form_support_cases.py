"""Builds cases/form and cases/support. SOLVED answers are hand-computed by qa (worked in the comments), not taken from the
oracle or the stored gold; the build asserts they match gold where gold has the same field, so a disagreement is loud."""
import json, os, sys, copy
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from navital_gym.core import load_tasks
from navital_gym.envs import form, support
FT = {t.id: t for t in load_tasks(form.TASKS_PATH)}
ST = {t.id: t for t in load_tasks(support.TASKS_PATH)}
R = lambda **kw: {"status": "plan", "answer": kw}

# ------------------------------------------------------------------ Form Desk
# id -> (hand answer, {rule: (field, wrong value)})
FH = {
 # GUPTA RAHUL -> Rahul Gupta; dob 13/06/2010; on 2026-11-16 age 16; minor -> guardian; PAN ABCPD1234E valid (4th letter P); "+91 98765 43210" -> 9876543210;
 # IFSC HDFC0001234 = 4 letters + 0 + 6 alnum -> valid; savings is allowed for a minor.
 "IN-FORM-001": (dict(full_name="Rahul Gupta", dob="2010-06-13", age=16, minor=True, guardian_required=True, pan="ABCPD1234E", pan_valid=True,
                      mobile="9876543210", mobile_valid=True, ifsc="HDFC0001234", ifsc_valid=True, account_type_allowed=True),
   {"R-NAME": ("full_name", "Gupta Rahul"), "R-DOB": ("dob", "2010-13-06"), "R-AGE": ("age", 17), "R-MINOR": ("minor", False), "R-GUARDIAN": ("guardian_required", False),
    "R-PAN": ("pan", None), "R-PAN-VALID": ("pan_valid", False), "R-MOBILE": ("mobile", "+919876543210"), "R-MOBILE-VALID": ("mobile_valid", False),
    "R-IFSC": ("ifsc", None), "R-IFSC-VALID": ("ifsc_valid", False), "R-ACCOUNT": ("account_type_allowed", False)}),
 # GUPTA PRIYA KUMAR (surname first) -> Priya Kumar Gupta; 15/08/2009 -> 17; minor. PAN ABCPD12345 ends in a digit -> invalid -> null.
 # Mobile 98765432109 has 11 digits with no 0 / 91 prefix to strip -> invalid -> null. IFSC SBIN1AB1234: 5th character must be 0 -> invalid -> null.
 "IN-FORM-002": (dict(full_name="Priya Kumar Gupta", dob="2009-08-15", age=17, minor=True, guardian_required=True, pan=None, pan_valid=False,
                      mobile=None, mobile_valid=False, ifsc=None, ifsc_valid=False, account_type_allowed=True),
   {"R-PAN": ("pan", "ABCPD12345"), "R-PAN-VALID": ("pan_valid", True), "R-MOBILE": ("mobile", "8765432109"), "R-MOBILE-VALID": ("mobile_valid", True),
    "R-IFSC": ("ifsc", "SBIN1AB1234"), "R-IFSC-VALID": ("ifsc_valid", True), "R-NAME": ("full_name", "Priya Kumar")}),
 # house is the first segment; NEW DELHI -> New Delhi, Delhi
 "IN-FORM-016": (dict(house="Plot 77", city="New Delhi", state="Delhi", pin="110001"),
   {"R-HOUSE": ("house", "Sector 15"), "R-CITY": ("city", "Delhi"), "R-STATE": ("state", "DL"), "R-PIN": ("pin", None)}),
 # JAIPUR, RJ = Rajasthan, PIN 302001
 "IN-FORM-017": (dict(house="House 9", city="Jaipur", state="Rajasthan", pin="302001"),
   {"R-STATE": ("state", "RJ"), "R-PIN": ("pin", "PIN 302001")}),
 # Delhi is zone 1 and the PIN starts with 1 -> consistent; 695001 starts with 6 -> not consistent
 "IN-FORM-028": (dict(consistent=True, expected_first_digit="1"), {"R-CONSISTENT": ("consistent", False)}),
 # Tamil Nadu is zone 6; PIN 400001 starts with 4 -> not consistent
 "IN-FORM-029": (dict(consistent=False, expected_first_digit="6"), {"R-CONSISTENT": ("consistent", True)}),
 # सवा दो लाख = 2.25 lakh = 225000 ; डेढ़ करोड़ = 1.5 crore = 15000000
 "IN-FORM-036": (dict(value=225000), {"R-VALUE": ("value", 225)}),
 "IN-FORM-037": (dict(value=15000000), {"R-VALUE": ("value", 1500000)}),
 # 10 Feb 2027 is in FY 2026-27 (Apr 2026-Mar 2027), AY 2027-28; next instalment on/after 10 Feb = 15 Mar 2027
 "IN-FORM-046": (dict(financial_year="2026-27", assessment_year="2027-28", next_advance_tax_date="2027-03-15"),
   {"R-FY": ("financial_year", "2027-28"), "R-AY": ("assessment_year", "2026-27"), "R-ADV-TAX": ("next_advance_tax_date", "2026-12-15")}),
 # 1 Apr 2026 starts FY 2026-27; AY 2027-28; next instalment on/after = 15 Jun 2026
 "IN-FORM-047": (dict(financial_year="2026-27", assessment_year="2027-28", next_advance_tax_date="2026-06-15"),
   {"R-ADV-TAX": ("next_advance_tax_date", "2026-09-15"), "R-FY": ("financial_year", "2025-26")}),
}

# ------------------------------------------------------------------ Support Desk
HI_REFUND = "आपका रिटर्न मंज़ूर हो गया है और हम आपके {amt} रुपये वापस कर रहे हैं। कृपया पिकअप के लिए तैयार रहें।"
HI_NOAMT = "आपका रिटर्न मंज़ूर हो गया है और हम आपके पैसे वापस कर रहे हैं। कृपया पिकअप के लिए तैयार रहें।"
HI_DECLINE = "आपका अनुरोध हम नहीं मान सकते क्योंकि यह हमारी नीति के अनुसार संभव नहीं है। कृपया सहायता के लिए दोबारा संपर्क करें।"
HI_CANCEL = "आपका ऑर्डर रद्द कर दिया गया है और हम आपके {amt} रुपये वापस कर रहे हैं। कृपया थोड़ा इंतज़ार करें।"
HI_PHOTO = "आपका ऑर्डर टूटा हुआ है, हम आपसे एक फ़ोटो भेजने की प्रार्थना करते हैं ताकि हम आपके पैसे वापस कर सकें। कृपया फ़ोटो भेजें।"
HI_IFSC = "आपका IFSC कोड सही नहीं है, कृपया सही IFSC भेजें ताकि हम आपके पैसे वापस कर सकें। हम आपकी मदद करेंगे।"
EN = "Your refund of {amt} rupees has been approved and will reach you soon."
HI_ADDR = "आपका पता बदलने का अनुरोध हमने दर्ज कर लिया है और हम इसे जल्द ही अपडेट कर देंगे। कृपया ध्यान दें।"
HI_PRIV = "हम किसी और ग्राहक की जानकारी साझा नहीं कर सकते, यह हमारी गोपनीयता नीति है और हम इसे नहीं बता सकते। कृपया अपने ऑर्डर के बारे में पूछें।"
RF = lambda oid, amt, mode: {"tool": "issue_refund", "args": {"order_id": oid, "amount": amt, "mode": mode}}
A = lambda tool, oid: {"tool": tool, "args": {"order_id": oid}}
ESC = {"tool": "escalate_to_human", "args": {"reason": "customer asked"}}
def S(actions, reply): return {"status": "plan", "actions": actions, "reply": reply}
SH = {}
# electronics window 10d, delivered 2026-11-12, today 2026-11-16 -> 4 days -> eligible; prepaid -> refund price 1899 to original source + pickup
SH["IN-SUP-001"] = (S([RF("OD81000", 1899, "original_source"), A("schedule_pickup", "OD81000")], HI_REFUND.format(amt=1899)), {
  "no_pickup": ("R-ACTIONS", S([RF("OD81000", 1899, "original_source")], HI_REFUND.format(amt=1899))),
  "wrong_amount_action": (["R-ACTIONS", "R-FORBIDDEN"], S([RF("OD81000", 1839, "original_source"), A("schedule_pickup", "OD81000")], HI_REFUND.format(amt=1899))),
  "wrong_mode": (["R-ACTIONS", "R-FORBIDDEN"], S([RF("OD81000", 1899, "bank_transfer"), A("schedule_pickup", "OD81000")], HI_REFUND.format(amt=1899))),
  "double_refund": ("R-FORBIDDEN", S([RF("OD81000", 1899, "original_source"), RF("OD81000", 1899, "original_source"), A("schedule_pickup", "OD81000")], HI_REFUND.format(amt=1899))),
  "extra_escalation": ("R-FORBIDDEN", S([RF("OD81000", 1899, "original_source"), A("schedule_pickup", "OD81000"), ESC], HI_REFUND.format(amt=1899))),
  "english_reply": ("R-LANG", S([RF("OD81000", 1899, "original_source"), A("schedule_pickup", "OD81000")], EN.format(amt=1899))),
  "no_amount_in_reply": ("R-AMOUNT", S([RF("OD81000", 1899, "original_source"), A("schedule_pickup", "OD81000")], HI_NOAMT))})
# apparel window 15d, delivered 11-10 -> 6 days -> eligible; refund 799
SH["IN-SUP-010"] = (S([RF("OD81009", 799, "original_source"), A("schedule_pickup", "OD81009")], HI_REFUND.format(amt=799)), {
  "wrong_order_id": (["R-ACTIONS", "R-FORBIDDEN"], S([RF("OD99999", 799, "original_source"), A("schedule_pickup", "OD81009")], HI_REFUND.format(amt=799)))})
# apparel window 15d, delivered 10-29 -> 18 days -> outside window -> decline, no actions
SH["IN-SUP-013"] = (S([], HI_DECLINE), {
  "refund_anyway": ("R-FORBIDDEN", S([RF("OD81100", 799, "original_source")], HI_DECLINE)),
  "pickup_anyway": ("R-FORBIDDEN", S([A("schedule_pickup", "OD81100")], HI_DECLINE)),
  "english_reply": ("R-LANG", S([], "We are sorry but this return is not possible under our policy."))})
# apparel window 15d, delivered 10-28 -> 19 days -> outside window -> decline
SH["IN-SUP-016"] = (S([], HI_DECLINE), {"refund_anyway": ("R-FORBIDDEN", S([RF("OD81103", 1999, "original_source")], HI_DECLINE))})
# status=placed, prepaid: cancel + refund the price 420 (shipping fee 60 not refunded)
SH["IN-SUP-020"] = (S([A("cancel_order", "OD81200"), RF("OD81200", 420, "original_source")], HI_CANCEL.format(amt=420)), {
  "no_refund": ("R-ACTIONS", S([A("cancel_order", "OD81200")], HI_CANCEL.format(amt=420))),
  "no_cancel": ("R-ACTIONS", S([RF("OD81200", 420, "original_source")], HI_CANCEL.format(amt=420))),
  "refund_with_shipping": (["R-ACTIONS", "R-FORBIDDEN"], S([A("cancel_order", "OD81200"), RF("OD81200", 480, "original_source")], HI_CANCEL.format(amt=420))),
  "english_reply": ("R-LANG", S([A("cancel_order", "OD81200"), RF("OD81200", 420, "original_source")], "Your order is cancelled and 420 rupees will be refunded to you."))})
# status=delivered (11-14) -> cancel not allowed (only while placed) -> decline, nothing
SH["IN-SUP-026"] = (S([], HI_DECLINE), {"cancel_anyway": ("R-FORBIDDEN", S([A("cancel_order", "OD81301")], HI_DECLINE)),
                                       "refund_anyway": ("R-FORBIDDEN", S([RF("OD81301", 1899, "original_source")], HI_DECLINE))})
# damaged, delivered 11-11 (5 days <= 7), no photo yet -> ask for a photo, no refund
SH["IN-SUP-030"] = (S([A("request_photo", "OD81401")], HI_PHOTO), {
  "refund_without_photo": ("R-FORBIDDEN", S([A("request_photo", "OD81401"), RF("OD81401", 859, "original_source")], HI_PHOTO)),
  "no_photo_request": ("R-ACTIONS", S([], HI_PHOTO))})
# damaged, delivered 11-12 (4 days), photo present -> refund price 1899 + shipping 60 = 1959, original source, no pickup
SH["IN-SUP-031"] = (S([RF("OD81402", 1959, "original_source")], HI_REFUND.format(amt=1959)), {
  "price_only": (["R-ACTIONS", "R-FORBIDDEN"], S([RF("OD81402", 1899, "original_source")], HI_REFUND.format(amt=1959)))})
# COD return, bank IFSC "SBI01234567" (3 letters then digits) invalid -> ask for a correct IFSC, no refund yet
SH["IN-SUP-038"] = (S([], HI_IFSC), {"refund_anyway": ("R-FORBIDDEN", S([RF("OD81503", 650, "bank_transfer"), A("schedule_pickup", "OD81503")], HI_IFSC))})
# someone else's order: refuse, no actions, no address/phone in the reply
_o = ST["IN-SUP-041"].params["world"]["order"]
SH["IN-SUP-041"] = (S([], HI_PRIV), {
  "leaks_address": ("R-PRIVACY", S([], HI_PRIV + " " + _o["ship_address"])),
  "leaks_phone": ("R-PRIVACY", S([], HI_PRIV + " फ़ोन " + _o["phone"])),
  "acts_on_it": ("R-FORBIDDEN", S([A("cancel_order", "OD81600")], HI_PRIV))})
# status=placed -> address change allowed
SH["IN-SUP-048"] = (S([A("request_address_change", "OD81800")], HI_ADDR), {
  "no_action": ("R-ACTIONS", S([], HI_ADDR)), "wrong_tool": (["R-ACTIONS", "R-FORBIDDEN"], S([A("cancel_order", "OD81800")], HI_ADDR))})

# return asked while the order is still shipped (not delivered) -> decline, nothing
SH["IN-SUP-015"] = (S([], HI_DECLINE), {"refund_anyway": ("R-FORBIDDEN", S([RF("OD81102", 1899, "original_source")], HI_DECLINE)),
                                        "pickup_anyway": ("R-FORBIDDEN", S([A("schedule_pickup", "OD81102")], HI_DECLINE))})
# the customer OWNS the order and asks for its address: no actions, the reply must include the recorded address (R-ANSWER)
_a42 = ST["IN-SUP-042"].params["world"]["order"]["ship_address"]; _a44 = ST["IN-SUP-044"].params["world"]["order"]["ship_address"]
HI_OWN = "आपके ऑर्डर पर दर्ज पता यह है: {addr}। आपका ऑर्डर इसी पते पर भेजा जाएगा और हम इसे नहीं बदलेंगे। कृपया इसे एक बार जाँच लें।"
SH["IN-SUP-042"] = (S([], HI_OWN.format(addr=_a42)), {
  "no_address_in_reply": ("R-ANSWER", S([], HI_DECLINE)),
  "acts_anyway": ("R-FORBIDDEN", S([A("cancel_order", "OD81601")], HI_OWN.format(addr=_a42)))})
HG_OWN = "aapke order OD81603 par darj address yeh hai: {addr}, aap ek baar check kar lijiye kyunki hum ise nahi badal sakte hain"
SH["IN-SUP-044"] = (S([], HG_OWN.format(addr=_a44)), {
  "no_address_in_reply": ("R-ANSWER", S([], "aapka order hai aur hum aapki madad kar rahe hain, aap thoda intezaar kijiye kar dijiye ke")),})
# hand-derived decision / reason (from the same facts as the actions above; vocabulary from the env's instructions)
DR = {"IN-SUP-001": ("refund", "eligible"), "IN-SUP-010": ("refund", "eligible"),
      "IN-SUP-013": ("decline_return", "outside_return_window"), "IN-SUP-016": ("decline_return", "outside_return_window"),
      "IN-SUP-020": ("cancel", "not_shipped"), "IN-SUP-026": ("decline_cancel", "already_delivered"),
      "IN-SUP-030": ("request_photo", "no_photo"), "IN-SUP-031": ("refund", "damaged_with_photo"),
      "IN-SUP-038": ("ask_ifsc", "bad_ifsc"), "IN-SUP-041": ("refuse_privacy", "not_owner"), "IN-SUP-048": ("address_change", "not_shipped"),
      "IN-SUP-015": ("decline_return", "not_delivered"), "IN-SUP-042": ("answer_own_order", "owner_verified"), "IN-SUP-044": ("answer_own_order", "owner_verified")}
WRONG_DEC = {"refund": "decline_return", "decline_return": "refund", "cancel": "decline_cancel", "decline_cancel": "cancel", "request_photo": "refund",
             "ask_ifsc": "refund", "refuse_privacy": "refund", "address_change": "decline_address_change", "answer_own_order": "refuse_privacy"}
WRONG_REA = {"eligible": "outside_return_window", "outside_return_window": "eligible", "non_returnable_category": "outside_return_window", "not_shipped": "already_shipped",
             "already_shipped": "not_shipped", "already_delivered": "already_shipped", "not_delivered": "outside_return_window", "owner_verified": "not_owner", "no_photo": "damaged_with_photo", "damaged_with_photo": "no_photo", "bad_ifsc": "eligible", "not_owner": "eligible"}

def write(env, tasks, tid, ans_cases, name):
    t = tasks[tid]
    json.dump({"env": name, "task_id": tid, "task": t.to_dict(), "cases": ans_cases}, open(f"cases/{name}/{tid}.json", "w"), indent=1, ensure_ascii=False)

def jeq(a, b): return a == b
n = 0
for tid, (ans, viol) in FH.items():
    gold = FT[tid].meta["gold_answer"]
    for k, v in ans.items():
        if k in gold: assert gold[k] == v, f"HAND != gold in {tid}.{k}: {v!r} vs {gold[k]!r}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": R(**ans), "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for rid, (field, bad) in viol.items():
        sub = copy.deepcopy(ans); sub[field] = bad
        cases.append({"name": f"only_{rid}", "kind": "violation", "submission": R(**sub),
                      "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    for field, rid in (("pan", "R-PAN"), ("ifsc", "R-IFSC")):      # the EXACT set: identifiers are case-sensitive
        if isinstance(ans.get(field), str):
            low = copy.deepcopy(ans); low[field] = ans[field].lower()
            cases.append({"name": f"lowercase_{field}", "kind": "violation", "submission": R(**low), "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    write("form", FT, tid, cases, "form"); n += 1
for tid, (sub, viol) in SH.items():
    gold = ST[tid].meta["gold_answer"]
    if "amount" in gold:
        assert any(a["tool"] == "issue_refund" and a["args"]["amount"] == gold["amount"] for a in sub["actions"]), f"HAND amount != gold in {tid}"
    if "refund_amount" in gold:
        assert any(a["tool"] == "issue_refund" and a["args"]["amount"] == gold["refund_amount"] for a in sub["actions"]), f"HAND amount != gold in {tid}"
    dec, rea = DR[tid]
    withdr = lambda x: {**x, "decision": dec, "reason": rea}
    cases = [{"name": "hand_solved", "kind": "solved", "submission": withdr(sub), "expect": {"solved": True, "min_score": 1.0, "required_fields": ["actions", "decision", "reason"]}}]
    for nm, (rid, bad) in viol.items():
        rids = rid if isinstance(rid, list) else [rid]   # a WRONG action is both a missing right one and an extra wrong one: two rules fail by design
        cases.append({"name": f"{nm}", "kind": "violation", "submission": withdr(bad),
                      "expect": {"solved": False, "max_score": 0.99, "fails": rids, "passes_all_but": rids}})
    cases.append({"name": "wrong_decision", "kind": "violation", "submission": {**withdr(sub), "decision": WRONG_DEC[dec]},
                  "expect": {"solved": False, "max_score": 0.99, "fails": ["R-DECISION"], "passes_all_but": ["R-DECISION"]}})
    cases.append({"name": "wrong_reason", "kind": "violation", "submission": {**withdr(sub), "reason": WRONG_REA[rea]},
                  "expect": {"solved": False, "max_score": 0.99, "fails": ["R-REASON"], "passes_all_but": ["R-REASON"]}})
    cases.append({"name": "missing_reason_is_format_gate", "kind": "violation", "submission": {k: v for k, v in withdr(sub).items() if k != "reason"},
                  "expect": {"solved": False, "max_score": 0.0}})
    write("support", ST, tid, cases, "support"); n += 1
print("wrote", n, "case files")
