#!/usr/bin/env python3
"""Fill the Results section of README.md (between the RESULTS markers) and write docs/RESULTS.md, both from the saved run files only.
Standard and easy tiers are separate column groups; small and mid-size models first, the larger model as a labelled reference; incomplete or error-heavy rows never appear.
usage: python3 scripts/update_readme_results.py     (run scripts/regrade.py on the run files first so every row is graded by one commit)"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runfiles
root = runfiles.ROOT
LARGE = ("sonnet", "opus", "fable", "-pro")
ERR = 0.2
cell = {}
for r in sorted(runfiles.rows(), key=lambda r: (r["kind"] == "sample", r["file"])):      # the whole split before a sample
    if not r["complete"] or r["summary"]["errors"] >= ERR:
        continue
    key = r["env"] + (" easy" if r["tier"] == "easy" else "")
    cell.setdefault(r["model"], {}).setdefault(key, (r["summary"]["pass@1"], r["n"], runfiles.first_run_partial(r["tasks"], r["summary"]) if r["summary"]["k"] > 1 else r["summary"]["mean_score"]))
std = [e for e in ["trip", "form", "form_multidoc", "gst", "support", "upi"] if any(e in c for c in cell.values())]
easy = [e + " easy" for e in ["trip", "gst", "support", "upi"] if any(e + " easy" in c for c in cell.values())]
cols = std + easy
LABEL = {"form_multidoc": "form multi-document"}
def table(models, title, partial=False):
    if not models:
        return ""
    out = [f"**{title}**\n", "| model | " + " | ".join(LABEL.get(c, c) for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for m in models:
        out.append(f"| {m} | " + " | ".join((f"{runfiles.r2(cell[m][c][2])}" if partial else f"{runfiles.r2(cell[m][c][0])} (n={cell[m][c][1]})") if c in cell[m] else "-" for c in cols) + " |")
    return "\n".join(out) + "\n"
small = sorted(m for m in cell if not any(x in m.lower() for x in LARGE))
large = sorted(m for m in cell if any(x in m.lower() for x in LARGE))
block = ("Pass@1 on deterministic stratified samples or whole splits (k=1, one run per cell; n = tasks, so one task is 1/n of the cell: read small-n cells as indicative). "
         "'easy' columns are the easy tier (designed so a 7B-30B model can sometimes solve them); the others are the standard tasks. "
         "Full tables with format failures, strict (no-repair) pass@1, partial credit, spend, dates and commits: [`docs/RESULTS.md`](https://github.com/Navitallabs/navital-gym/blob/main/docs/RESULTS.md). "
         "Every row was re-graded by the same grading code (`scripts/regrade.py`); check it with `git rev-parse v1.0.1:navital_gym` (see `docs/RESULTS.md`).\n\n"
         + table(small, "Small and mid-size models: pass@1 (the typical user's models)") + "\n"
         + table(small, "Small and mid-size models: partial credit (mean fraction of scored rules passed; shows progress where pass@1 is near zero)", partial=True) + "\n"
         + table(large, "Larger models, for reference (what strong models reach)")
         + "\nMost of the models people will test are small or mid-size, so they come first. Many score low: that is the point of a hard benchmark, but a cell near zero says little, so read partial credit next to it. "
         "Samples are small and the small and mid-size models above are not the strongest agents available; these results show that the environments separate models, not a leaderboard. "
         "Task difficulty labels are designer intent, not calibrated.")
readme = os.path.join(root, "README.md")
text = open(readme).read()
new = re.sub(r"<!-- RESULTS:START -->.*<!-- RESULTS:END -->", lambda m: "<!-- RESULTS:START -->\n" + block + "\n<!-- RESULTS:END -->", text, flags=re.S)
if new == text and "<!-- RESULTS:START -->" not in text:
    sys.exit("README has no RESULTS markers")
open(readme, "w").write(new)
open(os.path.join(root, "docs", "RESULTS.md"), "w").write(subprocess.check_output([sys.executable, os.path.join(root, "scripts", "make_results.py")], text=True))
print("README and docs/RESULTS.md updated")
