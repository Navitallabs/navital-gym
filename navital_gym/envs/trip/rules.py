"""Env #1 rules and grader. Every rule is a deterministic function of (task, world, plan). The plan's own claims
(total_cost, fares, score, solved) are never read: costs and availability are recomputed from the world.
Rule ids match the task authors' domain rules; the semantics below are the documented simplification."""
from __future__ import annotations
import datetime as dt, math
from fractions import Fraction
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import data as D
from .world import TripWorld, FOOD_PER_DAY, BERTH_CLASSES, AC_CLASSES, TATKAL_PCT, BUFFER_MIN, iso

MAX_DAYS, MAX_LEGS_PER_DAY, MAX_STR = 31, 14, 120
DT_FMT = "%Y-%m-%dT%H:%M"

def _s(x, n=MAX_STR, f="value"):
    if not isinstance(x, str) or len(x) > n:
        raise ValueError(f"{f} must be a string of at most {n} characters")
    return x

def _i(x, lo=0, hi=1000, f="value"):
    if isinstance(x, bool) or not isinstance(x, int) or not lo <= x <= hi:
        raise ValueError(f"{f} must be an integer from {lo} to {hi}")
    return x

def _dt(x, f="value"):
    try:
        return dt.datetime.strptime(_s(x, 16, f), DT_FMT)
    except ValueError:
        raise ValueError(f"{f} must look like YYYY-MM-DDTHH:MM")

def _d(x, f="value"):
    try:
        return dt.date.fromisoformat(_s(x, 10, f))
    except ValueError:
        raise ValueError(f"{f} must look like YYYY-MM-DD")

def travelers(task):
    t = task.params.get("travelers") or {}
    ages = [30] * int(t.get("adults", 1)) + [65] * int(t.get("seniors", 0)) + [int(a) for a in t.get("child_ages", [])]
    return {"ages": ages, "n": len(ages), "n5": sum(a >= 5 for a in ages), "n2": sum(a >= 2 for a in ages),
            "k5_11": sum(5 <= a <= 11 for a in ages), "seniors": int(t.get("seniors", 0)),
            "full": sum(a >= 12 for a in ages), "half": sum(5 <= a <= 11 for a in ages)}

def parse(sub):
    return sub if isinstance(sub, dict) else None

