import importlib.util, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.adapters.openenv_env import NavitalSession
from navital_gym.core.leak import HIDDEN_KEYS, find_leaks
from navital_gym.envs.trip.solver import Solver

TID = "IN-TRIP-002"
HAVE = importlib.util.find_spec("openenv") is not None and importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None

def oracle(s):
    return Solver(s.env.tasks[TID]).solve()

class Protocol(unittest.TestCase):
    def test_reset_tool_finalize_oracle(self):
        s = NavitalSession("trip")
        o = s.reset(TID)
        self.assertEqual(o["task_id"], TID)
        self.assertTrue(o["tools"] and o["prompt"])
        r = s.step({"tool": "calendar_info", "args": {}})
        self.assertFalse(r["done"]); self.assertEqual(r["reward"], 0.0)
        self.assertIn("today", r["result"])
        r = s.step({"finalize": oracle(s)})
        self.assertTrue(r["done"]); self.assertEqual(r["reward"], 1.0)
        self.assertNotIn("info", r)
        self.assertEqual(s.state()["tools_called"], ["calendar_info"])
        self.assertEqual(s.state()["step_count"], 2)

    def test_empty_submission_scores_zero(self):
        s = NavitalSession("trip"); s.reset(TID)
        r = s.step({"finalize": {}})
        self.assertTrue(r["done"]); self.assertEqual(r["reward"], 0.0)

    def test_step_after_done_refused(self):
        s = NavitalSession("trip"); s.reset(TID)
        s.step({"finalize": {}})
        n = s.state()["step_count"]
        r = s.step({"tool": "calendar_info", "args": {}})
        self.assertIn("error", r["result"]); self.assertTrue(r["done"]); self.assertEqual(r["reward"], 0.0)
        r = s.step({"finalize": oracle(s)})
        self.assertEqual(r["reward"], 0.0)
        self.assertEqual(s.state()["step_count"], n)

    def test_step_before_reset_and_bad_actions(self):
        s = NavitalSession("trip")
        self.assertIn("error", s.step({"tool": "calendar_info"})["result"])
        s.reset(TID)
        self.assertIn("error", s.step({})["result"])
        self.assertIn("error", s.step({"tool": "calendar_info", "finalize": {}})["result"])
        self.assertFalse(s.state()["done"])

    def test_task_selection(self):
        s = NavitalSession("trip"); ids = s.env.task_ids()
        self.assertEqual(s.reset()["task_id"], ids[0])
        self.assertEqual(s.reset(TID)["task_id"], TID)
        self.assertEqual(s.reset(1)["task_id"], ids[1])
        self.assertEqual(s.reset(seed=2)["task_id"], ids[2])
        with self.assertRaises(KeyError):
            s.reset("nope")

class NoLeaks(unittest.TestCase):
    def test_observation_and_state_hide_task_fields(self):
        s = NavitalSession("trip")
        for tid in s.env.task_ids()[:12]:
            task = s.env.tasks[tid]
            o = s.reset(tid)
            r = s.step({"tool": "calendar_info", "args": {}})
            fin = s.step({"finalize": {}})
            for name, blob in (("reset", o), ("step", r), ("final", fin), ("state", s.state())):
                text = json.dumps(blob)
                self.assertEqual(find_leaks(task, text, name) if name != "reset" else find_leaks(task, o["prompt"].split("\n\n")[0], "prompt") + find_leaks(task, json.dumps(o["tools"]), "tools"), [], tid)
                for k in HIDDEN_KEYS + ("rules", "params", "info"):
                    self.assertNotIn(f'"{k}"', text, f"{tid} {name} exposes {k}")

class Isolation(unittest.TestCase):
    def test_two_episodes_do_not_share_world(self):
        a, b = NavitalSession("trip"), NavitalSession("trip")
        a.reset(TID); b.reset(TID)
        self.assertIsNot(a.env.world, b.env.world)
        a.step({"tool": "calendar_info", "args": {}})
        self.assertEqual(b.state()["tools_called"], [])
        a.step({"finalize": oracle(a)})
        self.assertTrue(a.state()["done"]); self.assertFalse(b.state()["done"])
        self.assertEqual(b.step({"finalize": {}})["reward"], 0.0)
        # reset on the same session builds a fresh world and clears the log
        w = a.env.world; a.reset(TID)
        self.assertIsNot(a.env.world, w); self.assertEqual(a.state()["tools_called"], [])

@unittest.skipUnless(HAVE, "openenv-core (+ fastapi, httpx) not installed")
class OpenEnvBinding(unittest.TestCase):
    def test_environment_subclass(self):
        from navital_gym.adapters.openenv_env import NavitalOpenEnv, NavitalAction
        e = NavitalOpenEnv("trip")
        o = e.reset(task_id=TID)
        self.assertEqual(o.task_id, TID); self.assertFalse(o.done)
        r = e.step(NavitalAction(tool="calendar_info"))
        self.assertIn("today", r.result)
        sub = Solver(e.session.env.tasks[TID]).solve()
        r = e.step(NavitalAction(finalize=sub))
        self.assertTrue(r.done); self.assertEqual(r.reward, 1.0)
        st = e.state
        self.assertEqual((st.task_id, st.done, st.step_count), (TID, True, 2))
        e.reset(task_id=TID)
        self.assertEqual(e.step(NavitalAction(finalize={})).reward, 0.0)
        e2 = NavitalOpenEnv("trip"); self.assertIsNot(e.session.env, e2.session.env)

    def test_http_routes(self):
        from fastapi.testclient import TestClient
        from navital_gym.adapters.openenv_env import make_app
        c = TestClient(make_app("trip"))
        self.assertEqual(c.get("/health").status_code, 200)
        r = c.post("/reset", json={"task_id": TID})
        self.assertEqual(r.status_code, 200, r.text)
        obs = r.json()["observation"]
        self.assertEqual(obs["task_id"], TID)
        # plain HTTP /step is stateless per request in OpenEnv; the stateful session is the WebSocket
        with c.websocket_connect("/ws") as ws:
            def send(m):
                ws.send_json(m); return ws.receive_json()
            m = send({"type": "reset", "data": {"task_id": TID}})
            self.assertEqual(m["data"]["observation"]["task_id"] if "observation" in m["data"] else m["data"]["task_id"], TID, m)
            m = send({"type": "step", "data": {"tool": "calendar_info", "args": {}}})
            self.assertIn("today", json.dumps(m))
            sub = Solver(NavitalSession("trip").env.tasks[TID]).solve()
            m = send({"type": "step", "data": {"finalize": sub}})
            d = m["data"]
            self.assertTrue(d["done"]); self.assertEqual(d["reward"], 1.0)
            st = send({"type": "state"})
            self.assertEqual(st["data"]["task_id"], TID); self.assertTrue(st["data"]["done"])
            self.assertNotIn("expected_feasible", json.dumps(st))

if __name__ == "__main__":
    unittest.main()
