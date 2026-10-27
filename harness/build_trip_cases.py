"""Builds cases/trip. Plans are HAND-SOLVED by qa from the world's own tools (search_trains / train_availability / attraction_info /
calendar_info), each different from the reference solver's pick, and every violation is a one-edit copy whose failing rule(s) were
predicted by qa BEFORE running the grader. Infeasible claims are reasoned from the stated rules. Nothing here is copied from solver.py.
Findings from this exercise are in harness/README.md (R-ROUTE hidden requirement for rail-booking tasks, fixed upstream in 75e9480)."""
import copy, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import load_tasks
from navital_gym.envs import trip
T = {t.id: t for t in load_tasks(trip.TASKS_PATH)}
def leg(i, f, t, d, a, cls, q, pax, **kw):
    L = {"mode": "rail", "id": i, "from": f, "to": t, "dep": d, "arr": a, "class": cls, "quota": q, "pax": pax, "half": 0}; L.update(kw); return L
def plan(booking, day, legs, acts): return {"status": "plan", "booking_date": booking, "days": [{"date": day, "legs": legs, "activities": acts}]}
L0 = lambda p: p["days"][0]["legs"][0]
A0 = lambda p: p["days"][0]["activities"][0]
H = {}
# ---- IN-TRIP-041: Delhi->Jaipur 2027-01-10, 2 adults, today 2026-11-15 (56 days ahead: General quota 2-60). 16208 dep 05:30 arr 10:49, 2S AVL 10 >= 2.
# R-ROUTE needs a night or a sight in Jaipur (a 1-day trip has no night) -> City Palace (open 09:30-17:00, 120 min) 12:00-14:00.
H["IN-TRIP-041"] = (plan("2026-11-15", "2027-01-10", [leg("16208", "Delhi", "Jaipur", "2027-01-10T05:30", "2027-01-10T10:49", "2S", "GN", 2)],
                         [{"id": "City Palace", "start": "2027-01-10T12:00", "end": "2027-01-10T14:00"}]), [
  ("booking_date_not_today", ["R-QUOTA"], lambda p: p.update(booking_date="2026-11-16")),
  ("one_ticket_for_two", ["R-OCC"], lambda p: L0(p).update(pax=1)),
  ("departure_not_a_real_service", ["R-CONN"], lambda p: L0(p).update(dep="2027-01-10T06:30")),
  ("sight_after_closing", ["R-OPEN"], lambda p: A0(p).update(start="2027-01-10T16:00", end="2027-01-10T18:00")),
  ("sight_shorter_than_visit_length", ["R-OPEN"], lambda p: A0(p).update(end="2027-01-10T13:00")),
  ("tatkal_56_days_early", ["R-QUOTA"], lambda p: L0(p).update(quota="TQ", book_at="10:00"))])
# ---- IN-TRIP-043: Mumbai->Pune 2026-12-04, 3 adults, today 2026-12-03: General is closed (<2 days) -> Tatkal the day before; CC is AC -> opens 10:00.
# 12260 dep 06:15 arr 09:05, CC TQ AVL 5 >= 3. (2S TQ on 12260 is WL 1; 15301 CC TQ is RAC.) Shaniwar Wada (08:00-18:00, 75 min) 10:30-11:45.
H["IN-TRIP-043"] = (plan("2026-12-03", "2026-12-04", [leg("12260", "Mumbai", "Pune", "2026-12-04T06:15", "2026-12-04T09:05", "CC", "TQ", 3, book_at="10:00")],
                         [{"id": "Shaniwar Wada", "start": "2026-12-04T10:30", "end": "2026-12-04T11:45"}]), [
  ("general_quota_one_day_before", ["R-QUOTA"], lambda p: L0(p).update(quota="GN", book_at=None)),
  ("ac_class_with_non_ac_opening_time", ["R-QUOTA"], lambda p: L0(p).update(book_at="11:00")),
  ("waitlisted_2s", ["R-AVAIL"], lambda p: L0(p).update({"class": "2S", "book_at": "11:00"})),
  ("booked_two_days_early", ["R-QUOTA"], lambda p: p.update(booking_date="2026-12-02"))])
# ---- IN-TRIP-044: Delhi->Agra 2026-12-05 = today -> Current quota; CC only; train must leave before 12:00.
# 13207 07:45 CC CUR is WL 38; 17946 dep 09:30 arr 12:52 CC CUR AVL 2 >= 2 -> 17946. Saturday: Agra Fort (06:00-18:00, 120 min) 14:00-16:00.
H["IN-TRIP-044"] = (plan("2026-12-05", "2026-12-05", [leg("17946", "Delhi", "Agra", "2026-12-05T09:30", "2026-12-05T12:52", "CC", "CUR", 2)],
                         [{"id": "Agra Fort", "start": "2026-12-05T14:00", "end": "2026-12-05T16:00"}]), [
  ("waitlisted_cc_train", ["R-AVAIL"], lambda p: L0(p).update(id="13207", dep="2026-12-05T07:45", arr="2026-12-05T11:40")),
  ("tatkal_instead_of_current", ["R-QUOTA"], lambda p: L0(p).update(quota="TQ", book_at="10:00")),
  # 17946 2S Current is WL 21 as well, so the class swap breaks the CC-only request AND availability
  ("second_class_where_cc_only", ["R-ROUTE", "R-AVAIL"], lambda p: L0(p).update({"class": "2S"}))])
