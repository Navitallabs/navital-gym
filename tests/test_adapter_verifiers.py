import asyncio, importlib.util, json, os, shutil, sys, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

HIDDEN = ("expected_feasible", "binding", "traps", "rules", "params")

def fake_openai(final_text):
    """Scripted OpenAI-compatible endpoint (stdlib, localhost, no network): call the first tool once with {}, then answer `final_text`."""
    log = []
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            log.append(body)
            if not any(m["role"] == "tool" for m in body["messages"]) and body.get("tools"):
                msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "index": 0,
                       "function": {"name": body["tools"][0]["function"]["name"], "arguments": "{}"}}]}; fr = "tool_calls"
            else:
                msg = {"role": "assistant", "content": final_text}; fr = "stop"
            usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            def chunk(delta, finish=None, choices=None):
                return "data: " + json.dumps({"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "fake",
                       "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if choices is None else choices, **({"usage": usage} if choices == [] else {})}) + "\n\n"
            b = "".join([chunk(msg), chunk({}, fr), chunk(None, choices=[]), "data: [DONE]\n\n"]).encode()
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, log

@unittest.skipUnless(importlib.util.find_spec("verifiers"), "verifiers not installed")
class VerifiersAdapter(unittest.TestCase):
    def test_builds_55_tasks_with_prompt_and_policy(self):
        from navital_gym.adapters.verifiers_env import load_environment
        from navital_gym.envs.trip import load_env
        env = load_environment("trip"); nav = load_env()
        tasks = list(env.taskset)
        self.assertEqual(len(tasks), 55)
        self.assertEqual({t.data.id for t in tasks}, set(nav.task_ids()))
        t = tasks[0]
        self.assertTrue(t.data.prompt.startswith(nav.tasks[t.data.id].prompt))
        self.assertTrue(t.data.prompt.endswith(nav.instructions))

    def test_no_hidden_field_reaches_the_model(self):
        from navital_gym.adapters.verifiers_env import load_environment
        from navital_gym.core import leak
        from navital_gym.envs.trip import load_env
        env = load_environment("trip"); nav = load_env()
        for t in env.taskset:
            data = json.loads(t.data.model_dump_json())
            for k in HIDDEN: self.assertNotIn(k, data, t.data.id)       # structurally absent from the task data (it rides on traces and to the tool server)
            tid = t.data.id; world = nav.make_world(nav.tasks[tid])
            self.assertEqual(leak.leaks_in_observation(nav.tasks[tid], {"prompt": t.data.prompt, "tools": world.tool_specs()}), [], tid)

    def test_reward_and_tool_wiring_unit_level(self):
        # no subprocess: the reward on a hand-made trace, and the world behind the toolset
        from navital_gym.adapters.verifiers_env import NavitalTaskset, NavitalConfig, NavitalToolset
        from navital_gym.envs.trip import load_env
        from navital_gym.envs.trip.solver import Solver
        nav = load_env(); tid = "IN-TRIP-002"
        task = list(NavitalTaskset(NavitalConfig(ids=[tid])))[0]
        class Tr:  # the only thing the reward reads
            def __init__(self, reply): self.last_reply = reply
        plan = Solver(nav.tasks[tid]).solve()
        ok = asyncio.run(task.navital_score(Tr("my plan:\n" + json.dumps(plan))))
        self.assertEqual(ok, 1.0)
        self.assertEqual(asyncio.run(task.solved(Tr(json.dumps(plan)))), 1.0)
        self.assertEqual(asyncio.run(task.navital_score(Tr(""))), 0.0)
        ts = NavitalToolset.__new__(NavitalToolset); ts.world = nav.make_world(nav.tasks[tid])
        names = [t.name for t in asyncio.run(ts.list_tools())]
        self.assertEqual(names, sorted(ts.world.tools()))
        out = asyncio.run(ts.call_tool("calendar_info", {}))
        self.assertFalse(out.is_error)
        self.assertTrue(asyncio.run(ts.call_tool("no_such_tool", {})).is_error)

    @unittest.skipUnless(shutil.which("uv"), "uv needed to launch verifiers' chat harness")
    def test_end_to_end_rollout_offline_with_scripted_model(self):
        """Real verifiers rollout: null chat harness in a local subprocess, a real per-rollout MCP tool-server subprocess, a scripted
        localhost model. Needs `uv` and its package cache (the harness is a uv script); makes no external network calls."""
        import verifiers.v1 as vf
        from verifiers.v1.clients import ModelContext
        from verifiers.v1.env import RunSlot
        from navital_gym.adapters.verifiers_env import load_environment
        from navital_gym.envs.trip import load_env
        from navital_gym.envs.trip.solver import Solver
        nav = load_env(); tid = "IN-TRIP-002"
        plan = Solver(nav.tasks[tid]).solve()
        os.environ["PYTHONPATH"] = os.path.abspath(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")  # tool server is `python -m navital_gym...`
        os.environ.setdefault("NAVITAL_FAKE_KEY", "x")
        for final, want in (("Plan:\n" + json.dumps(plan), 1.0), ("", 0.0)):
            srv, log = fake_openai(final)
            try:
                env = load_environment("trip", ids=[tid]); task = list(env.taskset)[0]
                ctx = ModelContext(client=vf.EvalClientConfig(base_url=f"http://127.0.0.1:{srv.server_address[1]}/v1", api_key_var="NAVITAL_FAKE_KEY"), model="fake", sampling=None)
                async def go():
                    async with env.serving():
                        return await env.run_slot(RunSlot(task), ctx)
                ep = asyncio.run(go())
            finally:
                srv.shutdown()
            tr = ep.traces[0]
            self.assertEqual(tr.errors, [])
            self.assertEqual(tr.rewards["navital_score"].score, want)
            self.assertEqual(tr.metrics["solved"], want)
            self.assertEqual(len(tr.tool_messages), 1)                      # the tool call went through the Navital world
            self.assertIn("calendar_info", [t["function"]["name"] for t in log[0]["tools"]])
            sent = json.dumps(log[0])                                       # what the model was actually shown
            for k in HIDDEN: self.assertNotIn(f'"{k}":', sent.replace(' ', ''))
            self.assertIn(nav.tasks[tid].prompt, json.dumps(log[0]["messages"], ensure_ascii=False) + json.dumps(log[0]["messages"]))

if __name__ == "__main__":
    unittest.main()
