#!/usr/bin/env python3
"""Launch charts built ONLY from the saved run files (runs/*-s<N>.json and their transcripts). Nothing is typed by hand.
Writes docs/figures/: baseline_pass1.(svg|png), gap_strongest_vs_cheaper.(svg|png), failed_rules.(svg|png), figures.alt.json (alt text with the real numbers),
failures.md (6 real failure excerpts for 'failure cards'; public prompt, trimmed final answer, rule id; never hidden fields).
Needs matplotlib (dev-only): .venv/bin/python scripts/make_charts.py [--runs DIR] [--out DIR] [--commit SHA] [--require-single-commit]
Regenerate whenever run files change (after scripts/regrade.py). Only run files graded by ONE commit are drawn: --commit SHA, else the most common graded_with; files graded
elsewhere (or never regraded) are skipped and listed on stderr. Incomplete runs (fewer tasks than their sample size) are skipped. A complete full-set run replaces the
sample run of the same model and environment (n on every bar says which). --require-single-commit exits 2 if anything had to be skipped for its commit."""
import glob, importlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from navital_gym.core import leak
def _opt(name, default=None, flag=False):
    if name in sys.argv:
        i = sys.argv.index(name); sys.argv.pop(i)
        return True if flag else sys.argv.pop(i)
    return default
RUNS = _opt("--runs", os.path.join(ROOT, "runs")); OUT = _opt("--out", os.path.join(ROOT, "docs", "figures"))
ONLY_COMMIT = _opt("--commit"); REQUIRE_ONE = _opt("--require-single-commit", flag=True)
os.makedirs(OUT, exist_ok=True)
ENVS = ["trip", "form", "form_multidoc", "gst", "support", "upi"]
ENV_LABEL = {"trip": "Trip planning", "form": "Form Desk", "form_multidoc": "Form Desk: multi-document", "gst": "GST Desk", "support": "Bhasha Support", "upi": "UPI Desk"}
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#7F7F7F"]     # Okabe-Ito, colour-blind safe
LARGE = ("sonnet", "opus", "fable", "-pro")
BG, FG, GRID = "white", "#1a1a1a", "#d0d0d0"      # drawn on an opaque white card so contrast holds on light and dark pages
plt.rcParams.update({"svg.fonttype": "none", "font.family": "DejaVu Sans", "axes.edgecolor": FG, "text.color": FG, "axes.labelcolor": FG, "xtick.color": FG, "ytick.color": FG})

SKIPPED = []

def load():
    cands = []
    paths = sorted(p for p in glob.glob(os.path.join(RUNS, "*.json")) if not p.endswith((".transcripts.json", "spend-ledger.json")) and "scripted" not in p and "smoke" not in p and "-s" in os.path.basename(p) or p.endswith("-full.json"))
    for path in paths:
        name = os.path.basename(path)[:-5]
        sample = "full" if name.endswith("-full") else name.rsplit("-s", 1)[1] if name.rsplit("-s", 1)[-1].isdigit() else None
        if sample is None:
            continue
        env = name.split("-")[0]
        tpath = path.replace(".json", ".transcripts.json")
        tr = json.load(open(tpath)) if os.path.exists(tpath) else {}
        for agent, d in json.load(open(path)).items():
            summ = d["summary"]
            if d.get("partial") or summ["errors"] >= 0.5:
                continue
            if sample == "full":                     # a full-set row must hold every task of the standard split (a run cut short by a quota is not a bar)
                import runfiles
                need = len(runfiles.env_tasks(env))
                if summ["tasks"] < need:
                    SKIPPED.append((os.path.basename(path), f"incomplete: {summ['tasks']} of {need} tasks")); continue
            if sample != "full" and summ.get("answered", summ["tasks"]) < int(sample):
                SKIPPED.append((os.path.basename(path), f"incomplete: {summ['tasks']} of {sample} tasks")); continue
            cands.append({"env": env, "agent": agent, "model": d.get("settings", {}).get("model", agent), "summary": summ, "tasks": d["tasks"], "sample": sample, "file": os.path.basename(path),
                          "transcripts": tr.get(agent, {}), "commit": d.get("graded_with"), "run_commit": d.get("navital_gym_commit")})
    import collections
    modal = collections.Counter(c["commit"] for c in cands if c["commit"]).most_common(1)
    want = ONLY_COMMIT or (modal[0][0] if modal else None)
    runs = []
    for c in cands:
        if c["commit"] != want:
            SKIPPED.append((c["file"], f"graded at {c['commit'] or 'no recorded commit'}, not {want}")); continue
        runs.append(c)
    # one run per (env, model): a complete full-set run beats a sample; otherwise the larger sample
    best = {}
    for r in runs:
        k = (r["env"], r["model"]); cur = best.get(k)
        if cur is None or r["summary"]["tasks"] > cur["summary"]["tasks"]:
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["env"], r["model"]))

