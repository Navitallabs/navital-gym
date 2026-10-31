"""Env #1 world: a deterministic synthetic snapshot of Indian travel (trains with IRCTC-style classes and quotas, flights,
road transfers, hotels, attractions) built from (seed, snapshot date). Everything an agent can learn comes through the
tools below. Prices and seat counts are synthetic."""
from __future__ import annotations
import datetime as dt, math
from ...core.world import World, tool, ToolError
from . import data as D

FOOD_PER_DAY = {1: 300, 2: 600, 3: 1000, "houseboat": 800}     # per person per day by the tier of that day's stay (R-BUD)
BERTH_CLASSES = ("SL", "3A", "2A")
AC_CLASSES = ("CC", "3A", "2A")
FARE_RATE = {"2S": 0.45, "SL": 0.62, "CC": 1.35, "3A": 1.65, "2A": 2.4}
FARE_FLOOR = {"2S": 40, "SL": 150, "CC": 280, "3A": 450, "2A": 650}
TATKAL_PCT = {"2S": 0.10, "SL": 0.30, "CC": 0.30, "3A": 0.30, "2A": 0.30}   # Tatkal surcharge on the base fare, by class: 10% for 2S only, 30% for every other class including Sleeper (synthetic caps omitted)
DAY_DEPS = [330, 375, 465, 570, 790, 940]    # minutes after midnight
NIGHT_DEPS = [1170, 1275, 1360, 1400]
BUFFER_MIN = {"rail": 60, "road": 30, "air": 120}   # arrive-to-next-departure buffer, by the NEXT leg's mode
HOTEL_WORDS = ["Aravali", "Sunrise", "Heritage", "Lotus", "Royal", "Palm", "Grand", "Riverview", "Orchid", "Residency", "Courtyard", "Haveli"]

def iso(d: dt.date, minute: int) -> str:
    t = dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=minute)
    return t.strftime("%Y-%m-%dT%H:%M")

