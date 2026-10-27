"""cases/trip_easy: 5 feasible plans HAND-SOLVED by qa from the world tools (search_trains, train_availability, calendar_info, attraction_info, search_hotels) and 3 infeasible
claims reasoned from the rules, for backend's trip easy split. Each violation is a one-edit copy whose failing rule(s) were predicted before running.
NAVITAL_GYM_ROOT=<checkout> python3 build_trip_easy_cases.py"""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from navital_gym.envs import trip
T = {t.id: t for t in trip.load_env(splits=("easy",)).tasks.values()}
def leg(i, f, t, d, a, cls, q, pax, **kw):
    L = {"mode": "rail", "id": i, "from": f, "to": t, "dep": d, "arr": a, "class": cls, "quota": q, "pax": pax, "half": 0}; L.update(kw); return L
L0 = lambda p: p["days"][0]["legs"][0]
H = {}
# E01: Delhi->Agra 2026-12-02, 2 adults, today 2026-11-15 (17 days ahead: General quota). 13207 07:45->11:40: CC/2S General AVL 30/38 (17946 CC is RAC, 2S has 1 seat).
H["IN-TRIP-E01"] = ({"status": "plan", "booking_date": "2026-11-15", "days": [{"date": "2026-12-02", "legs": [leg("13207", "Delhi", "Agra", "2026-12-02T07:45", "2026-12-02T11:40", "2S", "GN", 2)]}]}, [
  ("booking_date_not_today", ["R-QUOTA"], lambda p: p.update(booking_date="2026-11-16")),
  ("one_ticket_for_two", ["R-OCC"], lambda p: L0(p).update(pax=1)),
  ("rac_train_17946_cc", ["R-AVAIL"], lambda p: L0(p).update(id="17946", dep="2026-12-02T09:30", arr="2026-12-02T12:52", **{"class": "CC"}))])
# E03: Mumbai->Pune 2026-12-01, 3 adults. 12260 CC is waitlisted (WL19); 14895 dep 16:30 arr 19:14, 2S General AVL 18 >= 3.
H["IN-TRIP-E03"] = ({"status": "plan", "booking_date": "2026-11-15", "days": [{"date": "2026-12-01", "legs": [leg("14895", "Mumbai", "Pune", "2026-12-01T16:30", "2026-12-01T19:14", "2S", "GN", 3)]}]}, [
  ("two_tickets_for_three", ["R-OCC"], lambda p: L0(p).update(pax=2)),
  ("waitlisted_cc_12260", ["R-AVAIL"], lambda p: L0(p).update(id="12260", dep="2026-12-01T06:15", arr="2026-12-01T09:05", **{"class": "CC"})),
  ("tatkal_three_weeks_early", ["R-QUOTA"], lambda p: L0(p).update(quota="TQ", book_at="11:00"))])
# E04: Chennai->Bengaluru 2026-12-03, 2 adults. 15105 CC is WL4 and 19718 CC is RAC7: take 15105 2S General AVL 39 (07:45->14:28).
H["IN-TRIP-E04"] = ({"status": "plan", "booking_date": "2026-11-15", "days": [{"date": "2026-12-03", "legs": [leg("15105", "Chennai", "Bengaluru", "2026-12-03T07:45", "2026-12-03T14:28", "2S", "GN", 2)]}]}, [
  ("waitlisted_cc", ["R-AVAIL"], lambda p: L0(p).update({"class": "CC"})),
  ("departure_not_a_real_service", ["R-CONN"], lambda p: L0(p).update(dep="2026-12-03T08:45"))])
# E09: one-day Delhi->Agra on Saturday 2026-12-05, 2 adults, Taj Mahal, Rs 9,000. Out 17946 09:30->12:52 (2S General AVL 47; 13207 is RAC/WL). Taj open 06:00-18:30 (closed only Fridays), 150 min.
# Back by rail would need a 60-min buffer after the visit: arrival 12:52 + 30 min to reach the Taj = 13:22, visit ends 15:52, and the only evening train leaves 16:30: too tight.
# So the way back is the Agra->Delhi taxi (245 min, departure at my choice, 30-min buffer): visit 13:25-15:55, taxi 16:30->20:35. (My first plan used the 16:30 train and failed R-CONN: found by running it.)
# Cost by hand: fares 2x130=260, taxi about 3,600, Taj 2x1,100=2,200, food well under the remaining 9,000.
def e09(): return {"status": "plan", "booking_date": "2026-11-15", "days": [{"date": "2026-12-05", "legs": [
    leg("17946", "Delhi", "Agra", "2026-12-05T09:30", "2026-12-05T12:52", "2S", "GN", 2),
    {"mode": "road", "id": "TX-AGRA-DELH", "from": "Agra", "to": "Delhi", "dep": "2026-12-05T16:30", "arr": "2026-12-05T20:35", "pax": 2, "vehicles": 1}],
    "activities": [{"id": "Taj Mahal", "start": "2026-12-05T13:25", "end": "2026-12-05T15:55"}]}]}
