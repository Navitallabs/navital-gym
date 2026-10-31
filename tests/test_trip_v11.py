"""v1.1 trip rule changes (review's K2-K4 spec): Tatkal OTP hand-off, general quota open to the day before, Ladakh fee instead of a permit."""
import copy, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.trip import load_env, grade
from navital_gym.envs.trip.solver import Solver
from navital_gym.envs.trip.world import TripWorld

ENV = load_env()

def solved_plan(tid):
    return copy.deepcopy(Solver(ENV.tasks[tid]).solve())

def rail_legs(plan):
    return [lg for d in plan["days"] for lg in d["legs"] if lg["mode"] == "rail"]

class Tatkal(unittest.TestCase):
    """K2: a Tatkal leg is only valid if the traveller's Aadhaar OTP hand-off is marked."""
    def test_043_stays_a_tatkal_task_and_the_oracle_marks_the_otp(self):
        t = ENV.tasks["IN-TRIP-043"]; self.assertTrue(t.expected_feasible)
        plan = solved_plan("IN-TRIP-043"); legs = rail_legs(plan)
        self.assertTrue(legs and all(lg["quota"] == "TQ" and lg["traveller_otp"] is True for lg in legs))
        self.assertTrue(grade(t.to_dict(), plan)["solved"])

    def test_a_tatkal_leg_without_the_otp_fails_r_quota_alone(self):
        t = ENV.tasks["IN-TRIP-043"]; plan = solved_plan("IN-TRIP-043")
        for lg in rail_legs(plan): lg.pop("traveller_otp")
        r = grade(t.to_dict(), plan)
        self.assertFalse(r["rules"]["R-QUOTA"]); self.assertEqual([k for k, v in r["rules"].items() if not v], ["R-QUOTA"])

    def test_a_non_boolean_otp_is_a_format_error(self):
        t = ENV.tasks["IN-TRIP-043"]; plan = solved_plan("IN-TRIP-043")
        for lg in rail_legs(plan): lg["traveller_otp"] = "yes"
        self.assertFalse(grade(t.to_dict(), plan)["solved"])

    def test_the_tool_says_the_otp_is_needed(self):
        ENV.reset("IN-TRIP-043")
        out = ENV.world.call("train_availability", {"train_id": rail_legs(solved_plan("IN-TRIP-043"))[0]["id"], "date": "2026-12-04", "cls": rail_legs(solved_plan("IN-TRIP-043"))[0]["class"], "quota": "TQ"})
        self.assertIn("Aadhaar OTP", str(out))

class General(unittest.TestCase):
    """K3: General quota is open until the day before departure (v1.0.1 closed it 2 days before); sold-out corridors keep 023 and 043 on Tatkal."""
    def test_general_quota_is_open_one_day_before_unless_sold_out(self):
        w = TripWorld(ENV.tasks["IN-TRIP-002"], 0)
        from navital_gym.envs.trip import rules as R
        import datetime as dt
        today = w.today
        lg = lambda days, q="GN": {"dep": dt.datetime.combine(today + dt.timedelta(days=days), dt.time(8)), "quota": q}
        self.assertTrue(R._quota_open(w, today, lg(1))[0]); self.assertTrue(R._quota_open(w, today, lg(60))[0])
        self.assertFalse(R._quota_open(w, today, lg(0))[0]); self.assertFalse(R._quota_open(w, today, lg(61))[0])

    def test_023_and_043_corridors_are_sold_out_on_their_dates(self):
        from navital_gym.envs.trip import data as D
        self.assertIn("2026-12-04", D.SOLD_OUT[("Mumbai", "Pune")]); self.assertIn("2026-11-16", D.SOLD_OUT[("Mumbai", "Goa")])
        self.assertTrue(ENV.tasks["IN-TRIP-023"].expected_feasible)