def normalize(ctx: Ctx):
    """-> (plan dict with real dates/datetimes, [problems]). Strict: anything unknown or malformed is a problem (gate)."""
    if "plan" in ctx.cache:
        return ctx.cache["plan"]
    w, sub, problems = ctx.world, ctx.sub, []
    plan = {"days": [], "legs": []}
    try:
        plan["booking_date"] = _d(sub.get("booking_date"), "booking_date")
        days = sub.get("days")
        if not isinstance(days, list) or not 1 <= len(days) <= MAX_DAYS:
            raise ValueError("days must be a list of 1 to 31 day objects")
        for di, day in enumerate(days):
            if not isinstance(day, dict):
                raise ValueError("a day must be an object")
            dd = {"date": _d(day.get("date"), f"days[{di}].date"), "legs": [], "stay": None, "acts": []}
            legs = day.get("legs") or []
            if not isinstance(legs, list) or len(legs) > MAX_LEGS_PER_DAY:
                raise ValueError("legs must be a short list")
            for li, lg in enumerate(legs):
                if not isinstance(lg, dict):
                    raise ValueError("a leg must be an object")
                mode = _s(lg.get("mode"), 8, f"days[{di}].legs[{li}].mode")
                if mode not in ("rail", "road", "air"):
                    raise ValueError(f"days[{di}].legs[{li}].mode must be rail, road or air")
                L = {"mode": mode, "id": _s(lg.get("id"), 40, f"days[{di}].legs[{li}].id"), "frm": _s(lg.get("from"), 40, f"days[{di}].legs[{li}].from"), "to": _s(lg.get("to"), 40, f"days[{di}].legs[{li}].to"),
                     "dep": _dt(lg.get("dep"), f"days[{di}].legs[{li}].dep"), "arr": _dt(lg.get("arr"), f"days[{di}].legs[{li}].arr"), "pax": _i(lg.get("pax"), 0, 100, f"days[{di}].legs[{li}].pax"), "half": _i(lg.get("half", 0), 0, 100, f"days[{di}].legs[{li}].half"),
                     "vehicles": _i(lg.get("vehicles", 0), 0, 50, f"days[{di}].legs[{li}].vehicles"), "cls": lg.get("class"), "quota": lg.get("quota"), "book_at": lg.get("book_at"), "otp": lg.get("traveller_otp"), "day": di}
                if L["frm"] not in D.CITIES or L["to"] not in D.CITIES:
                    raise ValueError(f"days[{di}].legs[{li}]: unknown city (use names such as Delhi, Agra)")
                if mode == "rail":
                    if w.train(L["id"]) is None:
                        raise ValueError(f"days[{di}].legs[{li}].id: unknown train id {L['id']!r} (use a train_id from search_trains)")
                    L["cls"] = _s(L["cls"], 4, f"days[{di}].legs[{li}].class"); L["quota"] = _s(L["quota"], 4, f"days[{di}].legs[{li}].quota")
                    if L["book_at"] is not None: L["book_at"] = _s(L["book_at"], 5, f"days[{di}].legs[{li}].book_at")
                    if L["otp"] is not None and not isinstance(L["otp"], bool):
                        raise ValueError(f"days[{di}].legs[{li}].traveller_otp must be true or false")
                dd["legs"].append(L); plan["legs"].append(L)
            st = day.get("stay")
            if isinstance(st, dict) and not st.get("hotel_id") and not st.get("rooms"):
                st = None          # {"hotel_id": null, "rooms": []} / {} means "no hotel this night": same as omitting it (models often write it)
            if st is not None:
                if not isinstance(st, dict):
                    raise ValueError("stay must be an object")
                hid = _s(st.get("hotel_id"), 40, f"days[{di}].stay.hotel_id")
                if hid not in w.hotel_by_id:
                    raise ValueError(f"days[{di}].stay.hotel_id: unknown hotel id {hid!r} (use a hotel_id from search_hotels)")
                rooms = st.get("rooms")
                if not isinstance(rooms, list) or not 1 <= len(rooms) <= 20:
                    raise ValueError("rooms must be a list")
                dd["stay"] = {"hotel": w.hotel_by_id[hid], "guests": [_i(r.get("guests"), 0, 10, f"days[{di}].stay.rooms[].guests") for r in rooms]}
            acts = day.get("activities") or []
            if not isinstance(acts, list) or len(acts) > 12:
                raise ValueError("activities must be a short list")
            for a in acts:
                if not isinstance(a, dict):
                    raise ValueError("an activity must be an object")
                name = _s(a.get("id"), 80, f"days[{di}].activities[].id")
                if name not in D.ATTRACTIONS:
                    raise ValueError(f"days[{di}].activities[].id: unknown attraction {name!r} (use a name from list_attractions)")
                pb = a.get("fee_paid")
                if pb is not None and not isinstance(pb, bool):
                    raise ValueError(f"days[{di}].activities[].fee_paid must be true or false")
                dd["acts"].append({"name": name, "start": _dt(a.get("start"), f"days[{di}].activities[].start"), "end": _dt(a.get("end"), f"days[{di}].activities[].end"), "fee_paid": pb is True, "day": di})
            plan["days"].append(dd)
        b = sub.get("binding", [])
        plan["binding"] = [x for x in b if isinstance(x, str) and len(x) < 16][:8] if isinstance(b, list) else []
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        problems.append(str(e) or "malformed")
        plan = None
    ctx.cache["plan"] = (plan, problems)
    return ctx.cache["plan"]

def _plan(ctx):
    plan, _ = normalize(ctx)
    return plan

def _start(task):
    return dt.date.fromisoformat(task.params["start"])

def _legs_sorted(plan):
    return sorted(plan["legs"], key=lambda l: (l["dep"], l["arr"]))

def timeline(ctx):
    """Presence intervals [(city, t_in, t_out, arrived_by_leg)] and the location at each midnight (None = in transit)."""
    if "tl" in ctx.cache:
        return ctx.cache["tl"]
    t, plan = ctx.task, _plan(ctx)
    start = _start(t)
    legs = _legs_sorted(plan)
    n = len(plan["days"])
    trip_start = dt.datetime.combine(start, dt.time())
    trip_end = dt.datetime.combine(start + dt.timedelta(days=n - 1), dt.time()) + dt.timedelta(hours=23, minutes=59)
    loc, tin, arrived = t.params["origin"], trip_start, False
    ivs, problems = [], []
    for lg in legs:
        if lg["frm"] != loc:
            problems.append(f"leg {lg['id']} leaves {lg['frm']} but you are in {loc}")
        ivs.append((loc, tin, lg["dep"], arrived, lg))
        loc, tin, arrived = lg["to"], lg["arr"], True
    ivs.append((loc, tin, trip_end, arrived, None))
    mids = []
    for i in range(n - 1):
        mid = dt.datetime.combine(start + dt.timedelta(days=i + 1), dt.time())
        where = None
        for city, a, b, _, nxt in ivs:
            if a <= mid <= b:
                where = city
                break
        mids.append(where)
    ctx.cache["tl"] = (ivs, mids, loc, problems)
    return ctx.cache["tl"]

