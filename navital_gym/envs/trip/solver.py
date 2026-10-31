"""Reference solver for env #1: an ORACLE, not a baseline. It searches a structured plan space (stop order x nights per stop x one service per
hop x cheapest compatible hotel x earliest activity slot) and checks every candidate with the real grader, so a plan it returns is feasible by
construction. Infeasibility is established by exhaustive search of that space; the binding rules are found by relaxation: a rule is binding when
dropping only that rule (not a 'demand' rule such as R-ROUTE) makes a plan appear. It is used to confirm every task's expected_feasible and
binding flags, and as the env's upper-bound agent. Limitation (said in the README): 'infeasible' means no plan in this space, which is the
space of sensible plans (single hotel per night, one leg per hop, direct links only)."""
from __future__ import annotations
import datetime as dt, itertools, math
from dataclasses import replace
from ...core.grader import Ctx
from . import data as D
from .world import TripWorld, FOOD_PER_DAY, BERTH_CLASSES, AC_CLASSES, BUFFER_MIN, iso
from . import rules as R

TAXI_DEPS = [h * 60 + 30 for h in range(5, 21)]      # a taxi may leave at any time; the solver tries every hour at :30
TAXI_NIGHT = [1290, 1350]
MAX_LEAVES = 400_000

def _dtm(d, minute):
    return dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=minute)

