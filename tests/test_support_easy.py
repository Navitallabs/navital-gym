"""Support Desk easy split (qa): 18 one-decision Hinglish tasks, loaded only on request, graded by the same grader."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import support
from navital_gym.core.runner import run_suite

EASY = support.load_env(splits=("easy",))

class T(unittest.TestCase):
    def test_default_load_is_unchanged_and_easy_is_opt_in(self):
        self.assertEqual(len(support.load_env().tasks), 50)
        self.assertEqual(len(support.load_env(include_experimental=True).tasks), 76)
        self.assertEqual(len(EASY.tasks), 18)
        self.assertEqual(len(support.load_env(include_experimental=True, splits=("core", "easy")).tasks), 94)
        self.assertEqual(sorted(EASY.tasks), [f"IN-SUP-E{i:02d}" for i in range(1, 19)])
        self.assertTrue(all(t.meta["split"] == "easy" and t.lang == "hinglish" for t in EASY.tasks.values()))

    def test_stored_gold_matches_the_independent_oracle(self):
        self.assertEqual(support.check_gold(list(EASY.tasks.values())), [])

    def test_reference_solver_solves_all_and_the_floors_stay_low(self):
        b = support.get_baselines()
        self.assertEqual(run_suite(EASY, b["oracle"])["summary"]["pass@1"], 1.0)
        for name in ("empty", "noop_lang", "refund_all", "english"):
            self.assertLess(run_suite(EASY, b[name])["summary"]["pass@1"], 0.25, name)

    def test_one_short_rule_per_task(self):
        for t in EASY.tasks.values():
            env = support.load_env(splits=("easy",)); env.reset(t.id)
            keys = [k for k in env.world.call("get_policy")["policy"] if k not in ("approved_returns_need_pickup", "customer_cancel_refund", "actions_you_may_list", "today")]
            self.assertLessEqual(len(keys), 2, (t.id, keys))        # the trimmed policy holds only what the task needs

    def test_nothing_hidden_in_prompt_or_tools(self):
        from navital_gym.core import leak
        for t in EASY.tasks.values():
            self.assertEqual(leak.leaks_in_observation(t, EASY.reset(t.id)), [], t.id)

if __name__ == "__main__":
    unittest.main()
