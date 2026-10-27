import copy, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import leak
from navital_gym.envs.trip import load_env, grade, RULES
from navital_gym.envs.trip.solver import Solver, verdict
from navital_gym.envs.trip.world import TripWorld

ENV = load_env()
FAST = ["IN-TRIP-002", "IN-TRIP-003", "IN-TRIP-006", "IN-TRIP-012", "IN-TRIP-027", "IN-TRIP-041", "IN-TRIP-044", "IN-TRIP-050"]
INFEASIBLE_FAST = ["IN-TRIP-001", "IN-TRIP-016", "IN-TRIP-025", "IN-TRIP-032", "IN-TRIP-042", "IN-TRIP-049"]

class Tasks(unittest.TestCase):
    def test_every_task_rule_exists_and_ids_unique(self):
        self.assertEqual(len(ENV.tasks), 55)
        for t in ENV.tasks.values():
            for r in t.rules:
                self.assertIn(r, RULES, f"{t.id}: unknown rule {r}")

    def test_no_hidden_field_reaches_the_agent(self):
        for tid in ENV.task_ids():
            obs = ENV.reset(tid)
            self.assertEqual(leak.leaks_in_observation(ENV.task, obs), [], tid)
            self.assertEqual(set(ENV.task.public()), {"id", "prompt", "lang"})
            blob = json.dumps(obs)
            for key in leak.HIDDEN_KEYS:
                self.assertNotIn(f'"{key}"', blob)

    def test_tool_output_never_exposes_hidden_fields(self):
        for tid in FAST + INFEASIBLE_FAST:
            ENV.reset(tid)
            outs = [ENV.world.call("calendar_info", {}), ENV.world.call("list_attractions", {"city": ENV.task.params["origin"]}),
                    ENV.world.call("search_hotels", {"city": ENV.task.params["origin"], "check_in": ENV.task.params["start"], "nights": 1})]
            self.assertEqual(leak.find_leaks(ENV.task, json.dumps(outs), "tools"), [], tid)

class World(unittest.TestCase):
    def test_world_is_deterministic_and_seeded(self):
        t = ENV.tasks["IN-TRIP-002"]
        self.assertEqual(TripWorld(t, 0).fingerprint(), TripWorld(t, 0).fingerprint())
        self.assertNotEqual(TripWorld(t, 0).fingerprint(), TripWorld(t, 1).fingerprint())

    def test_tools_never_crash_on_bad_args(self):
        ENV.reset("IN-TRIP-002")
        for name, args in [("search_trains", {}), ("search_trains", {"from_city": "X", "to_city": "Y", "date": "2026-12-01"}), ("search_hotels", {"city": "Delhi", "check_in": "nope", "nights": 2}),
                           ("train_availability", {"train_id": "1", "date": "2026-12-01", "cls": "ZZ", "quota": "GN"}), ("nope", {}), ("attraction_info", {"name": 5})]:
            self.assertIn("error", ENV.world.call(name, args))

class RuleIndependence(unittest.TestCase):
    """A plan that breaks exactly one rule fails that rule and nothing else (qa's purity check, in-repo)."""
    def failed(self, tid, mutate):
        t = ENV.tasks[tid]; p = copy.deepcopy(Solver(t).solve()); mutate(p, TripWorld(t, 0))
        r = grade(t.to_dict(), p)
        return sorted(k for k, v in r["rules"].items() if not v)

    @staticmethod
    def swap_hotel(pred):
        def m(p, w):
            for d in p["days"]:
                if "stay" in d:
                    bad = [h for h in w.hotels[w.hotel_by_id[d["stay"]["hotel_id"]]["city"]] if pred(h)]
                    if bad:
                        d["stay"]["hotel_id"] = bad[0]["id"]; return
            raise unittest.SkipTest("no such hotel in this task's cities")
        return m

    def test_quota(self):
        self.assertEqual(self.failed("IN-TRIP-002", lambda p, w: p.update(booking_date="2026-11-14")), ["R-QUOTA"])

    def test_occupancy_rooms(self):
        self.assertEqual(self.failed("IN-TRIP-002", lambda p, w: next(d for d in p["days"] if "stay" in d)["stay"]["rooms"][0].update(guests=1)), ["R-OCC"])

    def test_diet(self):
        self.assertEqual(self.failed("IN-TRIP-006", self.swap_hotel(lambda h: not h["veg"])), ["R-DIET"])

    def test_stairs(self):
        for tid in ("IN-TRIP-008", "IN-TRIP-011", "IN-TRIP-028", "IN-TRIP-050"):
            try:
                self.assertEqual(self.failed(tid, self.swap_hotel(lambda h: not h["lift"] and not h["ground_floor"])), ["R-ACC"], tid)
                return
            except unittest.SkipTest:
                continue
        self.skipTest("no stair-only hotel in any no_stairs task")

    def test_last_date(self):
        self.assertIn("R-DATE", self.failed("IN-TRIP-003", lambda p, w: p["days"].pop()))

