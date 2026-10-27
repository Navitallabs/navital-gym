import http.server, json, os, sys, threading, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import agents as A
from navital_gym.core.runner import run_suite
from navital_gym.envs.trip import load_env
from navital_gym.envs.trip.solver import Solver

ENV = load_env()
TID = "IN-TRIP-002"
PLAN = json.dumps(Solver(ENV.tasks[TID]).solve())

# fake secrets are assembled at run time so no key-shaped string sits in the source (GitHub push protection scans for provider prefixes)
FAKE_SK = "s" + "k-" + "abcdefghijklmnop1234"
FAKE_AIZA = "AI" + "za" + "SyABCDEFGHIJKLMNOP"

class Fake:
    """A stdlib HTTP server that plays a scripted model for either wire format and records what it was sent."""
    def __init__(self, kind, script, usage=(100, 50)):
        self.kind, self.script, self.requests, self.usage, outer = kind, list(script), [], usage, self
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, dict(self.headers), body))
                step = outer.script.pop(0) if outer.script else ("text", "{}")
                if step[0] == "status":
                    self.send_response(step[1]); self.send_header("Retry-After", "0"); self.end_headers(); self.wfile.write(b"{}"); return
                if outer.kind == "openai":
                    msg = {"role": "assistant", "content": step[1] if step[0] == "text" else None}
                    if step[0] == "tool":
                        msg["tool_calls"] = [{"id": "c1", "type": "function", "function": {"name": step[1], "arguments": json.dumps(step[2])}}]
                    out = {"choices": [{"message": msg}], "usage": {"prompt_tokens": outer.usage[0], "completion_tokens": outer.usage[1]}}
                else:
                    out = {"content": [{"type": "text", "text": step[1]}] if step[0] == "text" else [{"type": "tool_use", "id": "tu1", "name": step[1], "input": step[2]}],
                           "usage": {"input_tokens": outer.usage[0], "output_tokens": outer.usage[1]}}
                data = json.dumps(out).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def close(self): self.srv.shutdown(); self.srv.server_close()