def pdate(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        raise ToolError(f"bad date {s!r}, use YYYY-MM-DD")

def rnd5(x: float) -> int:
    return int(round(x / 5.0) * 5)

class TripWorld(World):
    env_name = "trip"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        self.today = dt.date.fromisoformat(task.snapshot_date or D.DEFAULT_SNAPSHOT)
        self.edges = {}
        for a, b, km, modes in D.EDGES:
            self.edges[(a, b)] = self.edges[(b, a)] = (km, set(modes.split()))
        self._trains, self._by_id, self._ids = {}, {}, set()
        for (a, b), (km, modes) in sorted(self.edges.items()):
            if "rail" in modes:
                lst = self._gen_trains(a, b, km)
                self._trains[(a, b)] = lst
                for t in lst:
                    self._by_id[t["id"]] = t
        self.hotels = {c: self._gen_hotels(c) for c in D.CITIES}
        self.hotel_by_id = {h["id"]: h for hs in self.hotels.values() for h in hs}

    # ------------------------------------------------------------------ generation
    def _gen_trains(self, a, b, km):
        out = []
        if km <= 250: shape = ["day"] * 3
        elif km <= 450: shape = ["day", "day", "night"] if km >= 350 else ["day"] * 3
        else: shape = ["night", "night"] + (["day"] if km <= 900 else [])
        used = set()
        for i, kind in enumerate(shape):
            pool = DAY_DEPS if kind == "day" else NIGHT_DEPS
            if kind == "day" and km <= 450 and i < 2:       # short corridors always have a daily morning and a daily late-afternoon service
                pool = [330, 375, 465] if i == 0 else [940, 990]
            dep = pool[self.h("dep", a, b, i) % len(pool)]
            while dep in used:
                dep = pool[(pool.index(dep) + 1) % len(pool)]
            used.add(dep)
            speed = (62 if kind == "day" else 50) * (0.9 + (self.h("spd", a, b, i) % 21) / 100)
            dur = int(km / speed * 60) + 15 + 10 * (km // 150)
            n = self.h('tid', a, b, i) % 8000
            while f"{12000 + n}" in self._ids:
                n = (n + 1) % 8000
            tid = f"{12000 + n}"
            self._ids.add(tid)
            runs = D.WEEKDAYS if (self.h("runs", a, b, i) % 10 < 7 or (kind == "day" and km <= 450 and i < 2)) else [d for j, d in enumerate(D.WEEKDAYS) if (j + self.h("rd", a, b, i)) % 7 != 0 and (j + self.h("rd", a, b, i)) % 7 != 3]
            classes = ["CC", "2S"] if kind == "day" else ["SL", "3A", "2A"]
            fares = {c: max(FARE_FLOOR[c], rnd5(km * FARE_RATE[c])) + (60 if c in AC_CLASSES else 40) for c in classes}
            out.append(dict(id=tid, name=f"{a[:4].upper()}-{b[:4].upper()} {'Express' if kind == 'night' else 'Intercity'}", frm=a, to=b,
                            dep_min=dep, dur_min=dur, classes=classes, fares=fares, runs=runs, night=kind == "night"))
        return out

    def _gen_hotels(self, city):
        reg, alt, hill, pf = D.CITIES[city]
        pilgrim = city in ("Varanasi", "Ayodhya")
        hs = []
        for n in range(6):
            tier = 1 + n // 2
            base = {1: 1100, 2: 2400, 3: 5200}[tier] * pf * (0.9 + (self.h("hb", city, n) % 21) / 100)
            word = HOTEL_WORDS[self.h("hn", city, n) % len(HOTEL_WORDS)]
            h = dict(id=f"H-{city[:4].upper()}-{n + 1}", name=f"Hotel {word} {city}", city=city, tier=tier, kind="hotel", base_rate=rnd5(base),
                     lift=(tier == 3) or (tier == 2 and n == 2) or (n != 1 and self.h("lift", city, n) % 100 < 20),
                     ground_floor=(tier == 3) or (n == 0) or (n != 1 and self.h("gf", city, n) % 100 < 45),   # hotel #2 of every city is stairs-only, so no_stairs always bites
                     veg=self.h("veg", city, n) % 100 < 85 or n >= 3,
                     jain=(n == 5) or (n == 3) or (self.h("jain", city, n) % 100 < 25),
                     satvik=(n == 5) or (pilgrim and (n == 3 or self.h("sat", city, n) % 100 < 60)) or (self.h("sat", city, n) % 100 < 15),
                     max_guests=3)
            hs.append(h)
        if city == "Alleppey":
            for k in range(2):
                hs.append(dict(id=f"H-ALLE-HB{k + 1}", name=f"Kettuvallam Houseboat {k + 1}", city=city, tier="houseboat", kind="houseboat",
                               base_rate=rnd5(6500 * (0.92 + 0.1 * k)), lift=False, ground_floor=True, veg=True, jain=k == 1, satvik=k == 1, max_guests=3))
        return hs

    # ------------------------------------------------------------------ lookups (used by tools, grader and solver)
    def km(self, a, b):
        e = self.edges.get((a, b))
        return e[0] if e else None

    def is_hill(self, a, b):
        return D.CITIES[a][2] or D.CITIES[b][2]

    def trains_between(self, a, b, date: dt.date):
        wd = D.WEEKDAYS[date.weekday()]
        return [t for t in self._trains.get((a, b), []) if wd in t["runs"]]

    def train(self, tid):
        return self._by_id.get(str(tid))

    def avail(self, tid, date: dt.date, cls, quota, ignore_window=False):
        """-> (status, count). status: AVL | RAC | WL | CLOSED | NOT_OPEN. Count = seats (AVL) or queue position.
        ignore_window is for the solver's rule-relaxation only: pretend the quota window is open."""
        t = self.train(tid)
        if t is None or cls not in t["classes"]:
            raise ToolError("unknown train or class")
        gap = (date - self.today).days
        if quota not in ("GN", "TQ", "CUR"):
            raise ToolError("quota must be GN, TQ or CUR")
        if not ignore_window:
            if gap < 0:
                return "CLOSED", 0
            if quota == "GN":
                if gap > 60: return "NOT_OPEN", 0
                if gap < 1: return "CLOSED", 0            # general quota is open up to the day before departure (env simplification: in reality until the chart is prepared); on the day itself, Current
            elif quota == "TQ":
                if gap != 1: return "NOT_OPEN", 0
            elif quota == "CUR":
                if gap != 0: return "NOT_OPEN", 0
        if quota == "GN" and date.isoformat() in D.SOLD_OUT.get((t["frm"], t["to"]), []):
            return "WL", 1 + self.h("wl", tid, date, cls) % 40
        r = self.h("av", tid, date.isoformat(), cls, quota) % 100
        peak = D.is_peak(date)
        wl_cut = {"GN": 14 + (38 if peak else 0), "TQ": 30 + (15 if peak else 0), "CUR": 45}[quota]
        if r < wl_cut:
            return "WL", 1 + self.h("wln", tid, date, cls, quota) % 40
        if r < wl_cut + 8:
            return "RAC", 1 + self.h("rac", tid, date, cls, quota) % 20
        cap = {"GN": 48, "TQ": 8, "CUR": 6}[quota]
        return "AVL", 1 + self.h("cnt", tid, date.isoformat(), cls, quota) % cap

    def lower_berths(self, tid, date: dt.date, cls, quota, count):
        if cls not in BERTH_CLASSES:
            return None
        return min(count, self.h("lb", tid, date.isoformat(), cls, quota) % 7)

    def flights(self, a, b, date: dt.date):
        e = self.edges.get((a, b))
        if not e or "air" not in e[1]:
            return []
        km = e[0]
        out = []
        for i, dep in enumerate([[370, 800, 1240], [560, 1060, 1300]][self.h("fl", a, b) % 2]):
            dur = max(55, int(km / 650 * 60) + 40)
            noise = 0.88 + (self.h("fp", a, b, i, date.isoformat()) % 25) / 100
            price = rnd5((2400 + km * 2.6) * noise * (1.7 if D.is_peak(date) else 1.0))
            out.append(dict(id=f"IX{100 + self.h('fid', a, b, i) % 900}", frm=a, to=b, dep_min=dep, dur_min=dur, price_pp=price))
        return out

    def flight(self, fid, a, b, date):
        return next((f for f in self.flights(a, b, date) if f["id"] == fid), None)

    def road_open(self, a, b, date: dt.date):
        win = D.ROAD_SEASON.get((a, b)) or D.ROAD_SEASON.get((b, a))
        return True if not win else D.in_window(date, win)

    def transfers(self, a, b, date: dt.date):
        e = self.edges.get((a, b))
        if not e or "road" not in e[1]:
            return []
        km = e[0]
        hill = self.is_hill(a, b)
        out = [dict(id=f"TX-{a[:4].upper()}-{b[:4].upper()}", kind="taxi", frm=a, to=b, dur_min=int(km / (30 if hill else 52) * 60) + 15,
                    price_vehicle=rnd5((km * 16 + 400) * (1.35 if hill else 1)), seats=4, departures=None)]
        if km >= 120:
            out.append(dict(id=f"BUS-{a[:4].upper()}-{b[:4].upper()}", kind="bus", frm=a, to=b, dur_min=int(km / (26 if hill else 42) * 60) + 20,
                            price_pp=int(round(km * (2.6 if hill else 2.2) / 10) * 10), seats=None, departures=[480, 1290]))
        return out

    def transfer(self, tid, a, b, date):
        return next((t for t in self.transfers(a, b, date) if t["id"] == tid), None)

    def hotel_rate(self, hid, date: dt.date):
        h = self.hotel_by_id.get(hid)
        if h is None:
            raise ToolError("unknown hotel")
        noise = 0.95 + (self.h("hr", hid, date.isoformat()) % 11) / 100
        return rnd5(h["base_rate"] * noise * (1.4 if D.is_peak(date) else 1.0))

    def attraction(self, name):
        return D.ATTRACTIONS.get(name)

    def attraction_open(self, name, date: dt.date):
        """(ok, reason). Weekday closing and seasonal window."""
        a = D.ATTRACTIONS[name]
        if D.WEEKDAYS[date.weekday()] in a["closed"]:
            return False, "closed on " + D.WEEKDAYS[date.weekday()]
        if a["season"] and not D.in_window(date, a["season"]):
            return False, f"out of season (open {a['season'][0]} to {a['season'][1]})"
        return True, ""

    def snapshot(self) -> dict:
        return {"today": self.today.isoformat(), "trains": {f"{a}>{b}": v for (a, b), v in sorted(self._trains.items())}, "hotels": self.hotels}

    # ------------------------------------------------------------------ tools (what the agent sees)
    @tool("Today's date in this world and calendar facts for a date: weekday, peak-season flag, how many days away it is, quota windows.",
          {"date": {"type": "string", "description": "YYYY-MM-DD", "optional": True}})
    def calendar_info(self, date=None):
        out = {"today": self.today.isoformat(), "peak_season": "24 Dec to 2 Jan: hotels +40%, flights +70%",
               "booking": "Rail bookings are made today. General quota (GN): 1 to 60 days before departure. Tatkal (TQ): only the day before, opens 10:00 for AC classes and 11:00 for non-AC, surcharge on the base fare: +10% for 2S, +30% for every other class (SL, CC, 3A, 2A). Current (CUR): same day. Plan 'booking_date' must be today."}
        if date:
            d = pdate(date)
            out.update(date=date, weekday=D.WEEKDAYS[d.weekday()], days_from_today=(d - self.today).days, peak=D.is_peak(d), winter=D.is_winter(d))
        return out

    @tool("List trains between two cities that run on a date, with departure/arrival, classes and base fares per person.",
          {"from_city": {"type": "string", "description": "city name, e.g. Delhi"}, "to_city": {"type": "string", "description": "city name, e.g. Agra"}, "date": {"type": "string", "description": "YYYY-MM-DD"}})
    def search_trains(self, from_city, to_city, date):
        d = pdate(date)
        self._city(from_city); self._city(to_city)
        res = []
        for t in self.trains_between(from_city, to_city, d):
            res.append({"train_id": t["id"], "name": t["name"], "from": from_city, "to": to_city, "dep": iso(d, t["dep_min"]),
                        "arr": iso(d, t["dep_min"] + t["dur_min"]), "duration_min": t["dur_min"], "classes": t["classes"], "base_fare_pp": t["fares"]})
        return {"trains": res}

    @tool("Seat status for one train, date, class and quota. Status AVL (count = seats), RAC or WL (unconfirmed: not acceptable), CLOSED, NOT_OPEN.",
          {"train_id": {"type": "string", "description": "train_id from search_trains"}, "date": {"type": "string", "description": "YYYY-MM-DD"}, "cls": {"type": "string", "description": "SL, 3A, 2A, CC or 2S"},
           "quota": {"type": "string", "description": "GN, TQ or CUR"}})
    def train_availability(self, train_id, date, cls, quota):
        d = pdate(date)
        st, n = self.avail(train_id, d, cls, quota)
        out = {"train_id": train_id, "date": date, "class": cls, "quota": quota, "status": st, "count": n}
        if st == "AVL":
            lb = self.lower_berths(train_id, d, cls, quota, n)
            if lb is not None: out["lower_berths_free"] = lb
        if quota == "TQ":
            out["tatkal_surcharge_pct"] = int(TATKAL_PCT[cls] * 100)
            out["booking_opens"] = "10:00" if cls in AC_CLASSES else "11:00"
            out["booking_requires"] = "traveller's Aadhaar OTP (IRCTC, since July 2025); the agent cannot complete this alone"
        return out

    @tool("Flights between two cities on a date (price per person; every traveller aged 2 or more pays).",
          {"from_city": {"type": "string", "description": "city name"}, "to_city": {"type": "string", "description": "city name"}, "date": {"type": "string", "description": "YYYY-MM-DD"}})
    def search_flights(self, from_city, to_city, date):
        d = pdate(date)
        self._city(from_city); self._city(to_city)
        return {"flights": [{"flight_id": f["id"], "from": from_city, "to": to_city, "dep": iso(d, f["dep_min"]), "arr": iso(d, f["dep_min"] + f["dur_min"]),
                             "duration_min": f["dur_min"], "price_pp": f["price_pp"]} for f in self.flights(from_city, to_city, d)]}

    @tool("Road transfers between two cities: taxi (4 seats, price per vehicle, you choose the departure time) and bus (fixed departures, price per person aged 5+). Says if the road is closed that day.",
          {"from_city": {"type": "string", "description": "city name"}, "to_city": {"type": "string", "description": "city name"}, "date": {"type": "string", "description": "YYYY-MM-DD"}})
    def search_transfers(self, from_city, to_city, date):
        d = pdate(date)
        self._city(from_city); self._city(to_city)
        if not self.road_open(from_city, to_city, d):
            return {"transfers": [], "note": "road closed on this date (seasonal)"}
        res = []
        for t in self.transfers(from_city, to_city, d):
            r = {"transfer_id": t["id"], "kind": t["kind"], "from": from_city, "to": to_city, "duration_min": t["dur_min"], "hill_road": self.is_hill(from_city, to_city)}
            if t["kind"] == "taxi": r.update(price_per_vehicle=t["price_vehicle"], seats=4, note="departure time is your choice; arrival = departure + duration")
            else: r.update(price_pp=t["price_pp"], departures=[iso(d, m)[11:] for m in t["departures"]])
            res.append(r)
        return {"transfers": res}

    @tool("Hotels in a city with the nightly rate for each night of a stay, lift/ground-floor flags and which diets the kitchen serves.",
          {"city": {"type": "string", "description": "city name"}, "check_in": {"type": "string", "description": "YYYY-MM-DD of the first night"}, "nights": {"type": "integer", "description": "number of nights, 1 to 14"}})
    def search_hotels(self, city, check_in, nights):
        d = pdate(check_in)
        self._city(city)
        if isinstance(nights, bool):                # True is not a number of nights
            raise ToolError("nights must be a whole number from 1 to 14")
        try:
            n = int(nights)                     # "oops", inf, NaN or a list is a tool error, never a crash
        except (TypeError, ValueError, OverflowError):
            raise ToolError("nights must be a whole number from 1 to 14")
        if isinstance(nights, float) and nights != n:
            raise ToolError("nights must be a whole number from 1 to 14")
        if not 1 <= n <= 14:
            raise ToolError("nights must be 1 to 14")
        res = []
        for h in self.hotels[city]:
            res.append({"hotel_id": h["id"], "name": h["name"], "kind": h["kind"], "tier": h["tier"], "max_guests_per_room": 3,
                        "rate_per_room_night": {(d + dt.timedelta(days=i)).isoformat(): self.hotel_rate(h["id"], d + dt.timedelta(days=i)) for i in range(n)},
                        "lift": h["lift"], "ground_floor_rooms": h["ground_floor"], "serves_veg": h["veg"], "serves_jain": h["jain"], "serves_satvik": h["satvik"]})
        return {"hotels": res}

    @tool("Facts about one attraction: city, closed weekdays, hours, visit length, ticket price per adult (children 5-11 half, under 5 free), season, wheelchair access, permit.",
          {"name": {"type": "string", "description": "attraction name exactly as listed by list_attractions"}})
    def attraction_info(self, name):
        a = self.attraction(name)
        if a is None:
            raise ToolError("unknown attraction; use list_attractions(city)")
        return {"name": name, **{k: a[k] for k in ("city", "closed", "open", "close", "minutes", "adult_inr", "season", "wheelchair", "permit", "kind")},
                "altitude_m": D.CITIES[a["city"]][1], "has_sunrise_slot": a["sunrise"]}

    @tool("Attractions in a city (names to use in the plan).", {"city": {"type": "string", "description": "city name"}})
    def list_attractions(self, city):
        self._city(city)
        return {"attractions": [n for n, a in D.ATTRACTIONS.items() if a["city"] == city]}

    @tool("Ladakh protected-area fees: which places need them and the price per person.", {"place": {"type": "string", "description": "attraction name"}})
    def permit_info(self, place):
        a = self.attraction(place)
        if a is None:
            raise ToolError("unknown place")
        return {"place": place, "fee_required": a["permit"], "fee_pp": 400 if a["permit"] else 0, "what": "Ladakh environment fee and Red Cross fee, paid with registration before the visit (Indian nationals; no Inner Line Permit needed since Aug 2021; env figure, 2021 reports Rs 300 + Rs 100, check the LAHDC portal). Foreign nationals need a Protected Area Permit (not modelled)." if a["permit"] else None}

    @tool("Submit the final plan (same as ending your turn with the plan JSON).", {"plan": {"type": "object"}})
    def finalize_plan(self, plan):
        self.finalized = plan
        return {"received": True}

    def _city(self, c):
        if c not in D.CITIES:
            raise ToolError(f"unknown city {c!r}; cities: {', '.join(D.CITIES)}")
