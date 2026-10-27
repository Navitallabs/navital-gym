"""GST standard prompts name the answer fields the grader scores; the easy prompts (which already say "Answer field: x") are unchanged."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.gst import load_env, INSTRUCTIONS
from navital_gym.envs.gst.rules import FIELDS

class GstAnswerFields(unittest.TestCase):
    def test_every_scored_field_is_named_in_a_standard_prompt(self):
        env = load_env()
        for tid, t in env.tasks.items():
            prompt = env.reset(tid)["prompt"]
            kind = t.meta["kind"]
            want = [f for _, f in FIELDS[kind]] if kind in FIELDS else ["eligible" if "R-ELIGIBLE" in t.rules else "required"]
            for f in want: self.assertIn(f, prompt, f"{tid}: scored field {f!r} is not named in the prompt")

    def test_easy_prompts_are_exactly_as_before(self):
        env = load_env(splits=("easy",))
        for tid, t in env.tasks.items():
            self.assertEqual(env.reset(tid)["prompt"], t.prompt + "\n\n" + INSTRUCTIONS)

    def test_the_prompt_does_not_leak_a_hidden_field_or_the_answer(self):
        from navital_gym.core import leak
        env = load_env()
        for tid, t in env.tasks.items():
            obs = env.reset(tid)
            self.assertEqual(leak.leaks_in_observation(t, obs), [])
            for v in (t.meta["gold_answer"] or {}).values(): self.assertNotIn(f'"{v}"', obs["prompt"]) if isinstance(v, str) and len(v) > 5 else None

if __name__ == "__main__":
    unittest.main()
