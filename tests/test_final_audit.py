"""Final pre-release audit (31 Oct, integrate/t111 @ 6c85bde): one regression test per fixed finding."""
import unittest
from decimal import Decimal
from navital_gym.envs.trip import load_env as trip_env
from navital_gym.envs.trip.solver import Solver
from navital_gym.envs.trip import rules as TR

TRIP = trip_env()

def _alt_day_plan():
    """IN-TRIP-033 gold plan; used as a base for altitude and fee cases."""
    t = TRIP.tasks["IN-TRIP-033"]
    return t, Solver(t).solve()

class TripAlt(unittest.TestCase):
    def test_gold_031_has_no_onward_travel_on_the_leh_arrival_day(self):
        t = TRIP.tasks["IN-TRIP-031"]; p = Solver(t).solve()
        r = TRIP.grade(t, p).to_dict()
        self.assertTrue(r["solved"])
        leh = [l for l in p["days"][0]["legs"] if l["to"] == "Leh"][0]
        self.assertFalse([l for l in p["days"][0]["legs"] if l is not leh and l["dep"][:10] == leh["arr"][:10]])

    def test_onward_bus_on_the_leh_arrival_day_fails(self):
        t = TRIP.tasks["IN-TRIP-031"]; p = Solver(t).solve()
        leh = [l for d in p["days"] for l in d["legs"] if l["to"] == "Leh"][0]
        bus = [l for d in p["days"] for l in d["legs"] if l["from"] == "Leh"][0]
        dur = (TR.dt.datetime.strptime(bus["arr"], TR.DT_FMT) - TR.dt.datetime.strptime(bus["dep"], TR.DT_FMT))
        day = leh["arr"][:10]
        bus["dep"] = day + "T21:30"; bus["arr"] = (TR.dt.datetime.strptime(bus["dep"], TR.DT_FMT) + dur).strftime(TR.DT_FMT)
        self.assertFalse(TRIP.grade(t, p).to_dict()["rules"]["R-ALT"])

    def test_sleeping_in_pangong_on_day_2_still_fails(self):
        t, p = _alt_day_plan()
        p["days"][1]["stay"] = {"hotel_id": "H-PANG-1", "rooms": [{"guests": 3}]}
        self.assertFalse(TRIP.grade(t, p).to_dict()["rules"]["R-ALT"])

class TripPermitAndInputs(unittest.TestCase):
    def test_a_night_in_a_protected_area_with_no_paid_visit_fails(self):
        t, p = _alt_day_plan()      # the audit's exact case: nights in Nubra and Pangong, no visits, so no fee anywhere
        a = p["days"][3]["legs"].pop(); a.update(dep="2027-07-09T08:00", arr="2027-07-09T16:01")
        b = p["days"][4]["legs"].pop(); b.update(dep="2027-07-10T08:00", arr="2027-07-10T14:29")
        p["days"][4]["legs"] = [a]; p["days"][5]["legs"] = [b]
        for d in p["days"]: d["activities"] = []
        p["days"][3]["stay"] = {"hotel_id": "H-NUBR-1", "rooms": [{"guests": 3}]}
        p["days"][4]["stay"] = {"hotel_id": "H-PANG-1", "rooms": [{"guests": 3}]}
        self.assertFalse(TRIP.grade(t, p).to_dict()["rules"]["R-PERMIT"])

    def test_calendar_edge_dates_return_an_error_not_a_crash(self):
        for call in ({"tool": "search_hotels", "args": {"city": "Delhi", "check_in": "9999-12-31", "nights": 2}},
                     {"tool": "search_trains", "args": {"from_city": "Mumbai", "to_city": "Kochi", "date": "9999-12-31"}}):
            TRIP.reset("IN-TRIP-002"); out = TRIP.step(call)
            self.assertIn("error", out["obs"])

    def test_a_malformed_binding_list_names_nothing(self):
        TRIP.reset("IN-TRIP-001")
        self.assertFalse(TRIP.grade(TRIP.task, {"status": "infeasible", "binding": ["R-OPEN", {"rule": "R-BUD"}]}).to_dict()["solved"])

class Upi(unittest.TestCase):
    def run_upi(self, tid, calls, ans):
        from navital_gym.envs.upi import load_env
        e = load_env(); e.reset(tid)
        for n, a in calls: e.step({"tool": n, "args": a})
        return e.step({"finalize": ans})["info"]

    def test_a_bare_answer_keeps_the_action_log(self):
        self.assertFalse(self.run_upi("IN-UPI-041", [("create_mandate", {"merchant": "StreamCo", "amount": 5000})],
                                      {"action": "needs_user_pin_to_register", "each_debit_needs_approval": False, "cap_applied": 15000})["solved"])
        self.assertTrue(self.run_upi("IN-UPI-001", [("initiate_payment", {"vpa": "asha10@upibank", "amount": 3800})], {"action": "paid"})["solved"])

    def test_compensation_is_compared_exactly(self):
        info = self.run_upi("IN-UPI-022", [("raise_dispute", {"txn_id": "TXN7003", "category": "failed_txn_debited"})],
                            {"answer": {"action": "escalate", "type": "p2m", "tat_date": "2026-11-15", "days_late": 1, "compensation_rs": "100.000000000000001", "compensation_automatic": True}})
        self.assertFalse(info["solved"])

class SupportNegative(unittest.TestCase):
    def test_a_negative_refund_fails_and_a_day_range_does_not(self):
        from navital_gym.envs.support import load_env
        from navital_gym.envs.support.baselines import oracle_agent
        env = load_env(); t = env.tasks["IN-SUP-001"]
        def ok(reply):
            sub = oracle_agent(None, None, t); sub["reply"] = reply
            return env.grade(t, sub).solved
        self.assertFalse(ok("आपका रिफंड ₹-1899 5 कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।"))
        self.assertFalse(ok("आपका रिफंड -1899 रुपये 5 कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।"))
        self.assertTrue(ok("आपका रिफंड ₹1899 5-7 कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।"))
        for bad in ("Aapka refund -₹1899 aapke account mein wapas aayega. Hum pickup bhej rahe hain.", "Aapka refund -₹ 1899 aapke account mein wapas aayega. Hum pickup bhej rahe hain.",
                    "Aapka refund Rs. -1899 aapke account mein wapas aayega. Hum pickup bhej rahe hain."):
            self.assertIsNotNone(__import__("re").search(r"(?:₹|(?<![a-z])rs\.?|(?<![a-z])inr)\s*[-−]\s*\d|(?<![\w.])(?<!\d )[-−](?:₹\s*)?\d", bad.lower()), bad)
        self.assertTrue(ok("आपका रिफंड ₹1899 5 -7 कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।"))
        self.assertTrue(ok("आपका रिफंड - ₹1899 आपके भुगतान स्रोत में 5 कार्य-दिवसों में आ जाएगा। हम पिकअप भेज रहे हैं।"))

if __name__ == "__main__":
    unittest.main()
