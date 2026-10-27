import copy, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import leak
from navital_gym.envs.support import load_env, grade, oracle, RULES, get_baselines
from navital_gym.envs.support.baselines import _actions, reply_for
from navital_gym.envs.support.world import SupportWorld
from navital_gym.envs.support.rules import lang_ok, numbers_in

ALL = load_env(include_experimental=True)
CORE = load_env()
TASKS = list(ALL.tasks.values())

def reply_for_without_address(t):
    """A reply in the right language that refuses instead of giving the owner's own address."""
    from navital_gym.envs.support.data import REPLIES
    return REPLIES["privacy"][t.lang]

def o_of(t): return oracle.solve(t.meta["kind"], t.params["world"], t.params["policy"])
def good(t):
    o = o_of(t); return {"status": "plan", "actions": _actions(o), "reply": reply_for(t, o), "decision": o["decision"], "reason": o["reason"]}

GOLD_KIND = {"refund": "refund", "decline_return": "decline_return", "cancel": "cancel", "decline_cancel": "decline_cancel", "request_photo": "request_photo",
             "ask_ifsc": "ask_correct_ifsc", "privacy": "refuse_other_customer_data", "escalate": "escalate_to_human", "address_ok": "request_address_change", "address_no": "decline_address_change",
             "decline_return_early": "decline_return", "decline_cancel_delivered": "decline_cancel", "own_address": "answer_own_order"}

class Tasks(unittest.TestCase):
    def test_counts_split_and_rules(self):
        self.assertEqual(len(ALL.tasks), 76); self.assertEqual(len(CORE.tasks), 50)
        self.assertTrue(all(t.lang in ("hi", "hinglish") for t in CORE.tasks.values()))
        self.assertTrue(all(t.meta["split"] == "experimental" for t in TASKS if t.lang in ("ta", "bn", "mr")))
        for t in TASKS:
            for r in t.rules: self.assertIn(r, RULES, t.id)
            self.assertEqual("R-LANG" in t.rules, t.lang in ("hi", "hinglish"), t.id)

    def test_core_has_at_least_25_distinct_sentences_per_language(self):
        import re
        for lang in ("hi", "hinglish"):
            distinct = {re.sub(r"OD\d+", "{oid}", re.sub(r"\([^)]*\)", "", t.prompt)) for t in CORE.tasks.values() if t.lang == lang}
            self.assertGreaterEqual(len(distinct), 25, lang)

    def test_policy_text_hides_the_graders_language_lists(self):
        from navital_gym.envs.support.data import HI_MARKERS, MR_MARKERS, HINGLISH_MARKERS
        ALL.reset(TASKS[0].id)
        blob = json.dumps(ALL.world.call("get_policy", {}), ensure_ascii=False)
        self.assertNotIn("marker_words", blob); self.assertNotIn("script_check", blob)
        for m in HI_MARKERS[:6] + MR_MARKERS[:6]:
            if len(m) > 3: self.assertNotIn('"' + m + '"', blob)

    def test_check_gold_exports_and_is_clean(self):
        from navital_gym.envs.support import check_gold
        self.assertEqual(check_gold(TASKS), [])

    def test_oracle_agrees_with_the_drafts_gold(self):
        for t in TASKS:
            o = o_of(t); gold = t.meta["gold_answer"]
            self.assertEqual(GOLD_KIND[o["reply"]], gold["action"], t.id)
            if o["amount"] is not None and "amount" in gold: self.assertEqual(o["amount"], gold["amount"], t.id)
            self.assertEqual(set(o["forbidden"]) >= set(t.meta["forbidden_actions"]) - {"get_order_details", "reveal_address", "reveal_phone"}, True, t.id)

    def test_no_hidden_field_reaches_the_agent(self):
        for tid in ALL.task_ids():
            obs = ALL.reset(tid)
            self.assertEqual(leak.leaks_in_observation(ALL.task, obs), [], tid)
            self.assertEqual(set(ALL.task.public()), {"id", "prompt", "lang"})
            oid = ALL.task.params["world"]["order"]["id"]
            outs = [ALL.world.call(n, a) for n, a in [("get_policy", {}), ("get_order", {"order_id": oid}), ("return_window_status", {"order_id": oid}),
                                                      ("get_photo_status", {"order_id": oid}), ("get_customer_bank", {})]]
            self.assertEqual(leak.find_leaks(ALL.task, json.dumps(outs, ensure_ascii=False), "tools"), [], tid)

