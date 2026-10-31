"""Builds tasks.jsonl (v1) from the task authors' specs (tasks_source.jsonl, designer intent) by adding the STRUCTURED params the
rules read (the prose prompt stays what the agent sees) and deriving each task's rule list from those params.
`python -m navital_gym.envs.trip.build_tasks` rewrites tasks.jsonl; solver.py then confirms or corrects feasibility.
Prompt edits are listed in PROMPT_APPEND and reported in FLAG_CHANGES.md; nothing else in a prompt is changed."""
import json, os, re, sys
from . import data as D
from ...core.leak import TELLS

HERE = os.path.dirname(os.path.abspath(__file__))
MB_LEH = {"mode": "road", "from": "Manali", "to": "Leh", "dir": 1}

# structured params per task number (merged into params; params never reach the agent)
STRUCT = {
    1: {"day_visit": [{"name": "Taj Mahal", "day": 1}]}, 3: {"rest_days": 1}, 6: {"rest_days": 1}, 7: {"max_travel_hours_per_day": 5},
    8: {"no_stairs": True}, 10: {"no_road_after": "20:00", "route": ["Delhi", "Jaipur", "Udaipur", "Jodhpur"]},
    11: {"no_stairs": True}, 12: {"stay_kind": [{"kind": "houseboat", "city": "Alleppey"}]},
    13: {"must_use": [{"mode": "air", "from": "Mumbai", "to": "Kochi", "dir": 1}, {"mode": "rail", "from": "Kochi", "to": "Mumbai", "dir": 1}]},
    16: {"must_visit": ["Rohtang Pass"]}, 17: {"no_night_road": True}, 20: {"must_use": [MB_LEH], "extra_cities": ["Leh"]},
    24: {"mode_policy": "rail_only"}, 25: {"mode_policy": "rail_only"},
    27: {"rest_days": 1, "daily_in_city": [{"city": "Varanasi", "name": "Ganga Aarti"}]}, 28: {"no_stairs": True},
    30: {"must_visit": ["Kashi Vishwanath darshan"]},
    31: {"must_use": [{"mode": "air", "from": "Delhi", "to": "Leh", "dir": 1}], "must_visit": ["Pangong Lake", "Diskit Monastery and Hunder dunes"]},
    32: {"day_visit": [{"name": "Pangong Lake", "day": 2}], "must_visit": []},
    33: {"must_use": [MB_LEH, {"mode": "air", "from": "Leh", "to": "Delhi", "dir": 1}], "extra_cities": ["Chandigarh", "Manali"]},
    34: {"must_use": [MB_LEH], "extra_cities": ["Manali", "Chandigarh"]}, 35: {"must_visit": ["Pangong Lake"]},
    36: {"must_visit": ["Kaziranga Jeep Safari"]}, 37: {"must_visit": ["Kaziranga Jeep Safari"]},
    38: {"must_visit": ["Kaziranga Jeep Safari", "Kaziranga Elephant Safari"]},
    39: {"route": ["Guwahati", "Shillong"], "must_visit": ["Cherrapunji day trip"]},
    41: {"end": "Jaipur", "snapshot_date": "2026-11-15", "mode_policy": "rail_only"}, 42: {"end": "Jaipur", "snapshot_date": "2026-11-15", "mode_policy": "rail_only"},
    43: {"end": "Pune", "snapshot_date": "2026-12-03", "mode_policy": "rail_only"},
    44: {"end": "Agra", "snapshot_date": "2026-12-05", "classes_only": ["CC"], "rail_dep_before": "12:00", "mode_policy": "rail_only"},
    45: {"end": "Bengaluru", "snapshot_date": "2026-12-10", "mode_policy": "rail_only"},
    46: {"rest_days": 1}, 48: {"mode_policy": "rail_only"}, 49: {"day_visit": [{"name": "Taj Mahal", "day": 1}]},
    50: {"no_stairs": True},
}
# hill/Ladakh tasks whose designer prompt does not say "by train" but whose intent needs it
PROMPT_APPEND = {24: " Travel by train.", 25: " Travel by train.",
                 # v1.1: Nubra is a required city in these tasks (R-ROUTE) but the prompt never said so
                 32: " Include Leh, Nubra and Pangong.", 33: " Include Leh, Nubra and Pangong.", 34: " Include Leh, Nubra and Pangong.", 35: " Include Leh, Nubra and Pangong."}
