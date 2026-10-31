"""T-107 regression tests (qa/delta): one test per finding in ~/claude-team/env-review/qa.md.
Each test is fix-agnostic where the fix can go two ways (accept the answer, or make the prompt unambiguous); the docstring says which.
Against v1.0.1 every test here must FAIL (that proves it catches the bug); against v1.1 every test must PASS.
Fixtures are real final answers copied from runs/ (run id in each test). No model calls, no spend."""
import json, os, re, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import upi, support, trip, gst, form

FX = json.loads(r'''{
 "sup020_opus": {
  "status": "plan",
  "actions": [
   {
    "tool": "cancel_order",
    "args": {
     "order_id": "OD81200"
    }
   },
   {
    "tool": "issue_refund",
    "args": {
     "order_id": "OD81200",
     "amount": 480,
     "mode": "original_source"
    }
   }
  ],
  "decision": "cancel",
  "reason": "not_shipped",
  "reply": "नमस्ते! आपका ऑर्डर OD81200 (Rice 5kg) अभी शिप नहीं हुआ है, इसलिए हम इसे रद्द कर रहे हैं। आपने इसका भुगतान पहले ही कर दिया था, इसलिए ₹480 (सामान के ₹420 और शिपिंग के ₹60) आपके उसी भुगतान माध्यम में वापस भेजे जाएँगे। यह पैसा लगभग 5 कार्य दिवसों में आ जाना चाहिए। कोई और मदद चाहिए तो बताइए।"
 },
 "sup020_sonnet": {
  "status": "plan",
  "actions": [
   {
    "tool": "cancel_order",
    "args": {
     "order_id": "OD81200"
    }
   }
  ],
  "decision": "cancel",
  "reason": "eligible",
  "reply": "नमस्ते! आपका ऑर्डर OD81200 (Rice 5kg) अभी \"placed\" स्थिति में है और शिप नहीं हुआ है। इसलिए मैं इसे रद्द कर रही हूँ। यह ऑर्डर प्रीपेड था, इसलिए भुगतान की गई राशि आपके मूल भुगतान माध्यम में वापस भेज दी जाएगी। धन्यवाद!"
 },
 "sup029_opus": {
  "status": "plan",
  "actions": [
   {
    "tool": "issue_refund",
    "args": {
     "order_id": "OD81400",
     "amount": 2059,
     "mode": "original_source"
    }
   },
   {
    "tool": "schedule_pickup",
    "args": {
     "order_id": "OD81400"
    }
   }
  ],
  "decision": "refund",
  "reason": "damaged_with_photo",
  "reply": "Namaste! Aapka Denim jacket (order OD81400) toota hua aaya, iske liye maafi chahte hain. Aapki photo humein mil gayi hai aur aapne delivery ke 3 din ke andar bataya hai, isliye aapka refund approve ho gaya hai. Aapko ₹2,059 wapas milenge (jacket ke ₹1,999 + shipping ke ₹60). Ye paise usi payment method mein aayenge jisse aapne pay kiya tha, lagbhag 5 working days mein. Jacket wapas lene ke liye hum pickup bhi schedule kar rahe hain. Kripya jacket ko pickup ke liye taiyaar rakhein."
 },
 "sup048_opus": {
  "status": "plan",
  "actions": [
   {
    "tool": "request_address_change",
    "args": {
     "order_id": "OD81800"
    }
   }
  ],
  "decision": "address_change",
  "reason": "eligible",
  "reply": "नमस्ते! आपका ऑर्डर OD81800 (Novel set) अभी भेजा नहीं गया है, इसलिए इसका पता बदला जा सकता है। मैंने पता बदलने का अनुरोध दर्ज कर दिया है। आगे आपसे नया पता पक्का किया जाएगा। कृपया उसे सही-सही बताएँ, खासकर पिन कोड। ऑर्डर भेजे जाने के बाद पता नहीं बदला जा सकेगा। धन्यवाद!"
 },
 "sup026_opus": {
  "status": "plan",
  "actions": [],
  "decision": "decline_cancel",
  "reason": "already_shipped",
  "reply": "मुझे खेद है, आपका ऑर्डर OD81301 (Bluetooth speaker) रद्द नहीं हो सकता। हमारी नीति के हिसाब से ऑर्डर तभी रद्द होता है जब वह अभी 'placed' स्थिति में हो, यानी भेजा न गया हो। आपका ऑर्डर भेजा जा चुका है और 14-11-2026 को आप तक पहुँच भी गया है। आप इसे वापस (return) कर सकते हैं। Electronics सामान के लिए return window डिलीवरी से 10 दिन की है। आपको डिलीवरी मिले अभी 2 दिन हुए हैं, तो 24-11-2026 तक return माँग सकते हैं। अगर आप return करना चाहें या सामान खराब निकला हो, तो मुझे बताएँ। मैं आगे की मदद करूँगा।"
 },
 "sup035_opus": {
  "status": "plan",
  "actions": [
   {
    "tool": "schedule_pickup",
    "args": {
     "order_id": "OD81500"
    }
   },
   {
    "tool": "issue_refund",
    "args": {
     "order_id": "OD81500",
     "amount": 1999,
     "mode": "bank_transfer"
    }
   }
  ],
  "decision": "refund",
  "reason": "eligible",
  "reply": "Your return for order OD81500 (Denim jacket) is approved. It was delivered 4 days ago, which is well inside our 15-day return window for clothing. We'll schedule a pickup from Flat 30, Sample Colony, Pune 411001. You paid cash on delivery, so we'll send a refund of ₹1,999 by bank transfer to your account ending in 4321 (IFSC SBIN0001234). It should arrive within about 5 working days. The ₹60 shipping fee is only refunded when the problem is the seller's fault, so it isn't included. Let us know if you need anything else!"
 },
 "sup001_gptoss": {
  "status": "plan",
  "actions": [
   {
    "tool": "issue_refund",
    "args": {
     "order_id": "OD81000",
     "amount": 1899,
     "mode": "original_source"
    }
   },
   {
    "tool": "schedule_pickup",
    "args": {
     "order_id": "OD81000"
    }
   }
  ],
  "decision": "refund",
  "reason": "eligible",
  "reply": "आपके Bluetooth speaker का रिटर्न अनुरोध स्वीकार कर लिया गया है। हम 4,899 रुपये (उत्पाद की कीमत 1,899 रुपये) की राशि को आपके मूल भुगतान स्रोत में वापस कर देंगे। हमारी टीम जल्द ही आपके पते पर पिकअप शेड्यूल करेगी। यदि आपको कोई और सहायता चाहिए तो बताइए।"
 },
 "gst027_opus": {
  "status": "plan",
  "answer": {
   "eligible_itc": "4680.00",
   "eligible_invoices": [
    "P30",
    "P31",
    "P34"
   ]
  }
 },
 "form046_haiku": {
  "status": "plan",
  "answer": {
   "financial_year": "2026-2027",
   "assessment_year": "2027-2028",
   "next_advance_tax_date": "2027-03-15"
  }
 },
 "upi022_opus": {
  "status": "plan",
  "answer": {
   "action": "dispute_raised",
   "type": "p2m",
   "tat_date": "2026-11-15",
   "days_late": 1,
   "compensation_rs": 100,
   "compensation_automatic": true
  }
 },
 "upi046_opus": {
  "status": "plan",
  "answer": {
   "action": "paid"
  }
 },
 "upi039_opus": {
  "status": "plan",
  "answer": {
   "action": "abort_and_confirm"
  }
 },
 "upi039_4omini": {
  "status": "plan",
  "answer": {
   "action": "approved"
  }
 }
}''')
ENVS = {"upi": upi.load_env(), "support": support.load_env(include_experimental=True), "trip": trip.load_env(), "gst": gst.load_env(), "form": form.load_env()}

