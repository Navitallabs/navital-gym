"""Four regression tests requested by backend (31 Oct, grader id moving off d770b51e8362). Drop into tests/ of release/v1.1.
Each test says which v1.0.1/d770b51e8362 behaviour it catches. Fixtures: the Gemini answer is the real final answer of run
trip-gemini-3.1-flash-lite-full (IN-TRIP-039), embedded so the test needs no runs/ folder. No model calls, no spend."""
import copy, dataclasses, json, math, os, sys, unittest
from fractions import Fraction
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core.grader import Ctx
from navital_gym.envs import form, trip, upi
from navital_gym.envs.form import oracle as form_oracle
from navital_gym.envs.trip.rules import recompute_cost
from navital_gym.envs.trip.solver import Solver

FORM, TRIP, UPI = form.load_env(), trip.load_env(), upi.load_env()
GEMINI_039 = json.loads(r'''{"status": "plan", "booking_date": "2026-11-15", "days": [{"date": "2027-01-06", "legs": [{"mode": "road", "id": "TX-GUWA-SHIL", "from": "Guwahati", "to": "Shillong", "dep": "2027-01-06T10:00", "arr": "2027-01-06T13:35", "pax": 2, "vehicles": 1}], "stay": {"hotel_id": "H-SHIL-1", "rooms": [{"guests": 2}]}, "activities": []}, {"date": "2027-01-07", "legs": [], "stay": {"hotel_id": "H-SHIL-1", "rooms": [{"guests": 2}]}, "activities": [{"id": "Umiam Lake", "start": "2027-01-07T09:00", "end": "2027-01-07T10:30"}]}, {"date": "2027-01-08", "legs": [], "stay": {"hotel_id": "H-SHIL-1", "rooms": [{"guests": 2}]}, "activities": [{"id": "Cherrapunji day trip", "start": "2027-01-08T09:00", "end": "2027-01-08T14:00"}]}, {"date": "2027-01-09", "legs": [{"mode": "road", "id": "TX-GUWA-SHIL", "from": "Shillong", "to": "Guwahati", "dep": "2027-01-09T10:00", "arr": "2027-01-09T13:35", "pax": 2, "vehicles": 1}], "activities": []}]}''')

def trip_cost(task, plan):
    g = TRIP.grader
    ctx = Ctx(task=task, world=g.world_factory(task), sub=g.parse(copy.deepcopy(plan)))
    return recompute_cost(ctx)

def with_budget(task, budget):
    t = copy.deepcopy(task); t.params["budget_inr"] = int(budget); return t

def grade_trip(task, plan):
    return TRIP.grader.grade(task, copy.deepcopy(plan)).to_dict()


class FormPinAsNumber(unittest.TestCase):
    def test_1_pin_written_as_a_number_passes_r_pin_and_a_wrong_one_fails(self):
        """IN-FORM-016: pin 110001 as int must pass R-PIN (fails on d770b51e8362 because the oracle value is a string); a wrong PIN as int must still fail."""
        t = FORM.tasks["IN-FORM-016"]
        want = form_oracle.solve(t.meta["kind"], t.params["world"])
        self.assertEqual(str(want["pin"]), "110001")
        good = {"status": "plan", "answer": dict(want, pin=int(want["pin"]))}
        r = FORM.grader.grade(t, good).to_dict()
        self.assertTrue(r["rules"]["R-PIN"], r["details"].get("R-PIN"))
        bad = {"status": "plan", "answer": dict(want, pin=int(want["pin"]) + 1)}
        self.assertFalse(FORM.grader.grade(t, bad).to_dict()["rules"]["R-PIN"])
        # the string form keeps passing, and a malformed PIN (null where the oracle has a PIN) still fails
        self.assertTrue(FORM.grader.grade(t, {"status": "plan", "answer": dict(want)}).to_dict()["rules"]["R-PIN"])
        self.assertFalse(FORM.grader.grade(t, {"status": "plan", "answer": dict(want, pin=None)}).to_dict()["rules"]["R-PIN"])