# ---- IN-TRIP-045: Chennai->Bengaluru 2026-12-14, 6 adults, today 2026-12-10 (4 days ahead, General). 15105 dep 07:45 arr 14:28, CC GN AVL 17 >= 6
# (2S has 1 seat; the overnight 17059 is SL WL / 3A RAC). Lalbagh (06:00-19:00, 90 min) 16:00-17:30.
H["IN-TRIP-045"] = (plan("2026-12-10", "2026-12-14", [leg("15105", "Chennai", "Bengaluru", "2026-12-14T07:45", "2026-12-14T14:28", "CC", "GN", 6)],
                         [{"id": "Lalbagh Garden", "start": "2026-12-14T16:00", "end": "2026-12-14T17:30"}]), [
  ("five_tickets_for_six", ["R-OCC"], lambda p: L0(p).update(pax=5)),
  ("second_class_one_seat_left", ["R-AVAIL"], lambda p: L0(p).update({"class": "2S"})),
  ("booked_on_travel_day", ["R-QUOTA"], lambda p: p.update(booking_date="2026-12-14"))])


# ---- IN-TRIP-005: 3 days Delhi->Agra->Jaipur->Delhi from 2027-01-02, 2 adults, Rs 12,000, trains. Today 2026-11-15 (all General quota, 48-50 days ahead).
# Day 1 Sat: 13207 07:45->11:40 2S AVL 46; night H-AGRA-2 (tier 1, Rs 1285, 1 room x 2); Agra Fort 14:00-16:00 (06:00-18:00, 120 min).
# Day 2 Sun: Taj Mahal 08:00-10:30 (open 06:00-18:30, closed only Fridays, 150 min); 15705 15:40->19:42 2S AVL 26; night H-JAIP-1 (tier 1, Rs 1175).
# Day 3 Mon: Hawa Mahal 10:00-11:00 (09:00-16:30) and City Palace 12:00-14:00 (09:30-17:00); 18348 16:30->21:52 2S AVL 9 back to Delhi.
# Cost by hand: fares 2x(130+150+175)=910; rooms 1285+1175=2460; tickets 2x(650+1100+200+700)=5300; food <= 2 people x 3 days x 300 = 1800 -> about 10,470 <= 12,000.
def d5(): 
    return {"status": "plan", "booking_date": "2026-11-15", "days": [
     {"date": "2027-01-02", "legs": [leg("13207", "Delhi", "Agra", "2027-01-02T07:45", "2027-01-02T11:40", "2S", "GN", 2)], "stay": {"hotel_id": "H-AGRA-2", "rooms": [{"guests": 2}]},
      "activities": [{"id": "Agra Fort", "start": "2027-01-02T14:00", "end": "2027-01-02T16:00"}]},
     {"date": "2027-01-03", "legs": [leg("15705", "Agra", "Jaipur", "2027-01-03T15:40", "2027-01-03T19:42", "2S", "GN", 2)], "stay": {"hotel_id": "H-JAIP-1", "rooms": [{"guests": 2}]},
      "activities": [{"id": "Taj Mahal", "start": "2027-01-03T08:00", "end": "2027-01-03T10:30"}]},
     {"date": "2027-01-04", "legs": [leg("18348", "Jaipur", "Delhi", "2027-01-04T16:30", "2027-01-04T21:52", "2S", "GN", 2)],
      "activities": [{"id": "Hawa Mahal", "start": "2027-01-04T10:00", "end": "2027-01-04T11:00"}, {"id": "City Palace", "start": "2027-01-04T12:00", "end": "2027-01-04T14:00"}]}]}
Dy = lambda p, i: p["days"][i]
def _wl(p):   # RAC train on day 2 (17721 CC, RAC 17): drop the day's sight so nothing else clashes with the 06:15 departure
    Dy(p, 1)["legs"][0].update(id="17721", dep="2027-01-03T06:15", arr="2027-01-03T10:11", **{"class": "CC"}); Dy(p, 1)["activities"] = []
