"""Env checks beyond the case files, for Form Desk and Bhasha Support Desk (qa, T-099).
  python3 -I env_checks.py form|support
FORM: oracle == stored gold on all tasks; every gold scores 1.0; any single-field perturbation fails exactly one rule; the env's scripted
      baselines (empty/shotgun/naive) do not solve; a repaired-instead-of-null invalid field fails.
SUPPORT: oracle agent solves all tasks; a NO-ACTION agent that replies in the right language (the gaming risk) is measured per split and
      per kind, and the core split FAILS the anti-gaming gate if that agent solves more than GATE of it; summaries must be reportable per split."""
import copy, datetime as dt, json, os, sys
from decimal import Decimal as Dc
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import load_tasks
from navital_gym.core.runner import run_suite
GATE = 0.25
fails = []
def check(ok, msg):
    if not ok: fails.append(msg); print("FAIL", msg)
def perturb(v):
    if isinstance(v, bool): return not v
    if v is None: return "X1234"
    if isinstance(v, list): return v + ["ZZ"]
    if isinstance(v, str):
        try: return (dt.date.fromisoformat(v) + dt.timedelta(days=1)).isoformat()
        except ValueError: pass
        return v + "x"
    return v + 1

which = sys.argv[1] if len(sys.argv) > 1 else "form"
if which in ("form", "form_multidoc"):
    import importlib; form = importlib.import_module(f"navital_gym.envs.{which}")
    env = form.load_env(); tasks = load_tasks(form.TASKS_PATH)
    check(not form.check_gold(tasks), f"oracle disagrees with stored gold: {form.check_gold(tasks)[:2]}")
    for t in tasks:
        gold = t.meta["gold_answer"]
        r = env.contract_grade(t.to_dict(), {"status": "plan", "answer": gold})
        check(r["solved"] and r["score"] == 1.0, f"{t.id}: gold does not score 1.0 ({r['rules']})")
        for k, v in gold.items():
            if k not in {f for _, f in form.rules.FIELDS[t.meta["kind"]]}: continue   # descriptive extra, not graded
            bad = copy.deepcopy(gold); bad[k] = perturb(v)
            rr = env.contract_grade(t.to_dict(), {"status": "plan", "answer": bad})
            failed = [x for x, ok in rr["rules"].items() if not ok]
            check(not rr["solved"] and len(failed) == 1, f"{t.id}.{k}: perturbation failed {failed}")
        # invalid values must be null: replace each null with a 'repaired' string -> must fail that field's rule
        for k, v in gold.items():
            if v is None:
                rep = copy.deepcopy(gold); rep[k] = "REPAIRED1"
                rr = env.contract_grade(t.to_dict(), {"status": "plan", "answer": rep})
                check(not rr["solved"], f"{t.id}.{k}: a repaired value was accepted where null is required")
                missing = {a: b for a, b in gold.items() if a != k}
                rr = env.contract_grade(t.to_dict(), {"status": "plan", "answer": missing})
                check(not rr["solved"], f"{t.id}.{k}: omitting a required null field was accepted")
    for name, agent in form.get_baselines().items():
        rep = run_suite(env, agent)
        s = rep["summary"]; print(f"form baseline {name:8} pass@1={s['pass@1']:.2f} mean={s['mean_score']:.2f}")
        if name in ("empty", "shotgun", "reject_only"): check(s["pass@1"] < 0.25, f"scripted agent '{name}' solves {s['pass@1']:.0%} of Form Desk")
        elif name == "naive": check(0 < s["pass@1"] < 1.0, "the validation-skipping 'naive' agent should solve some but not all tasks (it is a careless-reader baseline, not a cheat)")
        elif name == "oracle": check(s["pass@1"] == 1.0, "oracle agent does not solve everything")
        else: print(f"  (baseline '{name}' reported, no gate defined)")

elif which == "support":
    from navital_gym.envs import support
    from navital_gym.envs.support import data as D
    env = support.load_env(include_experimental=True); tasks = load_tasks(support.TASKS_PATH)
    bl = support.get_baselines()
    rep = run_suite(env, bl["oracle"]); s = rep["summary"]
    check(s["pass@1"] == 1.0, f"oracle agent solves {s['pass@1']:.0%} (not 100%): " + str([t for t, r in rep["results"].items() if not r[0].solved][:5]))
    mr = " ".join(D.MR_MARKERS[:3]) + " आपली माहिती मिळाली आणि आम्ही मदत करू"
    canned = {"hi": "आपका संदेश हमें मिल गया है और हम आपकी मदद करेंगे, यह हमारी नीति के अनुसार है।",
              "hinglish": "aapka message hum tak pahunch gaya hai aur hum aapki madad karenge, yeh hamari policy ke hisab se hai",
              "mr": mr, "ta": "உங்கள் கோரிக்கையை நாங்கள் பார்த்தோம், இது எங்கள் கொள்கையின்படி இப்போது சாத்தியமில்லை, தயவுசெய்து காத்திருக்கவும்.",
              "bn": "আপনার অনুরোধ আমরা দেখেছি, এটি আমাদের নীতি অনুযায়ী এখন সম্ভব নয়, অনুগ্রহ করে অপেক্ষা করুন।"}
    # the smartest no-action floor: constant (decision, reason) guess, empty actions, right-language canned reply; best constant per split
    PAIRS = [("decline_return", "outside_return_window"), ("decline_return", "non_returnable_category"), ("decline_cancel", "already_shipped"),
             ("refuse_privacy", "not_owner"), ("ask_ifsc", "bad_ifsc"), ("decline_address_change", "already_shipped"), ("request_photo", "no_photo"),
             ("escalate", "customer_requests_human"), ("refund", "eligible"), ("cancel", "not_shipped"), ("address_change", "not_shipped")]
    solved = {}
    for t in tasks:
        for dec, rea in PAIRS:
            r = env.contract_grade(t.to_dict(), {"status": "plan", "actions": [], "reply": canned[t.lang], "decision": dec, "reason": rea})
            solved.setdefault((t.meta["split"], dec, rea), []).append(bool(r["solved"]))
    best = {}
    for (sp, dec, rea), v in solved.items():
        n = len(v); a = sum(v)
        if sp not in best or a > best[sp][0]: best[sp] = (a, n, dec, rea)
    for sp, (a, n, dec, rea) in sorted(best.items()):
        print(f"best no-action constant guess on {sp}: {a}/{n} = {a/n:.0%} with decision={dec!r}, reason={rea!r}")
    core = best["core"]; frac = core[0] / core[1]
    check(frac <= GATE, f"ANTI-GAMING GATE: an agent that never acts (best constant decision/reason, right-language canned reply) solves {core[0]}/{core[1]} = {frac:.0%} of the CORE split (gate {GATE:.0%})")
    # a reply without decision/reason must not score at all (format gate)
    r0 = env.contract_grade(tasks[0].to_dict(), {"status": "plan", "actions": [], "reply": canned[tasks[0].lang]})
    check(not r0["solved"] and r0["score"] == 0.0, "a submission without decision/reason should fail the format gate")
    # per-split reporting available?
    check("by_split" in s and {"core", "experimental"} <= set(s["by_split"]), "summarize() has no per-split breakdown: core and experimental scores would be mixed in one number")
print(f"env_checks {which}:", "PASS" if not fails else f"FAIL ({len(fails)})"); sys.exit(1 if fails else 0)
