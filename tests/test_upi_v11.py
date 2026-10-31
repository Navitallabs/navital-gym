"""v1.1 UPI changes. Lite payee and the dead policy key were found by backend's audit (backend.md); the test names say what v1.0.1 did."""
import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.upi import load_env, load_tasks, grade
from navital_gym.envs.upi.world import UpiWorld

ENV = load_env(splits=("core", "easy"))

class Lite(unittest.TestCase):
    """v1.0.1: pay_with_lite had no payee, so a payment to the wrong merchant could not be told from the right one."""
    def sub(self, vpa):
        return {"status": "plan", "answer": {"action": "done"}, "actions": [{"tool": "pay_with_lite", "args": {"vpa": vpa, "amount": 300}}]}

    def test_right_payee_solves(self):
        self.assertTrue(grade(_task("IN-UPI-046"), self.sub("cafe@upibank"))["solved"])

    def test_wrong_or_unknown_payee_fails(self):
        self.assertFalse(grade(_task("IN-UPI-046"), self.sub("someone@else"))["solved"])

    def test_the_tool_requires_a_vpa_from_the_directory(self):
        ENV.reset("IN-UPI-046")
        self.assertIn("error", json.dumps(ENV.world.call("pay_with_lite", {"vpa": "nobody@x", "amount": 100})).lower())

class Policy(unittest.TestCase):
    def test_no_task_policy_shows_the_unenforced_daily_limit_verified(self):
        for t in load_tasks(splits=("core", "easy")):
            self.assertNotIn("daily_limit_verified", t.params["rules"], t.id)

class Collect(unittest.TestCase):
    def test_core_collect_family_has_decline_and_approve(self):
        from navital_gym.envs.upi import oracle
        acts = [oracle.expected("collect_request", t.params)["answer"]["action"] for t in load_tasks() if t.meta["kind"] == "collect_request"]
        self.assertEqual(sorted(set(acts)), ["approved", "declined_and_reported"])
        self.assertEqual(acts.count("approved"), 1)

def _task(tid):
    return next(t for t in load_tasks(splits=("core", "easy")) if t.id == tid).to_dict()

if __name__ == "__main__":
    unittest.main()
