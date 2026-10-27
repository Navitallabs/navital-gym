"""Builds cases/form_multidoc from qa's HAND SOLVES (cases/form_multidoc_src/hand-solves*.json, or FORM_HARD_HAND_DIR: written from the prompt and get_policy text only, before
looking at the oracle or any gold). The build asserts each hand answer equals the stored gold, so a disagreement between my reading and the env is loud.
Every violation is a one-field copy of the hand answer whose failing rule is predicted from the field name (one rule per field)."""
import copy, json, os, sys
ROOT = os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from navital_gym.core import load_tasks
from navital_gym.envs import form_multidoc
from navital_gym.envs.form_multidoc import rules as R
HAND = {}
for _f in ("hand-solves.json", "hand-solves-2.json"):      # batch 1: 17 tasks, batch 2: the other 23 (all written before comparing with any gold)
    HAND.update(json.load(open(os.path.join(os.environ.get("FORM_HARD_HAND_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases", "form_multidoc_src"), _f))))
T = {t.id: t for t in load_tasks(form_multidoc.TASKS_PATH)}
RULE_OF = {k: dict((f, r) for r, f in fs) for k, fs in R.FIELDS.items()}

def wrong(v, field):
    if isinstance(v, bool): return not v
    if isinstance(v, int): return v + 1
    if v is None: return "X1234"
    if isinstance(v, list): return v + ["ZZ9"] if len(v) < 3 else v[:-1]
    if isinstance(v, str):
        if len(v) == 10 and v[4] == "-" and v[7] == "-": return v[:8] + ("01" if v[8:] != "01" else "02")      # a date one off
        return v + "x" if field not in ("reason",) else ("ok" if v != "ok" else "holder_type_mismatch")
    return v

n = 0
os.makedirs("cases/form_multidoc", exist_ok=True)
for tid, ans in HAND.items():
    if tid.startswith("_"): continue
    t = T[tid]; gold = t.meta["gold_answer"]; kind = t.meta["kind"]
    for k, v in ans.items():
        assert k in gold and (sorted(v) == sorted(gold[k]) if isinstance(v, list) else v == gold[k]), f"HAND != gold in {tid}.{k}: {v!r} vs {gold.get(k)!r}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": {"status": "plan", "answer": ans}, "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for field, value in ans.items():
        rid = RULE_OF[kind][field]; bad = copy.deepcopy(ans); bad[field] = wrong(value, field)
        cases.append({"name": f"only_{rid}", "kind": "violation", "submission": {"status": "plan", "answer": bad},
                      "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    if isinstance(ans.get("conflicts", ans.get("inconsistent_fields", ans.get("repaired"))), list):    # order/duplicate handling of list fields
        fld = next(f for f in ("conflicts", "inconsistent_fields", "repaired") if f in ans)
        if len(ans[fld]) >= 1:
            dup = copy.deepcopy(ans); dup[fld] = ans[fld] + ans[fld][:1]
            rid = RULE_OF[kind][fld]    # lists are graded as sets with no duplicates. NOTE the policy text never says "each item once"
            cases.append({"name": f"duplicate_item_in_{fld}", "kind": "violation", "submission": {"status": "plan", "answer": dup}, "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    for field in ("pan", "ifsc"):                  # identifiers are compared case-sensitively (the EXACT set)
        if isinstance(ans.get(field), str):
            low = copy.deepcopy(ans); low[field] = ans[field].lower()
            rid = RULE_OF[kind][field]
            cases.append({"name": f"lowercase_{field}", "kind": "violation", "submission": {"status": "plan", "answer": low}, "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    for field in ("invalid_pans", "current_account_eligible"):
        if isinstance(ans.get(field), list) and ans[field]:
            low = copy.deepcopy(ans); low[field] = [x.lower() for x in ans[field]]
            rid = RULE_OF[kind][field]
            cases.append({"name": f"lowercase_ids_in_{field}", "kind": "violation", "submission": {"status": "plan", "answer": low}, "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    json.dump({"env": "form_multidoc", "task_id": tid, "task": t.to_dict(), "cases": cases}, open(f"cases/form_multidoc/{tid}.json", "w"), indent=1, ensure_ascii=False); n += 1
print("wrote", n, "case files")