class Agents(unittest.TestCase):
    def setUp(self):
        self._sleep = A.time.sleep; A.time.sleep = lambda s: None
    def tearDown(self):
        A.time.sleep = self._sleep

    def run_one(self, agent):
        r = run_suite(ENV, agent, [TID], 1)
        return r["results"][TID][0], r["summary"]

    def test_openai_tool_loop_then_good_answer_is_strict_pass(self):
        f = Fake("openai", [("tool", "calendar_info", {}), ("text", "Here you go: " + PLAN)])
        try:
            sc, summ = self.run_one(A.OpenAIChatAgent("m", f.url))
        finally: f.close()
        self.assertTrue(sc.solved); self.assertFalse(sc.meta["repaired"]); self.assertEqual(summ["strict_pass@1"], 1.0)
        # the tool result went back to the model in the wire format, and no hidden field was sent
        sent = json.dumps(f.requests)
        self.assertIn('"role": "tool"', sent)
        for k in ("expected_feasible", "binding_constraint", "traps"):
            self.assertNotIn(k, sent)

    def test_unparseable_final_gets_one_repair_retry_in_json_mode_and_is_reported(self):
        f = Fake("openai", [("text", "I think the trip is fine!"), ("text", PLAN)])
        try:
            sc, summ = self.run_one(A.OpenAIChatAgent("m", f.url))
        finally: f.close()
        self.assertTrue(sc.solved); self.assertTrue(sc.meta["repaired"])
        self.assertEqual(summ["pass@1"], 1.0); self.assertEqual(summ["strict_pass@1"], 0.0)       # strict column keeps the no-retry number
        last = f.requests[-1][2]
        self.assertEqual(last.get("response_format"), {"type": "json_object"}); self.assertNotIn("tools", last)
        self.assertIn("did not parse", last["messages"][-1]["content"])

    def test_no_repair_flag_gives_the_strict_result_and_a_format_failure(self):
        f = Fake("openai", [("text", "no json here")])
        try:
            sc, summ = self.run_one(A.OpenAIChatAgent("m", f.url, repair=False))
        finally: f.close()
        self.assertFalse(sc.solved); self.assertFalse(sc.valid); self.assertEqual(summ["format_fail"], 1.0)

    def test_wrong_status_is_a_format_problem_and_repairable(self):
        f = Fake("openai", [("text", '{"hello": 1}'), ("text", PLAN)])
        try:
            sc, _ = self.run_one(A.OpenAIChatAgent("m", f.url))
        finally: f.close()
        self.assertTrue(sc.solved and sc.meta["repaired"])

    def test_running_out_of_turns_forces_a_final_answer_and_is_reported(self):
        f = Fake("openai", [("tool", "calendar_info", {})] * 3 + [("text", PLAN)])
        try:
            sc, summ = self.run_one(A.OpenAIChatAgent("m", f.url, max_turns=3))
        finally: f.close()
        self.assertTrue(sc.meta["turns_exhausted"]); self.assertTrue(sc.solved); self.assertEqual(summ["turns_exhausted"], 1.0)

    def test_rate_limit_is_retried_and_a_dead_provider_is_an_error_not_a_wrong_answer(self):
        f = Fake("openai", [("status", 429), ("text", PLAN)])
        try:
            sc, _ = self.run_one(A.OpenAIChatAgent("m", f.url))
        finally: f.close()
        self.assertTrue(sc.solved)
        f = Fake("openai", [("status", 500)] * 10)
        try:
            sc, summ = self.run_one(A.OpenAIChatAgent("m", f.url))
        finally: f.close()
        self.assertFalse(sc.solved); self.assertTrue(sc.meta["error"]); self.assertEqual(summ["errors"], 1.0)

    def test_anthropic_wire_format(self):
        f = Fake("anthropic", [("tool", "calendar_info", {}), ("text", PLAN)])
        try:
            sc, _ = self.run_one(A.AnthropicChatAgent("claude-x", api_key="k", base_url=f.url))
        finally: f.close()
        self.assertTrue(sc.solved)
        path, headers, body = f.requests[0]
        self.assertEqual(path, "/v1/messages"); self.assertEqual({k.lower(): v for k, v in headers.items()}.get("x-api-key"), "k"); self.assertIn("anthropic-version", {k.lower() for k in headers})
        self.assertTrue(all("input_schema" in t for t in body["tools"]))
        second = f.requests[1][2]["messages"]
        self.assertEqual(second[1]["content"][0]["type"], "tool_use"); self.assertEqual(second[2]["content"][0]["type"], "tool_result")

    def test_cerebras_and_mistral_resolve_with_their_own_key_names_and_headers(self):
        for spec, base, key_env in (("cerebras:llama-3.3-70b", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"), ("mistral:mistral-small-latest", "https://api.mistral.ai/v1", "MISTRAL_API_KEY")):
            os.environ.pop(key_env, None)
            with self.assertRaises(ValueError):
                A.make_agent(spec)
            os.environ[key_env] = "SECRET-KEY-456"
            try:
                a = A.make_agent(spec, ledger_path="/tmp/provider-test-ledger.json")
                self.assertEqual(a.base, base); self.assertNotIn("SECRET-KEY-456", json.dumps(a.settings()))
                self.assertIsNone(a.spend_cap_usd)                       # free-tier providers: tokens counted, no dollars
            finally:
                os.environ.pop(key_env, None)

    def test_providers_resolve_and_demand_their_key(self):
        os.environ.pop("GROQ_API_KEY", None)
        with self.assertRaises(ValueError):
            A.make_agent("groq:llama-3.3-70b-versatile")
        os.environ["GROQ_API_KEY"] = "SECRET-KEY-123"
        try:
            a = A.make_agent("groq:llama-3.3-70b-versatile")
            self.assertEqual(a.base, "https://api.groq.com/openai/v1")
            self.assertNotIn("SECRET-KEY-123", json.dumps(a.settings()))          # a key never lands in the saved settings
        finally:
            os.environ.pop("GROQ_API_KEY", None)
        self.assertEqual(A.make_agent("ollama:qwen2.5:7b").model, "qwen2.5:7b")

class ProviderQuirks(unittest.TestCase):
    def test_gemini_thought_signature_is_sent_back_unchanged_and_tool_schema_has_no_unknown_keys(self):
        ag = A.OpenAIChatAgent("m", "http://x")
        sig = {"google": {"thought_signature": "SIG123"}}
        wire = ag._wire([{"role": "user", "content": "q"}, {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "t", "args": {}, "extra": sig}]},
                         {"role": "tool", "tool_call_id": "c1", "content": "{}"}])
        self.assertEqual(wire[1]["tool_calls"][0]["extra_content"], sig)
        for tid in ENV.task_ids()[:3]:
            for spec in ENV.reset(tid)["tools"]:
                for prop in spec["function"]["parameters"]["properties"].values():
                    self.assertNotIn("optional", prop)

    def test_provider_error_text_is_extracted_and_scrubbed(self):
        body = json.dumps([{"error": {"code": 404, "message": "model_not_found for " + FAKE_SK}}])
        self.assertEqual(A._error_text(body), "model_not_found for " + FAKE_SK)
        self.assertNotIn(FAKE_SK, str(A.ProviderError("HTTP 404: " + A._error_text(body))))

