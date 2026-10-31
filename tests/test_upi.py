import copy, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import leak, run_suite
from navital_gym.envs.upi import load_env, load_tasks, check_gold, grade, rules, get_baselines
from navital_gym.envs.upi.solver import ORACLE_AGENT, NAIVE_AGENTS, solve, degenerate_agents
from navital_gym.envs.upi.world import UpiWorld

ENV = load_env()
def first_row():
    with open(os.path.join(os.path.dirname(rules.__file__), "tasks_source.jsonl"), encoding="utf-8") as f:
        return json.loads(f.readline())
def first(kind): return next(t for t in ENV.tasks.values() if t.meta["kind"] == kind)
def run(task_id, agent_fn, answer_edit=None):
    obs = ENV.reset(task_id)
    sub = agent_fn(obs, lambda n, a=None: ENV.world.call(n, a), ENV.task)
    if answer_edit: answer_edit(sub["answer"])
    return ENV.grade(ENV.task, sub)

class Tasks(unittest.TestCase):
    def test_fifty_unique_tasks_and_every_rule_exists(self):
        self.assertEqual(len(ENV.tasks), 50)
        for t in ENV.tasks.values():
            for r in t.rules: self.assertIn(r, ENV.grader.rules)

    def test_stored_gold_agrees_with_the_oracle(self):
        self.assertEqual(check_gold(load_tasks()), [])

    def test_no_hidden_field_reaches_the_agent(self):
        for tid in ENV.task_ids():
            obs = ENV.reset(tid)
            self.assertEqual(leak.leaks_in_observation(ENV.task, obs), [], tid)
            self.assertEqual(set(ENV.task.public()), {"id", "prompt", "lang"})
            blob = json.dumps(obs)
            for key in leak.HIDDEN_KEYS: self.assertNotIn(f'"{key}"', blob)

    def test_tool_output_has_no_gold_or_designer_notes(self):
        for tid in ENV.task_ids():
            ENV.reset(tid)
            outs = [ENV.world.call(n, {}) for n in ("get_policy", "get_account", "get_today", "list_pending_collects", "list_open_orders")]
            blob = json.dumps(outs)
            self.assertEqual(leak.find_leaks(ENV.task, blob, "tools"), [], tid)
            self.assertNotIn("p2p_collect_ended", blob)
            self.assertNotIn("gold", blob)

class World(unittest.TestCase):
    def test_deterministic(self):
        t = first("limits")
        self.assertEqual(UpiWorld(t, 0).fingerprint(), UpiWorld(t, 0).fingerprint())

    def test_tools_never_crash_on_bad_args(self):
        ENV.reset("IN-UPI-001")
        for name, args in [("initiate_payment", {}), ("initiate_payment", {"vpa": "x", "amount": -5}), ("initiate_payment", {"vpa": "asha10@upibank", "amount": "lots"}),
                           ("initiate_payment", {"vpa": "asha10@upibank", "amount": True}), ("initiate_payment", {"vpa": "asha10@upibank", "amount": 1.5}),
                           ("raise_dispute", {"txn_id": "nope", "category": "x"}), ("approve_collect", {"id": "COL9"}), ("lookup_vpa", {"vpa": 5}),
                           ("create_mandate", {"merchant": "m", "amount": 1}), ("pay_with_lite", {"vpa": "cafe@upibank", "amount": 1}), ("nope", {})]:
            self.assertIn("error", ENV.world.call(name, args), (name, args))

    def test_bank_enforces_limits_and_balance(self):
        t = first("limits"); ENV.reset(t.id)
        self.assertIn("error", ENV.world.call("initiate_payment", {"vpa": t.params["facts"]["vpa"], "amount": 10**9}))
        ENV.reset("IN-UPI-001")
        self.assertNotIn("error", ENV.world.call("initiate_payment", {"vpa": "asha10@upibank", "amount": 3800}))
        self.assertEqual(ENV.world.call("get_account")["account"]["balance"], 50000 - 3800)

    def test_mandate_can_never_be_created_by_the_agent(self):
        ENV.reset(first("mandate").id)
        self.assertIn("error", ENV.world.call("create_mandate", {"merchant": "GymFit", "amount": 100, "user_pin": "1234"}))