def evening_possible(ivs, city, att, date) -> bool:
    """Can the traveller attend the whole of `att` (an evening session such as the Ganga Aarti) in `city` on `date`? True when some stay in the city, shortened by the 30-minute
    arrival buffer and the buffer before the next leg, holds a slot of the activity's length inside its opening hours on an open weekday and in season."""
    if D.WEEKDAYS[date.weekday()] in att["closed"] or (att["season"] and not D.in_window(date, att["season"])):
        return False
    o = dt.datetime.combine(date, dt.datetime.strptime(att["open"], "%H:%M").time())
    c = dt.datetime.combine(date, dt.datetime.strptime(att["close"], "%H:%M").time())
    need = dt.timedelta(minutes=att["minutes"])
    for ccity, t_in, t_out, arrived, nxt in ivs:
        if ccity != city:
            continue
        lo = t_in + (dt.timedelta(minutes=30) if arrived else dt.timedelta())
        hi = t_out - (dt.timedelta(minutes=BUFFER_MIN[nxt["mode"]]) if nxt else dt.timedelta())
        if max(lo, o) + need <= min(hi, c):
            return True
    return False

# ----------------------------------------------------------------------------------------------- rules
class RFmt(Rule):
    id, gate = "R-FMT", True
    description = "Schema-valid JSON with known ids"
    def check(self, ctx):
        plan, problems = normalize(ctx)
        return RuleResult(plan is not None, "; ".join(problems))

class RDate(Rule):
    id = "R-DATE"; description = "Exactly `days` consecutive dates from `start`; starts at origin, ends at the end city on the last date"
    def check(self, ctx):
        t, plan = ctx.task, _plan(ctx)
        start, n = _start(t), t.params["days"]
        if len(plan["days"]) != n:
            return RuleResult(False, f"plan has {len(plan['days'])} days, task needs {n}")
        for i, d in enumerate(plan["days"]):
            if d["date"] != start + dt.timedelta(days=i):
                return RuleResult(False, f"day {i + 1} should be {start + dt.timedelta(days=i)}")
            for lg in d["legs"]:
                if lg["dep"].date() != d["date"]:
                    return RuleResult(False, f"leg {lg['id']} departs on {lg['dep'].date()} but is listed under {d['date']}")
        ivs, mids, final, problems = timeline(ctx)
        end = t.params.get("end") or t.params["origin"]
        if final != end:
            return RuleResult(False, f"trip ends in {final}, not {end}")
        last = start + dt.timedelta(days=n - 1)
        if plan["legs"] and max(l["arr"] for l in plan["legs"]).date() > last:
            return RuleResult(False, "a leg arrives after the last day")
        arrive_last = [l for l in plan["legs"] if l["to"] == end and l["arr"].date() == last]
        if n > 1 and not arrive_last:
            return RuleResult(False, "the trip must use all its days: be back on the last date")
        return RuleResult(True)

def _service_ok(w, lg):
    """The leg is a real service on that date with the right times. -> (ok, why, info)"""
    d = lg["dep"].date()
    a, b = lg["frm"], lg["to"]
    if lg["mode"] == "rail":
        tr = w.train(lg["id"])
        if tr is None or (tr["frm"], tr["to"]) != (a, b) or D.WEEKDAYS[d.weekday()] not in tr["runs"]:
            return False, "train does not run between these cities on this date", None
        if lg["dep"] != dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=tr["dep_min"]) or lg["arr"] - lg["dep"] != dt.timedelta(minutes=tr["dur_min"]):
            return False, "train times do not match the timetable", None
        return True, "", tr
    if lg["mode"] == "air":
        f = w.flight(lg["id"], a, b, d)
        if f is None:
            return False, "no such flight on this date", None
        if lg["dep"] != dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=f["dep_min"]) or lg["arr"] - lg["dep"] != dt.timedelta(minutes=f["dur_min"]):
            return False, "flight times do not match", None
        return True, "", f
    t = w.transfer(lg["id"], a, b, d)
    if t is None:
        return False, "no such road transfer", None
    if lg["arr"] - lg["dep"] != dt.timedelta(minutes=t["dur_min"]):
        return False, "transfer duration does not match", None
    if t["kind"] == "bus" and (lg["dep"].hour * 60 + lg["dep"].minute) not in t["departures"]:
        return False, "bus does not leave at that time", None
    return True, "", t

