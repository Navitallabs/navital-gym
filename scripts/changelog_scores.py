#!/usr/bin/env python3
"""Markdown for the v1.1 CHANGELOG, computed from two leaderboard exports (nothing typed by hand).
usage: python3 scripts/changelog_scores.py BEFORE.json AFTER.json
BEFORE = the last published export before v1.1 (the 30 Oct results update, graded at ed78addcd557; it holds the Claude Opus 5.5 rows), AFTER = the v1.1 export (graded at the final id).
Prints (1) the before -> after table for the full standard set of every model that has a v1.1 row (passes / tasks; "x -> not re-run" when a v1.0.1 cell has no v1.1 cell; an env whose
'all' split is incomplete but whose core split is complete shows the core cell), (2) how each cell was produced, (3) the not-re-run list: every BEFORE row, by model, env and set, with
no AFTER row of the same model, env and set (a sample is covered only by an AFTER full row of that model and env; easy-tier rows are never covered)."""
import sys
import json
ENVS = [("trip", "Trip"), ("upi", "UPI"), ("gst", "GST"), ("support", "Support"), ("form", "Form"), ("form_multidoc", "Form multidoc")]
HOW = {"trip": "re-run", "upi": "re-run", "support": "re-run", "form": "re-run", "gst": "6 tasks re-run, 44 regraded", "form_multidoc": "regraded"}
NAMES = {"claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-haiku-4-5": "Claude Haiku 4.5", "sarvam-105b": "Sarvam 105B",
         "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "gpt-4o-mini": "GPT-4o mini", "openai/gpt-oss-120b": "gpt-oss 120B", "openai/gpt-oss-20b": "gpt-oss 20B"}
def cell(e): n = e["n"]; return f"{round(e['pass_at_1'] * n)}/{n}"
def build(bp, ap):
    B = json.load(open(bp))["entries"]; A = json.load(open(ap))["entries"]
    def full(es, split_ok):
        return {(e["model"], e["env"]): e for e in es if e["sample"] == "full" and e["split"] in split_ok and e["env"] in dict(ENVS)}
    before = full(B, ("all",)); after = full(A, ("all",))
    for e in A:                                     # an env whose 'all' split is partial but whose core split is complete (Gemini support, decided by lead)
        if e["sample"] == "full" and e["split"] == "core" and (e["model"], e["env"]) not in after and e["env"] == "support": after[(e["model"], e["env"])] = e
    pts = lambda e: round(e["pass_at_1"] * e["n"])
    models = sorted({m for m, _ in after}, key=lambda m: -sum(pts(after[(m, k)]) for k, _ in ENVS if (m, k) in after))
    out = ["| model | " + " | ".join(l for _, l in ENVS) + " | all six |", "|---|" + "---|" * (len(ENVS) + 1)]
    for m in models:
        cells, tb, ta, partial = [], 0, 0, False
        for env, _ in ENVS:
            a, b = after.get((m, env)), before.get((m, env))
            if a is None:
                cells.append(f"{cell(b)} -> not re-run" if b else "not re-run"); partial = True; continue
            ta += pts(a)
            if b is None: cells.append(f"n/a -> {cell(a)}" + (" (core only; experimental not run, free-tier quota)" if a["split"] == "core" else "")); partial = True; continue
            tb += pts(b); cells.append(f"{cell(b)} -> {cell(a)}")
        out.append(f"| {NAMES.get(m, m)} | " + " | ".join(cells) + f" | {'-' if partial else f'{tb}/321 -> {ta}/321'} |")
    out.append("\nHow each v1.1 cell was produced: " + "; ".join(f"{lbl}: {HOW[env]}" for env, lbl in ENVS) + ".")
    out.append("\nNot re-run for v1.1 (every v1.0.1 row, by model, env and set, with no v1.1 row of the same model, env and set; a sample is covered only by a v1.1 full run of that model and env; v1.0.1 results, from the v1.0.1 grader, passes / tasks):\n")
    out += ["| model | env | set | pass / tasks |", "|---|---|---|---|"]
    order = {k: i for i, (k, _) in enumerate(ENVS)}; seen = set(); rows = []
    for e in B:
        if e["split"] not in ("all", "", "easy"): continue
        if e["sample"] == "easy": covered = False                                  # no v1.1 easy-tier runs
        else: covered = (e["model"], e["env"]) in full(A, ("all", "core"))          # full row or a sample under a full v1.1 run
        if covered: continue
        k = (e["model"], e["env"], e["sample"])
        if k in seen: continue
        seen.add(k); rows.append(e)
    for e in sorted(rows, key=lambda e: (NAMES.get(e["model"], e["model"]), order.get(e["env"], 9), e["sample"])):
        label = dict(ENVS).get(e["env"], e["env"]); st = "full set" if e["sample"] == "full" else ("easy tier" if e["sample"] == "easy" else e["sample"].replace("stratified-", "sample of "))
        out.append(f"| {NAMES.get(e['model'], e['model'])} | {label} | {st} | {cell(e)} |")
    return "\n".join(out) + "\n"

if __name__ == "__main__":
    sys.stdout.write(build(sys.argv[1], sys.argv[2]))