def is_large(model):
    return any(x in model.lower() for x in LARGE)

def model_colors(runs):
    """One colour per model, the same in every figure."""
    models = sorted({r["model"] for r in runs}, key=lambda m: (is_large(m), m))
    return {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(models)}

def short(model):
    return model.split("/")[-1]

def save(fig, name):
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), facecolor=BG, bbox_inches="tight", dpi=200)
    plt.close(fig)

def fig_headline(runs, alt):
    models = sorted({r["model"] for r in runs}, key=lambda m: (is_large(m), m))
    color = model_colors(runs)
    cell = {(r["env"], r["model"]): r for r in runs}
    fig, ax = plt.subplots(figsize=(13, 5.6), facecolor=BG)
    w = 0.8 / max(1, len(models))
    dense = len(models) > 4
    for j, m in enumerate(models):
        for i, e in enumerate(ENVS):
            r = cell.get((e, m))
            if not r:
                continue
            v, n = r["summary"]["pass@1"] * 100, r["summary"]["tasks"]
            ax.bar(i - 0.4 + w * (j + 0.5), v, w * 0.92, color=color[m], hatch="//" if n < 10 else None, edgecolor=FG if n < 10 else color[m], linewidth=0.8)
            ax.text(i - 0.4 + w * (j + 0.5), v + 1.5, f"{v:.0f}%\nn={n}", ha="center", va="bottom", fontsize=6.5 if dense else 7.5, rotation=90 if dense else 0)
    ax.set_xticks(range(len(ENVS))); ax.set_xticklabels([ENV_LABEL[e] for e in ENVS])
    ax.set_ylim(0, 118); ax.set_yticks(range(0, 101, 20)); ax.set_ylabel("pass@1 (tasks solved by the first run)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter()); ax.grid(axis="y", color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    handles = [Patch(facecolor=color[m], label=short(m) + ("  (larger model)" if is_large(m) else "")) for m in models]
    handles.append(Patch(facecolor="white", edgecolor=FG, hatch="//", label="hatched = fewer than 10 tasks: indicative only"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False, fontsize=8.5)
    ax.set_title("Navital Gym: pass@1 by environment, one run per model (n on each bar)", fontsize=11, loc="left")
    fig.text(0.01, -0.07, "n = tasks run, k=1, graded by one grader commit. A bar with n equal to the environment's task count is the full set; the others are stratified samples, so bars with different n are not on the same tasks. No error bars: with n=15 one task is 6.7 points. Source: runs/*.json.", fontsize=7, color="#555")
    save(fig, "baseline_pass1")
    parts = []
    for e in ENVS:
        bits = [f"{short(m)} {cell[(e, m)]['summary']['pass@1'] * 100:.0f}% (n={cell[(e, m)]['summary']['tasks']})" for m in models if (e, m) in cell]
        if bits: parts.append(f"{ENV_LABEL[e]}: " + ", ".join(bits))
    alt["baseline_pass1"] = "Grouped bar chart of pass@1 per environment for each model. Hatched bars have fewer than 10 tasks. " + "; ".join(parts) + "."

def fig_gap(runs, alt):
    big = [r for r in runs if is_large(r["model"])]
    small = [r for r in runs if not is_large(r["model"])]
    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=BG)
    models = sorted({r["model"] for r in small})
    color = model_colors(runs)
    rows_alt, ys = [], []
    for k, e in enumerate(ENVS):
        b = next((r for r in big if r["env"] == e), None)
        if not b:
            continue
        ids = set(b["tasks"])
        bs = sum(1 for t in ids if b["tasks"][t][0]["solved"]) / len(ids)
        y = len(ENVS) - k
        pts = []
        for m in models:
            r = next((x for x in small if x["env"] == e and x["model"] == m), None)
            if r and ids <= set(r["tasks"]):
                v = sum(1 for t in ids if r["tasks"][t][0]["solved"]) / len(ids)
                pts.append((m, v))
                ax.plot([v * 100, bs * 100], [y, y], color="#999", linewidth=1.2, zorder=1)
                ax.scatter([v * 100], [y], s=70, color=color[m], zorder=3, edgecolor=FG, linewidth=0.6)
        ax.scatter([bs * 100], [y], s=150, marker="D", color="#000000", zorder=4)
        ax.text(102, y, f"n={len(ids)}", va="center", fontsize=8)
        rows_alt.append(f"{ENV_LABEL[e]} (same {len(ids)} tasks): {short(b['model'])} {bs * 100:.0f}%, " + ", ".join(f"{short(m)} {v * 100:.0f}%" for m, v in pts))
        ys.append((y, ENV_LABEL[e]))
    ax.set_yticks([y for y, _ in ys]); ax.set_yticklabels([l for _, l in ys])
    ax.set_xlim(-3, 110); ax.set_ylim(0.4, len(ENVS) + 0.6); ax.set_xlabel("pass@1 on the same tasks")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter()); ax.grid(axis="x", color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    handles = [plt.Line2D([], [], marker="D", color="#000", linestyle="", markersize=9, label=short(big[0]["model"]) + " (larger model)")] + \
              [plt.Line2D([], [], marker="o", color=color[m], linestyle="", markersize=8, markeredgecolor=FG, label=short(m)) for m in models]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False, fontsize=8.5)
    ax.set_title("Larger model vs cheaper models, scored on the same tasks", fontsize=11, loc="left")
    save(fig, "gap_strongest_vs_cheaper")
    alt["gap_strongest_vs_cheaper"] = "Dot plot, one row per environment: the larger model (diamond) against each cheaper model (circles) on the same tasks. " + "; ".join(rows_alt) + "."

