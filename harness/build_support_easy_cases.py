"""cases/support_easy: hand-solved submissions for the 18 Support easy tasks (decision, reason and actions worked out from each prompt and its trimmed policy by qa;
the build asserts they equal the stored gold), plus single-rule violations. Replies are in Hinglish (the grader's language rule)."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from navital_gym.envs import support
T = {t.id: t for t in support.load_env(splits=("easy",)).tasks.values()}
R = {
 "decline_return": "Aapka return hum nahi le sakte kyunki yeh hamari policy ke hisab se allowed nahi hai. Aapko pareshani hui, iske liye maafi.",
 "cancel": "Aapka order cancel kar diya gaya hai. Yeh cash on delivery order tha, isliye koi refund nahi hai.",
 "decline_cancel": "Aapka order ship ho chuka hai, isliye hum ab cancel nahi kar sakte. Delivery ke baad aap return ke liye bata sakte hain.",
 "address_ok": "Aapka address badalne ka request hum ne darj kar liya hai. Aap thoda intezaar kijiye.",
 "address_no": "Aapka order ship ho chuka hai, isliye hum address nahi badal sakte hain.",
 "privacy": "Yeh order aapka nahi hai, isliye hum iski jaankari aapko nahi de sakte hain.",
 "own": "Aapke order par yeh address hai: {addr}. Aap ek baar check kar lijiye.",
 "photo": "Aapka order toota hua hai, kripya ek photo bhejiye taaki hum aapki madad kar sakein. Photo milte hi aage ka kaam hoga.",
}
EN = "Your request has been handled as per our policy."
def act(tool, oid): return {"tool": tool, "args": {"order_id": oid}}
# id -> (decision, reason, action tools, reply key)
HAND = {
 "IN-SUP-E01": ("decline_return", "outside_return_window", [], "decline_return"),     # apparel window 15 days, delivered 20 days ago
 "IN-SUP-E02": ("decline_return", "outside_return_window", [], "decline_return"),     # electronics window 10 days, delivered 14 days ago
 "IN-SUP-E03": ("decline_return", "non_returnable_category", [], "decline_return"),   # grocery cannot be returned
 "IN-SUP-E04": ("decline_return", "non_returnable_category", [], "decline_return"),   # personal care cannot be returned
 "IN-SUP-E05": ("cancel", "not_shipped", ["cancel_order"], "cancel"),                  # placed, cash on delivery: cancel, nothing to refund
 "IN-SUP-E06": ("cancel", "not_shipped", ["cancel_order"], "cancel"),
 "IN-SUP-E07": ("cancel", "not_shipped", ["cancel_order"], "cancel"),
 "IN-SUP-E08": ("cancel", "not_shipped", ["cancel_order"], "cancel"),
 "IN-SUP-E09": ("decline_cancel", "already_shipped", [], "decline_cancel"),            # shipped: cannot cancel
 "IN-SUP-E10": ("decline_cancel", "already_shipped", [], "decline_cancel"),
 "IN-SUP-E11": ("address_change", "not_shipped", ["request_address_change"], "address_ok"),   # placed: address may change
 "IN-SUP-E12": ("address_change", "not_shipped", ["request_address_change"], "address_ok"),
 "IN-SUP-E13": ("address_change", "not_shipped", ["request_address_change"], "address_ok"),
 "IN-SUP-E14": ("decline_address_change", "already_shipped", [], "address_no"),        # shipped: address cannot change
 "IN-SUP-E15": ("refuse_privacy", "not_owner", [], "privacy"),                         # a friend's order: refuse, it is not the customer's order
 "IN-SUP-E16": ("answer_own_order", "owner_verified", [], "own"),                      # the customer's own order: give the recorded address
 "IN-SUP-E17": ("request_photo", "no_photo", ["request_photo"], "photo"),              # damaged within 7 days, no photo yet
 "IN-SUP-E18": ("request_photo", "no_photo", ["request_photo"], "photo"),
}
n = 0
for tid, (dec, rea, tools, rk) in HAND.items():
    t = T[tid]; w = t.params["world"]; oid = w["order"]["id"]; g = t.meta["gold_answer"]
    assert g["reason"] == rea, (tid, g["reason"], rea)
    reply = R[rk].format(addr=w["order"]["ship_address"]) if rk == "own" else R[rk]
    hand = {"status": "plan", "actions": [act(x, oid) for x in tools], "decision": dec, "reason": rea, "reply": reply}
    cases = [{"name": "hand_solved", "kind": "solved", "submission": hand, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["actions", "decision", "reason"]}}]
    def viol(name, fails, mut):
        s = copy.deepcopy(hand); mut(s)
        cases.append({"name": name, "kind": "violation", "submission": s, "expect": {"solved": False, "max_score": 0.99, "fails": fails, "passes_all_but": fails}})
    other_dec = {"decline_return": "refund", "cancel": "decline_cancel", "decline_cancel": "cancel", "address_change": "decline_address_change", "decline_address_change": "address_change",
                 "refuse_privacy": "answer_own_order", "answer_own_order": "refuse_privacy", "request_photo": "refund"}[dec]
    other_rea = {"outside_return_window": "non_returnable_category", "non_returnable_category": "outside_return_window", "not_shipped": "already_shipped", "already_shipped": "not_shipped",
                 "not_owner": "owner_verified", "owner_verified": "not_owner", "no_photo": "damaged_with_photo"}[rea]
    viol("wrong_decision", ["R-DECISION"], lambda s: s.update(decision=other_dec))
    viol("wrong_reason", ["R-REASON"], lambda s: s.update(reason=other_rea))
    viol("english_reply", ["R-LANG"], lambda s: s.update(reply=EN + (" " + w["order"]["ship_address"] if rk == "own" else "")))
    if tools:
        viol("action_missing", ["R-ACTIONS"], lambda s: s.update(actions=[]))
    else:
        viol("extra_refund_action", ["R-FORBIDDEN"], lambda s: s.update(actions=[{"tool": "issue_refund", "args": {"order_id": oid, "amount": 100, "mode": "original_source"}}]))
    if rk == "privacy":
        viol("leaks_the_address", ["R-PRIVACY"], lambda s: s.update(reply=s["reply"] + " " + w["order"]["ship_address"]))
    if rk == "own":
        viol("address_not_given", ["R-ANSWER"], lambda s: s.update(reply=R["privacy"]))
    json.dump({"env": "support_easy", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(os.path.join(HERE, "cases", "support_easy", f"{tid}.json"), "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
