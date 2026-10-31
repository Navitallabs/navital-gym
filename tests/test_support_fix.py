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

class DayCountOnly(unittest.TestCase):
    """The security review's point: after 'N रुपये', only a number followed by a day/time unit is a count; any other second number is still a stray figure."""
    def test_a_second_number_without_a_unit_is_a_figure(self):
        for r in ("आपको 1899 रुपये 2500 अतिरिक्त मिलेंगे।", "आपको 1899 रुपये 2500 मिलेंगे।", "आपको 1899 रुपये 5 बोनस भी।"):
            self.assertFalse(verdict("IN-SUP-001", "R-AMOUNT", r), r)

    def test_a_look_alike_word_is_not_a_unit(self):
        for r in ("आपको 1899 रुपये 2500 dinner बोनस मिलेगा।", "आपको 1899 रुपये 2500 someday मिलेंगे।", "आपको 1899 रुपये 2500 अतिरिक्त दिन भर में।", "आपको 1899 रुपये 2500 कार्यक्रम में।"):
            self.assertFalse(verdict("IN-SUP-001", "R-AMOUNT", r), r)

    def test_a_count_with_a_unit_is_not(self):
        for r in ("आपके 1899 रुपये 5 दिन में वापस आएंगे।", "आपको 1899 रुपये 5 कार्य दिवसों में मिलेंगे।", "आपको 1899 रुपये 2 हफ्ते में मिलेंगे।", "आपको 1899 रुपये 5 कार्य-दिवसों में मिलेंगे।", "आपको 1899 रुपये 5 working days में मिलेंगे।"):
            self.assertTrue(verdict("IN-SUP-001", "R-AMOUNT", r), r)

class PrivacyFullAddressVariants(unittest.TestCase):
    """Daksh's Codex audit: the other customer's whole address, lower-cased or with other separators, must not pass (IN-SUP-041: Flat 50, Sample Colony, Pune 411001)."""
    def test_every_spelling_of_the_address_leaks(self):
        for extra in ("flat 50, sample colony, pune 411001", "flat 50 - sample colony - pune 411001", "FLAT 50/SAMPLE COLONY/PUNE 411 001", "Flat-50 ; Sample  Colony . Pune 411001",
                      "sample colony", "SAMPLE COLONY mein", "Flat 50", "फ्लैट ५०, Pune ४११००१", "Pune 411001"):
            self.assertFalse(verdict("IN-SUP-041", "R-PRIVACY", good(ALL.tasks["IN-SUP-041"])["reply"] + " " + extra), extra)

    def test_the_plain_refusal_passes(self):
        self.assertTrue(verdict("IN-SUP-041", "R-PRIVACY"))

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
    """R-AMOUNT: a figure that follows a refund word ('रिफंड केवल ₹60') must be the refund. Denials in words are NOT detected (documented limitation, see KnownLimitation)."""
    def amount(self, reply, tid="IN-SUP-001"): return verdict(tid, "R-AMOUNT", reply)

    def test_another_figure_promised_as_the_refund_fails(self):
        for r in ("आपका सामान ₹1899 का था। आपका रिफंड ₹60 होगा। हम आपकी मदद कर रहे हैं।", "Aapka saman Rs 1899 ka tha. Aapka refund Rs 60 hoga.", "Your item cost Rs 1899, your refund will be Rs 60.",
                  "सामान ₹1899 का था लेकिन आपका रिफंड केवल ₹60 होगा। हम पिकअप भेज रहे हैं।", "Refund of Rs 60 will be issued to you."):
            self.assertFalse(self.amount(r), r)

    def test_review_case_3_a_price_mention_does_not_excuse_a_wrong_promise(self):
        self.assertFalse(self.amount("सामान ₹1899 का था लेकिन आपका रिफंड केवल ₹60 होगा। हम पिकअप भेज रहे हैं।"))

    def test_review_cases_1_and_2_false_fails_are_gone(self):
        for r in ("आपका रिफंड ₹1899 मिलेगा कोई समस्या नहीं है। हम पिकअप भेज रहे हैं।", "चिंता न करें आपका रिफंड ₹1899 आएगा। हम पिकअप भेज रहे हैं।"):
            self.assertTrue(self.amount(r), r)

    def test_a_price_mention_elsewhere_stays_allowed(self):
        self.assertTrue(self.amount("आपके ₹1899 के ऑर्डर का रिफंड ₹1899 आपके खाते में आएगा। हम पिकअप भेज रहे हैं।"))
        self.assertTrue(self.amount("Aapka refund Rs 1899 aa jayega, pickup ke liye koi charge nahi lagega. Hum pickup bhej rahe hain."))

    def test_denying_the_shipping_refund_is_fine(self):
        self.assertTrue(self.amount("आपका ऑर्डर रद्द है। ₹420 वापस आएँगे; ₹60 शिपिंग वापस नहीं होगा।", "IN-SUP-020"))
        self.assertTrue(self.amount("Order cancel ho gaya. Refund Rs 420 milega. Shipping fee Rs 60 refund nahi hogi.", "IN-SUP-020"))
        self.assertTrue(self.amount("Refund Rs 420 will be issued. The Rs 60 shipping fee is not refunded.", "IN-SUP-020"))
        self.assertTrue(self.amount("Refund Rs 420 will be issued and will not include the Rs 60 shipping fee.", "IN-SUP-020"))

    def test_a_spaced_figure_is_read_whole_by_the_promise_check(self):
        self.assertFalse(self.amount("आपका रिफंड केवल 60 रुपये होगा। 1 899 रुपये का सामान था।"))
        self.assertTrue(self.amount("आपका रिफंड 1 899 रुपये आपके खाते में आएगा। हम पिकअप भेज रहे हैं।"))

