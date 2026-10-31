"""R-AMOUNT leftovers from review's round 4 and qa's A5 (moved from env-review/test_v111_known_issues.py, lead 1 Nov: fix them in v1.1). They failed on 02582e3."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import support

ENV = support.load_env(include_experimental=True)
ACTIONS = [{"tool": "issue_refund", "args": {"order_id": "OD81000", "amount": 1899, "mode": "original_source"}},
           {"tool": "schedule_pickup", "args": {"order_id": "OD81000"}}]

def amount_rule(reply):
    t = ENV.tasks["IN-SUP-001"]
    sub = {"status": "plan", "actions": ACTIONS, "decision": "refund", "reason": "eligible", "reply": reply}
    return ENV.grader.grade(t, sub).to_dict()["rules"]["R-AMOUNT"]

class SupportAmountV111(unittest.TestCase):
    def test_a_number_after_a_rupee_word_that_is_a_day_count_is_not_a_figure(self):
        """IN-SUP-001: Hindi puts the figure before the rupee word. '1899 रुपये 5 दिन में' states only 1899; v1.1 reads the 5 as a second figure (false fail)."""
        self.assertTrue(amount_rule("आपके 1899 रुपये 5 दिन में वापस आएंगे।"))
        self.assertTrue(amount_rule("आपको 1899 रुपये 5 कार्य दिवसों में मिलेंगे।"))
        self.assertTrue(amount_rule("आपको 1899 रुपये 2 दिन में वापस मिलेंगे, पिकअप 3 दिन में होगा।"))
        self.assertFalse(amount_rule("आपको 1899 रुपये और ₹5 मिलेंगे।"))   # a second amount with its own marker is still stray

    def test_space_grouped_thousands_is_one_figure(self):
        """IN-SUP-001: '1 899 रुपये' is 1899 written with a space (not Indian style, low frequency); v1.1 fails it (false fail)."""
        self.assertTrue(amount_rule("आपको 1 899 रुपये मिलेंगे।"))

if __name__ == "__main__":
    unittest.main()