H["IN-TRIP-E09"] = (e09(), [
  ("taj_before_it_opens_and_before_arriving", ["R-OPEN", "R-CONN"], lambda p: p["days"][0]["activities"][0].update(start="2026-12-05T04:00", end="2026-12-05T06:30")),
  ("no_taj_visit", ["R-ROUTE"], lambda p: p["days"][0].pop("activities")),
  ("one_ticket_on_the_train", ["R-OCC"], lambda p: p["days"][0]["legs"][0].update(pax=1)),
  ("visit_too_close_to_the_taxi", ["R-CONN"], lambda p: p["days"][0]["activities"][0].update(start="2026-12-05T14:00", end="2026-12-05T16:30"))])
# E13: 2 days in Jaipur from Delhi, 2026-12-14 (Mon), 2 adults, Rs 14,000. Out 16208 05:30->10:49 (2S AVL 34), night H-JAIP-1 (tier 1, Rs 1,105), back 13404 on 12-15 09:30->14:28 (2S AVL 27).
# Cost by hand: fares 2x(175+175)=700, room 1,105, food <= 2 people x 2 days x 300 = 1,200: about 3,000.
def e13(): return {"status": "plan", "booking_date": "2026-11-15", "days": [
    {"date": "2026-12-14", "legs": [leg("16208", "Delhi", "Jaipur", "2026-12-14T05:30", "2026-12-14T10:49", "2S", "GN", 2)], "stay": {"hotel_id": "H-JAIP-1", "rooms": [{"guests": 2}]}},
    {"date": "2026-12-15", "legs": [leg("13404", "Jaipur", "Delhi", "2026-12-15T09:30", "2026-12-15T14:28", "2S", "GN", 2)]}]}
H["IN-TRIP-E13"] = (e13(), [
  ("one_guest_in_the_room", ["R-OCC"], lambda p: p["days"][0]["stay"].update(rooms=[{"guests": 1}])),
  ("no_night_in_jaipur_so_never_seen", ["R-CONN", "R-ROUTE"], lambda p: p["days"][0].pop("stay")),
  ("unknown_hotel_id_fails_the_format_gate", ["R-FMT"], lambda p: p["days"][0]["stay"].update(hotel_id="H-NOWHERE-1"))])
INF = {"IN-TRIP-E07": ["R-QUOTA"],   # 2027-01-25 is 71 days after 2026-11-15; General opens 60 days ahead, Tatkal the day before: it cannot be booked today
       "IN-TRIP-E12": ["R-OPEN"],    # 2026-12-11 is a Friday and the Taj Mahal is closed on Fridays
       "IN-TRIP-E18": ["R-BUD"]}     # Rs 1,500 for 2 adults for 2 days: round-trip fares (700), a room (1,105 or more) and food already exceed it
n = 0
for tid, (hand, viols) in H.items():
    cases = [{"name": "hand_solved", "kind": "solved", "submission": hand, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["days", "booking_date"]}}]
    for name, fails, f in viols:
        p = copy.deepcopy(hand); f(p)
        cases.append({"name": name, "kind": "violation", "submission": p, "expect": {"solved": False, "max_score": 0.99, "fails": fails, "passes_all_but": fails}})
    cases.append({"name": "claims_infeasible_on_a_feasible_task", "kind": "violation", "submission": {"status": "infeasible", "binding": ["R-QUOTA"]}, "expect": {"solved": False, "max_score": 0.0}})
    json.dump({"env": "trip_easy", "task_id": tid, "task": T[tid].to_dict(), "cases": cases}, open(os.path.join(HERE, "cases", "trip_easy", f"{tid}.json"), "w"), indent=1, ensure_ascii=False); n += 1
for tid, binding in INF.items():
    t = T[tid]; assert not t.expected_feasible and set(binding) <= set(t.binding), f"{tid}: my reasoned binding {binding} vs stored {t.binding}"
    other = next(r for r in ("R-AVAIL", "R-OCC", "R-DATE") if r not in binding)
    cases = [{"name": "hand_infeasible_claim", "kind": "solved", "submission": {"status": "infeasible", "binding": binding}, "expect": {"solved": True, "min_score": 1.0}},
             {"name": "wrong_rule_named", "kind": "violation", "submission": {"status": "infeasible", "binding": [other]}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "padded_with_an_unrelated_rule", "kind": "violation", "submission": {"status": "infeasible", "binding": binding + [other]}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "empty_binding", "kind": "violation", "submission": {"status": "infeasible", "binding": []}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "a_plan_for_an_infeasible_task", "kind": "violation", "submission": copy.deepcopy(H["IN-TRIP-E01"][0]), "expect": {"solved": False, "max_score": 0.0}}]
    json.dump({"env": "trip_easy", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(os.path.join(HERE, "cases", "trip_easy", f"{tid}.json"), "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