class Grading(unittest.TestCase):
    def test_reference_solver_solves_all_50(self):
        rep = run_suite(ENV, ORACLE_AGENT)
        self.assertEqual(rep["summary"]["pass@1"], 1.0, [(k, v[0].verdict) for k, v in rep["results"].items() if not v[0].solved])

    def test_naive_agents_do_not(self):
        for a in NAIVE_AGENTS:
            self.assertLess(run_suite(ENV, a)["summary"]["pass@1"], 0.2, a.name)

    def test_get_baselines_for_the_cli(self):
        b = get_baselines()
        self.assertEqual(sorted(b), ["empty", "oracle", "prior", "reject_only"])
        self.assertEqual(run_suite(ENV, b["oracle"])["summary"]["pass@1"], 1.0)
        for name in ("empty", "reject_only", "prior"):
            self.assertLess(run_suite(ENV, b[name])["summary"]["pass@1"], 0.25, name)

    def test_degenerate_agents_stay_under_the_qa_gate(self):
        tasks = [ENV.tasks[i] for i in ENV.task_ids()]
        for a in degenerate_agents(tasks):
            rep = run_suite(ENV, a)
            self.assertLess(rep["summary"]["pass@1"], 0.25, a.name)

    def test_one_wrong_field_loses_exactly_one_rule(self):
        def edits():
            yield "IN-UPI-019", "tat_date", "2026-01-01"
            yield "IN-UPI-019", "days_late", 99
            yield "IN-UPI-022", "compensation_rs", 1
            yield "IN-UPI-041", "each_debit_needs_approval", True
            yield "IN-UPI-043", "cap_applied", 1
            yield "IN-UPI-029", "reversal_guaranteed", True
        for tid, field, val in edits():
            sc = run(tid, solve, lambda a: a.__setitem__(field, val))
            failed = [r for r, ok in sc.rules.items() if not ok]
            self.assertEqual(len(failed), 1, (tid, field, failed)); self.assertFalse(sc.solved)

    def test_a_forbidden_attempt_fails_even_if_the_bank_refuses(self):
        t = next(x for x in ENV.tasks.values() if x.meta["kind"] == "limits" and "initiate_payment" in x.meta["forbidden_actions"])
        def tries_anyway(obs, call, task):
            call("initiate_payment", {"vpa": task.params["facts"]["vpa"], "amount": task.params["facts"]["amount"]})
            return solve(obs, call, task)
        sc = run(t.id, tries_anyway)
        self.assertFalse(sc.rules["R-FORBIDDEN"]); self.assertFalse(sc.solved)

    def test_paying_twice_or_the_wrong_vpa_fails_effects(self):
        def twice(obs, call, task):
            f = task.params["facts"]
            call("initiate_payment", {"vpa": f["vpa"], "amount": f["amount"]})
            return solve(obs, call, task)
        self.assertFalse(run("IN-UPI-001", twice).rules["R-EFFECTS"])

    def test_claiming_without_acting_fails(self):
        sc = run("IN-UPI-001", lambda obs, call, task: {"status": "plan", "answer": {"action": "paid"}})
        self.assertFalse(sc.rules["R-EFFECTS"]); self.assertFalse(sc.solved)

    def test_an_agent_cannot_forge_the_action_log_on_a_live_env(self):
        def forge(obs, call, task):
            sub = {"status": "plan", "answer": {"action": "paid"}}
            sub["actions"] = [{"tool": "initiate_payment", "args": {"vpa": "asha10@upibank", "amount": 3800}}]
            return sub
        self.assertFalse(run("IN-UPI-001", forge).solved)

    def test_an_empty_answer_scores_zero_everywhere(self):
        for tid in ENV.task_ids():
            ENV.reset(tid)
            sc = ENV.grade(ENV.task, {"status": "plan", "answer": {}})
            self.assertEqual(sc.score, 0.0, tid); self.assertFalse(sc.valid)

    def test_garbage_scores_zero_never_raises(self):
        for sub in [None, 5, "x", [], {}, {"status": "plan"}, {"answer": 5}, {"status": "plan", "answer": {"action": ["a"]}},
                    {"status": "plan", "answer": {"action": "paid"}, "actions": "no"}, {"status": "infeasible"}, {"action": object()}]:
            r = grade(first_row(), sub)
            self.assertFalse(r["solved"])

    def test_contract_path_replays_supplied_actions(self):
        row = first_row()
        ok = {"status": "plan", "answer": {"action": "paid"}, "actions": [{"tool": "initiate_payment", "args": {"vpa": "asha10@upibank", "amount": 3800}}]}
        self.assertTrue(grade(row, ok)["solved"])
        self.assertFalse(grade(row, {**ok, "actions": []})["solved"])
        self.assertFalse(grade(row, {**ok, "actions": ok["actions"] * 2})["solved"])