class LedgerConcurrency(unittest.TestCase):
    def test_parallel_processes_do_not_overwrite_each_other(self):
        import subprocess, tempfile
        path = os.path.join(tempfile.mkdtemp(), "l.json")
        code = ("import sys; sys.path.insert(0, %r); from navital_gym.core.agents import Ledger\nL = Ledger(%r)\n"
                "for i in range(40): L.add(sys.argv[1], 'm', 10, 5, 0.01)") % (os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."), path)
        procs = [subprocess.Popen([sys.executable, "-c", code, prov]) for prov in ("anthropic", "openai", "anthropic", "openai")]
        for p in procs: p.wait()
        led = A.Ledger(path)
        self.assertAlmostEqual(led.total("anthropic"), 0.80, places=6); self.assertAlmostEqual(led.total("openai"), 0.80, places=6)

class GroqPseudoTool(unittest.TestCase):
    def test_a_pseudo_tool_call_named_json_becomes_the_final_answer(self):
        import http.server, threading
        calls = []
        gen = json.dumps({"name": "json", "arguments": json.loads(PLAN)})
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                calls.append(1); self.rfile.read(int(self.headers["Content-Length"]))
                body = json.dumps({"error": {"message": "Tool call validation failed: attempted to call tool 'json' which was not in request.tools", "failed_generation": gen}}).encode()
                self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            sc = run_suite(ENV, A.OpenAIChatAgent("m", f"http://127.0.0.1:{srv.server_port}"), [TID], 1)["results"][TID][0]
        finally:
            srv.shutdown(); srv.server_close()
        self.assertTrue(sc.solved, sc.verdict)
        # a REAL tool name is never rewritten
        self.assertIsNone(A._salvage_failed_generation(A.ProviderError("x", json.dumps({"error": {"failed_generation": json.dumps({"name": "search_trains", "arguments": {}})}}))))

class Resume(unittest.TestCase):
    def test_resume_keeps_finished_tasks_retries_errors_and_does_nothing_when_done(self):
        import tempfile
        from navital_gym import cli
        ids = ENV.task_ids()[:2]
        out = os.path.join(tempfile.mkdtemp(), "r.json")
        os.environ["OPENAI_API_KEY"] = "dummy-resume-key"
        A.time.sleep = lambda s_: None
        try:
            def run(script):
                f = Fake("openai", script)
                try:
                    cli.main(["run", "--env", "trip", "--agent", f"openai:m@{f.url}", "--tasks", ",".join(ids), "--out", out, "--resume", "--env-file", "/nonexistent"])
                finally: f.close()
                return len(f.requests)
            run([("status", 500)] * 100)                      # provider down: both tasks end in errors, nothing finished
            d = json.load(open(out)); k0 = list(d)[0]; self.assertTrue(all(r[0]["meta"].get("error") for r in d[k0]["tasks"].values()))
            self.assertEqual(run([("text", PLAN)] * 4), 2)    # next attempt: both tasks run again (one request each)
            d = json.load(open(out)); k = list(d)[0]
            self.assertEqual(len(d[k]["tasks"]), 2); self.assertFalse(any(r[0]["meta"].get("error") for r in d[k]["tasks"].values()))
            self.assertEqual(run([("text", PLAN)] * 4), 0)    # everything finished: no request at all
            d3 = json.load(open(out)); self.assertEqual(len(d3[list(d3)[0]]["tasks"]), 2)      # the fake server's port (so the spec string) differs per run; one agent per file
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

class AnthropicTemperature(unittest.TestCase):
    def test_a_model_that_rejects_temperature_is_retried_without_it_and_remembered(self):
        import http.server, threading
        seen = []
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); seen.append("temperature" in body)
                if "temperature" in body:
                    data = json.dumps({"error": {"message": "`temperature` is deprecated for this model."}}).encode(); self.send_response(400)
                else:
                    data = json.dumps({"content": [{"type": "text", "text": "{}"}], "usage": {"input_tokens": 1, "output_tokens": 1}}).encode(); self.send_response(200)
                self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)
        srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            ag = A.AnthropicChatAgent("m", api_key="k", base_url=f"http://127.0.0.1:{srv.server_port}")
            ag.meta = {}
            ag._chat([{"role": "user", "content": "q"}], [])
            ag._chat([{"role": "user", "content": "q"}], [])
        finally:
            srv.shutdown(); srv.server_close()
        self.assertEqual(seen, [True, False, False])          # first try with it, then never again