class RConn(Rule):
    id = "R-CONN"; description = "Real services, location continuity, buffers (rail 60 / road 30 / air 120 min), a hotel for each night"
    def check(self, ctx):
        w, t, plan = ctx.world, ctx.task, _plan(ctx)
        ivs, mids, final, problems = timeline(ctx)
        if problems:
            return RuleResult(False, problems[0])
        prev_arr = None
        for lg in _legs_sorted(plan):
            ok, why, _ = _service_ok(w, lg)
            if not ok:
                return RuleResult(False, f"{lg['mode']} {lg['id']}: {why}")
            if lg["arr"] <= lg["dep"]:
                return RuleResult(False, "a leg arrives before it departs")
            if prev_arr and lg["dep"] < prev_arr + dt.timedelta(minutes=BUFFER_MIN[lg["mode"]]):
                return RuleResult(False, f"connection to {lg['id']} is shorter than the {BUFFER_MIN[lg['mode']]} min buffer")
            prev_arr = lg["arr"]
        n = len(plan["days"])
        for i, d in enumerate(plan["days"]):
            last = i == n - 1
            where = None if last else mids[i]
            st = d["stay"]
            if last:
                if st:
                    return RuleResult(False, "no hotel on the last day (there is no night)")
                continue
            if where is None:
                if st:
                    return RuleResult(False, f"{d['date']}: hotel booked but you are in transit at midnight")
            else:
                if not st:
                    return RuleResult(False, f"{d['date']}: no hotel for the night in {where}")
                if st["hotel"]["city"] != where:
                    return RuleResult(False, f"{d['date']}: hotel is in {st['hotel']['city']} but you are in {where}")
        # activities must sit inside a presence interval of their own city
        acts = sorted((a for d in plan["days"] for a in d["acts"]), key=lambda a: a["start"])
        for a in acts:
            att = D.ATTRACTIONS[a["name"]]
            okk = False
            for city, t_in, t_out, arrived, nxt in ivs:
                if city != att["city"]:
                    continue
                lo = t_in + (dt.timedelta(minutes=30) if arrived else dt.timedelta())
                hi = t_out - (dt.timedelta(minutes=BUFFER_MIN[nxt["mode"]]) if nxt else dt.timedelta())
                if a["start"] >= lo and a["end"] <= hi:
                    okk = True
                    break
            if not okk:
                return RuleResult(False, f"{a['name']} is not reachable at that time (you are elsewhere or in transit)")
        for x, y in zip(acts, acts[1:]):
            if y["start"] < x["end"]:
                return RuleResult(False, "two activities overlap")
        return RuleResult(True)

def _quota_open(w, today, lg):
    """-> (open, why). Window rule only; seat counts are R-AVAIL."""
    gap = (lg["dep"].date() - today).days
    q = lg["quota"]
    if q == "GN":
        return (1 <= gap <= 60), f"general quota is open 60 days to 1 day before departure; this is {gap}"
    if q == "TQ":
        return gap == 1, f"Tatkal is only the day before departure; this is {gap}"
    if q == "CUR":
        return gap == 0, f"Current booking is only on the day of departure; this is {gap}"
    return False, "quota must be GN, TQ or CUR"

class RQuota(Rule):
    id = "R-QUOTA"; description = "booking_date is today; quota window open (GN 1-60 days before departure, TQ the day before at 10:00 AC / 11:00 non-AC with the traveller's Aadhaar OTP, CUR on the day of departure)"
    def check(self, ctx):
        w, plan = ctx.world, _plan(ctx)
        if plan["booking_date"] != w.today:
            return RuleResult(False, f"booking_date must be today ({w.today})")
        for lg in plan["legs"]:
            if lg["mode"] != "rail":
                continue
            if lg["cls"] not in (w.train(lg["id"]) or {"classes": []})["classes"]:
                return RuleResult(False, f"train {lg['id']} has no class {lg['cls']}")
            ok, why = _quota_open(w, w.today, lg)
            if not ok:
                return RuleResult(False, f"{lg['id']}: {why}")
            if lg["quota"] == "TQ" and lg["book_at"] != ("10:00" if lg["cls"] in AC_CLASSES else "11:00"):
                return RuleResult(False, f"{lg['id']}: Tatkal book_at must be 10:00 (AC) or 11:00 (non-AC)")
            if lg["quota"] == "TQ" and lg["otp"] is not True:
                return RuleResult(False, f"{lg['id']}: Tatkal needs the traveller's Aadhaar OTP: mark traveller_otp true (you cannot complete it alone)")
        return RuleResult(True)

class RAvail(Rule):
    id = "R-AVAIL"; description = "Every rail leg is confirmed (AVL with enough seats); RAC and WL do not count"
    def check(self, ctx):
        w, plan = ctx.world, _plan(ctx)
        for lg in plan["legs"]:
            if lg["mode"] != "rail" or w.train(lg["id"]) is None or lg["cls"] not in w.train(lg["id"])["classes"]:
                continue
            closed = not _quota_open(w, w.today, lg)[0]
            if closed and "R-QUOTA" in ctx.task.rules:
                continue                      # window problems belong to R-QUOTA
            st, n = w.avail(lg["id"], lg["dep"].date(), lg["cls"], lg["quota"], ignore_window=closed)
            if st != "AVL" or n < lg["pax"]:
                return RuleResult(False, f"{lg['id']} {lg['cls']} {lg['quota']} on {lg['dep'].date()}: {st} {n}, need {lg['pax']} confirmed seats")
        return RuleResult(True)

class ROpen(Rule):
    id = "R-OPEN"; description = "Each activity on an open weekday, within hours, for at least its visit length"
    def check(self, ctx):
        w, plan = ctx.world, _plan(ctx)
        for d in plan["days"]:
            for a in d["acts"]:
                att = D.ATTRACTIONS[a["name"]]
                if a["start"].date() != a["end"].date() or a["start"].date() != d["date"]:
                    return RuleResult(False, f"{a['name']}: an activity must start and end on its day")
                if D.WEEKDAYS[d["date"].weekday()] in att["closed"]:
                    return RuleResult(False, f"{a['name']} is closed on {D.WEEKDAYS[d['date'].weekday()]}")
                o = dt.datetime.combine(d["date"], dt.datetime.strptime(att["open"], "%H:%M").time())
                c = dt.datetime.combine(d["date"], dt.datetime.strptime(att["close"], "%H:%M").time())
                if a["start"] < o or a["end"] > c:
                    return RuleResult(False, f"{a['name']} is open {att['open']} to {att['close']}")
                if a["end"] - a["start"] < dt.timedelta(minutes=att["minutes"]):
                    return RuleResult(False, f"{a['name']} needs {att['minutes']} min")
        return RuleResult(True)