# v1.1: the grader needs the trip to start at the origin and end back there (params end defaults to origin), so the prompt says so, in the task's language.
RETURN_SENTENCE = {"en": " Start from {o} and be back in {o} on the last day.",
                   "hi": " {o} से शुरू करें और आख़िरी दिन {o} वापस आना है।",
                   "hinglish": " {o} se shuru karo aur aakhri din {o} wapas aana hai."}
HI_CITY = {"Delhi": "दिल्ली", "Kochi": "कोच्चि"}
# 001: a sunrise visit on day 1 is unreachable from Delhi whatever day it is (first train 05:30), which would hide the Friday closure the task is about.
PROMPT_REPLACE = {1: ("Taj visit at sunrise on the first day", "Taj visit on the first day"),
                  27: ("Ganga aarti every evening", "Ganga aarti each evening you are in Varanasi"),      # v1.1: the daily rule is graded for Varanasi nights only
                  31: ("Pangong and Nubra permitted", "include Pangong and Nubra"),                       # v1.1: no Inner Line Permit for Indians since 2021; the fee is the rule now
                  39: ("Guwahati -> Shillong -> Kaziranga", "Guwahati -> Shillong")}                      # v1.1: the prompt named Kaziranga and then excluded it
# Impossible-budget variants. The authors intended 005/009/015/029/040 as R-BUD-infeasible; in this world they are feasible (the cheapest plans cost
# 4,090 / 13,280 / 13,960 / 7,740 / 13,240, see calibrate.py), so those keep their rows and these NEW tasks use about half the cheapest cost.
# solver.verdict() then PROVES each infeasible (the budget lower bound prunes the whole search); the flags are never set by hand.
BUDGET_VARIANTS = {51: (5, 2000), 52: (9, 6500), 53: (15, 7000), 54: (29, 3500), 55: (40, 6500)}

def rules_for(p):
    r = ["R-FMT", "R-DATE", "R-CONN", "R-QUOTA", "R-AVAIL", "R-OPEN", "R-SEASON", "R-OCC", "R-ROUTE"]
    cities = set(p["route"]) | {p["origin"]}
    if p.get("budget_inr"): r.append("R-BUD")
    if p.get("rest_days"): r.append("R-REST")
    if p.get("diet") in ("veg", "jain", "satvik"): r.append("R-DIET")
    if p.get("no_stairs") or (p["travelers"].get("seniors", 0) > 0): r.append("R-ACC")
    if p.get("no_night_road") or p.get("no_road_after") or any(D.CITIES[c][2] for c in cities): r.append("R-NIGHT")
    if p.get("max_travel_hours_per_day"): r.append("R-HRS")
    if "Leh" in cities or "Pangong" in cities: r.append("R-ALT")
    if cities & {"Nubra", "Pangong"}: r.append("R-PERMIT")
    return r