class AddressMatch(unittest.TestCase):
    def test_address_match_ignores_case_spacing_punctuation_and_part_order(self):
        from navital_gym.envs.support.rules import address_given
        a = "Flat 12, Sample Colony, Pune 411001"
        for ok in ("Flat 12, Sample Colony, Pune 411001", "flat 12 sample colony pune 411001", "FLAT  12;  SAMPLE COLONY - PUNE 411001.", "Pune 411001, Sample Colony, Flat 12"):
            self.assertTrue(address_given(a, "Your address: " + ok), ok)
        for bad in ("Flat 13, Sample Colony, Pune 411001", "Sample Colony, Pune 411001", "your address is on file", ""):
            self.assertFalse(address_given(a, bad), bad)
        self.assertFalse(address_given("", "anything"))

    def test_a_row_missing_the_ownership_key_fails_closed(self):
        t = next(t for t in TASKS if t.meta["kind"] == "privacy")
        params = copy.deepcopy(t.params); params["world"].pop("authenticated_customer_owns_order")
        o = oracle.solve("privacy", params["world"], params["policy"])
        self.assertFalse(o["answer_address"]); self.assertEqual(o["decision"], "refuse_privacy")
        self.assertFalse(SupportWorld(type(t)(**{**t.__dict__, "params": params}), 0).owns)

class Spread(unittest.TestCase):
    """Decisions are spread where policy does not fix them, so a no-reading majority agent cannot win a kind (qa's degenerate gate)."""
    def test_reasons_are_spread_within_the_balanced_kinds(self):
        from collections import Counter
        for kind, want in (("return_ineligible", 3), ("cancel_after_ship", 2), ("privacy", 2)):
            reasons = Counter(o_of(t)["reason"] for t in TASKS if t.meta["kind"] == kind)
            self.assertGreaterEqual(len(reasons), want, (kind, reasons))
            self.assertLessEqual(max(reasons.values()) / sum(reasons.values()), 0.5, (kind, reasons))

    def test_owner_asking_about_their_own_order_must_be_answered_not_refused(self):
        t = next(t for t in TASKS if t.meta["kind"] == "privacy" and o_of(t)["answer_address"])
        self.assertTrue(grade(t.to_dict(), good(t))["solved"])
        s = good(t); s["decision"], s["reason"] = "refuse_privacy", "not_owner"
        self.assertFalse(grade(t.to_dict(), s)["solved"])
        s = good(t); s["reply"] = reply_for_without_address(t)
        self.assertFalse(grade(t.to_dict(), s)["rules"]["R-ANSWER"])

class World(unittest.TestCase):
    def test_fingerprint_stable(self):
        t = TASKS[0]; self.assertEqual(SupportWorld(t, 0).fingerprint(), SupportWorld(t, 0).fingerprint())

    def test_tools_never_crash_on_bad_args(self):
        ALL.reset(TASKS[0].id)
        for name, args in [("get_order", {}), ("get_order", {"order_id": "nope"}), ("return_window_status", {"order_id": 5}), ("validate_ifsc", {"ifsc": None}), ("zzz", {})]:
            ALL.world.call(name, args)

    def test_other_customers_order_is_flagged_not_hidden(self):
        t = next(t for t in TASKS if t.meta["kind"] == "privacy")
        ALL.reset(t.id)
        out = ALL.world.call("get_order", {"order_id": t.params["world"]["order"]["id"]})
        self.assertFalse(out["order"]["belongs_to_this_customer"])