class RSeason(Rule):
    id = "R-SEASON"; description = "Seasonal facts: sights in season, seasonal roads open"
    def check(self, ctx):
        w, plan = ctx.world, _plan(ctx)
        for d in plan["days"]:
            for a in d["acts"]:
                s = D.ATTRACTIONS[a["name"]]["season"]
                if s and not D.in_window(d["date"], s):
                    return RuleResult(False, f"{a['name']} is out of season on {d['date']}")
        for lg in plan["legs"]:
            if lg["mode"] == "road" and not w.road_open(lg["frm"], lg["to"], lg["dep"].date()):
                return RuleResult(False, f"{lg['frm']} to {lg['to']} road is closed on {lg['dep'].date()}")
        return RuleResult(True)

class RRest(Rule):
    id = "R-REST"; description = "A rest day: no leg over 2 hours touching the day (departing, arriving or passing through it), no ticketed activity"
    def check(self, ctx):
        need, plan = int(ctx.task.params.get("rest_days", 0)), _plan(ctx)
        n = 0
        for d in plan["days"]:
            # v1.1: a leg counts on every calendar day it touches, so an overnight arrival is travel on the arrival day (v1.0.1 looked only at legs departing that day)
            touching = [l for l in plan["legs"] if l["dep"].date() <= d["date"] <= l["arr"].date()]
            if all((l["arr"] - l["dep"]) <= dt.timedelta(hours=2) for l in touching) and all(D.ATTRACTIONS[a["name"]]["adult_inr"] == 0 for a in d["acts"]):
                n += 1
        return RuleResult(n >= need, f"{n} rest day(s), need {need}")

def room_ok(g):
    return all(1 <= x <= 3 for x in g)

class ROcc(Rule):
    id = "R-OCC"; description = "Rooms hold at most 3 guests and cover everyone; every leg is ticketed for exactly the right people"
    def check(self, ctx):
        tv, plan = travelers(ctx.task), _plan(ctx)
        for d in plan["days"]:
            st = d["stay"]
            if st and (not room_ok(st["guests"]) or sum(st["guests"]) != tv["n"]):
                return RuleResult(False, f"{d['date']}: rooms must hold all {tv['n']} guests, 1 to 3 per room")
        for lg in plan["legs"]:
            m = lg["mode"]
            if m == "rail":
                ok = lg["pax"] + lg["half"] == tv["n5"] and lg["half"] <= tv["k5_11"] and lg["pax"] >= 1
            elif m == "air":
                ok = lg["pax"] == tv["n2"] and lg["half"] == 0
            else:
                t = ctx.world.transfer(lg["id"], lg["frm"], lg["to"], lg["dep"].date())
                if t is None:
                    continue
                if t["kind"] == "taxi":
                    ok = lg["vehicles"] == math.ceil(tv["n"] / 4) and lg["half"] == 0
                else:
                    ok = lg["pax"] == tv["n5"] and lg["half"] == 0
            if not ok:
                return RuleResult(False, f"{m} {lg['id']}: wrong passenger count (rail: pax+half = travellers aged 5+, half only for ages 5-11; air: aged 2+; taxi: vehicles = ceil(everyone/4); bus: aged 5+)")
        return RuleResult(True)

def _q(x) -> Fraction:
    """Exact money: floats are read through their decimal text (0.3 means 3/10, not the nearest binary fraction)."""
    return Fraction(str(x)) if isinstance(x, float) else Fraction(x)

HALF = Fraction(1, 2)

def leg_cost(w, lg):
    """Exact (Fraction) cost of one leg: no binary floating point, so a plan that costs exactly the budget is within it."""
    d = lg["dep"].date()
    if lg["mode"] == "rail":
        tr = w.train(lg["id"])
        if tr is None or lg["cls"] not in tr["fares"]:
            return None          # not a real service: R-CONN / R-QUOTA report it; the cost of a leg that does not exist is unknown
        base = _q(tr["fares"][lg["cls"]])
        sur = _q(TATKAL_PCT[lg["cls"]]) if lg["quota"] == "TQ" else Fraction(0)
        return base * (1 + sur) * (lg["pax"] + HALF * lg["half"])
    if lg["mode"] == "air":
        f = w.flight(lg["id"], lg["frm"], lg["to"], d)
        return None if f is None else f["price_pp"] * lg["pax"]
    t = w.transfer(lg["id"], lg["frm"], lg["to"], d)
    if t is None:
        return None
    return t["price_vehicle"] * lg["vehicles"] if t["kind"] == "taxi" else t["price_pp"] * lg["pax"]