def build(src=None):
    src = src or os.path.join(HERE, "tasks_source.jsonl")
    out = []
    for line in open(src, encoding="utf-8"):
        row = json.loads(line)
        n = int(re.search(r"(\d+)$", row["id"]).group(1))
        p = dict(row["params"])
        p.pop("constraints", None)            # designer hints stay out of everything the agent can reach
        p.update(STRUCT.get(n, {}))
        if p.get("budget_inr") is None: p.pop("budget_inr", None)
        p.setdefault("end", p["origin"])
        p.setdefault("diet", "any")
        prompt = row["prompt"]
        if n in PROMPT_REPLACE:
            assert PROMPT_REPLACE[n][0] in prompt
            prompt = prompt.replace(*PROMPT_REPLACE[n])
        prompt += PROMPT_APPEND.get(n, "")
        if p["end"] == p["origin"] and p.get("route") and p["route"][-1] != p["origin"]:
            o = HI_CITY.get(p["origin"], p["origin"]) if row["lang"] == "hi" else p["origin"]
            if not prompt.rstrip().endswith((".", "।", "!", "?")): prompt = prompt.rstrip() + "."
            prompt += RETURN_SENTENCE[row["lang"]].format(o=o)
        out.append({"id": row["id"], "family": row["family"], "difficulty": row["difficulty"], "lang": row["lang"], "prompt": prompt,
                    "params": p, "rules": rules_for(p), "expected_feasible": row["expected_feasible"],
                    "binding_constraint": row["binding_constraint"], "traps": [t for t in row["traps"] if TELLS.search(t) or t.lower().startswith("designer note")],   # only genuinely hidden hints; prompt asks are not secrets
                    "meta": {"design_notes": [t for t in row["traps"] if t != "none"], "design_intent_feasible": row["expected_feasible"], "design_intent_binding": row["binding_constraint"]}})
    byn = {int(re.search(r"(\d+)$", r["id"]).group(1)): r for r in out}
    for new, (base, budget) in BUDGET_VARIANTS.items():
        if new in byn:
            continue          # the source file already has this variant (same budget): keep their row, the solver still re-proves its flags
        r = json.loads(json.dumps(byn[base]))
        r["id"] = f"IN-TRIP-{new:03d}"
        r["params"]["budget_inr"] = budget
        text = f"Rs {budget:,}"
        r["prompt"], k = re.subn(r"Rs ?\d[\d,]*\d", text, r["prompt"], count=1)
        assert k == 1, r["id"]
        r["rules"] = rules_for(r["params"])
        r["meta"] = {"design_notes": [], "design_intent_feasible": False, "design_intent_binding": ["R-BUD"], "variant_of": byn[base]["id"]}
        r["expected_feasible"], r["binding_constraint"], r["traps"] = False, ["R-BUD"], []
        out.append(r)
    return out

def write(rows, path=None):
    path = path or os.path.join(HERE, "tasks.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

if __name__ == "__main__" and "--solve" not in sys.argv:
    write(build()); print("wrote tasks.jsonl (flags = design intent; run with --solve to confirm them)")


def solve_flags(rows):
    """Confirm or correct every task's feasibility with the reference solver. Returns (rows, changes)."""
    from ...core import Task
    from .solver import verdict
    changes = []
    for r in rows:
        t = Task.from_dict(r)
        v = verdict(t)
        intent, intent_b = r["meta"]["design_intent_feasible"], r["meta"]["design_intent_binding"]
        r["expected_feasible"] = v["feasible"]
        r["binding_constraint"] = v["binding"]
        r["meta"]["binding_sets"] = v["binding_sets"]
        r["meta"]["solver_note"] = v["note"]
        if v["feasible"]:
            r["meta"]["oracle_plan_cost"] = None
        if v["feasible"] != intent or (not v["feasible"] and sorted(v["binding"]) != sorted(intent_b)):
            changes.append((r["id"], intent, intent_b, v["feasible"], v["binding"], v["note"]))
    return rows, changes

if __name__ == "__main__" and "--solve" in sys.argv:
    rows, changes = solve_flags(build())
    write(rows)
    with open(os.path.join(HERE, "FLAG_CHANGES.md"), "w") as f:
        f.write("# Env #1: where the reference solver disagreed with the design intent in the task authors' specs\n\n"
                "expected_feasible / binding are set by solver.py (exhaustive search of the plan space + rule relaxation), not by hand. "
                "the authors' original flags are kept in each task's meta (design_intent_*).\n\n| task | intent | solver | why |\n|---|---|---|---|\n")
        for tid, i, ib, fe, b, note in changes:
            f.write(f"| {tid} | {'feasible' if i else 'infeasible ' + ','.join(ib)} | {'feasible' if fe else 'infeasible ' + ','.join(b)} | {note} |\n")
    print("wrote tasks.jsonl and FLAG_CHANGES.md;", len(changes), "differ from design intent")