class TripBudgetIsExact(unittest.TestCase):
    def test_2a_cost_is_not_a_float(self):
        """The recomputed cost must be an exact number (Fraction, Decimal or int), never a float."""
        t = TRIP.tasks["IN-TRIP-002"]; p = Solver(t).solve()
        self.assertNotIsInstance(trip_cost(t, p), float)

    def test_2b_budget_equal_to_cost_passes_one_rupee_less_fails(self):
        """IN-TRIP-002 (a child on half fare): budget == true cost passes R-BUD, budget == cost - 1 fails."""
        t = TRIP.tasks["IN-TRIP-002"]; p = Solver(t).solve(); c = trip_cost(t, p)
        self.assertEqual(Fraction(c).denominator, 1, "pick a task whose cost is a whole rupee amount")
        self.assertTrue(grade_trip(with_budget(t, c), p)["rules"]["R-BUD"])
        self.assertFalse(grade_trip(with_budget(t, c - 1), p)["rules"]["R-BUD"])

    def test_2c_half_fare_total_is_summed_exactly(self):
        """IN-TRIP-030 (child aged 5, half fare, the cost has a half rupee): budget floor(cost) fails, ceil(cost) passes. A float or rounded sum can flip this."""
        t = TRIP.tasks["IN-TRIP-030"]; p = Solver(t).solve(); c = Fraction(trip_cost(t, p))
        self.assertNotEqual(c.denominator, 1, "this task is expected to cost a fraction of a rupee")
        self.assertTrue(grade_trip(with_budget(t, math.ceil(c)), p)["rules"]["R-BUD"])
        self.assertFalse(grade_trip(with_budget(t, math.floor(c)), p)["rules"]["R-BUD"])

    def test_2d_every_solver_plan_sits_exactly_on_its_own_boundary(self):
        """Over every feasible task with a Solver plan: budget == cost passes, budget == cost - 1 fails (whole-rupee costs only); no cost is a float."""
        n = 0
        for tid, t in TRIP.tasks.items():
            if not t.expected_feasible or "R-BUD" not in t.rules:
                continue
            p = Solver(t).solve()
            if not isinstance(p, dict) or p.get("status") != "plan":
                continue
            c = trip_cost(t, p); n += 1
            self.assertNotIsInstance(c, float, tid)
            if Fraction(c).denominator == 1:
                self.assertTrue(grade_trip(with_budget(t, c), p)["rules"]["R-BUD"], tid)
                self.assertFalse(grade_trip(with_budget(t, c - 1), p)["rules"]["R-BUD"], tid)
        self.assertGreater(n, 30)


class RuleExceptionIsNotAPlainFailure(unittest.TestCase):
    def test_3_gemini_answer_on_in_trip_039_never_reports_could_not_evaluate(self):
        """Real answer of run trip-gemini-3.1-flash-lite-full on IN-TRIP-039: on v1.0.1 and d770b51e8362 R-BUD says 'could not evaluate: TypeError'.
        After the fix the answer must either parse into a valid verdict (every rule has a True/False reason that is not a crash) or fail with a named format error."""
        t = TRIP.tasks["IN-TRIP-039"]
        r = grade_trip(t, GEMINI_039)
        crashed = {k: v for k, v in r["details"].items() if "could not evaluate" in str(v)}
        self.assertEqual(crashed, {}, crashed)
        self.assertNotIn("unscorable", r["verdict"])
        if not r["valid"]:
            self.assertTrue(r["verdict"].startswith("invalid format") or "not a valid submission" in r["verdict"], r["verdict"])

    def test_3b_a_crashing_rule_is_reported_as_an_error_not_as_a_plain_failure(self):
        """The grader contract: a rule that raises must be distinguishable from a rule that returns False (named error, e.g. a verdict or detail beginning 'rule error: <RuleId>')."""
        from navital_gym.core.grader import Grader, Rule, RuleResult
        class Boom(Rule):
            id = "R-BOOM"
            def check(self, ctx):
                raise TypeError("x")
        class Ok(Rule):
            id = "R-OK"
            def check(self, ctx):
                return RuleResult(True, "")
        t = TRIP.tasks["IN-TRIP-002"]
        gr = Grader({"R-FMT": TRIP.grader.rules["R-FMT"], "R-BOOM": Boom(), "R-OK": Ok()}, TRIP.grader.world_factory, TRIP.grader.parse)
        t2 = dataclasses.replace(t, rules=["R-FMT", "R-BOOM", "R-OK"])
        r = gr.grade(t2, Solver(t).solve()).to_dict()
        text = (r["verdict"] + " " + json.dumps(r["details"])).lower()
        self.assertFalse(r["solved"])
        self.assertNotIn("could not evaluate: typeerror", text, "a crash must not read like an ordinary rule failure")
        self.assertIn("error", text)


class UpiMandatePromptsNamePin(unittest.TestCase):
    def test_4_mandate_prompts_say_the_owners_own_upi_pin_is_needed(self):
        """IN-UPI-041..045 (mandate): the prompt must contain 'UPI PIN' (registering a mandate needs the owner's own UPI PIN)."""
        for n in range(41, 46):
            tid = f"IN-UPI-{n:03d}"
            t = UPI.tasks[tid]
            self.assertEqual(t.meta["kind"], "mandate", tid)
            self.assertIn("UPI PIN", t.prompt, tid)


if __name__ == "__main__":
    unittest.main()