def recompute_cost(ctx) -> Fraction:
    w, t, plan, tv = ctx.world, ctx.task, _plan(ctx), travelers(ctx.task)
    costs = [leg_cost(w, lg) for lg in plan["legs"]]
    if any(c is None for c in costs):
        return None              # a leg is not a real service: no total exists (R-BUD fails by name, R-CONN says which leg)
    total = sum(costs, Fraction(0))
    prev_tier = None
    n = len(plan["days"])
    for i, d in enumerate(plan["days"]):
        if d["stay"]:
            h = d["stay"]["hotel"]
            total += _q(w.hotel_rate(h["id"], d["date"])) * len(d["stay"]["guests"])
        h = d["stay"]["hotel"] if d["stay"] else None
        tier = h["tier"] if h else prev_tier
        if h:
            prev_tier = h["tier"]
        total += _q(FOOD_PER_DAY.get(tier if tier is not None else 1)) * (tv["full"] + HALF * tv["half"])
        for a in d["acts"]:
            att = D.ATTRACTIONS[a["name"]]
            total += _q(att["adult_inr"]) * (tv["full"] + HALF * tv["half"])
            if att["permit"]:
                total += 400 * tv["n5"]
    return total

class RBud(Rule):
    id = "R-BUD"; description = "Recomputed total cost (fares, rooms, transfers, tickets, permits, food allowance) within budget"
    def check(self, ctx):
        b = ctx.task.params.get("budget_inr")
        if b is None:
            return RuleResult(True, "no budget")
        c = recompute_cost(ctx)
        if c is None:
            return RuleResult(False, "cost cannot be computed: a leg is not a real service (R-CONN says which)")
        return RuleResult(c <= b, f"cost {float(c):.0f} vs budget {b}")

def food_hotels(plan):
    out, prev = [], None
    for d in plan["days"]:
        if d["stay"]: prev = d["stay"]["hotel"]
        out.append(d["stay"]["hotel"] if d["stay"] else prev)
    return out

class RDiet(Rule):
    id = "R-DIET"; description = "veg / jain / satvik: each day's food hotel serves the diet (flags are separate)"
    def check(self, ctx):
        diet = ctx.task.params.get("diet", "any")
        if diet in (None, "any"):
            return RuleResult(True)
        for d, h in zip(_plan(ctx)["days"], food_hotels(_plan(ctx))):
            if h is not None and not h[diet]:
                return RuleResult(False, f"{d['date']}: {h['name']} does not serve {diet}")
        return RuleResult(True)

class RAcc(Rule):
    id = "R-ACC"; description = "no_stairs: lift or ground-floor rooms and wheelchair-friendly sights; seniors need a free lower berth in berth classes"
    def check(self, ctx):
        p, w, plan, tv = ctx.task.params, ctx.world, _plan(ctx), travelers(ctx.task)
        if p.get("no_stairs"):
            for d in plan["days"]:
                if d["stay"] and not (d["stay"]["hotel"]["lift"] or d["stay"]["hotel"]["ground_floor"]):
                    return RuleResult(False, f"{d['stay']['hotel']['name']} has no lift or ground-floor rooms")
                if p.get("need_lift") and d["stay"] and not d["stay"]["hotel"]["lift"]:     # v1.1: the task asks for a hotel with a lift
                    return RuleResult(False, f"{d['stay']['hotel']['name']} has no lift")
                for a in d["acts"]:
                    if not D.ATTRACTIONS[a["name"]]["wheelchair"]:
                        return RuleResult(False, f"{a['name']} is not step-free")
        if tv["seniors"]:
            for lg in plan["legs"]:
                if lg["mode"] == "rail" and lg["cls"] in BERTH_CLASSES and w.train(lg["id"]):
                    closed = not _quota_open(w, w.today, lg)[0]
                    st, n = w.avail(lg["id"], lg["dep"].date(), lg["cls"], lg["quota"], ignore_window=closed)
                    lb = w.lower_berths(lg["id"], lg["dep"].date(), lg["cls"], lg["quota"], n) if st == "AVL" else 0
                    if (lb or 0) < tv["seniors"]:
                        return RuleResult(False, f"{lg['id']} {lg['cls']}: fewer than {tv['seniors']} free lower berths for seniors")
        return RuleResult(True)

def _road_overlap(lg, start_h, start_m):
    """Does a road leg overlap [start, 05:00 next day] on any day it touches?"""
    d0 = lg["dep"].date() - dt.timedelta(days=1)
    for k in range(3):
        day = d0 + dt.timedelta(days=k)
        a = dt.datetime.combine(day, dt.time(start_h, start_m))
        b = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(5, 0))
        if lg["dep"] < b and lg["arr"] > a:
            return True
    return False