def grade(env, tid, sub):
    e = ENVS[env]; return e.grader.grade(e.tasks[tid], sub).to_dict()

def enum_after(text, key):
    """Words in the `"<key>": one of a | b | c,` list of an env's prompt."""
    m = re.search(r'"%s": one of ([^,\n]+(?:\|[^,\n]+)*)' % key, text)
    return {w.strip() for w in m.group(1).split("|")} if m else set()

class UPI(unittest.TestCase):
    def test_U1_failed_debited_dispute_raised_is_accepted(self):
        """qa U1, IN-UPI-022, run upi-anthropic-opus-5-5-full: raised the dispute (correct effect), answered dispute_raised. Fix: accept it, or drop the escalate/dispute_raised overlap from the prompt (then change this fixture)."""
        sub = dict(FX["upi022_opus"], actions=[{"tool": "raise_dispute", "args": {"txn_id": "TXN7003", "category": "failed_txn_debited"}}])
        self.assertTrue(grade("upi", "IN-UPI-022", sub)["solved"])

    def test_U1_lite_payment_paid_is_accepted(self):
        """qa U1, IN-UPI-046, run upi-anthropic-opus-5-5-full: paid with Lite, answered `paid`. Fix: accept paid for a Lite payment, or remove `done` from the word list."""
        sub = dict(FX["upi046_opus"], actions=[{"tool": "pay_with_lite", "args": {"vpa": "cafe@upibank", "amount": 300}}])
        self.assertTrue(grade("upi", "IN-UPI-046", sub)["solved"])

    def test_U2_collect_scam_039_decline_passes_approve_fails(self):
        """qa U2, IN-UPI-039 (lead decision 31 Oct): the 'refund me' collect request is a scam. Declining and reporting must pass; approving must fail. The task must exist (task counts unchanged)."""
        self.assertIn("IN-UPI-039", ENVS["upi"].tasks)
        decline = {"status": "plan", "answer": {"action": "declined_and_reported"},
                   "actions": [{"tool": "decline_collect", "args": {"id": "COL5"}}, {"tool": "report_vpa", "args": {"vpa": "paytoshop@merchantbank"}}]}
        approve = dict(FX["upi039_4omini"], actions=[{"tool": "approve_collect", "args": {"id": "COL5"}}])
        self.assertTrue(grade("upi", "IN-UPI-039", decline)["solved"])
        self.assertFalse(grade("upi", "IN-UPI-039", approve)["solved"])

    def test_U2_collect_040_legit_merchant_approve_passes_decline_fails(self):
        """qa U2, IN-UPI-040 (lead decision 31 Oct): a legitimate merchant request with a matching open order. Approving must pass; declining and reporting must fail. The task must exist."""
        self.assertIn("IN-UPI-040", ENVS["upi"].tasks)
        t = ENVS["upi"].tasks["IN-UPI-040"]
        cid = t.params["world"]["pending_collects"][0]["id"]; vpa = t.params["world"]["pending_collects"][0]["from_vpa"]
        approve = {"status": "plan", "answer": {"action": "approved"}, "actions": [{"tool": "approve_collect", "args": {"id": cid}}]}
        decline = {"status": "plan", "answer": {"action": "declined_and_reported"},
                   "actions": [{"tool": "decline_collect", "args": {"id": cid}}, {"tool": "report_vpa", "args": {"vpa": vpa}}]}
        self.assertTrue(grade("upi", "IN-UPI-040", approve)["solved"])
        self.assertFalse(grade("upi", "IN-UPI-040", decline)["solved"])

