"""T-111 trip fixes (Codex full audit #10 and #12): an overnight arrival is travel on the arrival day (R-REST); the daily aarti is needed on every evening
the traveller can attend it, including the evening of the day they leave (IN-TRIP-027). Tests written before the fix: they fail on 02582e3."""
import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core.grader import Ctx
from navital_gym.envs.trip import load_env, rules as R
from navital_gym.envs.trip.solver import Solver
from navital_gym.envs.trip.world import TripWorld

ENV = load_env()
D1 = dt.date(2026, 12, 19)

def rest_verdict(legs, days, need=1, tid="IN-TRIP-003"):
    task = ENV.tasks[tid]
    ctx = Ctx(task=task, world=TripWorld(task, 0), sub={})
    ctx.cache["plan"] = ({"days": days, "legs": legs}, [])
    task.params["rest_days"] = need                       # a plain dict: set for this probe only
    return R.RRest().check(ctx)

def leg(dep, arr):
    return {"mode": "road", "id": "X", "frm": "A", "to": "B", "dep": dep, "arr": arr}

class RestDay(unittest.TestCase):
    def setUp(self):
        self.saved = {k: dict(t.params) for k, t in ENV.tasks.items()}
    def tearDown(self):
        for k, t in ENV.tasks.items(): t.params.clear(); t.params.update(self.saved[k])

    def days(self, n=2):
        return [{"date": D1 + dt.timedelta(days=i), "legs": [], "acts": []} for i in range(n)]

    def test_a_long_overnight_leg_makes_the_arrival_day_a_travel_day(self):
        """Codex: the Dec 21-22 bus arriving 04:58 left Dec 22 listed as a rest day (R-REST read only legs departing that day)."""
        night = leg(dt.datetime(2026, 12, 19, 22, 0), dt.datetime(2026, 12, 20, 4, 58))
        days = self.days(); days[0]["legs"] = [night]
        r = rest_verdict([night], days, need=1)
        self.assertFalse(r.passed, r.detail)

    def test_a_short_overnight_leg_does_not_spoil_the_rest_day(self):
        short = leg(dt.datetime(2026, 12, 19, 23, 0), dt.datetime(2026, 12, 20, 0, 30))      # 1.5 hours
        days = self.days(); days[0]["legs"] = [short]
        r = rest_verdict([short], days, need=1)
        self.assertTrue(r.passed, r.detail)

    def test_an_idle_day_is_still_a_rest_day(self):
        self.assertTrue(rest_verdict([], self.days(), need=2).passed)

class Aarti(unittest.TestCase):
    def test_the_oracle_attends_the_aarti_on_every_evening_it_can(self):
        """Codex: the oracle waits in Varanasi until 23:20 on the departure day and schedules no aarti that evening."""
        t = ENV.tasks["IN-TRIP-027"]
        plan = Solver(t).solve()
        self.assertIsNotNone(plan, "027 must stay solvable")
        w = TripWorld(t, 0)
        from navital_gym.envs.trip import data as D
        att = D.ATTRACTIONS["Ganga Aarti"]
        ctx = Ctx(task=t, world=w, sub=plan)
        R.normalize(ctx); ivs = R.timeline(ctx)[0]
        start = dt.date.fromisoformat(t.params["start"])
        missing = []
        for i, day in enumerate(plan["days"]):
            date = start + dt.timedelta(days=i)
            has = any(a["id"] == "Ganga Aarti" for a in day.get("activities", []))
            if R.evening_possible(ivs, "Varanasi", att, date) and not has: missing.append(str(date))
        self.assertEqual(missing, [])

    def test_dropping_the_aarti_on_an_attendable_evening_fails_the_route(self):
        from navital_gym.envs.trip import grade
        from navital_gym.envs.trip import data as D
        t = ENV.tasks["IN-TRIP-027"]; plan = Solver(t).solve()
        self.assertIsNotNone(plan)
        att = D.ATTRACTIONS["Ganga Aarti"]
        ctx = Ctx(task=t, world=TripWorld(t, 0), sub=plan); R.normalize(ctx); ivs = R.timeline(ctx)[0]
        start = dt.date.fromisoformat(t.params["start"]); import copy
        for i, day in enumerate(plan["days"]):
            if any(a["id"] == "Ganga Aarti" for a in day.get("activities", [])) and R.evening_possible(ivs, "Varanasi", att, start + dt.timedelta(days=i)):
                p2 = copy.deepcopy(plan); p2["days"][i]["activities"] = [a for a in p2["days"][i]["activities"] if a["id"] != "Ganga Aarti"]
                self.assertFalse(grade(t.to_dict(), p2)["rules"]["R-ROUTE"]); return
        self.fail("no aarti evening to drop")

if __name__ == "__main__":
    unittest.main()
