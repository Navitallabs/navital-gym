"""R-PERMIT, one fee per trip (T-111, 31 Oct): a night in Nubra or Pangong needs the Ladakh protected-area fee, paid with a fee_paid
visit to Nubra or Pangong anywhere on the trip."""
import copy, unittest
from navital_gym.envs.trip import load_env
from navital_gym.envs.trip.solver import Solver

TRIP = load_env()
T = TRIP.tasks["IN-TRIP-033"]
GOLD = Solver(T).solve()

def _nights(nubra=True, pangong=True):
    """IN-TRIP-033 gold, re-timed so the travellers sleep in Nubra (day 4) and/or Pangong (day 5); no activities, so no fee anywhere."""
    p = copy.deepcopy(GOLD)
    a = p["days"][3]["legs"].pop(); a.update(dep="2027-07-09T08:00", arr="2027-07-09T16:01")
    b = p["days"][4]["legs"].pop(); b.update(dep="2027-07-10T08:00", arr="2027-07-10T14:29")
    p["days"][4]["legs"] = [a]; p["days"][5]["legs"] = [b]
    for d in p["days"]: d["activities"] = []
    if nubra: p["days"][3]["stay"] = {"hotel_id": "H-NUBR-1", "rooms": [{"guests": 3}]}
    if pangong: p["days"][4]["stay"] = {"hotel_id": "H-PANG-1", "rooms": [{"guests": 3}]}
    return p

def _visit(p, day, name, start, end, paid=True):
    p["days"][day]["activities"].append({"id": name, "start": start, "end": end, "fee_paid": paid})

def permit(p):
    r = TRIP.grade(T, p).to_dict(); return r["rules"]["R-PERMIT"]

class OneFeePerTrip(unittest.TestCase):
    def test_no_fee_anywhere_fails(self):
        self.assertFalse(permit(_nights()))
        self.assertFalse(permit(_nights(pangong=False)))
        self.assertFalse(permit(_nights(nubra=False)))

    def test_a_night_in_nubra_and_a_paid_pangong_visit_passes(self):
        p = _nights(pangong=False); _visit(p, 5, "Pangong Lake", "2027-07-10T15:00", "2027-07-10T16:30")
        self.assertTrue(permit(p))

    def test_a_night_in_pangong_and_a_paid_nubra_visit_passes(self):
        p = _nights(nubra=False); _visit(p, 3, "Diskit Monastery and Hunder dunes", "2027-07-08T09:00", "2027-07-08T13:00")
        self.assertTrue(permit(p))

    def test_an_unpaid_visit_does_not_pay_the_fee(self):
        p = _nights(pangong=False); _visit(p, 5, "Pangong Lake", "2027-07-10T15:00", "2027-07-10T16:30", paid=False)
        self.assertFalse(permit(p))

    def test_a_paid_visit_elsewhere_does_not_pay_the_fee(self):
        p = _nights(pangong=False); _visit(p, 2, "Leh Palace", "2027-07-07T10:00", "2027-07-07T11:00")
        self.assertFalse(permit(p))

    def test_the_gold_plan_still_passes(self):
        self.assertTrue(TRIP.grade(T, GOLD).to_dict()["solved"])

if __name__ == "__main__":
    unittest.main()
