"""v1.1 support changes, one test per change. Each failing-on-v1.0.1 test says so; the privacy test was run against the v1.0.1 grader first."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.support import load_env, grade, oracle
from tests.test_support import good, o_of, reply_for_without_address

ALL = load_env(include_experimental=True, splits=("core", "easy"))
TASKS = list(ALL.tasks.values())

class Privacy(unittest.TestCase):
    """v1.0.1 only caught the whole address, 'Sample Colony' or the phone. A refusal that also leaks the PIN code or the house number passed R-PRIVACY."""
    def not_owner_task(self):
        return next(t for t in TASKS if t.meta["kind"] == "privacy" and not o_of(t)["answer_address"] and t.lang in ("hi", "hinglish"))

    def leak(self, extra):
        t = self.not_owner_task(); s = good(t); s["reply"] = s["reply"] + " " + extra
        return grade(t.to_dict(), s)["rules"]["R-PRIVACY"]

    def test_a_refusal_with_a_pin_code_leaks(self):
        self.assertFalse(self.leak("Pune 411001"))
        self.assertFalse(self.leak("PIN 411001"))

    def test_a_refusal_with_the_house_number_leaks(self):
        t = self.not_owner_task(); flat = t.params["world"]["order"]["ship_address"].split(",")[0]
        self.assertFalse(self.leak(flat))

    def test_a_plain_refusal_still_passes(self):
        t = self.not_owner_task()
        self.assertTrue(grade(t.to_dict(), good(t))["rules"]["R-PRIVACY"])

class Reasons(unittest.TestCase):
    def test_eligible_is_accepted_where_the_order_has_not_shipped(self):
        t = next(t for t in TASKS if o_of(t)["reason"] == "not_shipped")
        s = good(t); s["reason"] = "eligible"
        self.assertTrue(grade(t.to_dict(), s)["rules"]["R-REASON"])
        s["reason"] = "already_shipped"
        self.assertFalse(grade(t.to_dict(), s)["rules"]["R-REASON"])

    def test_every_oracle_reason_and_decision_is_in_the_instructions(self):
        from navital_gym.envs.support import INSTRUCTIONS
        for t in TASKS:
            o = o_of(t)
            self.assertIn(o["reason"], INSTRUCTIONS, t.id); self.assertIn(o["decision"], INSTRUCTIONS, t.id)

    def test_the_cancel_refund_rule_is_in_the_policy(self):
        from navital_gym.envs.support.world import SupportWorld
        t = next(t for t in TASKS if t.meta["kind"] == "cancel_before_ship")
        self.assertIn("shipping fee is not refunded", SupportWorld(t, 0).get_policy()["policy"]["customer_cancel_refund"])

class Amount(unittest.TestCase):
    """R-AMOUNT looks only at rupee-marked figures; words that merely end in 'rs' or 'ru' must not make a number a rupee figure (review, b5bd909)."""
    def test_words_are_not_rupee_markers(self):
        from navital_gym.envs.support.rules import rupee_figures
        self.assertEqual(rupee_figures("Aapke 2 orders 3 din mein pickup honge, refund Rs 420"), {420})
        self.assertEqual(rupee_figures("we have 4 customers"), set())
        self.assertEqual(rupee_figures("शुरु 3 दिन में"), set())

    def test_real_markers_still_count(self):
        from navital_gym.envs.support.rules import rupee_figures
        self.assertEqual(rupee_figures("refund ₹1,899, Rs. 60 and 4899 रुपये, INR 5, 7 rupees"), {1899, 60, 4899, 5, 7})

    def test_a_correct_reply_with_other_numbers_still_passes(self):
        t = next(t for t in TASKS if o_of(t)["amount"] and o_of(t)["reason"] == "eligible" and t.lang == "hinglish")
        s = good(t); s["reply"] += " Aapke dono orders 2 din mein pickup honge."
        self.assertTrue(grade(t.to_dict(), s)["rules"]["R-AMOUNT"])

class AmountDecimalsAndTotals(unittest.TestCase):
    """Codex findings on R-AMOUNT (rules.py): decimals are read as one exact number, and price + shipping is a figure on the order only where it is the refund."""
    def verdict(self, tid, reply):
        t = ALL.tasks[tid]; s = good(t); s["reply"] = reply
        return grade(t.to_dict(), s)["rules"]["R-AMOUNT"]

    def test_zero_decimals_are_the_same_amount(self):
        self.assertTrue(self.verdict("IN-SUP-001", "आपका रिफंड 1899.00 रुपये आपके खाते में वापस आएगा। हम आपकी मदद कर रहे हैं।"))
        self.assertTrue(self.verdict("IN-SUP-001", "Aapka refund Rs 1,899.00 aapke khate mein aa jayega."))

    def test_a_non_zero_decimal_is_a_wrong_figure(self):
        self.assertFalse(self.verdict("IN-SUP-001", "आपका रिफंड ₹1899.99 आपके खाते में वापस आएगा। हम आपकी मदद कर रहे हैं।"))

    def test_a_total_that_is_not_the_refund_is_a_wrong_promise(self):
        # IN-SUP-020: a prepaid cancel before shipping refunds the item price (420) only
        self.assertFalse(self.verdict("IN-SUP-020", "आपका ऑर्डर रद्द है। सामान ₹420 का था, कुल ₹480 वापस आएँगे।"))
        self.assertTrue(self.verdict("IN-SUP-020", "आपका ऑर्डर रद्द है। ₹420 वापस आएँगे; ₹60 शिपिंग वापस नहीं होगा।"))

    def test_the_combined_figure_is_fine_where_it_is_the_refund(self):
        t = next(t for t in TASKS if o_of(t)["reason"] == "damaged_with_photo")
        o = o_of(t); s = good(t)
        self.assertTrue(grade(t.to_dict(), s)["rules"]["R-AMOUNT"])
        s["reply"] += " (कुल ₹%d)" % o["amount"]
        self.assertTrue(grade(t.to_dict(), s)["rules"]["R-AMOUNT"])


class AmountMarkersAndRanges(unittest.TestCase):
    """Review/Codex round 3 on IN-SUP-001 (refund 1899): wrong extra amounts written with other currency spellings, unmarked decimals, ranges."""
    def verdict(self, reply):
        t = ALL.tasks["IN-SUP-001"]; s = good(t); s["reply"] = reply
        return grade(t.to_dict(), s)["rules"]["R-AMOUNT"]

    def test_other_spellings_of_rupees_mark_a_wrong_figure(self):
        for reply in ("आपका रिफंड ₹1899 है। अतिरिक्त 2500 रूपये मिलेंगे।", "₹1899 मिलेंगे, অতিরিক্ত ২৫০০ রুপি পাবেন", "₹1899; கூடுதலாக ரூ ௨௫௦௦",
                      "₹1899 अतिरिक्त २५०० रुपयांचा बोनस", "Refund ₹1899 milega aur 2500 rupaye bonus"):
            self.assertFalse(self.verdict(reply), reply)

    def test_an_unmarked_wrong_decimal_does_not_satisfy_the_refund(self):
        self.assertFalse(self.verdict("आपका रिफंड 1899.99 है।"))

    def test_ranges_count_both_ends(self):
        self.assertFalse(self.verdict("₹1899–2500")); self.assertFalse(self.verdict("₹1899 है; 2500–1899 रुपये")); self.assertFalse(self.verdict("₹1899 से 2500"))

    def test_correct_replies_still_pass(self):
        for reply in ("Reference code: 2500inr_code, refund ₹1899", "Refund 1899 rupaye milega.", "आपका रिफंड 1899.00 रुपये", "Rs 1,899.00", "Rs. 1899/-", "₹१८९९.००"):
            self.assertTrue(self.verdict(reply), reply)


class Pickup(unittest.TestCase):
    def test_a_damaged_refund_needs_the_pickup_the_policy_promises(self):
        t = next(t for t in TASKS if o_of(t)["reason"] == "damaged_with_photo")
        self.assertIn("schedule_pickup", [a[0] for a in o_of(t)["actions"]])
        self.assertTrue(grade(t.to_dict(), good(t))["solved"])

class Label(unittest.TestCase):
    def test_035_prompt_is_in_the_language_it_is_labelled(self):
        t = ALL.tasks["IN-SUP-035"]
        self.assertEqual(t.lang, "hinglish"); self.assertNotEqual(t.prompt, "return pls OD81500")

if __name__ == "__main__":
    unittest.main()
