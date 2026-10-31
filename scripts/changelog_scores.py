#!/usr/bin/env python3
"""Markdown for the v1.1 CHANGELOG, computed from two leaderboard exports (nothing typed by hand).
usage: python3 scripts/changelog_scores.py BEFORE.json[,BEFORE2.json] AFTER.json
BEFORE = the v1.0.1 export(s) (graded at ed78addcd557), AFTER = the v1.1 export (graded at the final id). Prints: the before -> after table for the full standard set of every
model that has a v1.1 row (passes / tasks, with how each cell was produced), and the list of v1.0.1 rows with no v1.1 row ('not re-run')."""
import json, sys

ENVS = [("trip", "Trip"), ("upi", "UPI"), ("gst", "GST"), ("support", "Support"), ("form", "Form"), ("form_multidoc", "Form multidoc")]
HOW = {"trip": "re-run", "upi": "re-run", "support": "re-run", "form": "re-run", "gst": "6 tasks re-run, 44 regraded", "form_multidoc": "regraded"}
NAMES = {"claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-haiku-4-5": "Claude Haiku 4.5", "sarvam-105b": "Sarvam 105B",
         "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "gpt-4o-mini": "GPT-4o mini", "openai/gpt-oss-120b": "gpt-oss 120B", "openai/gpt-oss-20b": "gpt-oss 20B"}

def load(paths):
    rows = {}
    for p in paths.split(","):
        for e in json.load(open(p))["entries"]:
            if e["sample"] == "full" and e["split"] == "all" and e["env"] in dict(ENVS):
                rows[(e["model"], e["env"])] = e
    return rows

def cell(e):
    n = e["n"]; return f"{round(e['pass_at_1'] * n)}/{n}"

before, after = load(sys.argv[1]), load(sys.argv[2])
models_after = sorted({m for m, _ in after}, key=lambda m: -sum(after[(m, e)]["pass_at_1"] * after[(m, e)]["n"] for _, e in [(m, k) for k, _ in ENVS] if (m, e) in after))
print("| model | " + " | ".join(f"{label}" for _, label in ENVS) + " | all six |")
print("|---|" + "---|" * (len(ENVS) + 1))
for m in models_after:
    cells, tb, ta, nb, na, partial = [], 0, 0, 0, 0, False
    for env, _ in ENVS:
        a, b = after.get((m, env)), before.get((m, env))
        if a is None:
            cells.append("not re-run"); partial = True; continue
        pa = round(a["pass_at_1"] * a["n"]); ta += pa; na += a["n"]
        if b is None: cells.append(f"n/a -> {cell(a)}"); partial = True; continue
        pb = round(b["pass_at_1"] * b["n"]); tb += pb; nb += b["n"]
        cells.append(f"{cell(b)} -> {cell(a)}")
    total = f"{tb}/{nb} -> {ta}/{na}" if not partial else "-"
    print(f"| {NAMES.get(m, m)} | " + " | ".join(cells) + f" | {total} |")
print("\nHow each v1.1 cell was produced: " + "; ".join(f"{lbl}: {HOW[env]}" for env, lbl in ENVS) + ".")
print("\nNot re-run for v1.1 (every v1.0.1 row of a model with no v1.1 row; v1.0.1 results, from the v1.0.1 grader, passes / tasks):\n")
allb = []
for pth in sys.argv[1].split(","):
    allb += json.load(open(pth))["entries"]
have = {e["model"] for e in json.load(open(sys.argv[2]))["entries"] if e["sample"] == "full" and e["split"] == "all"}
seen = set(); rows = []
for e in allb:
    if e["model"] in have or e["split"] not in ("all", "") : continue
    k = (e["model"], e["env"], e["sample"])
    if k in seen: continue
    seen.add(k); rows.append(e)
print("| model | env | set | pass / tasks |"); print("|---|---|---|---|")
order = {k: i for i, (k, _) in enumerate(ENVS)}
for e in sorted(rows, key=lambda e: (NAMES.get(e["model"], e["model"]), order.get(e["env"], 9), e["sample"])):
    label = dict(ENVS).get(e["env"], e["env"]); st = "full set" if e["sample"] == "full" else ("easy tier" if e["sample"] == "easy" else e["sample"].replace("stratified-", "sample of "))
    print(f"| {NAMES.get(e['model'], e['model'])} | {label} | {st} | {round(e['pass_at_1'] * e['n'])}/{e['n']} |")