class Cloudflare(unittest.TestCase):
    def test_workers_ai_url_uses_the_account_id_and_model_ids_keep_their_at_sign(self):
        for k in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
            os.environ.pop(k, None)
        with self.assertRaises(ValueError):
            A.make_agent("cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast")
        os.environ["CLOUDFLARE_ACCOUNT_ID"] = "acct0123456789abcdef"; os.environ["CLOUDFLARE_API_TOKEN"] = "CFTOKEN-secret-1234"
        try:
            a = A.make_agent("cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast", ledger_path="/tmp/cf-test-ledger.json")
            self.assertEqual(a.model, "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
            self.assertEqual(a.base, "https://api.cloudflare.com/client/v4/accounts/acct0123456789abcdef/ai/v1")
            self.assertIsNone(a.spend_cap_usd)
            saved = A.redact(json.dumps(a.settings()))
            self.assertNotIn("acct0123456789abcdef", saved); self.assertNotIn("CFTOKEN-secret-1234", saved)
        finally:
            os.environ.pop("CLOUDFLARE_ACCOUNT_ID", None); os.environ.pop("CLOUDFLARE_API_TOKEN", None)

class Sarvam(unittest.TestCase):
    def test_sarvam_sends_both_key_headers_and_thinking_is_not_the_answer(self):
        import http.server, threading
        seen = {}
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                seen["headers"] = {k.lower(): v for k, v in self.headers.items()}; self.rfile.read(int(self.headers["Content-Length"]))
                msg = {"role": "assistant", "content": '<think>maybe {"status": "plan", "x": 1}</think>' + PLAN, "reasoning_content": '{"status": "infeasible"}'}
                body = json.dumps({"choices": [{"message": msg}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        os.environ["SARVAM_API_KEY"] = "SARVAMSECRET123"
        try:
            ag = A.make_agent("sarvam:sarvam-105b", ledger_path="/tmp/sarvam-test-ledger.json")
            self.assertEqual(ag.base, "https://api.sarvam.ai/v1")
            ag.base = f"http://127.0.0.1:{srv.server_port}"
            sc = run_suite(ENV, ag, [TID], 1)["results"][TID][0]
        finally:
            srv.shutdown(); srv.server_close(); os.environ.pop("SARVAM_API_KEY", None)
        self.assertEqual(seen["headers"].get("api-subscription-key"), "SARVAMSECRET123")
        self.assertEqual(seen["headers"].get("authorization"), "Bear" + "er SARVAMSECRET123")
        self.assertTrue(sc.solved)              # the plan after the </think> block is the answer; reasoning_content was ignored
        self.assertNotIn("SARVAMSECRET123", json.dumps(ag.settings()))

    def test_token_cap_counts_every_run_of_the_provider_through_the_ledger(self):
        import tempfile
        led = os.path.join(tempfile.mkdtemp(), "l.json")
        A.Ledger(led).add("sarvam", "m", 900, 100, 0.0)        # an earlier process already used 1000 tokens
        os.environ["SARVAM_API_KEY"] = "k"
        try:
            ag = A.make_agent("sarvam:m", ledger_path=led); ag.token_cap = 1000
        finally: os.environ.pop("SARVAM_API_KEY", None)
        sc = run_suite(ENV, ag, [TID], 1)["results"][TID][0]
        self.assertTrue(sc.meta.get("cap_reached")); self.assertFalse(sc.solved)

class ToolsRequiredAfterToolMessages(unittest.TestCase):
    def test_a_tool_free_repair_or_final_call_is_retried_with_tools_and_tool_choice_none(self):
        import http.server, threading
        seen = []
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); seen.append(body)
                has_tool_msgs = any(m["role"] == "tool" for m in body["messages"])
                if has_tool_msgs and not body.get("tools"):
                    data = json.dumps({"error": {"message": "Tool messages found but no tools provided. Tools must be specified if tool calls or tool messages are present."}}).encode(); self.send_response(400)
                else:
                    n_tool = sum(1 for m in body["messages"] if m["role"] == "tool")
                    if n_tool == 0:
                        msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "calendar_info", "arguments": "{}"}}]}
                    elif body.get("tool_choice") == "none" or not body.get("tools"):
                        msg = {"role": "assistant", "content": PLAN}
                    else:
                        msg = {"role": "assistant", "content": "thinking out loud, no JSON"}
                    data = json.dumps({"choices": [{"message": msg, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 5}}).encode(); self.send_response(200)
                self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)
        srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            ag = A.OpenAIChatAgent("m", f"http://127.0.0.1:{srv.server_port}", max_tokens=4321)
            sc = run_suite(ENV, ag, [TID], 1)["results"][TID][0]
        finally:
            srv.shutdown(); srv.server_close()
        self.assertTrue(sc.solved, (sc.verdict, sc.meta)); self.assertTrue(sc.meta["repaired"]); self.assertFalse(sc.meta["error"])
        self.assertTrue(any(b.get("tool_choice") == "none" and b.get("tools") for b in seen))
        self.assertTrue(all(b.get("max_tokens") == 4321 for b in seen))

    def test_sarvam_gets_an_explicit_max_tokens(self):
        os.environ["SARVAM_API_KEY"] = "k"
        try:
            self.assertGreaterEqual(A.make_agent("sarvam:sarvam-105b", ledger_path="/tmp/s-l.json").max_tokens, 8000)
        finally: os.environ.pop("SARVAM_API_KEY", None)