class RNight(Rule):
    id = "R-NIGHT"; description = "No road leg in the night window: 22:00-05:00 if no_night_road; the task's no_road_after; winter hill roads 20:00-05:00"
    def check(self, ctx):
        p, w = ctx.task.params, ctx.world
        for lg in _plan(ctx)["legs"]:
            if lg["mode"] != "road" or not w.road_open(lg["frm"], lg["to"], lg["dep"].date()):
                continue                      # a closed seasonal road is already R-SEASON's violation
            h, m = 99, 0
            if p.get("no_night_road"): h, m = 22, 0
            if p.get("no_road_after"): h, m = (int(x) for x in p["no_road_after"].split(":"))
            if w.is_hill(lg["frm"], lg["to"]) and D.is_winter(lg["dep"].date()) and (h, m) > (20, 0):
                h, m = 20, 0
            if h < 99 and _road_overlap(lg, h, m):
                return RuleResult(False, f"road leg {lg['id']} runs in the night window (after {h:02d}:{m:02d})")
        return RuleResult(True)

class RHrs(Rule):
    id = "R-HRS"; description = "No more than max_travel_hours_per_day of travel on any day"
    def check(self, ctx):
        cap = float(ctx.task.params.get("max_travel_hours_per_day", 99)) * 60
        plan = _plan(ctx)
        for d in plan["days"]:
            lo = dt.datetime.combine(d["date"], dt.time()); hi = lo + dt.timedelta(days=1)
            mins = sum(max(0, (min(l["arr"], hi) - max(l["dep"], lo)).total_seconds()) / 60 for l in plan["legs"])
            if mins > cap:
                return RuleResult(False, f"{d['date']}: {mins / 60:.1f} h of travel, limit {cap / 60:.0f}")
        return RuleResult(True)

class RAlt(Rule):
    id = "R-ALT"; description = "Altitude pacing (simplified, not medical advice): the day you reach Leh is rest only; nothing higher than Leh (here: above 3,500 m) before day 3"
    def check(self, ctx):
        plan = _plan(ctx)
        first_leh = None
        for lg in _legs_sorted(plan):
            if lg["to"] == "Leh":
                first_leh = lg; break
        for i, d in enumerate(plan["days"]):
            for a in d["acts"]:
                alt = D.CITIES[D.ATTRACTIONS[a["name"]]["city"]][1]
                if alt > 3500 and i + 1 < 3:
                    return RuleResult(False, f"{a['name']} is above 3500 m before day 3")
                if first_leh and a["start"].date() == first_leh["arr"].date():
                    return RuleResult(False, "the day you reach Leh is rest only")
            if d["stay"] and D.CITIES[d["stay"]["hotel"]["city"]][1] > 3500 and i + 1 < 3:
                return RuleResult(False, f"sleeping above 3500 m before day 3")
        return RuleResult(True)

class RPermit(Rule):
    id = "R-PERMIT"; description = "Ladakh protected-area places (Nubra, Pangong) need the environment and Red Cross fee paid (Indian nationals; no Inner Line Permit since 2021)"
    def check(self, ctx):
        w = ctx.world
        for d in _plan(ctx)["days"]:
            for a in d["acts"]:
                if D.ATTRACTIONS[a["name"]]["permit"]:
                    if not a["fee_paid"]:
                        return RuleResult(False, f"{a['name']}: the Ladakh environment and Red Cross fee must be paid (fee_paid true)")
        return RuleResult(True)