H["IN-TRIP-005"] = (d5(), [
  ("two_tier3_hotels_blow_the_budget", ["R-BUD"], lambda p: (Dy(p, 0)["stay"].update(hotel_id="H-AGRA-6"), Dy(p, 1)["stay"].update(hotel_id="H-JAIP-6"))),
  ("sight_before_opening", ["R-OPEN"], lambda p: Dy(p, 2)["activities"][0].update(start="2027-01-04T08:00", end="2027-01-04T09:00")),
  ("taj_before_it_opens", ["R-OPEN"], lambda p: Dy(p, 1)["activities"][0].update(start="2027-01-03T05:00", end="2027-01-03T07:30")),
  ("one_guest_in_the_room", ["R-OCC"], lambda p: Dy(p, 0)["stay"].update(rooms=[{"guests": 1}])),
  ("no_night_in_agra", ["R-CONN"], lambda p: Dy(p, 0).pop("stay")),
  ("rac_train_not_confirmed", ["R-AVAIL"], _wl),
  # the last listed day then carries a night's stay and the trip ends in Jaipur, so connection and date rules both break
  ("trip_ends_a_day_early", ["R-DATE", "R-CONN"], lambda p: p["days"].pop()),
  ("never_leaves_agra_so_no_jaipur", ["R-CONN", "R-ROUTE"], lambda p: (Dy(p, 1).pop("stay"), Dy(p, 1).pop("legs")))])

# ---- infeasible by reasoning from the rules (binding chosen BEFORE looking at the task's stored binding; asserted equal below)
INF = {
 # 2027-01-20 is 66 days after 2026-11-15; General opens 60 days ahead, Tatkal only the day before, Current only that day -> cannot book today
 "IN-TRIP-042": ["R-QUOTA"],
 # Friday 2026-12-11 and the Taj Mahal is closed on Fridays (attraction_info closed ['Fri']); the task wants to see it that day
 "IN-TRIP-049": ["R-OPEN"],
 # Rs 2,000 for 3 days, 2 adults: the cheapest train fare plus hotel nights already exceed it
 "IN-TRIP-051": ["R-BUD"],
 # Rs 7,000 for 4 days, 4 adults in Kerala: far below the cheapest transport plus 3 nights
 "IN-TRIP-053": ["R-BUD"]}
FEAS = "IN-TRIP-041"
cases_written = 0
RAIL_ONLY = ("IN-TRIP-041", "IN-TRIP-043", "IN-TRIP-044", "IN-TRIP-045")   # one-day "book this train" tasks
for tid, (hand, viols) in H.items():
    cases = [{"name": "hand_solved", "kind": "solved", "submission": hand, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["days", "booking_date"]}}]
    if tid in RAIL_ONLY:
        # Since backend 75e9480 arriving in the trip's end city counts as visiting it: the bare ticket is a valid answer (before, it failed R-ROUTE)
        bare = copy.deepcopy(hand); bare["days"][0].pop("activities")
        cases.append({"name": "ticket_only_is_valid_now", "kind": "variant", "submission": bare, "expect": {"solved": True, "min_score": 1.0}})
    for name, fails, f in viols:
        p = copy.deepcopy(hand); f(p)
        cases.append({"name": name, "kind": "violation", "submission": p, "expect": {"solved": False, "max_score": 0.99, "fails": fails, "passes_all_but": fails}})
    cases.append({"name": "claims_infeasible_on_a_feasible_task", "kind": "violation", "submission": {"status": "infeasible", "binding": ["R-QUOTA"]}, "expect": {"solved": False, "max_score": 0.0}})
    json.dump({"env": "trip", "task_id": tid, "task": T[tid].to_dict(), "cases": cases}, open(f"cases/trip/{tid}.json", "w"), indent=1, ensure_ascii=False); cases_written += 1
for tid, binding in INF.items():
    t = T[tid]
    assert not t.expected_feasible and set(binding) <= set(t.binding), f"{tid}: my reasoned binding {binding} vs stored {t.binding}"
    other = next(r for r in ("R-AVAIL", "R-OCC", "R-DATE") if r not in binding)
    cases = [{"name": "hand_infeasible_claim", "kind": "solved", "submission": {"status": "infeasible", "binding": binding}, "expect": {"solved": True, "min_score": 1.0}},
             {"name": "wrong_rule_named", "kind": "violation", "submission": {"status": "infeasible", "binding": [other]}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "padded_with_an_unrelated_rule", "kind": "violation", "submission": {"status": "infeasible", "binding": binding + [other]}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "empty_binding", "kind": "violation", "submission": {"status": "infeasible", "binding": []}, "expect": {"solved": False, "max_score": 0.0, "fails": ["R-INFEASIBLE"]}},
             {"name": "a_plan_for_an_infeasible_task", "kind": "violation", "submission": copy.deepcopy(H[FEAS][0]), "expect": {"solved": False, "max_score": 0.0}}]
    json.dump({"env": "trip", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(f"cases/trip/{tid}.json", "w"), indent=1, ensure_ascii=False); cases_written += 1
print("wrote", cases_written, "case files")