class Leniency(unittest.TestCase):
    def test_an_empty_stay_object_means_no_hotel_but_a_half_filled_one_is_a_format_error(self):
        t = ENV.tasks["IN-TRIP-002"]; p = Solver(t).solve()
        base = grade(t.to_dict(), p)
        for empty in (None, {}, {"hotel_id": None, "rooms": []}, {"hotel_id": "", "rooms": []}):
            q = copy.deepcopy(p); q["days"][-1]["stay"] = empty
            self.assertEqual(grade(t.to_dict(), q), base)
        q = copy.deepcopy(p); q["days"][-1]["stay"] = {"hotel_id": None, "rooms": [{"guests": 2}]}
        r = grade(t.to_dict(), q)
        self.assertFalse(r["solved"]); self.assertFalse(r["rules"]["R-FMT"])

class EasySplit(unittest.TestCase):
    def test_easy_split_is_separate_labelled_by_the_solver_and_does_not_change_the_standard_set(self):
        self.assertEqual(len(ENV.tasks), 55)                                  # default load is core only: samples and results stay valid
        easy = load_env(splits=("easy",))
        self.assertEqual(len(easy.tasks), 18)
        self.assertTrue(all(t.meta.get("split") == "easy" and t.id.startswith("IN-TRIP-E") for t in easy.tasks.values()))
        self.assertFalse(set(easy.task_ids()) & set(ENV.task_ids()))
        both = load_env(splits=("core", "easy")); self.assertEqual(len(both.tasks), 73)
        inf = [t for t in easy.tasks.values() if not t.expected_feasible]
        self.assertTrue(3 <= len(inf) <= 6 and all(t.binding for t in inf))
        for tid in easy.task_ids():
            obs = easy.reset(tid)
            self.assertEqual(leak.leaks_in_observation(easy.task, obs), [], tid)
            t = easy.tasks[tid]
            if t.expected_feasible:
                self.assertTrue(grade(t.to_dict(), Solver(t).solve())["solved"], tid)
            else:
                self.assertTrue(grade(t.to_dict(), {"status": "infeasible", "binding": list(t.binding)})["solved"], tid)

    def test_by_split_reports_easy_and_core_separately(self):
        from navital_gym.core.runner import run_suite
        both = load_env(splits=("core", "easy"))
        r = run_suite(both, both_oracle(), ["IN-TRIP-002", "IN-TRIP-E01"], 1)
        self.assertEqual(sorted(r["summary"]["by_split"]), ["core", "easy"])

def both_oracle():
    from navital_gym.envs.trip import get_baselines
    return get_baselines()["oracle"]

class MultiCause(unittest.TestCase):
    def test_any_nonempty_subset_of_the_true_binding_rules_is_accepted(self):
        t = ENV.tasks["IN-TRIP-029"].to_dict()
        self.assertEqual(sorted(t["binding"]), ["R-BUD", "R-DATE"])
        for claim in (["R-BUD"], ["R-DATE"], ["R-BUD", "R-DATE"], ["R-DATE", "R-BUD"]):
            self.assertTrue(grade(t, {"status": "infeasible", "binding": claim})["solved"], claim)
        for claim in ([], ["R-ACC"], ["R-BUD", "R-ACC"]):
            self.assertFalse(grade(t, {"status": "infeasible", "binding": claim})["solved"], claim)

class Tatkal(unittest.TestCase):
    def test_surcharge_is_10_percent_for_2S_only_and_30_for_every_other_class(self):
        from navital_gym.envs.trip.world import TATKAL_PCT
        self.assertEqual(TATKAL_PCT["2S"], 0.10)
        for c in ("SL", "CC", "3A", "2A"):
            self.assertEqual(TATKAL_PCT[c], 0.30, c)

    def test_leg_cost_and_tool_use_the_same_surcharge(self):
        from navital_gym.envs.trip.rules import leg_cost
        import datetime as dt
        w = TripWorld(ENV.tasks["IN-TRIP-043"], 0)       # snapshot 2026-12-03, travel 12-04: Tatkal day
        tr = next(t for t in w.trains_between("Mumbai", "Pune", dt.date(2026, 12, 4)))
        for cls in tr["classes"]:
            base = tr["fares"][cls]
            lg = {"mode": "rail", "id": tr["id"], "cls": cls, "quota": "TQ", "pax": 2, "half": 0, "frm": "Mumbai", "to": "Pune", "dep": dt.datetime(2026, 12, 4, 8)}
            pct = 0.10 if cls == "2S" else 0.30
            self.assertAlmostEqual(leg_cost(w, lg), base * (1 + pct) * 2)
            lg["quota"] = "GN"
            self.assertAlmostEqual(leg_cost(w, lg), base * 2)
            ENV.reset("IN-TRIP-043")
            out = ENV.world.call("train_availability", {"train_id": tr["id"], "date": "2026-12-04", "cls": cls, "quota": "TQ"})
            self.assertEqual(out["tatkal_surcharge_pct"], int(pct * 100))