def fig_rules(runs, alt):
    fig, axes = plt.subplots(1, len(ENVS), figsize=(16, 4.2), facecolor=BG)
    alt_parts = []
    for ax, e in zip(axes, ENVS):
        rs = [r for r in runs if r["env"] == e]
        n_runs = sum(r["summary"]["tasks"] * max(1, r["summary"]["k"]) for r in rs) or 1
        counts = {}
        for r in rs:
            for rule, c in r["summary"]["rule_failures"].items():
                counts[rule] = counts.get(rule, 0) + c
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6][::-1]
        ax.barh([k for k, _ in top], [v / n_runs * 100 for _, v in top], color="#D55E00")
        for i, (k, v) in enumerate(top):
            ax.text(v / n_runs * 100 + 0.8, i, f"{v}", va="center", fontsize=7.5)
        ax.set_xlim(0, 100); ax.set_title(f"{ENV_LABEL[e]}\n(n={n_runs} runs)", fontsize=9)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter()); ax.grid(axis="x", color=GRID, linewidth=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8)
        alt_parts.append(f"{ENV_LABEL[e]}: " + ", ".join(f"{k} {v}" for k, v in top[::-1]))
    fig.suptitle("Rules broken most often: share of runs (all models) in which each rule failed", fontsize=11, x=0.01, y=1.06, ha="left")
    fig.text(0.01, -0.03, "A run can fail several rules; the label is the number of failing runs. Only rules that applied to a task count as failures. Source: runs/*.json.", fontsize=7, color="#555")
    save(fig, "failed_rules")
    alt["failed_rules"] = "Five small horizontal bar charts, one per environment, of the rules most often broken (number of failing runs): " + "; ".join(alt_parts) + "."