class RRoute(Rule):
    id = "R-ROUTE"; description = "The trip does what was asked: visits every named city, must_visit sights, must_use legs, day-specific visits"
    demand = True      # a demand rule restates the request; it is never reported as the binding reason a task is infeasible
    def check(self, ctx):
        t, plan = ctx.task, _plan(ctx)
        p = t.params
        arrived = {l["to"] for l in plan["legs"]}
        seen = {d["stay"]["hotel"]["city"] for d in plan["days"] if d["stay"]} | {D.ATTRACTIONS[a["name"]]["city"] for d in plan["days"] for a in d["acts"]}
        for c in p.get("route", []):
            if c != p["origin"] and c not in arrived:
                return RuleResult(False, f"never reaches {c}")
            if c != p["origin"] and c != p.get("end") and c not in seen:      # arriving is enough where the trip ENDS (a rail booking has no night or sight)
                return RuleResult(False, f"passes through {c} without a night or a sight there")
        for c in p.get("avoid_cities", []):      # v1.1: a city the task excludes ("no Kaziranga") must not be visited, stayed in or passed through
            if c in arrived or c in seen or any(l["frm"] == c for l in plan["legs"]):
                return RuleResult(False, f"the task excludes {c}")
        names = [(a["name"], i, a) for i, d in enumerate(plan["days"]) for a in d["acts"]]
        for need in p.get("must_visit", []):
            if not any(n == need for n, _, _ in names):
                return RuleResult(False, f"no visit to {need}")
        for mu in p.get("must_use", []):
            if not any(l["mode"] == mu["mode"] and {l["frm"], l["to"]} == {mu["from"], mu["to"]} and (not mu.get("dir") or (l["frm"], l["to"]) == (mu["from"], mu["to"])) for l in plan["legs"]):
                return RuleResult(False, f"must use {mu['mode']} {mu['from']} to {mu['to']}")
        for dv in p.get("day_visit", []):
            hit = [a for n, i, a in names if n == dv["name"] and i + 1 == dv["day"]]
            if not hit:
                return RuleResult(False, f"{dv['name']} must be visited on day {dv['day']}")
            if dv.get("slot") == "sunrise" and not all(a["start"].hour * 60 + a["start"].minute <= 420 for a in hit):
                return RuleResult(False, f"{dv['name']} visit must start by 07:00 (sunrise slot)")
        for hb in p.get("stay_kind", []):
            if not any(d["stay"] and d["stay"]["hotel"]["kind"] == hb["kind"] and d["stay"]["hotel"]["city"] == hb["city"] for d in plan["days"]):
                return RuleResult(False, f"needs a {hb['kind']} night in {hb['city']}")
        for dc in p.get("daily_in_city", []):    # v1.1: the activity on every evening the traveller can attend it in the city, the evening of the day they leave included
            ivs = timeline(ctx)[0]; att = D.ATTRACTIONS[dc["name"]]
            for d in plan["days"]:
                if evening_possible(ivs, dc["city"], att, d["date"]) and not any(a["name"] == dc["name"] for a in d["acts"]):
                    return RuleResult(False, f"{dc['name']} is needed on every evening you can attend it in {dc['city']} ({d['date']})")
        if p.get("classes_only") and any(l["mode"] == "rail" and l["cls"] not in p["classes_only"] for l in plan["legs"]):
            return RuleResult(False, "the task limits rail classes to " + ",".join(p["classes_only"]))
        if p.get("rail_dep_before"):
            h, m = (int(x) for x in p["rail_dep_before"].split(":"))
            if any(l["mode"] == "rail" and (l["dep"].hour, l["dep"].minute) >= (h, m) for l in plan["legs"]):
                return RuleResult(False, f"the train must leave before {p['rail_dep_before']}")
        if p.get("mode_policy") == "rail_only":
            if any(l["mode"] != "rail" for l in plan["legs"] if l["frm"] != l["to"] and (l["frm"] in D.CITIES and l["to"] in D.CITIES) and "rail" in (ctx.world.edges.get((l["frm"], l["to"]), (0, set()))[1])):
                return RuleResult(False, "the task asks for trains only where a train link exists")
        return RuleResult(True)

RULES = {r.id: r for r in (RFmt(), RDate(), RConn(), RQuota(), RAvail(), ROpen(), RSeason(), RRest(), ROcc(), RBud(), RDiet(), RAcc(), RNight(), RHrs(), RAlt(), RPermit(), RRoute())}

def infeasible_check(ctx):
    task = ctx.task
    claimed = [x for x in (ctx.sub.get("binding") or []) if isinstance(x, str)] if isinstance(ctx.sub.get("binding"), list) else []
    if task.expected_feasible:
        return False, "the task is feasible"
    union = set(task.binding) | {r for st in (task.meta.get("binding_sets") or []) for r in st}
    if claimed and set(claimed) <= union:
        return True, "binding rule(s) named"
    return False, "name only rules that are really part of the reason (a non-empty subset of the true binding rules)"

def soft(ctx):
    plan, w = _plan(ctx), ctx.world
    km = [(w.km(l["frm"], l["to"]) or 0, l["mode"]) for l in plan["legs"]]
    tot = sum(k for k, _ in km) or 1
    c, b = recompute_cost(ctx), ctx.task.params.get("budget_inr")
    if c is None:
        return {"rail_share_km": round(sum(k for k, m in km if m == "rail") / tot, 3), "legs": len(plan["legs"]), "cost_inr": None, "budget_slack": None}
    return {"rail_share_km": round(sum(k for k, m in km if m == "rail") / tot, 3), "legs": len(plan["legs"]), "cost_inr": round(float(c)),
            "budget_slack": round(float(1 - c / b), 3) if b else None}

def make_grader(seed: int = 0):
    """The grader judges a plan against the world of ITS seed (v1.1: it used seed 0 whatever the env was loaded with)."""
    return Grader(RULES, lambda task: TripWorld(task, seed), parse, soft, infeasible_check)


def format_problem(env, sub):
    """Shape check the runner uses to offer one repair retry: None if the answer is readable, else the reason (the same text R-FMT reports)."""
    if not isinstance(sub, dict) or sub.get("status") not in ("plan", "infeasible"):
        return 'the JSON object needs "status": "plan" (with booking_date and days) or "status": "infeasible" (with binding)'
    if sub["status"] == "infeasible":
        b = sub.get("binding")
        return None if isinstance(b, list) and all(isinstance(x, str) for x in b) else '"binding" must be a list of rule ids such as ["R-BUD"]'
    ctx = Ctx(task=env.task, world=env.world, sub=sub)
    plan, problems = normalize(ctx)
    return None if plan is not None else "; ".join(problems)