class Support(unittest.TestCase):
    def test_S1_every_oracle_reason_is_in_the_prompt_enum(self):
        """qa S1, IN-SUP-026 (and not_delivered / owner_verified): the reason the oracle wants must be a word the prompt offers."""
        from navital_gym.envs.support import oracle
        allowed = enum_after(support.INSTRUCTIONS, "reason")
        self.assertTrue(allowed)
        bad = {}
        for t in ENVS["support"].tasks.values():
            r = oracle.solve(t.meta["kind"], t.params["world"], t.params["policy"])["reason"]
            if r not in allowed: bad[t.id] = r
        self.assertEqual(bad, {}, "tasks whose required reason is not in the prompt")

    def test_S2_prepaid_cancel_amount_is_decidable(self):
        """qa S2, IN-SUP-020, run support-anthropic-opus-5-5-full (refunds 480) / -sonnet (cancel only). Fix: accept 480 + cancel+refund, or state in the prompt/policy that shipping is not refunded on cancel and that cancel does not refund by itself."""
        t = ENVS["support"].tasks["IN-SUP-020"]
        if grade("support", "IN-SUP-020", FX["sup020_opus"])["solved"]: return
        text = (t.prompt + " " + support.INSTRUCTIONS + " " + json.dumps(t.params["policy"])).lower()
        self.assertTrue("cancel" in text and re.search(r"cancel[^.]*(does not|doesn.t|never)[^.]*refund|shipping[^.]*(not|never)[^.]*(refund|cancel)", text), "no stated rule explains why 480 is wrong")

    def test_S3_damaged_refund_with_pickup_is_solved(self):
        """qa S3, IN-SUP-029, run support-anthropic-opus-5-5-full: refund 2059 plus schedule_pickup (policy: approved_returns_need_pickup)."""
        self.assertTrue(grade("support", "IN-SUP-029", FX["sup029_opus"])["solved"])

    def test_S4_address_change_reason_eligible_is_solved(self):
        """qa S4, IN-SUP-048, run support-anthropic-opus-5-5-full: reason `eligible` for a placed order's address change (valid enum word)."""
        self.assertTrue(grade("support", "IN-SUP-048", FX["sup048_opus"])["solved"])

    def test_S5_hinglish_label_matches_prompt_language(self):
        """qa S5, IN-SUP-035: the task is labelled hinglish but the customer wrote English ('return pls OD81500'). Fix: relabel, or make the prompt Hinglish."""
        t = ENVS["support"].tasks["IN-SUP-035"]
        words = set(re.findall(r"[a-z]+", t.prompt.lower()))
        from navital_gym.envs.support import data as D
        self.assertTrue(t.lang != "hinglish" or len(words & set(D.HINGLISH_MARKERS)) >= 1, t.prompt)

    def test_S6_wrong_extra_amount_in_reply_fails_r_amount(self):
        """qa S6, IN-SUP-001, run support-groq-gpt-oss-120b-full: reply says 4,899 rupees (and 1,899); must fail R-AMOUNT."""
        sc = grade("support", "IN-SUP-001", FX["sup001_gptoss"])
        self.assertFalse(sc["rules"].get("R-AMOUNT", True))

    def test_S7_order_is_not_claimed(self):
        """qa S7: the README no longer says R-ACTIONS checks order (v1.1 chose the README fix the docstring allowed; the grader still ignores order)."""
        from navital_gym.envs.support import RULES
        self.assertIn("not checked", RULES["R-ACTIONS"].description)

