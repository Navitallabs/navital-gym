import importlib.util, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

@unittest.skipUnless(importlib.util.find_spec("inspect_ai"), "inspect-ai not installed")
class InspectAdapter(unittest.TestCase):
    def test_tool_call_then_oracle_plan_is_scored_solved_and_a_wrong_answer_is_not(self):
        from inspect_ai import eval as ieval
        from inspect_ai.model import get_model, ModelOutput
        from navital_gym.adapters.inspect_task import navital_task
        from navital_gym.envs.trip import load_env
        from navital_gym.envs.trip.solver import Solver
        env = load_env(); tid = "IN-TRIP-002"
        plan = Solver(env.tasks[tid]).solve()
        for final, want in ((json.dumps(plan), "C"), ("no idea", "I")):
            outs = [ModelOutput.for_tool_call("mockllm/model", "calendar_info", {}), ModelOutput.from_content("mockllm/model", final)]
            log = ieval(navital_task("trip", [tid]), model=get_model("mockllm/model", custom_outputs=outs), log_dir="/tmp/navital-inspect-test-logs", display="none")[0]
            self.assertEqual(log.status, "success")
            self.assertEqual(log.samples[0].scores["navital_grader"].value, want)

    def test_model_input_has_no_hidden_fields(self):
        from navital_gym.adapters.inspect_task import navital_task
        from navital_gym.core import leak
        from navital_gym.envs.trip import load_env
        env = load_env()
        for s in navital_task("trip").dataset:
            self.assertEqual(leak.leaks_in_observation(env.tasks[s.id], {"prompt": s.input, "tools": []}), [], s.id)
            self.assertNotIn("expected_feasible", json.dumps(s.metadata))

if __name__ == "__main__":
    unittest.main()
