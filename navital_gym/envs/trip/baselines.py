"""Scripted baselines for env #1. None of them calls a model.
  empty      returns nothing useful (floor)
  shotgun    always claims infeasible and names 3 plausible rules (tests the infeasible-claim guard)
  heuristic  a lazy planner: reads the prompt with regexes, takes the first service of each hop, the cheapest hotel, ignores diet, rest days,
             seats and quotas. About what a careless agent produces.
  oracle     the reference solver (upper bound; sees hidden params, so it is NOT a fair baseline)
"""
import datetime as dt, math, re
from ...core.runner import ScriptedAgent
from . import data as D
from .solver import Solver

def empty(obs, call, task):
    return {"status": "infeasible", "binding": []}

def shotgun(obs, call, task):
    return {"status": "infeasible", "binding": ["R-BUD", "R-SEASON", "R-QUOTA"]}

def oracle(obs, call, task):
    s = Solver(task)
    plan = s.solve()
    if plan:
        return plan
    from .solver import verdict
    v = verdict(task)
    return {"status": "infeasible", "binding": (v["binding_sets"] or [[]])[0]}

CITY_RE = re.compile("|".join(sorted(map(re.escape, D.CITIES), key=len, reverse=True)))

def _parse(prompt):
    cities = []
    for m in CITY_RE.findall(prompt):
        if m not in cities: cities.append(m)
    dates = re.findall(r"20\d\d-\d\d-\d\d", prompt)
    days = re.search(r"(\d+)[- ]day|(\d+) days", prompt)
    adults = re.search(r"(\d+) adults?", prompt)
    n = int(adults.group(1)) if adults else 2
    kids = re.search(r"child(?:ren)?[^\[\d]*[\[\(]?([\d, ]+)", prompt)
    ages = [int(x) for x in re.findall(r"\d+", kids.group(1))] if kids else []
    seniors = re.search(r"(\d+) seniors?", prompt)
    return cities, dates[0] if dates else None, int(next(g for g in days.groups() if g)) if days else 3, n, ages, int(seniors.group(1)) if seniors else 0

def heuristic(obs, call, task):
    cities, start, ndays, adults, ages, seniors = _parse(task.prompt)
    if not start or len(cities) < 1:
        return {"status": "infeasible", "binding": []}
    today = call("calendar_info", {})["today"]
    origin = cities[0]
    stops = cities[1:] or cities[:1]
    seq = [origin] + stops + [origin]
    n_all = adults + seniors + len(ages)
    n5 = adults + seniors + sum(a >= 5 for a in ages)
    n2 = adults + seniors + sum(a >= 2 for a in ages)
    d0 = dt.date.fromisoformat(start)
    legs_by_day = {i: [] for i in range(ndays)}
    day = 0
    nights = max(1, (ndays - 1) // max(1, len(seq) - 1)) if ndays > 1 else 0
    for a, b in zip(seq, seq[1:]):
        date = d0 + dt.timedelta(days=min(day, ndays - 1))
        leg = None
        r = call("search_trains", {"from_city": a, "to_city": b, "date": date.isoformat()}).get("trains", [])
        if r:
            t = r[0]; cls = t["classes"][0]
            leg = {"mode": "rail", "id": t["train_id"], "from": a, "to": b, "dep": t["dep"], "arr": t["arr"], "class": cls, "quota": "GN", "pax": n5, "half": 0}
        else:
            f = call("search_flights", {"from_city": a, "to_city": b, "date": date.isoformat()}).get("flights", [])
            if f:
                leg = {"mode": "air", "id": f[0]["flight_id"], "from": a, "to": b, "dep": f[0]["dep"], "arr": f[0]["arr"], "pax": n2}
            else:
                tr = call("search_transfers", {"from_city": a, "to_city": b, "date": date.isoformat()}).get("transfers", [])
                taxi = next((x for x in tr if x["kind"] == "taxi"), None)
                if taxi:
                    dep = dt.datetime.combine(date, dt.time(8, 0))
                    leg = {"mode": "road", "id": taxi["transfer_id"], "from": a, "to": b, "dep": dep.strftime("%Y-%m-%dT%H:%M"),
                           "arr": (dep + dt.timedelta(minutes=taxi["duration_min"])).strftime("%Y-%m-%dT%H:%M"), "pax": 0, "vehicles": math.ceil(n_all / 4)}
        if leg:
            legs_by_day[min(day, ndays - 1)].append(leg)
        day += nights
    days = []
    for i in range(ndays):
        d = d0 + dt.timedelta(days=i)
        entry = {"date": d.isoformat(), "legs": legs_by_day[i], "activities": []}
        if i < ndays - 1:
            city = stops[min(i // max(1, nights), len(stops) - 1)]
            hs = call("search_hotels", {"city": city, "check_in": d.isoformat(), "nights": 1}).get("hotels", [])
            if hs:
                h = min(hs, key=lambda x: list(x["rate_per_room_night"].values())[0])
                k = math.ceil(n_all / 3)
                entry["stay"] = {"hotel_id": h["hotel_id"], "rooms": [{"guests": n_all // k + (1 if j < n_all % k else 0)} for j in range(k)]}
        days.append(entry)
    return {"status": "plan", "booking_date": today, "days": days}

BASELINES = {n: ScriptedAgent(n, f) for n, f in (("empty", empty), ("shotgun", shotgun), ("heuristic", heuristic), ("oracle", oracle))}
