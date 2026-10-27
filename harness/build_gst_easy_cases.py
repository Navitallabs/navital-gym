"""cases/gst_easy from qa's hand solves (cases/gst_easy_src/hand-solves.json); asserts each equals the stored gold, then one single-field violation per rule."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from decimal import Decimal as Dc
from navital_gym.envs import gst
from navital_gym.envs.gst import rules as R
T = {t.id: t for t in gst.load_env(splits=("easy",)).tasks.values()}
HAND = json.load(open(os.path.join(HERE, "cases", "gst_easy_src", "hand-solves.json")))
RULE_OF = {k: dict((f, r) for r, f in fs) for k, fs in R.FIELDS.items()}
RULE_OF["threshold"] = {"required": "R-REQUIRED"}
def wrong(v):
    if isinstance(v, bool): return not v
    if isinstance(v, int): return v + 1
    if isinstance(v, str) and v.replace(".", "", 1).isdigit(): return str(Dc(v) + 1)
    return "IGST" if v != "IGST" else "CGST+SGST"
n = 0
for tid, ans in HAND.items():
    if tid.startswith("_"): continue
    t = T[tid]; gold = t.meta["gold_answer"]; kind = t.meta["kind"]
    for k, v in ans.items():
        same = (Dc(str(v)) == Dc(str(gold[k]))) if not isinstance(v, (bool, str)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()) else v == gold[k]
        assert same, f"HAND != gold in {tid}.{k}: {v!r} vs {gold[k]!r}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": {"status": "plan", "answer": ans}, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for field, value in ans.items():
        rid = RULE_OF[kind][field]; bad = copy.deepcopy(ans); bad[field] = wrong(value)
        cases.append({"name": f"only_{rid}", "kind": "violation", "submission": {"status": "plan", "answer": bad}, "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    json.dump({"env": "gst_easy", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(os.path.join(HERE, "cases", "gst_easy", f"{tid}.json"), "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
