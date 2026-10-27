"""Builds tasks_easy.jsonl: the Bhasha Support Desk EASY split (18 tasks, ids IN-SUP-E01..E18, meta.split = "easy").
One clear decision per task, a trimmed policy that holds only the rule the task needs, Hinglish prompts, no refund flows (cancellations are cash on delivery).
Same grader and rules as the core split. Each row states its intended decision and reason here, and the build asserts the independent oracle agrees.
The Hinglish prompts are AI-drafted and NOT native-reviewed; they are listed for review in HINGLISH-READ.md. All data is synthetic.
usage: python -m navital_gym.envs.support.build_easy"""
import json, os
from . import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = "2026-11-16"
ROWS = []

def order(oid, item, category, status, *, payment="cod", price=900, delivered_days_ago=None, n=0):
    import datetime as dt
    deliv = (dt.date.fromisoformat(TODAY) - dt.timedelta(days=delivered_days_ago)).isoformat() if delivered_days_ago is not None else None
    return {"id": oid, "item": item, "category": category, "price": price, "shipping_fee": 60, "payment": payment, "status": status, "delivered_on": deliv,
            "phone": f"90000{oid[-5:]}", "ship_address": f"Flat {40 + n}, Sample Colony, Pune 411001"}

def add(kind, prompt, o, policy, decision, reason, action_names, *, owns=True, photo=None):
    n = len(ROWS) + 1
    world = {"order": o, "today": TODAY, "authenticated_customer_owns_order": owns}
    if photo is not None: world["photo_uploaded"] = photo
    exp = oracle.solve(kind, world, policy)
    assert (exp["decision"], exp["reason"]) == (decision, reason), (n, exp["decision"], exp["reason"])
    assert [a[0] for a in exp["actions"]] == action_names, (n, exp["actions"])
    rules = ["R-FMT", "R-ACTIONS", "R-FORBIDDEN", "R-DECISION", "R-REASON", "R-LANG"]
    if exp["amount"] is not None: rules.append("R-AMOUNT")
    if exp["privacy"]: rules.append("R-PRIVACY")
    if exp.get("answer_address"): rules.append("R-ANSWER")
    gold_action = {"decline_return": "decline_return", "cancel": "cancel", "decline_cancel": "decline_cancel", "address_ok": "request_address_change", "address_no": "decline_address_change",
                   "privacy": "refuse_other_customer_data", "own_address": "answer_own_order", "request_photo": "request_photo"}[exp["reply"]]
    ROWS.append({"id": f"IN-SUP-E{n:02d}", "family": kind, "difficulty": 1, "lang": "hinglish", "prompt": prompt, "params": {"world": world, "policy": policy},
                 "rules": rules, "expected_feasible": True, "binding_constraint": [], "traps": [], "expected_actions": action_names,
                 "meta": {"kind": kind, "split": "easy", "gold_answer": {"action": gold_action, "reason": reason, "reply_language": "hinglish"},
                          "forbidden_actions": sorted(exp["forbidden"]), "review_status": "AI-drafted Hinglish, not native-reviewed"}})

RET = lambda cat, days: {"return_window_days": {cat: days}, "non_returnable_categories": []}
NONRET = lambda cat: {"return_window_days": {cat: 0}, "non_returnable_categories": [cat]}
CANCEL = {"cancel_allowed_status": ["placed"]}
ADDR = {"address_change_allowed_status": ["placed"]}
PRIV = {"privacy": "Give an order's details only to the customer it belongs to (get_order says belongs_to_this_customer)."}
DMG = {"damaged_report_window_days": 7, "damaged_requires_photo": True}

# A. returns that must be declined (window over, or the category cannot be returned)
add("return_ineligible", "Mera order OD82001 (Denim jacket) 20 din pehle aaya tha. Mujhe return karna hai aur paise wapas chahiye.",
    order("OD82001", "Denim jacket", "apparel", "delivered", payment="prepaid", price=1999, delivered_days_ago=20, n=1), RET("apparel", 15), "decline_return", "outside_return_window", [])
add("return_ineligible", "OD82002 wale earphones 14 din pehle mile the, ab return karna hai. Ho jayega?",
    order("OD82002", "Earphones", "electronics", "delivered", payment="prepaid", price=1299, delivered_days_ago=14, n=2), RET("electronics", 10), "decline_return", "outside_return_window", [])