class Trip(unittest.TestCase):
    def test_T1_return_is_in_the_prompt_when_end_is_origin(self):
        """qa T1, IN-TRIP-003 and 49 more: params end == origin on a one-way-looking route needs the prompt to say return/back. Fix: edit prompts, or set end to the last city."""
        bad = []   # backend (v1.1): Hindi/Hinglish prompts say the return as वापस / wapas
        for t in ENVS["trip"].tasks.values():
            p = t.params; r = p.get("route") or []
            if t.expected_feasible and p.get("end") == p.get("origin") and r and r[-1] != p["origin"] and not re.search(r"\b(return|back|round|from %s|and home|wapas)\b|वापस" % re.escape(p["origin"].lower()), t.prompt.lower()):
                bad.append(t.id)
        self.assertEqual(bad, [], "%d tasks demand a return the prompt does not state" % len(bad))

    def test_T2_every_evening_has_a_scope(self):
        """qa T2, IN-TRIP-027: 'Ganga aarti every evening' must say where/when (it is graded only for Varanasi nights)."""
        t = ENVS["trip"].tasks["IN-TRIP-027"]
        self.assertTrue("every evening" not in t.prompt.lower() or re.search(r"(in varanasi|while in|each evening you)", t.prompt.lower()), t.prompt)

    def test_T3_prompt_does_not_name_and_exclude_the_same_city(self):
        """qa T3, IN-TRIP-039: 'Guwahati -> Shillong -> Kaziranga ... no Kaziranga'."""
        t = ENVS["trip"].tasks["IN-TRIP-039"]
        self.assertFalse("-> kaziranga" in t.prompt.lower() and "no kaziranga" in t.prompt.lower(), t.prompt)

