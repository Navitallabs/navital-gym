"""Env #1: Indian trip planning under real constraints (trains with quotas and waitlists, flights, road transfers, hotels, sights).
    from navital_gym.envs.trip import load_env, grade
    env = load_env(); obs = env.reset("IN-TRIP-002")      # obs = prompt + tool specs; the agent never sees hidden task fields
    grade(task_dict, submission)                           # the shared grader contract: {"score", "solved", "rules"}; never raises
"""
import os
from ...core import Env, load_tasks, Task
from .world import TripWorld
from .rules import make_grader, RULES

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_PATH = os.path.join(HERE, "tasks.jsonl")
EASY_PATH = os.path.join(HERE, "tasks_easy.jsonl")

INSTRUCTIONS = """You are planning a real trip in a fixed simulated India (prices, timetables and seats are synthetic and identical every run).
Use the tools to look things up. Nothing is booked until you finish. Finish with ONE JSON object and nothing else after it.

If a valid plan exists, answer:
{"status": "plan", "booking_date": "YYYY-MM-DD" (today, see calendar_info),
 "days": [ {"date": "YYYY-MM-DD",
            "legs": [ {"mode": "rail"|"road"|"air", "id": train_id | transfer_id | flight_id, "from": city, "to": city,
                       "dep": "YYYY-MM-DDTHH:MM", "arr": "YYYY-MM-DDTHH:MM",
                       "class": "SL|3A|2A|CC|2S" (rail), "quota": "GN|TQ|CUR" (rail), "book_at": "10:00" or "11:00" (Tatkal only: AC / non-AC),
                       "pax": n, "half": n (rail only: children 5-11 on half fare, no berth), "vehicles": n (taxi only)} ],
            "stay": {"hotel_id": id, "rooms": [{"guests": n}, ...]}   (the hotel for the NIGHT that starts on this date; omit on the last day and when you are on a train at midnight)
            "activities": [ {"id": attraction name, "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "permit_booked": "YYYY-MM-DD" (permit places only)} ] } ... one entry per day ] }
Shape of a plan (made-up ids and dates, only to show the format; look up real ids with the tools):
{"status": "plan", "booking_date": "2026-11-15", "days": [
  {"date": "2026-12-05", "legs": [{"mode": "rail", "id": "12345", "from": "Delhi", "to": "Agra", "dep": "2026-12-05T06:15", "arr": "2026-12-05T10:05", "class": "CC", "quota": "GN", "pax": 2, "half": 0}],
   "stay": {"hotel_id": "H-AGRA-1", "rooms": [{"guests": 2}]}, "activities": [{"id": "Agra Fort", "start": "2026-12-05T11:00", "end": "2026-12-05T13:00"}]},
  {"date": "2026-12-06", "legs": [{"mode": "rail", "id": "12346", "from": "Agra", "to": "Delhi", "dep": "2026-12-06T16:30", "arr": "2026-12-06T20:20", "class": "CC", "quota": "GN", "pax": 2, "half": 0}], "activities": []}]}
If no plan can satisfy every request, answer {"status": "infeasible", "binding": [the rule id(s) that make it impossible]}. Name only the rules that are the reason: any rule that is not part of the reason makes the answer wrong.

The rules we check (the same for every task; each only if the task makes it relevant):
R-FMT valid JSON with real ids. R-DATE exactly the requested days, start at the origin, be back (or at the end city) on the last date.
R-CONN real services, no teleporting, buffers between legs (rail 60, road 30, air 120 min), a hotel in the right city every night.
R-QUOTA booking_date is today; General quota 2-60 days before departure; Tatkal only the day before; Current only on the day.
R-AVAIL every train leg is confirmed (AVL with enough seats); RAC and waitlist do not count. R-OPEN sights on open days, within hours, for their full visit length.
R-SEASON sights in season and seasonal roads open. R-REST rest days (no leg over 2 hours, no ticketed sight). R-OCC rooms hold at most 3 guests and cover everyone; every leg is ticketed for exactly the right people.
R-BUD total cost within budget (the grader recomputes it from the tool prices; food allowance per person per day is 300 / 600 / 1000 by hotel tier, 800 on a houseboat).
R-DIET veg/jain/satvik hotels. R-ACC no_stairs hotels and sights; seniors need a free lower berth in sleeper/3A/2A. R-NIGHT no road legs in the night window. R-HRS travel hours per day.
R-ALT altitude pacing (the day you reach Leh is rest only; nothing higher than Leh, here above 3,500 m, before day 3). R-PERMIT permits booked at least a day ahead. R-ROUTE the trip does what was asked: every named city gets a night or a sight there (arriving is enough in the city where the trip ends)."""

def load_env(seed: int = 0, tasks_path: str = TASKS_PATH, splits=("core",)) -> Env:
    """splits: which task files to load: "core" (the standard 55, the default so existing samples and results never change) and/or "easy" (tasks_easy.jsonl)."""
    tasks = (load_tasks(tasks_path) if "core" in splits else []) + (load_tasks(EASY_PATH) if "easy" in splits else [])
    env = Env(tasks, TripWorld, make_grader(), seed)
    env.name, env.instructions = "trip", INSTRUCTIONS
    from .rules import format_problem
    env.format_check = lambda sub: format_problem(env, sub)
    return env

_ENV = None
def grade(task: dict, submission):
    """Shared grader contract (qa harness): grade(task: dict, submission) -> {"score": 0..1, "solved": bool, "rules": {rule_id: bool}}. Never raises."""
    global _ENV
    if _ENV is None:
        _ENV = load_env()
    return _ENV.contract_grade(task, submission)

def get_baselines():
    from .baselines import BASELINES
    return BASELINES