class Grading(unittest.TestCase):
    def plan(self, tid):
        return Solver(ENV.tasks[tid]).solve()

    def test_oracle_plans_solve_feasible_tasks(self):
        for tid in FAST:
            p = self.plan(tid)
            self.assertIsNotNone(p, tid)
            r = grade(ENV.tasks[tid].to_dict(), p)
            self.assertTrue(r["solved"] and r["score"] == 1.0, (tid, r))

    def test_infeasible_tasks_need_the_right_claim_and_plans_score_zero(self):
        for tid in INFEASIBLE_FAST:
            t = ENV.tasks[tid]
            self.assertFalse(t.expected_feasible, tid)
            self.assertTrue(grade(t.to_dict(), {"status": "infeasible", "binding": list(t.binding)})["solved"], tid)
            self.assertFalse(grade(t.to_dict(), {"status": "infeasible", "binding": ["R-FMT"]})["solved"], tid)
            self.assertFalse(grade(t.to_dict(), {"status": "infeasible", "binding": list(RULES)})["solved"], tid)   # shotgun claims fail
            self.assertFalse(grade(t.to_dict(), {"status": "infeasible", "binding": list(t.binding) + ["R-ACC"]})["solved"], tid)   # a true rule plus padding fails
            self.assertFalse(grade(t.to_dict(), {"status": "infeasible", "binding": []})["solved"], tid)

    def test_false_infeasible_claim_on_feasible_task_scores_zero(self):
        r = grade(ENV.tasks["IN-TRIP-002"].to_dict(), {"status": "infeasible", "binding": ["R-BUD"]})
        self.assertFalse(r["solved"]); self.assertEqual(r["score"], 0.0)

    def test_claimed_fields_are_ignored_and_input_not_mutated(self):
        t = ENV.tasks["IN-TRIP-002"].to_dict()
        p = self.plan("IN-TRIP-002")
        base = grade(t, p)
        forged = copy.deepcopy(p); forged.update({"total_cost": 1, "score": 1.0, "solved": True, "rules": {"R-BUD": True}})
        before = json.dumps(forged, sort_keys=True)
        self.assertEqual(grade(t, forged)["score"], base["score"])
        self.assertEqual(json.dumps(forged, sort_keys=True), before)
        self.assertEqual(grade(t, p), base)           # deterministic

    def test_garbage_scores_zero(self):
        t = ENV.tasks["IN-TRIP-002"].to_dict()
        for junk in (None, 7, "plan", [], {}, {"status": "plan"}, {"status": "plan", "days": "x", "booking_date": "2026-11-15"}, "A" * 300000, {"status": "plan", "days": [None] * 500}):
            r = grade(t, junk)
            self.assertFalse(r["solved"], str(junk)[:30]); self.assertLess(r["score"], 0.5)

    def test_single_violations_fail_that_rule(self):
        tid = "IN-TRIP-002"; t = ENV.tasks[tid].to_dict(); p = self.plan(tid)
        for mutate, rule in [(lambda q: q["days"][0]["legs"][0].update(pax=1), "R-OCC"),
                             (lambda q: q.update(booking_date="2026-11-14"), "R-QUOTA")]:
            q = copy.deepcopy(p); mutate(q)
            r = grade(t, q)
            self.assertFalse(r["solved"]); self.assertFalse(r["rules"][rule], (rule, r))

    def test_budget_is_recomputed_not_trusted(self):
        t = ENV.tasks["IN-TRIP-002"]; p = self.plan("IN-TRIP-002")
        tight = copy.deepcopy(t.to_dict()); tight["params"]["budget_inr"] = 1000
        r = grade(tight, p)
        self.assertFalse(r["rules"]["R-BUD"])

if __name__ == "__main__":
    unittest.main()
