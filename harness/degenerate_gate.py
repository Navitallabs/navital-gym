"""Degenerate-agent gate, every env (qa, T-099). Agents that read nothing must not solve much. GATE = 25% of an env's tasks (and of its core split).
Agents (all use only the task, never the world):
  empty        {} / empty answer
  reject_only  always says no: false / null / [] / 0 for every graded field; support: no actions + best constant 'decline' pair; trip: "infeasible"
  accept_only  always says yes: true for every boolean field (others null)
  prior        per (kind, field) the MOST COMMON gold value over the whole task set (a no-reading majority-vote agent)
  claim_all    trip only: status "infeasible" with binding = every rule id of the task (catches 'any subset of binding' loopholes)
UPI: constant answers with no actions (the action log is what makes a payment real).
Reports pass@1 per agent, per env and per kind; FAILS if any degenerate agent solves more than GATE of an env (or of a kind with >= 5 tasks, reported as WARN).
  python3 -I degenerate_gate.py [env ...]"""
import importlib.util
import collections, importlib, json, os, sys
sys.path.insert(0, os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import load_tasks
GATE = 0.25
envs = sys.argv[1:] or [e for e in ["trip", "gst", "form", "form_multidoc", "support", "upi"] if __import__("importlib").util.find_spec("navital_gym.envs." + e)]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import splitpatch; envs = splitpatch.apply_from_env(envs)
fails, warns = [], []

def graded_fields(t):
    mod = importlib.import_module(f"navital_gym.envs.{t.family and ''}") if False else None

def solved(env, t, sub):
    return bool(env.contract_grade(t.to_dict(), sub)["solved"])

for name in envs:
    pkg = importlib.import_module(f"navital_gym.envs.{name}")
    env = pkg.load_env(include_experimental=True) if name == "support" else pkg.load_env()
    tasks = [env.tasks[i] for i in env.task_ids()]
    n = len(tasks); res = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    def tally(agent, t, ok):
        kind = (t.meta.get("kind") or t.family or "?"); sp = t.meta.get("split", "core")
        for key in ("ALL", f"kind:{kind}", f"split:{sp}"):
            res[agent][key][1] += 1; res[agent][key][0] += ok
    if name in ("gst", "form", "form_multidoc"):
        gold_by = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        for t in tasks:
            for k, v in (t.meta.get("gold_answer") or {}).items():
                gold_by[t.meta["kind"]][k][json.dumps(v, sort_keys=True)] += 1
        for t in tasks:
            gold = t.meta.get("gold_answer") or {}
            kind = t.meta["kind"]
            subs = {
                "empty": {"status": "plan", "answer": {}},
                "reject_only": {"status": "plan", "answer": {k: (False if isinstance(v, bool) else [] if isinstance(v, list) else 0 if isinstance(v, (int, float)) and not isinstance(v, bool) else None) for k, v in gold.items()}},
                "accept_only": {"status": "plan", "answer": {k: (True if isinstance(v, bool) else None) for k, v in gold.items()}},
                "prior": {"status": "plan", "answer": {k: json.loads(gold_by[kind][k].most_common(1)[0][0]) for k in gold}},
            }
            for a, s in subs.items(): tally(a, t, solved(env, t, s))
    elif name == "support":
        PAIRS = {(dec, rea) for dec, rea in [("decline_return", "outside_return_window"), ("decline_return", "non_returnable_category"), ("decline_cancel", "already_shipped"),
                 ("refuse_privacy", "not_owner"), ("ask_ifsc", "bad_ifsc"), ("decline_address_change", "already_shipped"), ("request_photo", "no_photo")]}
        canned = {"hi": "आपका संदेश हमें मिल गया है और हम आपकी मदद करेंगे, यह हमारी नीति के अनुसार है।",
                  "hinglish": "aapka message hum tak pahunch gaya hai aur hum aapki madad karenge, yeh hamari policy ke hisab se hai",
                  "mr": "आहे तुमचा तुमची आपली माहिती मिळाली आणि आम्ही मदत करू",
                  "ta": "உங்கள் கோரிக்கையை நாங்கள் பார்த்தோம், இது எங்கள் கொள்கையின்படி இப்போது சாத்தியமில்லை, தயவுசெய்து காத்திருக்கவும்.",
                  "bn": "আপনার অনুরোধ আমরা দেখেছি, এটি আমাদের নীতি অনুযায়ী এখন সম্ভব নয়, অনুগ্রহ করে অপেক্ষা করুন।"}
        # best constant decline pair, chosen on the whole set (an agent with a prior); score it on every task
        scores = {p: sum(solved(env, t, {"status": "plan", "actions": [], "reply": canned[t.lang], "decision": p[0], "reason": p[1]}) for t in tasks) for p in PAIRS}
        best = max(scores, key=scores.get)
        for t in tasks:
            tally("empty", t, solved(env, t, {"status": "plan", "actions": [], "reply": "Okay."}))
            tally("reject_only", t, solved(env, t, {"status": "plan", "actions": [], "reply": canned[t.lang], "decision": best[0], "reason": best[1]}))
        # prior = majority (decision, reason) per kind with no actions
        by = collections.defaultdict(collections.Counter)
        from navital_gym.envs.support import oracle
        exp = {t.id: oracle.solve(t.meta["kind"], t.params["world"], t.params["policy"]) for t in tasks}
        for t in tasks: by[t.meta["kind"]][(exp[t.id]["decision"], exp[t.id]["reason"])] += 1
        for t in tasks:
            d, r = by[t.meta["kind"]].most_common(1)[0][0]
            tally("prior", t, solved(env, t, {"status": "plan", "actions": [], "reply": canned[t.lang], "decision": d, "reason": r}))
    elif name == "upi":
        gold_by = collections.defaultdict(collections.Counter)
        for t in tasks:
            g = {k: v for k, v in (t.meta.get("gold_answer") or {}).items() if k not in ("note", "reason_text")}
            gold_by[t.meta["kind"]][json.dumps(g, sort_keys=True)] += 1
        for t in tasks:
            kind = t.meta["kind"]
            subs = {"empty": {"status": "plan", "answer": {}, "actions": []},
                    "reject_only": {"status": "plan", "answer": {"action": "cannot_pay", "reason": "over_txn_limit"}, "actions": []},
                    "prior": {"status": "plan", "answer": json.loads(gold_by[kind].most_common(1)[0][0]), "actions": []}}
            for a, sb in subs.items(): tally(a, t, solved(env, t, sb))
    elif name == "trip":
        for t in tasks:
            tally("empty", t, solved(env, t, {}))
            tally("reject_only", t, solved(env, t, {"status": "infeasible", "binding": []}))
            tally("claim_all", t, solved(env, t, {"status": "infeasible", "binding": list(t.rules)}))
    print(f"\n== {name}: {n} tasks")
    for agent in sorted(res):
        allr = res[agent]["ALL"]; frac = allr[0] / allr[1]
        line = f"  {agent:12} {allr[0]:3}/{allr[1]:3} = {frac:4.0%}"
        extras = []
        for key, (a, m) in sorted(res[agent].items()):
            if key == "ALL": continue
            if key.startswith("split:") or (m >= 5 and a / m > GATE) or (key.startswith("kind:") and a / m > 0.6 and m >= 3):
                extras.append(f"{key} {a}/{m}")
        print(line + ("   [" + "; ".join(extras) + "]" if extras else ""))
        if frac > GATE: fails.append(f"{name}: degenerate agent '{agent}' solves {frac:.0%} of all tasks (gate {GATE:.0%})")
        for key, (a, m) in res[agent].items():
            if key.startswith("split:core") and a / m > GATE and key != "ALL": fails.append(f"{name}: '{agent}' solves {a}/{m} of the core split")
            if key.startswith("kind:") and m >= 5 and a / m > 0.5: warns.append(f"{name}: '{agent}' solves {a}/{m} of kind {key[5:]}")
for w in warns: print("WARN", w)
for f in fails: print("FAIL", f)
print("degenerate_gate:", "PASS" if not fails else f"FAIL ({len(fails)})"); sys.exit(1 if fails else 0)