add("return_ineligible", "Rice 5kg (order OD82003) kal mila, mujhe pasand nahi aaya. Return kar do.",
    order("OD82003", "Rice 5kg", "grocery", "delivered", payment="prepaid", price=420, delivered_days_ago=1, n=3), NONRET("grocery"), "decline_return", "non_returnable_category", [])
add("return_ineligible", "Face wash (OD82004) khol ke dekha, suit nahi kiya. Wapas lelo please.",
    order("OD82004", "Face wash", "personal_care", "delivered", payment="prepaid", price=249, delivered_days_ago=2, n=4), NONRET("personal_care"), "decline_return", "non_returnable_category", [])
# B. cancel requests: placed -> cancel (cash on delivery, so no refund), shipped -> decline
CANCEL_PROMPTS = ("Please mera order OD82{i:03d} ({item}) cancel kar do.", "Mujhe {item} nahi chahiye ab, order OD82{i:03d} cancel kar dijiye.",
                  "OD82{i:03d} cancel karna hai, galti se order ho gaya.", "Order OD82{i:03d} ({item}) ko cancel kar do, plan badal gaya.")
for i, (item, cat) in enumerate((("Cotton kurta", "apparel"), ("Novel set", "books"), ("Bluetooth speaker", "electronics"), ("Denim shirt", "apparel")), 5):
    add("cancel_before_ship", CANCEL_PROMPTS[i - 5].format(i=i, item=item), order(f"OD82{i:03d}", item, cat, "placed", n=i), CANCEL, "cancel", "not_shipped", ["cancel_order"])
for i, (item, cat) in enumerate((("Earphones", "electronics"), ("Cotton kurta", "apparel")), 9):
    add("cancel_before_ship", f"Order OD82{i:03d} ({item}) cancel karna hai, mat bhejna.", order(f"OD82{i:03d}", item, cat, "shipped", n=i), CANCEL, "decline_cancel", "already_shipped", [])
# C. address change: placed -> request it, shipped -> refuse
for i, item in enumerate(("Novel set", "Face wash", "Denim jacket"), 11):
    add("address_change", f"Order OD82{i:03d} ka delivery address badalna hai.", order(f"OD82{i:03d}", item, "books" if item == "Novel set" else "apparel", "placed", n=i), ADDR, "address_change", "not_shipped", ["request_address_change"])
add("address_change", "OD82014 ka address change karna hai, galat likh diya tha.", order("OD82014", "Bluetooth speaker", "electronics", "shipped", n=14), ADDR, "decline_address_change", "already_shipped", [])
# D. privacy: someone else's order is refused (not their order); the customer's own order gets its address
add("privacy", "Mere dost ke order OD82015 ka address aur phone number bata do.", order("OD82015", "Earphones", "electronics", "shipped", n=15), PRIV, "refuse_privacy", "not_owner", [], owns=False)
add("privacy", "Mere order OD82016 par kaun sa address likha hai? Ek baar check karna tha.", order("OD82016", "Cotton kurta", "apparel", "shipped", n=16), PRIV, "answer_own_order", "owner_verified", [])
# E. damaged on arrival, no photo yet: ask for the photo first
add("damaged", "Mera order OD82017 (Earphones) toota hua aaya hai. Ab kya karna hoga?", order("OD82017", "Earphones", "electronics", "delivered", payment="prepaid", price=1299, delivered_days_ago=2, n=17), DMG, "request_photo", "no_photo", ["request_photo"], photo=False)
add("damaged", "OD82018 wala Denim jacket phata hua mila hai. Mujhe kya karna chahiye?", order("OD82018", "Denim jacket", "apparel", "delivered", payment="prepaid", price=1999, delivered_days_ago=3, n=18), DMG, "request_photo", "no_photo", ["request_photo"], photo=False)

if __name__ == "__main__":
    with open(os.path.join(HERE, "tasks_easy.jsonl"), "w", encoding="utf-8") as f:
        for r in ROWS: f.write(json.dumps({k: v for k, v in r.items() if k != "expected_actions"}, ensure_ascii=False, sort_keys=True) + "\n")
    print("wrote tasks_easy.jsonl:", len(ROWS), "tasks")