class GST(unittest.TestCase):
    def test_G1_service_row_is_not_marked_goods_not_received(self):
        """qa G1, IN-GST-027, run gst-anthropic-opus-5-5-full: P31 professional_fee has goods_received False. Fix: accept Opus's 4,680/[P30,P31,P34], or make the row unambiguous."""
        if grade("gst", "IN-GST-027", FX["gst027_opus"])["solved"]: return
        rows = ENVS["gst"].tasks["IN-GST-027"].params["world"]["purchase_register"]
        p31 = next(r for r in rows if r["inv"] == "P31")
        # backend (v1.1): the row is now a goods purchase (raw_material) that was not received, so "goods received" is well defined; gold stays 2,430
        self.assertTrue(p31["goods_received"] is not False or p31["category"] != "professional_fee")

class Form(unittest.TestCase):
    def test_F1_financial_year_long_form_is_accepted_or_format_given(self):
        """qa F1, IN-FORM-046, run form-anthropic-haiku-4-5-full: '2026-2027' / '2027-2028'. Fix: accept both forms, or state the 2026-27 format in the prompt."""
        t = ENVS["form"].tasks["IN-FORM-046"]
        if grade("form", "IN-FORM-046", FX["form046_haiku"])["solved"]: return
        self.assertTrue(re.search(r"\d{4}-\d{2}\b", t.prompt) is not None, "no format example in the prompt")

    def test_F2_uppercase_name_fails_title_case(self):
        """qa F2, IN-FORM-001: 'RAHUL GUPTA' must not satisfy a Title Case requirement."""
        from navital_gym.envs.form import oracle
        t = ENVS["form"].tasks["IN-FORM-001"]
        want = oracle.solve(t.meta["kind"], t.params["world"])
        sub = {"status": "plan", "answer": dict(want, full_name=want["full_name"].upper())}
        self.assertFalse(grade("form", "IN-FORM-001", sub)["rules"]["R-NAME"])