class Solver:
    def __init__(self, task, active=None, seed=0, node_limit=MAX_LEAVES):
        self.task = task
        self.w = TripWorld(task, seed)
        self.active = set(active if active is not None else task.rules)
        self.tv = R.travelers(task)
        self.p = task.params
        self.start = dt.date.fromisoformat(self.p["start"])
        self.D = int(self.p["days"])
        self.last = self.start + dt.timedelta(days=self.D - 1)
        self.horizon = self.last if "R-DATE" in self.active else self.last + dt.timedelta(days=4)   # R-DATE relaxed: the trip may run long
        self.origin, self.end = self.p["origin"], self.p.get("end") or self.p["origin"]
        self.leaves = 0
        self.node_limit = node_limit
        self.rules = {k: v for k, v in R.RULES.items() if k in self.active}
        self.gtask = replace(task, rules=tuple(self.active), expected_feasible=True)   # grade candidates as if feasible: the solver is deciding that
        self.grader = R.make_grader()
        self._opt_cache = {}

    def on(self, r):
        return r in self.active

    # --------------------------------------------------------------------- required activities
    def required(self):
        req = []
        if not self.on("R-ROUTE"):
            return req
        for n in self.p.get("must_visit", []):
            req.append({"name": n, "day": None})
        for dv in self.p.get("day_visit", []):
            req.append({"name": dv["name"], "day": dv["day"], "slot": dv.get("slot")})
        return req

    def precheck(self):
        """Quick necessary conditions on required sights (open weekday/season on some usable date; altitude pacing). False = no plan exists."""
        for rq in self.required():
            ok = False
            for i in range(self.D):
                if rq["day"] and i + 1 != rq["day"]:
                    continue
                d = self.start + dt.timedelta(days=i)
                att = D.ATTRACTIONS[rq["name"]]
                if self.on("R-OPEN") and D.WEEKDAYS[d.weekday()] in att["closed"]:
                    continue
                if self.on("R-SEASON") and att["season"] and not D.in_window(d, att["season"]):
                    continue
                if self.on("R-ALT") and D.CITIES[att["city"]][1] > 3500 and i + 1 < 3:
                    continue
                ok = True
            if not ok:
                return False
        return True

    # --------------------------------------------------------------------- options for one hop
    def hop_options(self, a, b, date):
        key = (a, b, date)
        if key in self._opt_cache:
            return self._opt_cache[key]
        w, tv, out = self.w, self.tv, []
        edge = w.edges.get((a, b))
        if edge is None:
            self._opt_cache[key] = []
            return []
        modes = set(edge[1])
        pol = self.p.get("mode_policy") == "rail_only" and self.on("R-ROUTE") and "rail" in modes
        forced = {mu["mode"] for mu in self.p.get("must_use", []) if (mu["from"], mu["to"]) == (a, b)} if self.on("R-ROUTE") else set()
        if forced:
            modes &= forced
        if pol:
            modes = {"rail"}
        half = tv["k5_11"]
        if "rail" in modes:
            gap = (date - w.today).days
            quotas = [q for q, ok in (("GN", 1 <= gap <= 60), ("TQ", gap == 1), ("CUR", gap == 0)) if ok]
            if not self.on("R-QUOTA") and "GN" not in quotas:
                quotas = ["GN"] + quotas           # relaxed: as if the advance (general) window were open; Tatkal/Current only when truly open
            for t in w.trains_between(a, b, date):
                if self.on("R-ROUTE") and self.p.get("rail_dep_before"):
                    h, m = (int(x) for x in self.p["rail_dep_before"].split(":"))
                    if t["dep_min"] >= h * 60 + m:
                        continue
                best = None
                for cls in t["classes"]:
                    if self.on("R-ROUTE") and self.p.get("classes_only") and cls not in self.p["classes_only"]:
                        continue
                    for q in quotas:
                        window = R._quota_open(w, w.today, {"dep": _dtm(date, 0), "quota": q})[0]
                        if not window and self.on("R-QUOTA"):
                            continue
                        st, n = w.avail(t["id"], date, cls, q, ignore_window=not window)
                        pax = tv["n5"] - half
                        if self.on("R-AVAIL") and (st != "AVL" or n < pax):
                            continue
                        if self.on("R-ACC") and tv["seniors"] and cls in BERTH_CLASSES:
                            if st != "AVL" or (w.lower_berths(t["id"], date, cls, q, n) or 0) < tv["seniors"]:
                                continue
                        leg = {"mode": "rail", "id": t["id"], "from": a, "to": b, "dep": iso(date, t["dep_min"]), "arr": iso(date, t["dep_min"] + t["dur_min"]),
                               "class": cls, "quota": q, "pax": pax, "half": half}
                        if q == "TQ":
                            leg["book_at"] = "10:00" if cls in AC_CLASSES else "11:00"; leg["traveller_otp"] = True
                        c = R.leg_cost(w, self._plain(leg))
                        if best is None or c < best[0]:
                            best = (c, leg)
                if best:
                    out.append((best[0], best[1]))
        if "air" in modes:
            for f in w.flights(a, b, date):
                leg = {"mode": "air", "id": f["id"], "from": a, "to": b, "dep": iso(date, f["dep_min"]), "arr": iso(date, f["dep_min"] + f["dur_min"]), "pax": tv["n2"]}
                out.append((f["price_pp"] * tv["n2"], leg))
        if "road" in modes and (w.road_open(a, b, date) or not self.on("R-SEASON")):
            for t in w.transfers(a, b, date):
                if t["kind"] == "taxi":
                    for m in TAXI_DEPS + (TAXI_NIGHT if not self.on("R-NIGHT") else []):
                        leg = {"mode": "road", "id": t["id"], "from": a, "to": b, "dep": iso(date, m), "arr": iso(date, m + t["dur_min"]), "pax": 0, "vehicles": math.ceil(tv["n"] / 4)}
                        out.append((t["price_vehicle"] * leg["vehicles"], leg))
                else:
                    for m in t["departures"]:
                        leg = {"mode": "road", "id": t["id"], "from": a, "to": b, "dep": iso(date, m), "arr": iso(date, m + t["dur_min"]), "pax": tv["n5"]}
                        out.append((t["price_pp"] * tv["n5"], leg))
        res = []
        for c, leg in sorted(out, key=lambda x: (x[0], x[1]["dep"])):
            if leg["mode"] == "road" and self.on("R-NIGHT") and self._night_blocked(leg):
                continue
            res.append((c, leg))
        self._opt_cache[key] = res
        return res

    def _plain(self, leg):
        return {"mode": leg["mode"], "id": leg["id"], "frm": leg["from"], "to": leg["to"], "dep": dt.datetime.strptime(leg["dep"], R.DT_FMT),
                "arr": dt.datetime.strptime(leg["arr"], R.DT_FMT), "pax": leg["pax"], "half": leg.get("half", 0), "vehicles": leg.get("vehicles", 0),
                "cls": leg.get("class"), "quota": leg.get("quota")}

    def _night_blocked(self, leg):
        L = self._plain(leg)
        if not self.w.road_open(L["frm"], L["to"], L["dep"].date()):
            return False                    # mirrors R-NIGHT: a closed seasonal road is R-SEASON's violation, not R-NIGHT's
        h, m = 99, 0
        if self.p.get("no_night_road"): h, m = 22, 0
        if self.p.get("no_road_after"): h, m = (int(x) for x in self.p["no_road_after"].split(":"))
        if self.w.is_hill(L["frm"], L["to"]) and D.is_winter(L["dep"].date()) and (h, m) > (20, 0):
            h, m = 20, 0
        return h < 99 and R._road_overlap(L, h, m)

    # --------------------------------------------------------------------- stop sequences
    def _path(self, x, y):
        """Shortest link path x -> y (fewest hops, then fewest km); used to connect stops that have no direct link, e.g. Pangong back to Delhi via Leh."""
        if self.w.edges.get((x, y)):
            return [x, y]
        best = None
        frontier = [(0, 0, [x])]
        seen = {}
        import heapq
        heapq.heapify(frontier)
        while frontier:
            hops, km, path = heapq.heappop(frontier)
            c = path[-1]
            if c == y:
                return path
            if seen.get(c, (99, 1e9)) <= (hops, km):
                continue
            seen[c] = (hops, km)
            if hops >= 3:
                continue
            for (a, b), (k, _) in self.w.edges.items():
                if a == c and b not in path:
                    heapq.heappush(frontier, (hops + 1, km + k, path + [b]))
        return None

    def sequences(self):
        dest = [c for c in self.p["route"] if c != self.origin]
        extras = [c for c in self.p.get("extra_cities", []) if c not in dest and c != self.origin]
        raw = set()
        for k in range(len(extras) + 1):
            for sub in itertools.combinations(extras, k):
                for perm in itertools.permutations(dest + list(sub)):
                    if self.end != self.origin:
                        if not perm or perm[-1] != self.end:
                            continue
                        raw.add((self.origin,) + perm)
                    else:
                        raw.add((self.origin,) + perm + (self.origin,))
        if not dest:
            raw.add((self.origin, self.end))
        seqs = set()
        for seq in raw:
            full = [seq[0]]
            ok = True
            for x, y in zip(seq, seq[1:]):
                path = self._path(x, y)
                if path is None:
                    ok = False; break
                full += path[1:]
            if ok:
                seqs.add(tuple(full))
        out = []
        for seq in sorted(seqs, key=lambda q: (len(q), q)):
            if self.on("R-ROUTE"):
                if not all(any((x, y) == (mu["from"], mu["to"]) for x, y in zip(seq, seq[1:])) for mu in self.p.get("must_use", [])):
                    continue
            out.append(seq)
        return out

    # --------------------------------------------------------------------- search
    def solve(self):
        if not self.precheck():
            return None
        for seq in self.sequences():
            plan = self._dfs_seq(seq)
            if plan:
                return plan
            if self.leaves > self.node_limit:
                break
        return None

    def _hop_lb(self, seq):
        """Cheapest possible cost of each hop over all trip dates (no timing), for the budget bound."""
        out = []
        for a, b in zip(seq, seq[1:]):
            best = None
            for i in range(self.D):
                for c, _ in self.hop_options(a, b, self.start + dt.timedelta(days=i))[:1]:
                    best = c if best is None else min(best, c)
            out.append(best)
        return out

    def _dfs_seq(self, seq):
        hops = list(zip(seq, seq[1:]))
        if not hops:
            return None
        lb_hops = self._hop_lb(seq)
        if any(x is None for x in lb_hops):
            return None
        budget = self.p.get("budget_inr") if self.on("R-BUD") else None
        weights = self.tv["full"] + 0.5 * self.tv["half"]
        cheapest_night = self._cheapest_night(seq)
        cap = float(self.p.get("max_travel_hours_per_day", 99)) * 60 if self.on("R-HRS") else None
        rooms = math.ceil(self.tv["n"] / 3)

        def rec(i, prev_arr, legs, spent, daymins):
            if self.leaves > self.node_limit:
                return None
            a, b = hops[i]
            base = prev_arr.date() if prev_arr else self.start
            for n in range(0, self.D):
                dep_date = base + dt.timedelta(days=n)
                if i == 0 and n > 0:
                    break
                if dep_date > self.horizon:
                    break
                for cost, leg in self.hop_options(a, b, dep_date):
                    L = self._plain(leg)
                    if prev_arr is not None and L["dep"] < prev_arr + dt.timedelta(minutes=BUFFER_MIN[leg["mode"]]):
                        continue
                    if L["arr"].date() > self.horizon:
                        continue
                    last_hop = i == len(hops) - 1
                    if last_hop and self.on("R-DATE") and L["arr"].date() != self.last and self.D > 1:
                        continue
                    dm = dict(daymins)
                    if cap is not None:
                        ok = True
                        d0 = L["dep"].date()
                        while d0 <= L["arr"].date():
                            lo = dt.datetime.combine(d0, dt.time()); hi = lo + dt.timedelta(days=1)
                            m = max(0, (min(L["arr"], hi) - max(L["dep"], lo)).total_seconds() / 60)
                            dm[d0] = dm.get(d0, 0) + m
                            if dm[d0] > cap: ok = False
                            d0 += dt.timedelta(days=1)
                        if not ok:
                            continue
                    sp = spent + cost
                    if budget is not None:
                        rem_hops = sum(lb_hops[i + 1:])
                        nights_left = max(0, self.D - 1 - len(hops))
                        if sp + rem_hops + weights * FOOD_PER_DAY[1] * self.D + nights_left * cheapest_night > budget:
                            continue
                    if last_hop:
                        self.leaves += 1
                        plan = self._finish(seq, legs + [leg])
                        if plan:
                            return plan
                    else:
                        r = rec(i + 1, L["arr"], legs + [leg], sp, dm)
                        if r:
                            return r
            return None
        return rec(0, None, [], 0.0, {})

    def _cheapest_night(self, seq):
        best = None
        for c in set(seq):
            for h in self.w.hotels[c]:
                if self._hotel_ok(h):
                    r = min(self.w.hotel_rate(h["id"], self.start + dt.timedelta(days=j)) for j in range(self.D)) * math.ceil(self.tv["n"] / 3)
                    best = r if best is None else min(best, r)
        return best or 0

    def _hotel_ok(self, h):
        diet = self.p.get("diet", "any")
        if self.on("R-DIET") and diet in ("veg", "jain", "satvik") and not h[diet]:
            return False
        if self.on("R-ACC") and self.p.get("no_stairs") and not (h["lift"] or h["ground_floor"]):
            return False
        return True

    # --------------------------------------------------------------------- build + verify a candidate
    def _rooms(self):
        n, k = self.tv["n"], math.ceil(self.tv["n"] / 3)
        base, extra = divmod(n, k)
        return [{"guests": base + (1 if j < extra else 0)} for j in range(k)]

    def _finish(self, seq, legs):
        plan = {"status": "plan", "booking_date": self.w.today.isoformat(), "days": [], "binding": []}
        plain = [self._plain(l) for l in legs]
        for i in range(self.D):
            d = self.start + dt.timedelta(days=i)
            plan["days"].append({"date": d.isoformat(), "legs": [l for l in legs if l["dep"][:10] == d.isoformat()], "activities": []})
        # nights: location at each midnight
        night_city = []
        for i in range(self.D - 1):
            mid = dt.datetime.combine(self.start + dt.timedelta(days=i + 1), dt.time())
            loc, where = self.origin, None
            cur_loc = self.origin
            transit = False
            for L in sorted(plain, key=lambda x: x["dep"]):
                if L["dep"] < mid <= L["arr"]:
                    transit = True; break
                if L["arr"] <= mid:
                    cur_loc = L["to"]
            night_city.append(None if transit else cur_loc)
        want_boat = {x["city"] for x in self.p.get("stay_kind", [])} if self.on("R-ROUTE") else set()
        boat_done = set()
        for i, city in enumerate(night_city):
            if city is None:
                continue
            d = self.start + dt.timedelta(days=i)
            cands = [h for h in self.w.hotels[city] if self._hotel_ok(h)]
            if not cands:
                return None
            def night_cost(h):
                return self.w.hotel_rate(h["id"], d) * len(self._rooms()) + FOOD_PER_DAY[h["tier"]] * (self.tv["full"] + 0.5 * self.tv["half"])
            pick = min(cands, key=night_cost)
            if city in want_boat and city not in boat_done:
                boats = [h for h in cands if h["kind"] == "houseboat"]
                if boats:
                    pick = min(boats, key=night_cost); boat_done.add(city)
            plan["days"][i]["stay"] = {"hotel_id": pick["id"], "rooms": self._rooms()}
        acts = self._place(plan)
        if acts is None:
            return None
        for i, lst in acts.items():
            plan["days"][i]["activities"] = lst
        sc = self.grader.grade(self.gtask, plan) if self.rules else None
        return plan if sc is not None and sc.solved else None

    def _place(self, plan):
        """Earliest feasible slot for every required activity (must_visit, day_visit, daily_in_city)."""
        req = list(self.required())
        if self.on("R-ROUTE") and self.p.get("daily_in_city"):
            # v1.1: the daily activity on every evening it can be attended in the city (same test as the rule), the day of departure included
            ctx0 = Ctx(task=self.gtask, world=self.w, sub=plan)
            np0, _ = R.normalize(ctx0)
            if np0 is None:
                return None
            ivs0 = R.timeline(ctx0)[0]
            for dc in self.p["daily_in_city"]:
                att0 = D.ATTRACTIONS[dc["name"]]
                for i in range(len(plan["days"])):
                    if R.evening_possible(ivs0, dc["city"], att0, self.start + dt.timedelta(days=i)):
                        req.append({"name": dc["name"], "day": i + 1})
        if self.on("R-ROUTE"):      # every named city needs a night or a sight: add the first workable sight for cities that have neither
            have = {self.w.hotel_by_id[d["stay"]["hotel_id"]]["city"] for d in plan["days"] if d.get("stay")} | {D.ATTRACTIONS[r["name"]]["city"] for r in req}
            for c in self.p["route"]:
                if c != self.origin and c != self.end and c not in have:
                    req.append({"name": None, "day": None, "any_of": sorted([n for n, a in D.ATTRACTIONS.items() if a["city"] == c], key=lambda n: D.ATTRACTIONS[n]["adult_inr"])})
        if not req:
            return {}
        ctx = Ctx(task=self.gtask, world=self.w, sub=plan)
        np, problems = R.normalize(ctx)
        if np is None:
            return None
        ivs, mids, final, probs = R.timeline(ctx)
        placed, out = [], {}
        first_leh = next((l for l in R._legs_sorted(np) if l["to"] == "Leh"), None)
        for rq in sorted(req, key=lambda r: (r["day"] is None, r["day"] or 0)):
            choices = rq.get("any_of") or [rq["name"]]
            res = None
            for nm in choices:
                res = self._place_one(dict(rq, name=nm), ivs, placed, first_leh)
                if res is not None:
                    break
            if res is None:
                return None
            i, s, e, a = res
            placed.append((s, e))
            out.setdefault(i, []).append(a)
        return out

    def _place_one(self, rq, ivs, placed, first_leh):
        if True:
            att = D.ATTRACTIONS[rq["name"]]
            hit = None
            for city, t_in, t_out, arrived, nxt in ivs:
                if city != att["city"]:
                    continue
                lo = t_in + (dt.timedelta(minutes=30) if arrived else dt.timedelta())
                hi = t_out - (dt.timedelta(minutes=BUFFER_MIN[nxt["mode"]]) if nxt else dt.timedelta())
                day = lo.date()
                while day <= hi.date() and day <= self.last:
                    i = (day - self.start).days
                    if i >= 0 and (not rq["day"] or rq["day"] == i + 1):
                        if self._open_ok(att, day, i, first_leh):
                            o = _dtm(day, int(att["open"][:2]) * 60 + int(att["open"][3:]))
                            c = _dtm(day, int(att["close"][:2]) * 60 + int(att["close"][3:]))
                            s = max(lo, o)
                            for p0, p1 in sorted(placed):
                                if s < p1 and s + dt.timedelta(minutes=att["minutes"]) > p0:
                                    s = max(s, p1)
                            e = s + dt.timedelta(minutes=att["minutes"])
                            slot_ok = not (rq.get("slot") == "sunrise" and s.hour * 60 + s.minute > 420)
                            if e <= min(hi, c) and slot_ok and s.date() == day:
                                hit = (i, s, e); break
                    day += dt.timedelta(days=1)
                if hit:
                    break
            if not hit:
                return None
            i, s, e = hit
            a = {"id": rq["name"], "start": s.strftime(R.DT_FMT), "end": e.strftime(R.DT_FMT)}
            if att["permit"]:
                a["fee_paid"] = True
            return i, s, e, a

    def _open_ok(self, att, day, i, first_leh):
        if self.on("R-OPEN") and D.WEEKDAYS[day.weekday()] in att["closed"]:
            return False
        if self.on("R-SEASON") and att["season"] and not D.in_window(day, att["season"]):
            return False
        if self.on("R-ALT"):
            if D.CITIES[att["city"]][1] > 3500 and i + 1 < 3:
                return False
            if first_leh and day == first_leh["arr"].date():
                return False
        return True

