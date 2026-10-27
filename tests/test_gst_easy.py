"""GST Desk easy split (qa): 18 one-rule tasks, loaded only on request, graded by the same grader."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import gst

EASY = gst.load_env(splits=("easy",))

class T(unittest.TestCase):
    def test_default_load_is_unchanged_and_easy_is_opt_in(self):
        self.assertEqual(len(gst.load_env().tasks), 50)
        self.assertEqual(len(EASY.tasks), 18)
        self.assertEqual(len(gst.load_env(splits=("core", "easy")).tasks), 68)
        self.assertEqual(sorted(EASY.tasks), [f"IN-GST-E{i:02d}" for i in range(1, 19)])
        self.assertTrue(all(t.meta["split"] == "easy" for t in EASY.tasks.values()))
        self.assertFalse(any(t.meta["split"] == "easy" for t in gst.load_env().tasks.values()))

    def test_stored_gold_matches_the_independent_oracle(self):
        self.assertEqual(gst.check_gold(list(EASY.tasks.values())), [])

    def test_gold_scores_one_and_each_single_field_error_fails_one_rule(self):
        for t in EASY.tasks.values():
            gold = dict(t.meta["gold_answer"])
            r = EASY.contract_grade(t.to_dict(), {"status": "plan", "answer": gold})
            self.assertTrue(r["solved"], t.id)
            for k, v in gold.items():
                bad = dict(gold); bad[k] = (not v) if isinstance(v, bool) else ("x" if isinstance(v, str) and not v.replace(".", "").isdigit() else (v + 1 if isinstance(v, int) else str(float(v) + 1)))
                rb = EASY.contract_grade(t.to_dict(), {"status": "plan", "answer": bad})
                self.assertFalse(rb["solved"], (t.id, k))
                self.assertEqual(len([x for x, ok in rb["rules"].items() if not ok]), 1, (t.id, k))

    def test_one_short_rule_per_task_and_no_lookup_crash(self):
        for t in EASY.tasks.values():
            env = gst.load_env(splits=("easy",)); env.reset(t.id)
            pol = env.world.call("get_policy")["policy"]
            self.assertIn("rule", pol, t.id)
            self.assertLess(len(str(pol)), 420, t.id)                    # a short policy
            self.assertIn("error", env.world.call("lookup_rate", {"code": "G-ELEC"}))   # trimmed rules must not crash the tool

    def test_nothing_hidden_in_prompt_or_tools(self):
        from navital_gym.core import leak
        for t in EASY.tasks.values():
            obs = EASY.reset(t.id); self.assertEqual(leak.leaks_in_observation(t, obs), [], t.id)

if __name__ == "__main__":
    unittest.main()