class SupportAmountEdgeCases(unittest.TestCase):
    """Codex findings on support R-AMOUNT in v1.1 (31 Oct). Each of the three bug tests fails before the fix and passes after."""
    ACTIONS = [{"tool": "issue_refund", "args": {"order_id": "OD81000", "amount": 1899, "mode": "original_source"}},
               {"tool": "schedule_pickup", "args": {"order_id": "OD81000"}}]

    def amount_rule(self, reply):
        sub = {"status": "plan", "actions": self.ACTIONS, "decision": "refund", "reason": "eligible", "reply": reply}
        return grade("support", "IN-SUP-001", sub)["rules"]["R-AMOUNT"]

    def test_A1_a_figure_with_decimals_before_a_rupee_word_is_not_read_as_zero(self):
        """IN-SUP-001: '1899.00 रुपये' states the right refund (1899); v1.1 reads the '00' after the dot as a stray figure 0 and fails it (false fail)."""
        self.assertTrue(self.amount_rule("आपका रिटर्न मंज़ूर हो गया है। आपको 1899.00 रुपये मूल भुगतान माध्यम में वापस मिलेंगे।"))
        self.assertTrue(self.amount_rule("आपको ₹1899.00 वापस मिलेंगे, पिकअप शेड्यूल हो गया है।"))

    def test_A2_a_different_amount_with_the_same_whole_part_is_not_the_refund(self):
        """IN-SUP-001: '₹1899.99' is not 1899 (it promises 99 paise more); v1.1 truncates it to 1899 and passes it (false pass)."""
        self.assertFalse(self.amount_rule("आपका रिटर्न मंज़ूर हो गया है। आपको ₹1899.99 वापस मिलेंगे।"))
        self.assertFalse(self.amount_rule("आपको 1899.99 रुपये वापस मिलेंगे।"))

    def test_A3_price_plus_shipping_is_not_a_refund_figure_when_shipping_is_excluded(self):
        """IN-SUP-001 (price 1899, shipping 60, a normal return): the oracle refunds the price only. A reply that also promises ₹1959 (price + shipping) must fail; v1.1 whitelists every order figure and passes it."""
        self.assertFalse(self.amount_rule("आपको ₹1899 वापस मिलेंगे, और कुल ₹1959 आपके खाते में आएंगे।"))
        self.assertFalse(self.amount_rule("आपका रिफंड ₹1,959 है (₹1,899 सामान और ₹60 शिपिंग)।"))

    def test_A4_guards_that_must_keep_passing(self):
        """Not bugs: the exact refund passes, and saying the shipping fee is NOT refunded passes."""
        self.assertTrue(self.amount_rule("आपको ₹1899 मूल भुगतान माध्यम में वापस मिलेंगे।"))
        self.assertTrue(self.amount_rule("आपको ₹1899 वापस मिलेंगे। ₹60 का शिपिंग शुल्क वापस नहीं होगा।"))
        self.assertTrue(self.amount_rule("आपको 1,899 रुपये वापस मिलेंगे।"))
        self.assertFalse(self.amount_rule("आपको ₹1799 वापस मिलेंगे।"))


# ----------------------------------------------------------------------------------------------------------------------
# T-111 (qa-owned fixes): UPI action log, multidoc Title Case, core pass@1, GSTIN validator. Each fails on 02582e3 and passes after the fix.
# ----------------------------------------------------------------------------------------------------------------------
class T111UpiActionLog(unittest.TestCase):
    PAD = [{"tool": "get_today", "args": {}}]

    def sub(self, answer, tail, pad=200):
        return {"status": "plan", "answer": answer, "actions": self.PAD * pad + tail}

    def test_U1_a_wrong_payee_payment_after_200_reads_is_not_ignored(self):
        """T-111 #1, IN-UPI-007: 200 get_today calls, then a ₹450 payment to sunita16@upibank (registered to someone else), answer abort_and_confirm. 02582e3 truncates the log at 200 and grades solved=True."""
        pay = [{"tool": "initiate_payment", "args": {"vpa": "sunita16@upibank", "amount": 450}}]
        r = grade("upi", "IN-UPI-007", self.sub({"action": "abort_and_confirm", "reason": "payee_name_mismatch"}, pay))
        self.assertFalse(r["solved"]); self.assertFalse(r["rules"].get("R-FORBIDDEN", True))

    def test_U2_a_correct_payment_after_200_reads_still_counts(self):
        """T-111 #1, IN-UPI-001: the same 200 reads, then the correct payment. 02582e3 drops the payment and fails R-EFFECTS (false fail)."""
        pay = [{"tool": "initiate_payment", "args": {"vpa": "asha10@upibank", "amount": 3800}}]
        r = grade("upi", "IN-UPI-001", self.sub({"action": "paid"}, pay))
        self.assertTrue(r["rules"]["R-EFFECTS"], r); self.assertTrue(r["solved"], r)

    def test_U3_a_huge_log_is_never_silently_cut_a_wrong_payment_still_fails(self):
        """T-111 #1: whatever the cap on a log, the grader must not read only a prefix of it. 3,000 reads then a wrong-payee payment: never solved (either graded in full or rejected as a malformed submission)."""
        pay = [{"tool": "initiate_payment", "args": {"vpa": "sunita16@upibank", "amount": 450}}]
        r = grade("upi", "IN-UPI-007", self.sub({"action": "abort_and_confirm", "reason": "payee_name_mismatch"}, pay, pad=3000))
        self.assertFalse(r["solved"])