class Ladakh(unittest.TestCase):
    """K4: Nubra and Pangong need the fee paid; there is no advance-booking rule and no Pangong ticket."""
    def test_a_ladakh_plan_needs_fee_paid_and_has_no_date_rule(self):
        t = ENV.tasks["IN-TRIP-031"]; plan = solved_plan("IN-TRIP-031")
        acts = [a for d in plan["days"] for a in d["activities"] if a["id"] in ("Pangong Lake", "Diskit Monastery and Hunder dunes")]
        self.assertTrue(acts and all(a.get("fee_paid") is True for a in acts))
        self.assertTrue(grade(t.to_dict(), plan)["solved"])
        bad = copy.deepcopy(plan)
        for d in bad["days"]:
            for a in d["activities"]:
                a.pop("fee_paid", None)
        r = grade(t.to_dict(), bad); self.assertFalse(r["rules"]["R-PERMIT"])

    def test_pangong_has_no_ticket_and_the_tool_names_the_fee(self):
        from navital_gym.envs.trip import data as D
        self.assertEqual(D.ATTRACTIONS["Pangong Lake"]["adult_inr"], 0)
        ENV.reset("IN-TRIP-031"); info = ENV.world.call("permit_info", {"place": "Pangong Lake"})
        self.assertTrue(info["fee_required"]); self.assertIn("Red Cross", info["what"]); self.assertNotIn("permit_required", info)

class Labels(unittest.TestCase):
    def test_every_feasibility_label_still_matches_the_solver_for_the_changed_tasks(self):
        from navital_gym.envs.trip.solver import verdict
        for tid in ("IN-TRIP-023", "IN-TRIP-025", "IN-TRIP-029", "IN-TRIP-031", "IN-TRIP-032", "IN-TRIP-033", "IN-TRIP-034", "IN-TRIP-035", "IN-TRIP-042", "IN-TRIP-043"):
            t = ENV.tasks[tid]; v = verdict(t)
            self.assertEqual(v["feasible"], t.expected_feasible, tid)
            if not v["feasible"]: self.assertEqual(sorted(v["binding"]), sorted(t.binding), tid)



class TripDataFixes(unittest.TestCase):
    """fix/trip-data: no hidden diet requirement on 028/029/030/054; the calendar tool states the grader's 1-60 day GN window."""
    def test_pilgrimage_prompts_that_never_ask_for_satvik_carry_no_diet_param(self):
        from navital_gym.envs.trip import build_tasks
        rows = {r["id"]: r for r in build_tasks.build()}      # tasks.jsonl is generated from tasks_source.jsonl; check the source of truth
        for tid in ("IN-TRIP-027", "IN-TRIP-028", "IN-TRIP-029", "IN-TRIP-030", "IN-TRIP-054"):
            r = rows[tid]
            self.assertNotIn("satvik", r["prompt"].lower())
            self.assertEqual(r["params"]["diet"], "any", tid)
            self.assertNotIn("R-DIET", r["rules"], tid)

    def test_calendar_info_states_the_one_to_sixty_day_gn_window(self):
        info = TripWorld(ENV.tasks["IN-TRIP-001"]).calendar_info()
        self.assertIn("1 to 60 days", info["booking"]); self.assertNotIn("2 to 60", info["booking"])

if __name__ == "__main__":
    unittest.main()


class TaskIntent(unittest.TestCase):
    """v1.1 full audit (Codex, review-confirmed): 039 excludes Kaziranga; 050 asks for a hotel with a lift."""
    def test_039_a_kaziranga_visit_fails_r_route(self):
        t = ENV.tasks["IN-TRIP-039"]; plan = solved_plan("IN-TRIP-039")
        self.assertTrue(grade(t.to_dict(), plan)["solved"])
        day = plan["days"][1]
        day["activities"] = day.get("activities", []) + [{"id": "Kaziranga Jeep Safari", "start": day["date"] + "T09:00", "end": day["date"] + "T12:00"}]
        self.assertFalse(grade(t.to_dict(), plan)["rules"]["R-ROUTE"])

    def test_050_a_ground_floor_hotel_without_a_lift_fails_r_acc(self):
        t = ENV.tasks["IN-TRIP-050"]; plan = solved_plan("IN-TRIP-050")
        self.assertTrue(grade(t.to_dict(), plan)["solved"])
        for d in plan["days"]:
            if d.get("stay"):
                d["stay"]["hotel_id"] = "H-VARA-1"      # ground-floor rooms, no lift (the hotel the v1.1.0 oracle chose)
        self.assertFalse(grade(t.to_dict(), plan)["rules"]["R-ACC"])