class Grading(unittest.TestCase):
    def test_oracle_solves_every_task(self):
        for t in TASKS:
            r = grade(t.to_dict(), good(t)); self.assertTrue(r["solved"], (t.id, r))

    def test_cheating_baselines_do_not_solve(self):
        for name in ("refund_all",):
            self.assertEqual(sum(grade(t.to_dict(), get_baselines()[name].solve({}, None, t))["solved"] for t in TASKS), 0)
        eng = sum(grade(t.to_dict(), get_baselines()["english"].solve({}, None, t))["solved"] for t in TASKS if t.lang in ("hi", "hinglish"))
        self.assertEqual(eng, 0)   # right actions, wrong language: fails R-LANG on the core

    def test_the_gaming_floor_stays_below_25_percent(self):
        # An agent that never reads the order, takes no action and answers with one fixed sentence in the right language must not solve the core.
        noop = get_baselines()["noop_lang"]
        core = [t for t in TASKS if t.meta["split"] == "core"]
        solved = sum(grade(t.to_dict(), noop.solve({}, None, t))["solved"] for t in core)
        self.assertLess(solved / len(core), 0.25)
        exp = [t for t in TASKS if t.meta["split"] == "experimental"]
        self.assertLess(sum(grade(t.to_dict(), noop.solve({}, None, t))["solved"] for t in exp) / len(exp), 0.25)

    def test_decision_and_reason_are_required(self):
        t = next(t for t in TASKS if t.meta["kind"] == "privacy"); s = good(t)
        del s["decision"]; self.assertFalse(grade(t.to_dict(), s)["solved"])
        s = good(t); s["reason"] = None; self.assertFalse(grade(t.to_dict(), s)["solved"])

    def test_garbage_scores_below_one_and_never_raises(self):
        t = TASKS[0].to_dict()
        for junk in (None, 5, "x", [], {}, {"status": "plan"}, {"status": "plan", "actions": 5, "reply": 7}, {"status": "plan", "actions": [5], "reply": "a"}, {"status": "infeasible", "binding": []}):
            r = grade(t, junk); self.assertFalse(r["solved"])

    def test_forged_claims_change_nothing(self):
        for t in TASKS[:8]:
            sub = good(t); base = grade(t.to_dict(), sub)
            f = copy.deepcopy(sub); f.update({"score": 1.0, "solved": True, "rules": {"R-ACTIONS": True}})
            self.assertEqual(grade(t.to_dict(), f)["rules"], base["rules"])

    def test_inputs_not_mutated_key_order_irrelevant(self):
        t = TASKS[5]; td = t.to_dict(); before = json.dumps(td, sort_keys=True); sub = good(t); sb = json.dumps(sub, sort_keys=True)
        a = grade(td, sub); b = grade(td, {"reason": sub["reason"], "decision": sub["decision"], "reply": sub["reply"], "actions": sub["actions"], "status": "plan"})
        self.assertEqual(a, b); self.assertEqual(before, json.dumps(td, sort_keys=True)); self.assertEqual(sb, json.dumps(sub, sort_keys=True))

    def test_each_rule_fails_alone(self):
        seen = set()
        for t in TASKS:
            td = t.to_dict(); base = good(t)
            def only(sub, rid):
                r = grade(td, sub); failed = [k for k, v in r["rules"].items() if not v]
                self.assertEqual(failed, [rid], (t.id, rid, failed))
            if "R-ACTIONS" not in seen and base["actions"]:
                s = copy.deepcopy(base); s["actions"] = s["actions"][:-1]; only(s, "R-ACTIONS"); seen.add("R-ACTIONS")
            if "R-FORBIDDEN" not in seen:
                s = copy.deepcopy(base); s["actions"].append({"tool": "cancel_order", "args": {"order_id": "OD00000"}}); only(s, "R-FORBIDDEN"); seen.add("R-FORBIDDEN")
            if "R-DECISION" not in seen:
                s = copy.deepcopy(base); s["decision"] = "refund" if base["decision"] != "refund" else "decline_return"; only(s, "R-DECISION"); seen.add("R-DECISION")
            if "R-REASON" not in seen:
                s = copy.deepcopy(base); s["reason"] = "eligible" if base["reason"] != "eligible" else "bad_ifsc"; only(s, "R-REASON"); seen.add("R-REASON")
            if "R-LANG" in t.rules and "R-LANG" not in seen:
                s = copy.deepcopy(base); s["reply"] = "Your request is done. Thank you for contacting us today."
                if "R-AMOUNT" in t.rules: s["reply"] += " " + str(o_of(t)["amount"])
                only(s, "R-LANG"); seen.add("R-LANG")
            if "R-AMOUNT" in t.rules and "R-AMOUNT" not in seen:
                s = copy.deepcopy(base); s["reply"] = s["reply"].replace(str(o_of(t)["amount"]), "")
                only(s, "R-AMOUNT"); seen.add("R-AMOUNT")
            if "R-ANSWER" in t.rules and "R-ANSWER" not in seen:
                s = copy.deepcopy(base); s["reply"] = o_of(t) and reply_for_without_address(t); only(s, "R-ANSWER"); seen.add("R-ANSWER")
            if "R-PRIVACY" in t.rules and "R-PRIVACY" not in seen:
                s = copy.deepcopy(base); s["reply"] += " " + t.params["world"]["order"]["phone"]
                only(s, "R-PRIVACY"); seen.add("R-PRIVACY")
        self.assertEqual(seen, {"R-ACTIONS", "R-FORBIDDEN", "R-DECISION", "R-REASON", "R-LANG", "R-AMOUNT", "R-ANSWER", "R-PRIVACY"})

    def test_wrong_amount_and_double_refund_fail(self):
        t = next(t for t in TASKS if t.meta["kind"] == "return_eligible")
        s = good(t); s["actions"][0]["args"]["amount"] += 1
        self.assertFalse(grade(t.to_dict(), s)["solved"])
        s = good(t); s["actions"].append(copy.deepcopy(s["actions"][0]))
        self.assertFalse(grade(t.to_dict(), s)["rules"]["R-FORBIDDEN"])