def _relaxed_ok(task, drop, seed):
    return bool(Solver(task, active=[x for x in task.rules if x not in drop], seed=seed).solve())

def verdict(task, seed=0):
    """Feasibility and binding rules of a task, by exhaustive search + relaxation.
    -> dict(feasible, plan, binding (union), binding_sets (each a minimal set of rules; naming all of any one set explains the infeasibility), note)."""
    s = Solver(task, seed=seed)
    plan = s.solve()
    if plan:
        return {"feasible": True, "plan": plan, "binding": [], "binding_sets": [], "note": f"plan found ({s.leaves} candidates checked)"}
    cand = [r for r in task.rules if not getattr(R.RULES.get(r), "demand", False) and r not in ("R-FMT", "R-CONN")]
    singles = [r for r in cand if _relaxed_ok(task, {r}, seed)]
    sets = [[r] for r in singles]
    if not sets:
        for a, b in itertools.combinations(cand, 2):
            if _relaxed_ok(task, {a, b}, seed):
                sets.append([a, b])
    union = sorted({r for st in sets for r in st})
    note = "no plan in the search space" + ("" if sets else "; no relaxation of one or two rules helps (structural: R-CONN/R-ROUTE)")
    return {"feasible": False, "plan": None, "binding": union, "binding_sets": sets, "note": note, "leaves": s.leaves}