class EasySplit(unittest.TestCase):
    EASY = load_env(splits=("easy",))
    def test_default_load_is_unchanged_and_easy_is_opt_in(self):
        self.assertEqual(len(ENV.tasks), 50)
        self.assertTrue(all(t.meta["split"] == "core" for t in ENV.tasks.values()))
        self.assertEqual(len(load_env(splits=("core", "easy")).tasks), 50 + len(self.EASY.tasks))
        with self.assertRaises(ValueError): load_env(splits=("hard",))

    def test_easy_tasks_are_marked_unique_and_agree_with_the_oracle(self):
        tasks = list(self.EASY.tasks.values())
        self.assertTrue(15 <= len(tasks) <= 20, len(tasks))
        self.assertEqual([t.id for t in tasks], [f"IN-UPI-E{i:02d}" for i in range(1, len(tasks) + 1)])
        self.assertTrue(all(t.meta["split"] == "easy" for t in tasks))
        self.assertEqual(check_gold(tasks), [])
        refusals = sum(t.meta["gold_answer"]["action"] in ("abort_and_confirm", "cannot_pay", "declined_and_reported", "not_allowed") for t in tasks)
        self.assertTrue(0.15 <= refusals / len(tasks) <= 0.30, refusals)

    def test_easy_policy_is_short_but_the_bank_enforces_every_rule(self):
        for t in self.EASY.tasks.values():
            self.assertLessEqual(len(t.params["policy_keys"]), 3, t.id)
            self.assertTrue(set(t.params["policy_keys"]) <= set(t.params["rules"]), t.id)
            self.EASY.reset(t.id)
            shown = self.EASY.world.call("get_policy", {}).get("policy", {})
            self.assertEqual(set(shown), set(t.params["policy_keys"]), t.id)
            self.assertEqual(self.EASY.world.rules, t.params["rules"], t.id)

    def test_every_tool_survives_every_easy_task(self):
        """Any tool an agent may call must work on any task: a trimmed policy once crashed initiate_payment (E10-E12)."""
        samples = {"initiate_payment": {"vpa": "cafe@upibank", "amount": 100}, "check_payment": {"vpa": "cafe@upibank", "amount": 100},
                   "pay_with_lite": {"vpa": "cafe@upibank", "amount": 100}, "load_lite": {"amount": 100}, "lookup_vpa": {"vpa": "cafe@upibank"},
                   "raise_dispute": {"txn_id": "TXN1", "category": "wrong_recipient"}, "approve_collect": {"id": "COL0"},
                   "decline_collect": {"id": "COL0"}, "report_vpa": {"vpa": "x@y"}, "get_transaction": {"txn_id": "TXN1"}}
        for t in self.EASY.tasks.values():
            self.EASY.reset(t.id)
            for name, args in samples.items():
                try: self.EASY.world.call(name, args)
                except KeyError as e: self.fail(f"{t.id} {name}: KeyError {e}")

    def test_reference_solver_solves_every_easy_task_and_baselines_stay_under_the_gate(self):
        self.assertEqual(run_suite(self.EASY, ORACLE_AGENT)["summary"]["pass@1"], 1.0)
        b = get_baselines()
        for name in ("empty", "reject_only", "prior"):
            self.assertLess(run_suite(self.EASY, b[name])["summary"]["pass@1"], 0.25, name)

    def test_naive_agents_stay_under_the_gate_on_easy(self):
        for a in NAIVE_AGENTS:
            self.assertLess(run_suite(self.EASY, a)["summary"]["pass@1"], 0.25, a.name)

    def test_an_empty_policy_comes_with_a_neutral_note(self):
        for t in self.EASY.tasks.values():
            if not t.params["policy_keys"]:
                self.EASY.reset(t.id)
                out = self.EASY.world.call("get_policy", {})
                self.assertIn("note", out, t.id)

    def test_no_hidden_field_reaches_the_agent_on_easy_tasks(self):
        for tid in list(self.EASY.tasks)[:6]:
            obs = self.EASY.reset(tid)
            self.assertEqual(leak.leaks_in_observation(self.EASY.task, obs), [], tid)

if __name__ == "__main__":
    unittest.main()
