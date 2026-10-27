"""Trip 'easy' split (meta.split = "easy"): tasks a 7B-30B model can sometimes solve: one city or one leg, one or two rules at a time, a generous budget, a clear
quota window. Same world, same graders, same anti-cheat gates as the standard tasks. Feasibility and binding rules are set by the reference solver (solver.verdict), never by hand.
`python -m navital_gym.envs.trip.build_easy` rewrites tasks_easy.jsonl."""
import json, os
from ...core import Task
from .build_tasks import rules_for
from .solver import verdict

HERE = os.path.dirname(os.path.abspath(__file__))

def T(n, family, prompt, origin, dest, start, days, adults=2, budget=None, end=None, **extra):
    p = {"origin": origin, "route": [origin, dest], "start": start, "days": days, "travelers": {"adults": adults, "child_ages": [], "seniors": 0}, "diet": "any", "end": end or origin}
    if budget is not None:
        p["budget_inr"] = budget
    p.update(extra)
    return {"id": f"IN-TRIP-E{n:02d}", "family": family, "difficulty": 1, "lang": "en", "prompt": prompt, "params": p, "rules": rules_for(p),
            "expected_feasible": True, "binding_constraint": [], "traps": [], "meta": {"split": "easy"}}

def tasks():
    rail = {"mode_policy": "rail_only"}
    return [
        T(1, "easy-rail-booking", "Book a train from Delhi to Agra on 2026-12-02 for 2 adults.", "Delhi", "Agra", "2026-12-02", 1, 2, end="Agra", **rail),
        T(2, "easy-rail-booking", "Book a train from Delhi to Jaipur on 2026-12-09 for 1 adult.", "Delhi", "Jaipur", "2026-12-09", 1, 1, end="Jaipur", **rail),
        T(3, "easy-rail-booking", "Book a train from Mumbai to Pune on 2026-12-01 for 3 adults.", "Mumbai", "Pune", "2026-12-01", 1, 3, end="Pune", **rail),
        T(4, "easy-rail-booking", "Book a train from Chennai to Bengaluru on 2026-12-03 for 2 adults.", "Chennai", "Bengaluru", "2026-12-03", 1, 2, end="Bengaluru", **rail),
        T(5, "easy-rail-booking", "Book a train from Lucknow to Varanasi on 2026-12-07 for 2 adults.", "Lucknow", "Varanasi", "2026-12-07", 1, 2, end="Varanasi", **rail),
        T(6, "easy-rail-booking", "Book a train from Jaipur to Agra on 2026-12-10 for 2 adults.", "Jaipur", "Agra", "2026-12-10", 1, 2, end="Agra", **rail),
        T(7, "easy-rail-booking", "Book a train from Delhi to Agra on 2027-01-25 for 2 adults.", "Delhi", "Agra", "2027-01-25", 1, 2, end="Agra", **rail),
        T(8, "easy-rail-booking", "Book a train from Mumbai to Pune on 2027-02-01 for 1 adult.", "Mumbai", "Pune", "2027-02-01", 1, 1, end="Pune", **rail),
        T(9, "easy-day-trip", "Plan a one-day trip from Delhi to Agra on 2026-12-05 for 2 adults. Visit the Taj Mahal. Budget Rs 9,000.", "Delhi", "Agra", "2026-12-05", 1, 2, 9000, must_visit=["Taj Mahal"]),
        T(10, "easy-day-trip", "Plan a one-day trip from Delhi to Agra on 2026-12-13 for 2 adults. Visit the Taj Mahal. Budget Rs 9,000.", "Delhi", "Agra", "2026-12-13", 1, 2, 9000, must_visit=["Taj Mahal"]),
        T(11, "easy-day-trip", "Plan a one-day trip from Delhi to Jaipur on 2026-12-06 for 2 adults. Visit Hawa Mahal. Budget Rs 8,000.", "Delhi", "Jaipur", "2026-12-06", 1, 2, 8000, must_visit=["Hawa Mahal"]),
        T(12, "easy-day-trip", "Plan a one-day trip from Delhi to Agra on 2026-12-11 for 2 adults. Visit the Taj Mahal. Budget Rs 9,000.", "Delhi", "Agra", "2026-12-11", 1, 2, 9000, must_visit=["Taj Mahal"]),
        T(13, "easy-two-days", "Plan 2 days in Jaipur from Delhi, starting 2026-12-14, for 2 adults. Budget Rs 14,000.", "Delhi", "Jaipur", "2026-12-14", 2, 2, 14000),
        T(14, "easy-two-days", "Plan 2 days in Pune from Mumbai, starting 2026-12-08, for 2 adults. Budget Rs 12,000.", "Mumbai", "Pune", "2026-12-08", 2, 2, 12000),
        T(15, "easy-two-days", "Plan 2 days in Alleppey from Kochi, starting 2026-12-16, for 2 adults. Budget Rs 12,000.", "Kochi", "Alleppey", "2026-12-16", 2, 2, 12000),
        T(16, "easy-two-days", "Plan 3 days in Jaipur from Delhi, starting 2026-12-18, for 2 adults, vegetarian food. Budget Rs 18,000.", "Delhi", "Jaipur", "2026-12-18", 3, 2, 18000, diet="veg"),
        T(17, "easy-two-days", "Plan 2 days in Shimla from Chandigarh, starting 2026-12-04, for 2 adults, no road travel at night. Budget Rs 12,000.", "Chandigarh", "Shimla", "2026-12-04", 2, 2, 12000, no_night_road=True),
        T(18, "easy-two-days", "Plan 2 days in Jaipur from Delhi, starting 2026-12-14, for 2 adults. Budget Rs 1,500.", "Delhi", "Jaipur", "2026-12-14", 2, 2, 1500),
    ]

def build():
    rows = []
    for r in tasks():
        v = verdict(Task.from_dict(r))
        r["expected_feasible"], r["binding_constraint"] = v["feasible"], v["binding"]
        r["meta"].update(binding_sets=v["binding_sets"], solver_note=v["note"])
        rows.append(r)
    return rows

if __name__ == "__main__":
    rows = build()
    with open(os.path.join(HERE, "tasks_easy.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    for r in rows:
        print(r["id"], "FEAS" if r["expected_feasible"] else "INFEAS " + ",".join(r["binding_constraint"]), "|", r["prompt"][:70])
