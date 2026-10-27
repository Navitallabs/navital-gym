"""GST Desk env checks beyond the case files: all 50 gold answers score 1.0, wrong-by-one answers don't,
agent-visible text never carries gold/meta, tools are deterministic, and a mutated grader is caught."""
import sys, json, copy
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..") if "adapters" in __file__ else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")); sys.path.insert(0, "navital_qa")
from navital_gym.envs import gst
from navital_gym.core import leak
import conformance as C
tasks = gst.load_tasks(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "navital_gym", "envs", "gst", "tasks.jsonl"))
env = gst.make_env(tasks); fails = []
import datetime as dt
from decimal import Decimal as Dc
def perturb(v):
    if isinstance(v, bool): return not v
    if isinstance(v, list): return v + ["ZZ"]
    if isinstance(v, str):
        try: return (dt.date.fromisoformat(v) + dt.timedelta(days=1)).isoformat()
        except ValueError: pass
        try: return str(Dc(v) + 1)
        except Exception: return "x" + v
    return v + 1
def check(ok, msg):
    if not ok: fails.append(msg); print("FAIL", msg)
# 1. every gold scores 1.0; oracle == gold
check(not gst.check_gold(tasks), "oracle disagrees with gold")
for t in tasks:
    sc = env.contract_grade(t.to_dict(), {"status": "plan", "answer": t.meta["gold_answer"]})
    check(sc["solved"] and sc["score"] == 1.0, f"{t.id}: gold does not score 1.0 ({sc})")
    # 2. one field off by a bit -> not solved, exactly that rule fails
    for k, v in t.meta["gold_answer"].items():
        bad = copy.deepcopy(t.meta["gold_answer"])
        bad[k] = perturb(v)
        r = env.contract_grade(t.to_dict(), {"status": "plan", "answer": bad})
        failed = [x for x, ok in r["rules"].items() if not ok]
        if k in ("place_of_supply",):   # extra descriptive field in gold, not graded
            continue
        check(not r["solved"] and len(failed) == 1, f"{t.id}.{k}: perturbation failed {failed}, solved={r['solved']}")
    # 3. agent-visible surface has no gold/meta
    obs = env.reset(t.id)
    check(not leak.leaks_in_observation(t, obs), f"{t.id}: leak {leak.leaks_in_observation(t, obs)}")
    blob = json.dumps(obs) + json.dumps([env.world.call(n) for n in ("get_documents", "get_policy")])
    gold_text = json.dumps(t.meta["gold_answer"], sort_keys=True)
    check("gold_answer" not in blob and "forbidden_actions" not in blob and "expected_feasible" not in blob, f"{t.id}: hidden key in agent text")
    check('"rule"' not in json.dumps(env.world.call("get_documents")), f"{t.id}: designer rule note exposed")
    # 4. tools deterministic
    w2 = env.make_world(t); check(env.world.fingerprint() == w2.fingerprint(), f"{t.id}: world fingerprint differs")
# 5. tool behaviour
w = env.make_world(tasks[0])
check(w.call("validate_gstin", {"gstin": tasks[0].params["world"]["supplier"]["gstin"]})["valid"], "valid synthetic GSTIN rejected")
check(not w.call("validate_gstin", {"gstin": "24AAAPA1111A1Z0"})["valid"], "bad checksum accepted")
check("error" in w.call("lookup_rate", {"code": "NOPE"}), "unknown code not an error")
check("error" in w.call("calendar_info", {"date": "31-12-2026"}), "bad date not an error")
check("error" in w.call("finalize_plan", {}), "unknown tool not an error")
# 6. the harness catches a mutated grader (sanity of the sanity)
from navital_gym.envs.gst import oracle
orig = oracle.itc
def lax(world, rules):
    ok = [r for r in world["purchase_register"] if r["in_gstr2b"] and r["goods_received"]]   # forgets blocked categories
    from decimal import Decimal as D
    return {"eligible_itc": sum(D(str(r["tax"])) for r in ok), "eligible_invoices": sorted(r["inv"] for r in ok)}
oracle.itc = lax
rep = C.Report(); C.run_file(lambda t, s: env.contract_grade(t, s), "cases/gst/IN-GST-024.json", rep, 1)
oracle.itc = orig
check(rep.fail > 0, "harness did NOT catch a grader that ignores blocked ITC categories")
print("gst_checks:", "PASS" if not fails else f"FAIL ({len(fails)})"); sys.exit(1 if fails else 0)