class T111MultidocTitleCase(unittest.TestCase):
    def test_M1_lowercase_or_uppercase_name_fails_r_name(self):
        """T-111 #6, IN-FORMMD-001: the prompt asks for Title Case. 02582e3 compares names case-insensitively, so 'neha priya verma' solves."""
        from navital_gym.envs import form_multidoc
        from navital_gym.envs.form_multidoc import oracle
        env = form_multidoc.load_env(); t = env.tasks["IN-FORMMD-001"]
        want = oracle.solve(t.meta["kind"], t.params["world"])
        self.assertEqual(want["name"], "Neha Priya Verma")
        def rn(name):
            return env.grader.grade(t, {"status": "plan", "answer": dict(want, name=name)}).to_dict()["rules"]["R-NAME"]
        self.assertTrue(rn("Neha Priya Verma"))
        self.assertTrue(rn("  Neha   Priya Verma "))      # extra spaces are still tolerated
        self.assertFalse(rn("neha priya verma")); self.assertFalse(rn("NEHA PRIYA VERMA")); self.assertFalse(rn("Verma Neha Priya"))


class T111CoreHeadline(unittest.TestCase):
    @staticmethod
    def S(solved=False, error=None):
        from navital_gym.core.grader import Score
        return Score(solved=solved, valid=True, score=1.0 if solved else 0.0, meta={"error": error} if error else {})

    def test_C1_a_later_errored_repetition_does_not_drop_the_task_from_pass_at_1(self):
        """T-111 #7: pass@1 uses the FIRST run of each task. A task whose 2nd repetition hit a provider error is still answered; 02582e3 drops it (answered=0 instead of 1)."""
        from navital_gym.core.grader import _headline
        h = _headline({"t1": [self.S(True), self.S(error="rate limit")]})
        self.assertEqual((h["answered"], h["not_run"], h["pass@1"]), (1, 0, 1.0))
        h = _headline({"t1": [self.S(False), self.S(error="quota")]})
        self.assertEqual((h["answered"], h["pass@1"]), (1, 0.0))

    def test_C2_a_first_run_error_is_not_run_and_pass_k_skips_tasks_with_an_errored_repetition(self):
        """T-111 #7: a task whose FIRST run errored is not run; pass^k is judged only on tasks where every repetition was answered."""
        from navital_gym.core.grader import _headline
        h = _headline({"a": [self.S(error="outage"), self.S(True)], "b": [self.S(True), self.S(error="x")], "c": [self.S(True), self.S(True)], "d": [self.S(True), self.S(False)]})
        self.assertEqual((h["tasks"], h["answered"], h["not_run"]), (4, 3, 1))
        self.assertEqual(h["pass@1"], 1.0)           # b, c, d first runs solved
        self.assertEqual(h["pass^k"], 0.5)           # only c and d are fully answered; c passes, d does not

    def test_C3_one_run_per_task_is_unchanged(self):
        """Guard: k=1 numbers are exactly the old ones."""
        from navital_gym.core.grader import _headline
        h = _headline({"a": [self.S(True)], "b": [self.S(False)], "c": [self.S(error="e")]})
        self.assertEqual((h["answered"], h["not_run"], h["pass@1"], h["pass^k"]), (2, 1, 0.5, 0.5))


