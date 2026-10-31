"""T-111 (Daksh's Codex pass): an adapter must grade what the rollout EXECUTED, not what the final answer CLAIMS. On IN-UPI-001 (pay Rs 3800 to asha10@upibank):
a payment made through the tools earns credit whatever the final JSON lists; a claimed `actions` list without the tool call earns none. Written before the fix:
the Inspect and verifiers cases fail on 02582e3. Skipped when the adapter's library is not installed."""
import importlib.util, json, os, sys, types, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

PAY = {"vpa": "asha10@upibank", "amount": 3800}
HONEST = json.dumps({"status": "plan", "answer": {"action": "paid"}})                                   # no actions list: the log is the evidence
CLAIM = json.dumps({"status": "plan", "answer": {"action": "paid"}, "actions": [{"tool": "initiate_payment", "args": PAY}]})   # a claim, nothing executed

@unittest.skipUnless(importlib.util.find_spec("inspect_ai"), "inspect-ai not installed")
class Inspect(unittest.TestCase):
    def score(self, outputs):
        from inspect_ai import eval as ieval
        from inspect_ai.model import get_model
        from navital_gym.adapters.inspect_task import navital_task
        log = ieval(navital_task("upi", ["IN-UPI-001"]), model=get_model("mockllm/model", custom_outputs=outputs), log_dir="/tmp/navital-inspect-trusted-logs", display="none")[0]
        self.assertEqual(log.status, "success")
        return log.samples[0].scores["navital_grader"].value

    def test_an_executed_payment_is_credited_without_a_claimed_list(self):
        from inspect_ai.model import ModelOutput
        self.assertEqual(self.score([ModelOutput.for_tool_call("mockllm/model", "initiate_payment", PAY), ModelOutput.from_content("mockllm/model", HONEST)]), "C")

    def test_a_claimed_payment_that_was_never_executed_earns_nothing(self):
        from inspect_ai.model import ModelOutput
        self.assertEqual(self.score([ModelOutput.from_content("mockllm/model", CLAIM)]), "I")

    def test_a_claimed_list_cannot_replace_the_executed_one(self):
        """The model pays the wrong amount through the tool and claims the right one in the answer: the executed log decides."""
        from inspect_ai.model import ModelOutput
        wrong = dict(PAY, amount=1)
        self.assertEqual(self.score([ModelOutput.for_tool_call("mockllm/model", "initiate_payment", wrong), ModelOutput.from_content("mockllm/model", CLAIM)]), "I")

@unittest.skipUnless(importlib.util.find_spec("verifiers"), "verifiers not installed")
class Verifiers(unittest.TestCase):
    def grade(self, calls, final):
        from navital_gym.adapters.verifiers_env import NavitalTask
        msgs, results = [], []
        if calls:
            msgs.append(types.SimpleNamespace(tool_calls=[types.SimpleNamespace(id=f"c{i}", name=n, arguments=json.dumps(a)) for i, (n, a) in enumerate(calls)], content=""))
            results = [types.SimpleNamespace(tool_call_id=f"c{i}") for i in range(len(calls))]
        msgs.append(types.SimpleNamespace(tool_calls=None, content=final))
        trace = types.SimpleNamespace(last_reply=final, assistant_messages=msgs, tool_messages=results)
        return NavitalTask._grade(types.SimpleNamespace(data=types.SimpleNamespace(env_name="upi", id="IN-UPI-001")), trace)

    def test_a_call_without_a_tool_result_was_never_executed(self):
        """Security review: only calls with a matching tool result count; a call emitted in the final message, never run, earns nothing."""
        from navital_gym.adapters.verifiers_env import NavitalTask
        final = types.SimpleNamespace(tool_calls=[types.SimpleNamespace(id="late", name="initiate_payment", arguments=json.dumps(PAY))], content=HONEST)
        trace = types.SimpleNamespace(last_reply=HONEST, assistant_messages=[final], tool_messages=[])
        res = NavitalTask._grade(types.SimpleNamespace(data=types.SimpleNamespace(env_name="upi", id="IN-UPI-001")), trace)
        self.assertFalse(res["solved"])

    def test_an_executed_payment_is_credited_without_a_claimed_list(self):
        self.assertTrue(self.grade([("initiate_payment", PAY)], HONEST)["solved"])

    def test_a_claimed_payment_that_was_never_executed_earns_nothing(self):
        self.assertFalse(self.grade([], CLAIM)["solved"])

    def test_a_claimed_list_cannot_replace_the_executed_one(self):
        self.assertFalse(self.grade([("initiate_payment", dict(PAY, amount=1))], CLAIM)["solved"])

class OpenEnvControl(unittest.TestCase):
    """The OpenEnv session grades through env.step on its own live world: already trusted (kept as a guard)."""
    def test_executed_payment_counts_and_a_claim_does_not(self):
        from navital_gym.envs.upi import load_env
        env = load_env(); env.reset("IN-UPI-001")
        env.step({"tool": "initiate_payment", "args": PAY})
        self.assertTrue(env.step({"finalize": json.loads(HONEST)})["info"]["solved"])
        env.reset("IN-UPI-001")
        self.assertFalse(env.step({"finalize": json.loads(CLAIM)})["info"]["solved"])

if __name__ == "__main__":
    unittest.main()