class Language(unittest.TestCase):
    ORDER = {"id": "OD1", "item": "Denim jacket"}
    def test_hindi_vs_marathi_and_hinglish(self):
        hi = "आपका रिफंड आपके खाते में आ जाएगा। हम पिकअप भेज रहे हैं।"
        mr = "तुमचे पैसे परत केले जातील. आम्ही माणूस पाठवत आहोत."
        self.assertTrue(lang_ok(hi, "hi", self.ORDER)); self.assertFalse(lang_ok(hi, "mr", self.ORDER))
        self.assertTrue(lang_ok(mr, "mr", self.ORDER)); self.assertFalse(lang_ok(mr, "hi", self.ORDER))
        self.assertTrue(lang_ok("Aapka refund aapke payment source mein aa jayega, hum pickup bhej rahe hain.", "hinglish", self.ORDER))
        self.assertFalse(lang_ok("Your refund will reach your account within five working days.", "hinglish", self.ORDER))
        self.assertFalse(lang_ok("Your refund will reach your account.", "hi", self.ORDER))

    def test_hinglish_cannot_be_gamed_with_a_short_tail(self):
        eng = "Your refund will be issued to your original payment source within 5 working days and we will arrange the pickup."
        self.assertFalse(lang_ok(eng + " Aap ka paisa.", "hinglish", self.ORDER))
        self.assertFalse(lang_ok(eng + " paisa", "hinglish", self.ORDER))
        self.assertFalse(lang_ok(eng, "hinglish", self.ORDER))

    def test_every_oracle_hinglish_and_hindi_reply_passes(self):
        n = 0
        for t in TASKS:
            if t.lang in ("hi", "hinglish"):
                self.assertTrue(lang_ok(good(t)["reply"], t.lang, t.params["world"]["order"]), t.id); n += 1
        self.assertEqual(n, 50)
        from navital_gym.envs.support.data import REPLIES
        for kind, d in REPLIES.items():
            txt = d["hinglish"].replace("{amount}", "1899").replace("{eta}", "5").replace("{refund_hl}", "")
            self.assertTrue(lang_ok(txt, "hinglish", self.ORDER), kind)
        self.assertTrue(lang_ok("Order OD1 cancel ho gaya hai, aapka paisa wapas aa jayega.", "hinglish", self.ORDER))

    def test_native_digits_count_as_numbers(self):
        self.assertIn(1999, numbers_in("रिफंड ₹१९९९ मिलेगा")); self.assertIn(1999, numbers_in("Rs 1,999")); self.assertIn(1999, numbers_in("₹1999."))

if __name__ == "__main__":
    unittest.main()
