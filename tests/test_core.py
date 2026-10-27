import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import Task, leak, Grader, summarize
from navital_gym.core.schema import TaskError

class SchemaAndLeak(unittest.TestCase):
    def task(self, **kw):
        d = {"id": "t1", "family": "f", "difficulty": 1, "lang": "en", "prompt": "Plan a trip.", "params": {}, "rules": ["R-X"],
             "expected_feasible": False, "binding_constraint": ["R-X"], "traps": ["designer note: budget impossible"]}
        d.update(kw)
        return Task.from_dict(d)

    def test_public_view_has_only_id_prompt_lang(self):
        self.assertEqual(set(self.task().public()), {"id", "prompt", "lang"})

    def test_hidden_fields_are_declared(self):
        for k in ("expected_feasible", "binding", "traps", "gold_answer", "forbidden_actions", "grader_notes"):
            self.assertIn(k, Task.HIDDEN)

    def test_leak_check_catches_tells_and_trap_text(self):
        t = self.task()
        self.assertTrue(leak.find_leaks(t, "This budget impossible task"))
        self.assertTrue(leak.find_leaks(t, '{"expected_feasible": false}'))
        self.assertTrue(leak.find_leaks(self.task(traps=["the Taj is closed on Fridays"]), "note: the taj is closed on fridays"))
        self.assertEqual(leak.find_leaks(t, "Plan a 3 day trip, Rs 10,000."), [])

    def test_bad_task_rejected(self):
        with self.assertRaises(TaskError):
            Task.from_dict({"id": "x"})