def failure_examples(runs, k=6):
    """Real excerpts: one failing run per distinct (env, rule), feasible tasks only, cheaper models first. Public prompt + trimmed final answer + rule id and its generic description."""
    out, seen = [], set()
    envs = {e: importlib.import_module(f"navital_gym.envs.{e}").load_env() for e in ENVS}
    for r in sorted(runs, key=lambda r: (is_large(r["model"]), r["env"], r["model"])):
        env = envs[r["env"]]
        for tid, rs in sorted(r["tasks"].items()):
            x = rs[0]
            t = env.tasks.get(tid)
            failed = [k_ for k_, v in x["rules"].items() if not v]
            if x["solved"] or not failed or t is None or not t.expected_feasible or x["meta"].get("error"):
                continue
            rule = failed[0]
            if (r["env"], rule) in seen or r["env"] in {e for e, _ in seen} and len(seen) < len(ENVS) and False:
                continue
            msgs = (r["transcripts"].get(tid) or [[]])[0]
            final = [m for m in msgs if m.get("role") == "assistant" and not m.get("tool_calls")]
            if not final:
                continue
            answer = (final[-1].get("content") or "").strip().replace("\n", " ")
            if len(answer) > 420: answer = answer[:420].rsplit(" ", 1)[0] + " ..."
            calls = sum(len(m.get("tool_calls") or []) for m in msgs if m.get("role") == "assistant")
            desc = getattr(env.grader.rules.get(rule), "description", "") or ""
            text = f"{t.prompt}\n{answer}\n{rule} {desc}"
            if leak.find_leaks(t, text, "snippet"):
                continue
            out.append({"env": r["env"], "model": r["model"], "task": tid, "prompt": t.prompt, "answer": answer, "rule": rule, "desc": desc, "calls": calls, "turns": x["meta"].get("turns")})
            seen.add((r["env"], rule))
            break
        if len({o["env"] for o in out}) == len(ENVS) and len(out) >= k:
            break
    # prefer one per env first, then fill
    chosen, per_env = [], {}
    for o in out:
        if per_env.get(o["env"], 0) < 1:
            chosen.append(o); per_env[o["env"]] = 1
    for o in out:
        if o not in chosen and len(chosen) < k:
            chosen.append(o)
    return chosen[:k]

def write_failures(examples):
    lines = ["# Failure examples (real runs)\n", "Excerpts from saved runs in `runs/`, generated by `scripts/make_charts.py`. Each shows the public task prompt, the model's final answer (trimmed) and the rule it broke. "
             "No hidden task fields appear (checked with the repo's leak check). Samples are small and models are small or mid-size unless marked; these illustrate failure types, they are not a ranking.\n"]
    for i, o in enumerate(examples, 1):
        lines += [f"## {i}. {ENV_LABEL[o['env']]}: {o['model']} on {o['task']}\n", f"**Task prompt:** {o['prompt']}\n", f"**Model's final answer (trimmed):** `{o['answer']}`\n",
                  f"**Rule broken:** `{o['rule']}`" + (f": {o['desc']}" if o['desc'] else "") + f". The model made {o['calls']} tool calls over {o['turns']} turns.\n"]
    open(os.path.join(OUT, "failures.md"), "w").write("\n".join(lines))

def main():
    runs = load()
    for f, why in SKIPPED:
        print(f"skipped {f}: {why}", file=sys.stderr)
    if REQUIRE_ONE and any("graded at" in why for _, why in SKIPPED):
        sys.exit("--require-single-commit: some run files were not graded by the chosen commit; run scripts/regrade.py on them first")
    if not runs:
        sys.exit("no usable run files in " + RUNS)
    alt = {}
    fig_headline(runs, alt); fig_gap(runs, alt); fig_rules(runs, alt)
    ex = failure_examples(runs)
    write_failures(ex)
    alt["_generated"] = time.strftime("%Y-%m-%d") + " from runs/*.json (graded at " + ", ".join(sorted({str(r['commit']) for r in runs})) + "; " + str(len(runs)) + " model x environment cells)"
    json.dump(alt, open(os.path.join(OUT, "figures.alt.json"), "w"), indent=1, ensure_ascii=False)
    print("wrote", ", ".join(sorted(os.listdir(OUT))), f"({len(ex)} failure examples)")

if __name__ == "__main__":
    main()
