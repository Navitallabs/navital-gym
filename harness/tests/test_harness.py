"""The harness must pass a correct grader and FAIL known-bad ones (mutation test of the checker)."""
import os, random, sys, unittest, importlib
HERE = os.path.dirname(__file__); ROOT = os.path.join(HERE, "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "toy")]
from navital_qa import conformance as C
import toy_grader

CASES = os.path.join(ROOT, "cases")

def run(grader):
    rep = C.Report()
    import glob
    for f in sorted(glob.glob(os.path.join(CASES, "toy", "*.json"))):
        C.run_file(grader, f, rep, 3)
    return rep

def failing(rep):
    return {r["suite"] for r in rep.rows if not r["ok"]}

class T(unittest.TestCase):
    def test_good_grader_passes(self):
        rep = run(toy_grader.grade)
        self.assertEqual(rep.fail, 0, [r for r in rep.rows if not r["ok"]])

    def test_trusts_agent_total_cost(self):          # cheat: report a low total_cost
        def bad(task, sub):
            r = toy_grader.grade(task, sub)
            if isinstance(sub, dict) and "total_cost" in sub and sub["total_cost"] <= task["params"]["budget_inr"]:
                r["rules"]["R-BUD"] = True; r["score"] = sum(r["rules"].values()) / 3; r["solved"] = all(r["rules"].values())
            return r
        self.assertIn("correctness", failing(run(bad)))

    def test_trusts_claimed_score(self):
        def bad(task, sub):
            if isinstance(sub, dict) and sub.get("solved"):
                return {"score": 1.0, "solved": True, "rules": {}}
            return toy_grader.grade(task, sub)
        self.assertIn("cheating", failing(run(bad)))

    def test_crashes_on_garbage(self):
        def bad(task, sub):
            return toy_grader.grade(task, sub["status"]) if not isinstance(sub, dict) else toy_grader.grade(task, sub)
        self.assertIn("cheating", failing(run(bad)))

    def test_nondeterministic(self):
        def bad(task, sub):
            r = toy_grader.grade(task, sub); r["score"] = max(0.0, min(1.0, r["score"] - random.random() * 1e-3 * (r["score"] < 1))); return r
        self.assertIn("determinism", failing(run(bad)))

    def test_key_order_dependent(self):
        def bad(task, sub):
            r = toy_grader.grade(task, sub)
            if isinstance(sub, dict) and list(sub.keys())[0] != "status":
                r["score"] = 0.0; r["solved"] = False
            return r
        self.assertIn("determinism", failing(run(bad)))

    def test_mutates_input(self):
        def bad(task, sub):
            if isinstance(sub, dict): sub["graded"] = True
            return toy_grader.grade(task, sub)
        self.assertIn("determinism", failing(run(bad)))

    def test_impure_violation(self):                  # fails an extra rule -> purity check
        def bad(task, sub):
            r = toy_grader.grade(task, sub)
            if r["rules"].get("R-BUD") is False: r["rules"]["R-DATE"] = False
            return r
        self.assertIn("correctness", failing(run(bad)))

if __name__ == "__main__":
    unittest.main()