class KnownLimitation(unittest.TestCase):
    """A reply that denies or misstates the refund in words is not reliably detected (v1.1 known limitation; 0 real denials in the 318 saved support rows).
    The denial is still caught where the actions or the decision are wrong (R-ACTIONS, R-DECISION), which a denial usually comes with."""
    @unittest.expectedFailure
    def test_the_shipping_fee_promised_back_in_figure_first_order_is_not_detected(self):
        self.assertFalse(verdict("IN-SUP-020", "R-AMOUNT", "Aapka ₹420 refund ho jayega, lekin ₹60 shipping fee bhi wapas kiya jayega."))

    @unittest.expectedFailure
    def test_a_denial_in_words_still_passes_r_amount(self):
        self.assertFalse(verdict("IN-SUP-001", "R-AMOUNT", "आपका रिफंड ₹1899 आपके खाते में बिल्कुल भी वापस नहीं आएगा। हम पिकअप भेज रहे हैं।"))

class AmountCorpus(unittest.TestCase):
    """63 replies written by a Haiku subagent (21 per case, 14 correct and 7 wrong each) for IN-SUP-001 (refund 1899), 020 (refund 420, shipping not refunded) and 029 (refund 2059):
    R-AMOUNT must agree with the writer's label on every one. Two of them first disagreed ('non-refundable', a breakdown whose parts add up to the refund) and the rule was fixed."""
    def test_every_label_agrees(self):
        import json
        tid = {"A": "IN-SUP-001", "B": "IN-SUP-020", "C": "IN-SUP-029"}
        for r in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "support_amount_corpus.json"))):
            t = ALL.tasks[tid[r["case"]]]; s = good(t); s["reply"] = r["reply"]
            self.assertEqual(grade(t.to_dict(), s)["rules"]["R-AMOUNT"], r["expect"] == "pass", r["reply"])

class ReplyFloor(unittest.TestCase):
    """Daksh's Codex audit: correct actions + a reply of 'aap aap aap ...' plus the amount solved 24 tasks. R-LANG now also needs a reply that is not degenerate
    (at least 3 distinct words, no word over 40% of the words) and that states the required decision in words (Hindi / Hinglish / English vocabulary)."""
    HL = next(t.id for t in ALL.tasks.values() if t.lang == "hinglish" and o_of(t)["decision"] == "refund")      # a Hinglish refund task
    HI = "IN-SUP-001"                                                                                           # a Hindi refund task, refund 1899
    def amount(self, tid): return int(o_of(ALL.tasks[tid])["amount"])
    def solved(self, tid, reply):
        t = ALL.tasks[tid]; s = good(t); s["reply"] = reply
        return grade(t.to_dict(), s)

    def test_a_repeated_word_with_the_amount_no_longer_solves(self):
        a = self.amount(self.HL)
        g = self.solved(self.HL, f"aap aap aap aap aap aap aap aap {a}")
        self.assertFalse(g["rules"]["R-LANG"]); self.assertFalse(g["solved"])
        g = self.solved(self.HI, "आपका हम आपका हम आपका हम आपका हम आपका हम ₹1899")
        self.assertFalse(g["rules"]["R-LANG"]); self.assertFalse(g["solved"])

    def test_marker_words_without_the_decision_do_not_solve(self):
        a = self.amount(self.HL)
        # six distinct Hinglish marker words and the amount, but nothing about a refund
        self.assertFalse(self.solved(self.HL, f"Aap hum kar hai ho mein se ke ka ki ko Rs {a}")["rules"]["R-LANG"])
        self.assertFalse(self.solved(self.HI, "आपका आपके हम है हैं कर रहे जाएगा होगा ₹1899")["rules"]["R-LANG"])

    def test_one_dominant_word_fails(self):
        a = self.amount(self.HL)
        self.assertFalse(self.solved(self.HL, f"Aapka refund Rs {a} hum hum hum hum hum hum hum hum aayega")["rules"]["R-LANG"])

    def test_every_oracle_reply_passes_in_every_language(self):
        for t in ALL.tasks.values():
            self.assertTrue(grade(t.to_dict(), good(t))["rules"]["R-LANG"], t.id)

    def test_review_case_4_short_honest_replies_pass(self):
        for tid, lang_reply in (("IN-SUP-065", "ক্ষতিগ্রস্ত পণ্যের ছবি পাঠান।"), ("IN-SUP-058", "மன்னிக்கவும், இப்பொருளைத் திருப்பித் தர இயலாது.")):
            t = ALL.tasks[tid]; s = good(t); s["reply"] = lang_reply
            self.assertTrue(grade(t.to_dict(), s)["rules"]["R-LANG"], tid)
        # the Hinglish line: the new floor passes it; R-LANG still wants three Hinglish marker words (the rule since v1.0), which this 2-marker line does not have
        from navital_gym.envs.support.rules import reply_floor_ok
        self.assertTrue(reply_floor_ok(f"Aapka refund Rs {self.amount(self.HL)} approve hai.", "hinglish", ("refund",)))

    def test_natural_short_replies_pass(self):
        a = self.amount(self.HL)
        for tid, reply in ((self.HL, f"Aapka refund Rs {a} aa jayega. Hum pickup kal bhej rahe hain."), (self.HL, f"Aapke Rs {a} wapas mil jayenge, hum pickup bhej rahe hain."),
                           (self.HI, "आपका ₹1899 का रिफंड 5 दिन में आ जाएगा। हम पिकअप भेज रहे हैं।"), (self.HI, "आपके ₹1899 वापस मिल जाएंगे, हम आपका सामान उठाने आ रहे हैं।")):
            self.assertTrue(self.solved(tid, reply)["rules"]["R-LANG"], reply)

if __name__ == "__main__":
    unittest.main()
