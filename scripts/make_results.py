#!/usr/bin/env python3
"""Builds docs/RESULTS.md from the saved run files only (nothing typed by hand). usage: python3 scripts/make_results.py [runs_dir] > docs/RESULTS.md
Per model and env the best COMPLETE row is shown: the whole split if it was run, else the stratified sample. Easy and standard are separate tiers. Rows that are incomplete
(still running, or cut short by a daily limit) or where a fifth or more of the tasks hit provider errors are listed under 'not shown', never scored."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runfiles

runs_dir = sys.argv[1] if len(sys.argv) > 1 else None
LARGE = ("sonnet", "opus", "fable", "-pro", "gpt-5", "o3", "o4")
tier = lambda m: "large" if any(x in m.lower() for x in LARGE) else "small"
ERR = 0.2
allrows = list(runfiles.rows(runs_dir=runs_dir))
shown, hidden = {}, []
for r in sorted(allrows, key=lambda r: (r["kind"] == "sample", r["file"])):          # full / easy rows before sample rows
    key = (r["env"], r["tier"], r["model"])
    ok = r["complete"] and r["summary"]["errors"] < ERR
    if not ok:
        hidden.append(r); continue
    shown.setdefault(key, r)                                                          # the first complete row wins (the whole split over a sample)
rows = list(shown.values())
env_label = lambda r: {"form_multidoc": "form multi-document"}.get(r["env"], r["env"]) + (" (easy)" if r["tier"] == "easy" else "")
print("# Baseline results\n")
print("Each row is ONE run (k=1). The task count is in the table: a 15-task sample has a wide error bar (one task is 6.7 points) and a 5-task sample a very wide one. "
      "Easy and standard tasks are separate tiers. Columns: pass@1 = tasks solved by the first run (one format-repair retry is allowed); strict = solved with no repair retry; "
      "format fail = the answer was not a readable, valid-format submission; errors = provider failures (not wrong answers); length cut-off = number of UNSOLVED tasks whose first attempt hit the model's output-token limit before a final answer (the one format-repair retry is allowed, and a task it still solved is not counted; a model with many cut-offs may be under-scored; Sarvam's limit is 32,000 tokens and a reasoning model can spend all of it thinking); partial credit (first run of each task, like pass@1) = mean fraction of scored rules passed "
      "(a well-formed empty answer earns 0). Every row was re-graded without calling any model (scripts/regrade.py); the `graded` column is the id of the grading code.\n")
print("**Degenerate-baseline note (GST).** On the public GST standard set the built-in `careless` baseline (it reads everything but leaves freight untaxed and ignores the turnover-tiered late-fee cap: two built-in slips) scores 80%. The \"every non-oracle baseline solves under 25%\" gate therefore holds only for the private held-out sets (where `careless` scores 23%), not for the public GST set.\n")
print("**Degenerate-baseline note (support).** Since v1.0.1 the reply language is a hard rule on all 76 support tasks (Tamil and Bengali by script, Marathi also by two Marathi marker words; Hindi and Hinglish as before). In v1.0.0 it was hard only for the 50-task Hindi and Hinglish core and the 26 Tamil, Bengali and Marathi tasks were solved on state alone, so the built-in `english` baseline (right actions, English reply) solved 33% of the full split; it now solves 0%. The built-in `noop_lang` floor (reads nothing, no action, one fixed sentence in the right language) solves 5% of the 76 tasks. Every non-oracle scripted baseline is under 25% on the core, the experimental tasks and the full split. Rows graded under v1.0.0 were re-graded by replay at the v1.0.1 grader, so every support row follows the hard rule. For Hindi, Marathi, Bengali and Tamil at least 70% of the reply's letters must be in the customer's script, so a reply in the right language that is heavily mixed with English words fails by design (the same threshold has applied to the Hindi core since v1.0.0). The check is a heuristic and is not a native-speaker review.\n")
print("**Note on the Sarvam final answer (json_object).** The run settings of every row say `json_mode_on_final: true`. For Sarvam this was not applied on the final call: Sarvam rejects a tool-free call once the history holds tool messages, so the harness re-sends the tools with `tool_choice: none` and drops `response_format`. In a later test of that combination (tools + `tool_choice: none` + `response_format: json_object`, tool-message history) Sarvam accepted the call (HTTP 200) but returned empty content in 3 of 3 calls, while 2 of 2 calls without `response_format` returned valid JSON. We did not change the harness for this: the Sarvam rows were run as described here, and the cut-off column above counts the tasks the output limit ended.\n")
print("**Note on est. USD.** The estimate is only computed for Anthropic and OpenAI, whose per-token prices are in our price table. Gemini and Groq runs used free tiers (0.00). Sarvam's price is not in our price table, so the 0.00 on Sarvam rows means *not estimated*, not that the run was free. The Claude Sonnet 5.5 form and GST rows were first priced at the lower Haiku-level default; their est. USD was multiplied by 2.5 (the Sonnet-to-default price ratio, the same for input and output tokens) to the Sonnet rate.\n")
print(f"**Verify it.** The grading code is identified by the git tree id of `navital_gym/` at the release tag {os.environ.get('RELEASE_TAG', 'v1.0.1')}. "
      f"Check with `git rev-parse {os.environ.get('RELEASE_TAG', 'v1.0.1')}:navital_gym`: it must start with the id in the `graded` column.\n")
for which, title, note in (("small", "Small and mid-size models", "Most people testing will use models like these, so they come first. Many score low."),
                           ("large", "Larger model, for reference (Claude Sonnet 5.5)", "What a strong model reaches. Not the typical user's model.")):
    sel = sorted((r for r in rows if tier(r["model"]) == which), key=lambda r: (r["tier"] != "standard", r["env"], r["model"]))
    if not sel: continue
    print(f"## {title}\n\n{note}\n")
    print("| env | model (provider) | tasks | pass@1 | strict | format fail | errors | length cut-off | partial credit | est. USD | date | graded |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sel:
        s = r["summary"]
        print(f"| {env_label(r)} | {r['model']} ({r['provider']}) | {s.get('answered', s['tasks'])} | {runfiles.r2(s['pass@1'])} | {runfiles.r2(s['strict_pass@1'])} | {s['format_fail']:.0%} | {s['errors']:.0%} | {runfiles.truncated_tasks(r['tasks'])} | {runfiles.r2(runfiles.first_run_partial(r['tasks'], s) if s['k'] > 1 else s['mean_score'])} | {r['usd']:.2f} | {r['date']} | {r['graded']} |")
    print()
# do the designers' difficulty labels predict who solves what?
buckets = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
for r in rows:
    if tier(r["model"]) != "small": continue
    tasks = runfiles.env_tasks(r["env"], easy=(r["tier"] == "easy"))
    for tid, res in r["tasks"].items():
        t = tasks.get(tid)
        if t:
            b = "difficulty 1-2" if t.difficulty <= 2 else "difficulty 3" if t.difficulty == 3 else "difficulty 4-5"
            buckets[r["model"]][b][1] += 1; buckets[r["model"]][b][0] += int(res[0]["solved"])
if buckets:
    print("## Do the difficulty labels separate small and mid-size models?\n")
    print("Tasks solved / tried by the designers' difficulty label (designer intent, not calibrated; all shown rows together). If the columns are close the labels do not predict who solves what.\n")
    print("| model | difficulty 1-2 | difficulty 3 | difficulty 4-5 |\n|---|---|---|---|")
    for m in sorted(buckets):
        print(f"| {m} | " + " | ".join(f"{buckets[m][b][0]}/{buckets[m][b][1]}" for b in ("difficulty 1-2", "difficulty 3", "difficulty 4-5")) + " |")
    print()
if hidden:
    print("## Not shown\n")
    print("Runs that are incomplete (still running, or cut short by a daily free-tier limit) or where at least a fifth of the tasks ended in provider errors say nothing yet about the model:\n")
    for r in sorted(hidden, key=lambda r: (r["env"], r["model"])):
        why = "incomplete" if not r["complete"] else f"{r['summary']['errors']:.0%} provider errors"
        print(f"- {env_label(r)} / {r['model']} ({r['provider']}): {why}, {r['n']} of {r['need']} tasks")
    print()
import json as _j
try:
    led = _j.load(open(os.path.join(runs_dir or os.path.join(runfiles.ROOT, "runs"), "spend-ledger.json")))
    print("Spend (conservative per-token prices; free tiers cost nothing): " + ", ".join(f"{k} ${v['usd']:.2f}" for k, v in sorted(led.items()) if v["usd"]) + ".")
except OSError:
    pass
