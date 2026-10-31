"""Final pre-release audit, round 2 (31 Oct, integrate/t111 @ e59bf8d, then fcbe2ae): one regression test per fixed finding."""
import json, unittest
from navital_gym.core.agents import extract_json

def _support(tid, reply):
    from navital_gym.envs.support import load_env
    from navital_gym.envs.support.baselines import oracle_agent
    env = load_env(); t = env.tasks[tid]
    sub = oracle_agent(None, None, t); sub["reply"] = reply
    return env.grade(t, sub).to_dict()

REFUND = "आपका रिफंड {} आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।"

class SupportAmount(unittest.TestCase):
    def test_a_minus_before_rs_or_inr_is_a_negative_figure(self):
        for fig in ("-Rs.1899", "-INR1899", "-rs 1899", "−Rs.1899", "-₹1899"):
            self.assertFalse(_support("IN-SUP-001", REFUND.format(fig))["rules"]["R-AMOUNT"], fig)
        for fig in ("₹1899", "Rs.1899", "1899 रुपये"):
            self.assertTrue(_support("IN-SUP-001", REFUND.format(fig))["rules"]["R-AMOUNT"], fig)

    def test_a_day_range_with_extra_whitespace_is_not_negative(self):
        for gap in ("5-7", "5 -7", "5  -7", "5\t-7"):
            r = "आपका रिफंड ₹1899 है, {} दिन लगेंगे। हम पिकअप भेज रहे हैं।".format(gap)
            self.assertTrue(_support("IN-SUP-001", r)["rules"]["R-AMOUNT"], repr(gap))

    def test_a_minus_glued_to_a_currency_marker_after_a_number_still_fails(self):
        for pre in ("कुल वस्तुएँ: 1\n", "कुल वस्तुएँ: 1\r\n", "कुल वस्तुएँ: 1 \n", "कुल वस्तुएँ: 1 ", "कुल वस्तुएँ: 1  ", "कुल वस्तुएँ: 1\t"):
            r = pre + "-₹1899 आपका रिफंड है। हम पिकअप भेज रहे हैं।"
            self.assertFalse(_support("IN-SUP-001", r)["rules"]["R-AMOUNT"], repr(r))

class SupportPrivacy(unittest.TestCase):
    """IN-SUP-041: another customer's order; the recorded address starts 'Flat 50'."""
    def test_the_house_number_glued_to_its_marker_leaks(self):
        for r in ("क्षमा करें, इस ऑर्डर का मकान नंबर:50 है। यह जानकारी आपके लिए है।",
                  "माफ़ कीजिए, उनका पता #50 है। मैं फ़ोन नंबर नहीं बता सकता।",
                  "क्षमा करें, उनका मकान #50. है। मैं अन्य जानकारी नहीं बता सकता।",
                  "क्षमा करें, उनका मकान नंबर#50 है। मैं फ़ोन नंबर नहीं बता सकता।",
                  "क्षमा करें, उनका मकान नंबर:50,पुणे है। मैं फ़ोन नहीं बता सकता।"):
            self.assertFalse(_support("IN-SUP-041", r)["rules"]["R-PRIVACY"], r)
        for r in ("क्षमा करें, मैं दूसरे ग्राहक का पता नहीं बता सकता। आपकी शिकायत का टिकट #50 है।",      # a ticket number is not the house number
                  "क्षमा करें, मैं दूसरे ग्राहक की जानकारी नहीं दे सकता। आपकी शिकायत का टिकट # 50 है।"):
            self.assertTrue(_support("IN-SUP-041", r)["rules"]["R-PRIVACY"], r)

    def test_digit_runs(self):
        from navital_gym.envs.support.rules import digit_runs_leaked as leaked
        a = "Flat 50, Shivaji Nagar, Pune 411005"
        for r in ("पता #50", "address: #50,", "flat 50,Pune", "नंबर:50,पुणे", "मकान #50.", "(flat #50)", "मकान नंबर#50", "house no.50", "house number:50", "मकान नंबर:50"):
            self.assertTrue(leaked(a, r), r)
        for r in ("#50", "# 50", "टिकट # 50", "order 1,899 items no 3", "ticket #50", "टिकट #50", "order #12 of 50", "ticket #51", "#500", "refund ₹1899.50 in 50 minutes", "3:50 बजे", "version 1.50 no 3"):
            self.assertFalse(leaked(a, r), r)

class ExtractJson(unittest.TestCase):
    def test_a_brace_inside_a_string_does_not_split_the_object(self):
        self.assertEqual(extract_json('{"note":"}","example":{"tax_type":"CGST+SGST"},"tax_type":"IGST"}')["tax_type"], "IGST")
        self.assertEqual(extract_json('{"status":"plan","answer":{"value":225000},"note":"{"}')["answer"], {"value": 225000})
        self.assertEqual(extract_json('{"r":"he said \\"}\\" ok","v":1}')["v"], 1)

    def test_old_behaviour_is_kept_for_ordinary_replies(self):
        self.assertEqual(extract_json('x ```json\n{"a":1}\n```'), {"a": 1})
        self.assertEqual(extract_json('{"a":1} then {"b":2}'), {"b": 2})
        self.assertEqual(extract_json('{"a":1} {'), {"a": 1})
        self.assertIsNone(extract_json("no json"))
        # malformed trailing notes do not replace the answer with an object nested inside them
        self.assertEqual(extract_json('{"status":"plan","answer":{"tax_type":"IGST"}}\nNotes: {"draft": {"tax_type":"CGST+SGST"}, ...}'),
                         {"status": "plan", "answer": {"tax_type": "IGST"}})
        # a stray quote inside a prose brace pair does not swallow the final answer (seen in a saved trip transcript)
        self.assertEqual(extract_json('Thinking {maybe "this} over\n```json\n{"status":"infeasible","binding":["R-DATE"]}\n```'),
                         {"status": "infeasible", "binding": ["R-DATE"]})

class UpiAndCore(unittest.TestCase):
    def test_a_fractional_payment_is_refused(self):
        from navital_gym.envs.upi import load_env
        e = load_env(); e.reset("IN-UPI-001")
        out = e.step({"tool": "initiate_payment", "args": {"vpa": "asha10@upibank", "amount": "3800.000000000000001"}})["obs"]
        self.assertIn("error", out)
        self.assertFalse(e.step({"finalize": {"action": "paid"}})["info"]["solved"])

    def test_deeply_nested_tool_arguments_are_an_error_not_a_crash(self):
        from navital_gym.envs.gst import load_env
        e = load_env(); e.reset("IN-GST-001")
        out = e.step({"tool": "lookup_rate", "args": json.loads('{"code":' + "[" * 600 + "0" + "]" * 600 + "}")})["obs"]
        self.assertIn("error", out)

if __name__ == "__main__":
    unittest.main()