class RetiredProviders(unittest.TestCase):
    def test_github_models_is_not_offered(self):
        with self.assertRaises(ValueError):
            A.make_agent("github:openai/gpt-4o-mini")

class EnvFile(unittest.TestCase):
    def test_only_provider_key_names_are_loaded(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), ".env.local")
        open(path, "w").write("GROQ_API_KEY=abc12345678\nHTTPS_PROXY=http://evil:1\nSSL_CERT_FILE=/tmp/x\nPYTHONPATH=/tmp/evil\nGIT_SSH_COMMAND=curl evil\nUNRELATED=1\n")
        for k in ("GROQ_API_KEY", "HTTPS_PROXY", "SSL_CERT_FILE", "PYTHONPATH", "GIT_SSH_COMMAND", "UNRELATED"):
            os.environ.pop(k, None)
        try:
            self.assertEqual(A.load_env_file(path), 1)
            self.assertEqual(os.environ.get("GROQ_API_KEY"), "abc12345678")
            for k in ("HTTPS_PROXY", "SSL_CERT_FILE", "PYTHONPATH", "GIT_SSH_COMMAND", "UNRELATED"):
                self.assertNotIn(k, os.environ)
        finally:
            for k in ("GROQ_API_KEY", "HTTPS_PROXY", "SSL_CERT_FILE", "PYTHONPATH", "GIT_SSH_COMMAND", "UNRELATED"):
                os.environ.pop(k, None)

