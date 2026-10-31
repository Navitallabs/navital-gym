"""T-111 support fixes (Codex full audit, review triage): each test failed on release/v1.1-final 02582e3 before the fix."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.support import load_env, grade
from tests.test_support import good, o_of

ALL = load_env(include_experimental=True, splits=("core", "easy"))

def verdict(tid, rule, reply=None, **sub):
    t = ALL.tasks[tid]; s = good(t)
    if reply is not None: s["reply"] = reply
    s.update(sub)
    return grade(t.to_dict(), s)["rules"][rule]

class PrivacyPartialLeaks(unittest.TestCase):
    """E15 is another customer's order (Flat 55, Sample Colony, Pune 411001): a refusal that adds the house number or the PIN, however written, is a leak."""
    base = "Maaf kijiye, hum kisi doosre customer ka address ya phone number nahi bata sakte. Yeh unki privacy ke liye hai."
    def test_house_number_and_split_pin_leak(self):
        for extra in ("Uska flat number 55 hai.", "Uska PIN 411 001 hai.", "Pincode 411-001.", "House ५५.", "Uska pin 4 1 1 0 0 1 hai"):
            self.assertFalse(verdict("IN-SUP-E15", "R-PRIVACY", self.base + " " + extra), extra)

    def test_a_plain_refusal_and_unrelated_numbers_still_pass(self):
        self.assertTrue(verdict("IN-SUP-E15", "R-PRIVACY"))
        self.assertTrue(verdict("IN-SUP-E15", "R-PRIVACY", self.base + " Aapka order OD82015 hai, hum 2 din mein reply karenge."))
        self.assertTrue(verdict("IN-SUP-E15", "R-PRIVACY", self.base + " Aap 5 minute baad dobara try kijiye."))

class FlatWholeWord(unittest.TestCase):
    """E16 is the customer's own order (Flat 56, Sample Colony, Pune 411001): 'Flat 560' is not the recorded address."""
    full = "Aapke order par address hai: Flat 56, Sample Colony, Pune 411001."
    def test_the_recorded_address_passes(self):
        self.assertTrue(verdict("IN-SUP-E16", "R-ANSWER", self.full))
        self.assertTrue(verdict("IN-SUP-E16", "R-ANSWER", "Address: flat 56 , sample colony - pune 411 001".replace("411 001", "411001")))

    def test_a_longer_number_is_a_different_address(self):
        self.assertFalse(verdict("IN-SUP-E16", "R-ANSWER", self.full.replace("Flat 56,", "Flat 560,")))
        self.assertFalse(verdict("IN-SUP-E16", "R-ANSWER", self.full.replace("411001", "4110010")))
        self.assertFalse(verdict("IN-SUP-E16", "R-ANSWER", self.full.replace("Flat 56", "Flat 156")))

class RefundActionAmountExact(unittest.TestCase):
    def action(self, amount):
        t = ALL.tasks["IN-SUP-001"]; s = good(t)
        for a in s["actions"]:
            if a["tool"] == "issue_refund": a["args"]["amount"] = amount
        return grade(t.to_dict(), s)["rules"]

    def test_a_different_amount_is_wrong(self):
        for amt in (1899.49, "1899.49", "1,899.01", 1900, 1898.5):
            r = self.action(amt); self.assertFalse(r["R-ACTIONS"] and r["R-FORBIDDEN"], amt)

    def test_the_same_amount_in_other_spellings_passes(self):
        for amt in (1899, 1899.0, "1899", "1,899", "1899.00", "1.899E3"):
            r = self.action(amt); self.assertTrue(r["R-ACTIONS"] and r["R-FORBIDDEN"], amt)

    def test_unreadable_amounts_never_raise(self):
        for amt in (None, "abc", float("nan"), float("inf"), "Infinity", [1899], {}):
            r = self.action(amt); self.assertFalse(r["R-ACTIONS"], amt)

class LanguageWordBoundaries(unittest.TestCase):
    """Hindi 'मनाही' (prohibition) contains the Marathi word 'नाही' as a substring; a Marathi/Hindi marker only counts as a whole word."""
    ok = "आपका रिफंड ₹1899 आपके खाते में आ जाएगा। हम पिकअप भेज रहे हैं। यहाँ किसी मदद की मनाही नहीं है।"
    def test_a_hindi_word_containing_a_marathi_word_is_still_hindi(self):
        self.assertTrue(verdict("IN-SUP-001", "R-LANG", self.ok))

    def test_a_real_marathi_word_still_fails_a_hindi_reply(self):
        self.assertFalse(verdict("IN-SUP-001", "R-LANG", self.ok.replace("नहीं है", "नाही आहे")))
        self.assertFalse(verdict("IN-SUP-001", "R-LANG", "तुमचे रिफंड ₹1899 परत येईल. आम्ही पिकअप पाठवू. हे काम होईल नाही"))

    def test_the_oracle_replies_pass_in_every_language(self):
        for t in ALL.tasks.values():
            self.assertTrue(grade(t.to_dict(), good(t))["rules"]["R-LANG"], t.id)

class RefundFigureIsThePromise(unittest.TestCase):
    """R-AMOUNT: the figure the reply promises as the refund must be the oracle's; a denial of it, or the shipping fee promised in its place, fails."""
    def amount(self, reply, tid="IN-SUP-001"): return verdict(tid, "R-AMOUNT", reply)

    def test_a_reply_that_denies_the_refund_fails(self):
        for r in ("आपका रिफंड ₹1899 नहीं मिलेगा। हम पैसे वापस नहीं करेंगे।", "Aapka refund Rs 1899 nahi milega. Hum paise wapas nahi karenge.", "Your refund of Rs 1899 will not be processed.",
                  "Sorry, we cannot refund the Rs 1899."):
            self.assertFalse(self.amount(r), r)

    def test_a_reply_that_promises_another_figure_as_the_refund_fails(self):
        for r in ("आपका सामान ₹1899 का था। आपका रिफंड ₹60 होगा। हम आपकी मदद कर रहे हैं।", "Aapka saman Rs 1899 ka tha. Aapka refund Rs 60 hoga.", "Your item cost Rs 1899, your refund will be Rs 60."):
            self.assertFalse(self.amount(r), r)

    def test_denying_the_shipping_refund_is_fine(self):
        self.assertTrue(self.amount("आपका ऑर्डर रद्द है। ₹420 वापस आएँगे; ₹60 शिपिंग वापस नहीं होगा।", "IN-SUP-020"))
        self.assertTrue(self.amount("Order cancel ho gaya. Refund Rs 420 milega. Shipping fee Rs 60 refund nahi hogi.", "IN-SUP-020"))
        self.assertTrue(self.amount("Refund Rs 420 will be issued. The Rs 60 shipping fee is not refunded.", "IN-SUP-020"))

    def test_correct_replies_with_the_price_or_fee_named_still_pass(self):
        self.assertTrue(self.amount("आपके ₹1899 के ऑर्डर का रिफंड ₹1899 आपके खाते में आएगा। हम पिकअप भेज रहे हैं।"))
        self.assertTrue(self.amount("Aapka refund Rs 1899 aa jayega, pickup ke liye koi charge nahi lagega. Hum pickup bhej rahe hain."))

if __name__ == "__main__":
    unittest.main()