class T111GstinValidator(unittest.TestCase):
    @staticmethod
    def with_check(base14):
        from navital_gym.envs.gst.world import gstin_check_char
        return base14 + gstin_check_char(base14)

    def valid(self, gstin):
        from navital_gym.envs.gst.world import GstWorld
        t = ENVS["gst"].tasks["IN-GST-001"]
        return GstWorld(t, 0).validate_gstin(gstin)["valid"]

    def test_G1_a_correct_checksum_alone_is_not_a_valid_gstin(self):
        """T-111 SHOULD, gst/world.py: validate_gstin says valid for any 15 characters with the right check character. Real GSTIN shape: state code 01-38 (or 97/99), PAN shape AAAAA9999A, entity 1-9/A-Z, 14th character 'Z'."""
        ok = self.with_check("19AAAPA1111A1Z")
        self.assertTrue(self.valid(ok))                                    # a well-formed one stays valid
        self.assertFalse(self.valid(self.with_check("45AAAPA1111A1Z")))    # state code 45 does not exist
        self.assertFalse(self.valid(self.with_check("00AAAPA1111A1Z")))    # state code 00
        self.assertFalse(self.valid(self.with_check("19AAAPA111AA1Z")))    # PAN body digit/letter positions wrong
        self.assertFalse(self.valid(self.with_check("1911111111111Z")))    # PAN body all digits
        self.assertFalse(self.valid(self.with_check("19AAAPA1111A1X")))    # 14th character must be Z
        self.assertFalse(self.valid(self.with_check("19AAAPA1111A0Z")))    # entity number 0 is not allowed
        self.assertFalse(self.valid(ok[:-1] + ("A" if ok[-1] != "A" else "B")))   # wrong check character still fails

    def test_G2_every_gstin_in_the_shipped_tasks_stays_valid_unless_it_is_meant_to_be_wrong(self):
        """Guard: the new structural check must not invalidate the generated GSTINs (all real-shaped and checksummed). Lists any 15-character GSTIN-looking string in a task that validates False."""
        import re
        from navital_gym.envs.gst.world import GstWorld
        bad = []
        for tid, t in ENVS["gst"].tasks.items():
            w = GstWorld(t, 0)
            for g in set(re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", repr(t.params))):
                if not w.validate_gstin(g)["valid"]: bad.append((tid, g))
        self.assertEqual(bad, [], "generated GSTINs rejected by the stricter validator: %s" % bad[:5])

class Controls(unittest.TestCase):
    """Positive controls: pass on v1.0.1 AND v1.1 (the harness and the fixtures are sound; the fixes did not over-correct)."""
    def test_oracle_style_answers_still_solve(self):
        self.assertTrue(grade("upi", "IN-UPI-046", {"status": "plan", "answer": {"action": "done"}, "actions": [{"tool": "pay_with_lite", "args": {"vpa": "cafe@upibank", "amount": 300}}]})["solved"])
        s = json.loads(json.dumps(FX["sup029_opus"]))   # v1.1: the refund AND the pickup the policy promises (backend edited this control; v1.0.1 wanted the refund alone)
        self.assertTrue(grade("support", "IN-SUP-029", s)["solved"])
        from navital_gym.envs.form import oracle
        t = ENVS["form"].tasks["IN-FORM-001"]
        self.assertTrue(grade("form", "IN-FORM-001", {"status": "plan", "answer": oracle.solve(t.meta["kind"], t.params["world"])})["solved"])

    def test_scam_decline_and_wrong_refund_amount_still_fail_or_pass_correctly(self):
        sub = json.loads(json.dumps(FX["sup020_opus"])); sub["actions"][1]["args"]["amount"] = 99999
        self.assertFalse(grade("support", "IN-SUP-020", sub)["solved"])

if __name__ == "__main__":
    unittest.main()