class GraderNeverRaises(unittest.TestCase):
    def test_garbage_scores_zero(self):
        g = Grader({}, lambda t: None, lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
        t = Task.from_dict({"id": "t", "prompt": "p", "params": {}, "rules": []})
        for junk in (None, 1, "x", [], {}, {"a": object()}):
            r = g.grade(t, junk)
            self.assertFalse(r.solved); self.assertEqual(r.score, 0.0)

    def test_summarize_pass_at_k(self):
        from navital_gym.core.grader import Score
        s = summarize({"a": [Score(solved=True, score=1), Score(solved=True, score=1)], "b": [Score(solved=True, score=1), Score()]})
        self.assertEqual(s["pass@1"], 1.0); self.assertEqual(s["pass^k"], 0.5)

class PartialCredit(unittest.TestCase):
    def test_a_well_formed_empty_answer_earns_nothing(self):
        from navital_gym.core.grader import Rule, RuleResult
        class Fmt(Rule):
            id, gate = "R-FMT", True
            def check(self, ctx): return RuleResult(isinstance(ctx.sub, dict))
        class Need(Rule):
            id = "R-NEED"
            def check(self, ctx): return RuleResult(ctx.sub.get("x") == 1)
        g = Grader({"R-FMT": Fmt(), "R-NEED": Need()}, lambda t: None, lambda s: s if isinstance(s, dict) else None)
        t = Task.from_dict({"id": "t", "prompt": "p", "params": {}, "rules": ["R-FMT", "R-NEED"], "expected_feasible": True})
        empty = g.grade(t, {"status": "plan"})
        self.assertEqual(empty.score, 0.0); self.assertFalse(empty.solved)
        self.assertTrue(g.grade(t, {"status": "plan", "x": 1}).solved)

class SplitsAndKinds(unittest.TestCase):
    def test_summary_never_only_a_mixed_number(self):
        from navital_gym.core.grader import Score
        mk = lambda i, split, feas, solved: (i, Task.from_dict({"id": i, "prompt": "p", "params": {}, "rules": [], "expected_feasible": feas, "meta": {"split": split} if split else {}}), [Score(solved=solved, score=1.0 if solved else 0.0)])
        rows = [mk("a", None, True, True), mk("b", "core", False, False), mk("c", "experimental", True, False), mk("d", "experimental", False, False)]
        results = {i: r for i, _, r in rows}; tasks = {i: t for i, t, _ in rows}
        s = summarize(results, tasks)
        self.assertEqual(s["pass@1"], 0.25)
        self.assertEqual(s["by_split"]["core"]["tasks"], 2); self.assertEqual(s["by_split"]["core"]["pass@1"], 0.5)
        self.assertEqual(s["by_split"]["experimental"]["pass@1"], 0.0)
        self.assertEqual(s["by_kind"]["feasible"]["tasks"], 2); self.assertEqual(s["by_kind"]["infeasible"]["tasks"], 2)
        self.assertNotIn("by_split", summarize(results))        # no task info, no breakdown claimed

    def test_report_prints_each_split_table(self):
        from navital_gym.core.runner import format_report
        from navital_gym.core.grader import Score
        t = {"a": Task.from_dict({"id": "a", "prompt": "p", "params": {}, "rules": []}), "b": Task.from_dict({"id": "b", "prompt": "p", "params": {}, "rules": [], "meta": {"split": "experimental"}})}
        rep = {"agent": "x", "summary": summarize({"a": [Score(solved=True, score=1)], "b": [Score()]}, t)}
        txt = format_report([rep])
        self.assertIn("split = core", txt); self.assertIn("split = experimental", txt)

if __name__ == "__main__":
    unittest.main()


class CodeId(unittest.TestCase):
    def test_code_id_is_a_tree_id_matching_git(self):
        from navital_gym.core.version import code_id
        import subprocess, os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try: tree = subprocess.check_output(["git", "rev-parse", "HEAD:navital_gym"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()[:12]
        except Exception: self.skipTest("not a git checkout")
        self.assertTrue(code_id().startswith(tree))


class NotRun(unittest.TestCase):
    def _sc(self, solved, error=None):
        from navital_gym.core.grader import Score
        sc = Score(solved=solved, score=1.0 if solved else 0.0, rules={"R": solved}, valid=True, verdict="pass" if solved else "fail") if "verdict" in Score.__dataclass_fields__ else None
        if sc is None: self.skipTest("Score signature differs")
        sc.meta = {"error": error} if error else {}
        return sc

    def test_provider_errors_are_not_run_and_never_count_as_wrong_answers(self):
        from navital_gym.core.grader import summarize
        res = {"a": [self._sc(True)], "b": [self._sc(False)], "c": [self._sc(False, "HTTP 429: quota")], "d": [self._sc(False, "HTTP 429: quota")]}
        s = summarize(res)
        self.assertEqual((s["tasks"], s["answered"], s["not_run"]), (4, 2, 2))
        self.assertAlmostEqual(s["pass@1"], 0.5)          # 1 of the 2 answered tasks, not 1 of 4

    def test_daily_quota_is_told_apart_from_a_per_minute_limit(self):
        from navital_gym.core import agents as A
        self.assertEqual(A._daily_quota_wait("Rate limit reached ... on tokens per day (TPD): Limit 200000 ... Please try again in 1h2m3.5s."), (True, 3723.5))
        self.assertEqual(A._daily_quota_wait("you have used up your daily free allocation of 10,000 neurons")[0], True)
        self.assertEqual(A._daily_quota_wait("Rate limit reached on tokens per minute (TPM). Please try again in 4s."), (False, None))

    def test_a_daily_quota_stops_the_suite_and_the_task_is_not_stored(self):
        from navital_gym.core.runner import run_suite
        from navital_gym.envs import trip
        env = trip.load_env()
        class Q:
            name = "q"; meta = {}
            def __init__(self): self.n = 0
            def solve(self, obs, call, task):
                self.n += 1
                self.meta = {"error": "HTTP 429: daily quota used up", "quota_exhausted": True, "quota_wait": 60} if self.n == 3 else {}
                return {}
        rep = run_suite(env, Q(), env.task_ids()[:6], 1)
        self.assertEqual(len(rep["results"]), 2)                       # the third task hit the quota: not run, not stored
        self.assertEqual(rep["quota_exhausted"]["wait"], 60)