class Spend(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.ledger = os.path.join(tempfile.mkdtemp(), "ledger.json")
        self._caps_env = os.environ.get("NAVITAL_INTERNAL_CAPS"); self._req = os.environ.pop("NAVITAL_REQUIRE_CAPS", None)
        caps = os.path.join(tempfile.mkdtemp(), "caps.json"); open(caps, "w").write('{"anthropic": 65, "openai": 3}')
        os.environ["NAVITAL_INTERNAL_CAPS"] = caps          # tests never read the real ~/.navital-gym/caps.json
        self._sleep = A.time.sleep; A.time.sleep = lambda s: None
        os.environ["ANTHROPIC_API_KEY"] = "dummy-anthropic-test-key"
    def tearDown(self):
        A.time.sleep = self._sleep; os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._caps_env is None: os.environ.pop("NAVITAL_INTERNAL_CAPS", None)
        else: os.environ["NAVITAL_INTERNAL_CAPS"] = self._caps_env
        if self._req is not None: os.environ["NAVITAL_REQUIRE_CAPS"] = self._req

    def agent(self, f, **kw):
        ag = A.make_agent("anthropic:claude-test", ledger_path=self.ledger, **kw)
        ag.url = f.url + "/v1/messages"
        return ag

    def test_ledger_counts_tokens_times_price_and_persists(self):
        f = Fake("anthropic", [("tool", "calendar_info", {}), ("text", PLAN)], usage=(1000, 500))
        try:
            ag = self.agent(f, price_in=2.0, price_out=10.0)
            sc = run_suite(ENV, ag, [TID], 1)["results"][TID][0]
        finally: f.close()
        self.assertTrue(sc.solved)
        want = 2 * (1000 * 2.0 + 500 * 10.0) / 1e6
        self.assertAlmostEqual(A.Ledger(self.ledger).total("anthropic"), want, places=6)
        self.assertAlmostEqual(sc.meta["usd"], want, places=6)
        self.assertNotIn("dummy-anthropic-test-key", open(self.ledger).read())

    def test_a_call_that_could_cross_the_cap_is_refused_before_it_is_made(self):
        f = Fake("anthropic", [("text", PLAN)] * 3, usage=(1000, 500))
        try:
            ag = self.agent(f, spend_cap_usd=0.02, price_in=2.0, price_out=10.0)   # worst case of one call (2500 in + 4096 out) is about $0.046
            sc = run_suite(ENV, ag, [TID], 1)["results"][TID][0]
        finally: f.close()
        self.assertTrue(sc.meta.get("cap_reached")); self.assertEqual(len(f.requests), 0)
        self.assertEqual(A.Ledger(self.ledger).total("anthropic"), 0.0)

    def test_sonnet_is_priced_at_the_sonnet_rate_not_the_provider_default(self):
        self.assertEqual(A.make_agent("anthropic:claude-sonnet-5-5", ledger_path=self.ledger).price, (5.0, 25.0))
        self.assertEqual(A.make_agent("anthropic:claude-haiku-4-5", ledger_path=self.ledger).price, (2.0, 10.0))
        self.assertEqual(A.make_agent("anthropic:claude-sonnet-5-5", price_in=1.0, price_out=2.0, ledger_path=self.ledger).price, (1.0, 2.0))

    def test_a_flag_can_lower_but_never_raise_a_configured_cap(self):
        self.assertEqual(A.make_agent("anthropic:m", spend_cap_usd=1.0, ledger_path=self.ledger).spend_cap_usd, 1.0)
        self.assertEqual(A.make_agent("anthropic:m", spend_cap_usd=999.0, ledger_path=self.ledger).spend_cap_usd, 65.0)
        os.environ["OPENAI_API_KEY"] = "dummy"
        try:
            self.assertEqual(A.make_agent("openai:m", spend_cap_usd=50, ledger_path=self.ledger).spend_cap_usd, 3.0)
        finally: os.environ.pop("OPENAI_API_KEY", None)

    def test_public_default_has_no_cap_and_our_scripts_refuse_paid_providers_without_one(self):
        import tempfile
        os.environ["NAVITAL_INTERNAL_CAPS"] = os.path.join(tempfile.mkdtemp(), "none.json")       # no internal config at all
        self.assertIsNone(A.make_agent("anthropic:m", ledger_path=self.ledger).spend_cap_usd)       # a public user: no cap unless they set one
        self.assertEqual(A.make_agent("anthropic:m", spend_cap_usd=5, ledger_path=self.ledger).spend_cap_usd, 5.0)
        os.environ["NAVITAL_REQUIRE_CAPS"] = "1"
        try:
            with self.assertRaises(ValueError) as cm:
                A.make_agent("anthropic:m", ledger_path=self.ledger)
            self.assertIn("caps.json", str(cm.exception))
            with self.assertRaises(ValueError):
                A.make_agent("anthropic:m", spend_cap_usd=5, ledger_path=self.ledger)             # a flag alone does not satisfy the requirement
            os.environ["OPENAI_API_KEY"] = "dummy"
            with self.assertRaises(ValueError):
                A.make_agent("openai:m", ledger_path=self.ledger)
            A.make_agent("groq:x", ledger_path=self.ledger) if os.environ.get("GROQ_API_KEY") else None   # free providers are not affected
        finally:
            os.environ.pop("NAVITAL_REQUIRE_CAPS", None); os.environ.pop("OPENAI_API_KEY", None)

    def test_every_one_of_our_run_scripts_requires_caps(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
        for name in ("run_sample.sh", "run_subset.sh", "resume_until_done.sh", "run_local_overnight.sh", "redteam.py"):
            self.assertIn("NAVITAL_REQUIRE_CAPS", open(os.path.join(root, name)).read(), name)

    def test_a_script_run_without_caps_config_refuses_before_any_network_call(self):
        import subprocess, tempfile
        env = {**os.environ, "NAVITAL_INTERNAL_CAPS": os.path.join(tempfile.mkdtemp(), "none.json"), "ANTHROPIC_API_KEY": "dummy-key-not-real"}
        out = subprocess.run(["sh", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "run_subset.sh"), "anthropic:claude-test", "captest", "0", "trip"],
                             env=env, capture_output=True, text=True, timeout=60)
        log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs", "trip-captest-s15.log")
        text = open(log).read() if os.path.exists(log) else out.stdout + out.stderr
        self.assertIn("no spend cap is configured", text)
        for f in (log, log.replace("-s15.log", "-s15.json")):
            if os.path.exists(f): os.remove(f)

    def test_openrouter_only_free_models(self):
        os.environ["OPENROUTER_API_KEY"] = "dummy"
        try:
            with self.assertRaises(ValueError): A.make_agent("openrouter:meta-llama/llama-3.3-70b-instruct")
            A.make_agent("openrouter:meta-llama/llama-3.3-70b-instruct:free", ledger_path=self.ledger)
        finally: os.environ.pop("OPENROUTER_API_KEY", None)

    def test_three_failures_in_a_row_stop_the_suite(self):
        f = Fake("openai", [("status", 500)] * 100)
        try:
            r = run_suite(ENV, A.OpenAIChatAgent("m", f.url), list(ENV.task_ids())[:8], 1)
        finally: f.close()
        self.assertEqual(len(r["results"]), 3)

class Redaction(unittest.TestCase):
    def test_secrets_are_scrubbed_from_errors_transcripts_and_saved_files(self):
        import tempfile
        os.environ["FAKE_API_KEY"] = "zzTOPSECRETzz12345"
        had = os.environ.get("OPENAI_API_KEY"); os.environ["OPENAI_API_KEY"] = "dummy-test-key-0000"
        try:
            for leaked in ("bad key zzTOPSECRETzz12345 rejected", "Incorrect API key provided: " + FAKE_SK, "x-api-key: " + FAKE_AIZA, "Authorization: Bear" + "er abcdefghijklmnopqrstuv"):
                out = A.redact(leaked)
                self.assertNotIn("zzTOPSECRETzz12345", out); self.assertNotIn(FAKE_SK, out); self.assertNotIn(FAKE_AIZA, out); self.assertNotIn("abcdefghijklmnopqrstuv", out)
            self.assertNotIn("zzTOPSECRETzz12345", str(A.ProviderError("HTTP 401: key zzTOPSECRETzz12345")))
            from navital_gym import cli
            f = Fake("openai", [("text", "my key is zzTOPSECRETzz12345 " + PLAN)])
            out_path = os.path.join(tempfile.mkdtemp(), "r.json")
            try:
                cli.main(["run", "--env", "trip", "--agent", f"openai:m@{f.url}", "--tasks", TID, "--out", out_path, "--env-file", "/nonexistent"])
            finally: f.close()
            for path in (out_path, out_path.replace(".json", ".transcripts.json")):
                self.assertNotIn("zzTOPSECRETzz12345", open(path).read())
        finally:
            os.environ.pop("FAKE_API_KEY", None)
            if had is None: os.environ.pop("OPENAI_API_KEY", None)
            else: os.environ["OPENAI_API_KEY"] = had

    def test_token_cap_stops_the_agent_and_is_reported(self):
        f = Fake("openai", [("tool", "calendar_info", {})] * 5)
        orig = A.OpenAIChatAgent._chat
        def counting(self, m, t, j=False):
            out = orig(self, m, t, j); self._count(600, 600); return out
        A.OpenAIChatAgent._chat = counting
        try:
            ag = A.OpenAIChatAgent("m", f.url); ag.token_cap = 1000
            r = run_suite(ENV, ag, [TID], 1)
        finally:
            A.OpenAIChatAgent._chat = orig; f.close()
        sc = r["results"][TID][0]
        self.assertTrue(sc.meta.get("cap_reached")); self.assertFalse(sc.solved)

if __name__ == "__main__":
    unittest.main()
