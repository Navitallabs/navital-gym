"""Builds tasks.jsonl (core Task format) from the task authors' file tasks_support.jsonl.
Applicable rules come from the oracle: R-ACTIONS, R-FORBIDDEN, R-DECISION, R-REASON always; R-LANG only for the Hindi / Hinglish core; R-AMOUNT when a refund is due; R-PRIVACY for privacy tasks.
Tamil, Bengali and Marathi rows are tagged meta.split = "experimental" (machine-assisted, not native-reviewed)."""
import json, os, sys
from . import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.environ.get("NAVITAL_SUPPORT_SRC", "tasks_support.jsonl")   # the authoring source file (not shipped); pass a path or set NAVITAL_SUPPORT_SRC
CORE = ("hi", "hinglish")

def build(src=DEFAULT_SRC):
    out = []
    for line in open(src, encoding="utf-8"):
        row = json.loads(line)
        o = oracle.solve(row["kind"], row["world"], row["policy"])
        rules = ["R-FMT", "R-ACTIONS", "R-FORBIDDEN", "R-DECISION", "R-REASON"]
        if row["lang"] in CORE: rules.append("R-LANG")
        if o["amount"] is not None: rules.append("R-AMOUNT")
        if o["privacy"]: rules.append("R-PRIVACY")
        if o.get("answer_address"): rules.append("R-ANSWER")
        out.append({"id": row["id"], "family": row["kind"], "difficulty": row["difficulty"], "lang": row["lang"], "prompt": row["prompt"],
                    "params": {"world": row["world"], "policy": row["policy"]}, "rules": rules, "expected_feasible": True, "binding_constraint": [], "traps": [],
                    "meta": {"kind": row["kind"], "split": "core" if row["lang"] in CORE else "experimental", "gold_answer": row["gold_answer"],
                             "forbidden_actions": row["forbidden_actions"],
                             **({} if row["lang"] in CORE else {"review_status": "machine-assisted, not native-reviewed"})}})
    return out

if __name__ == "__main__":
    rows = build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
    with open(os.path.join(HERE, "tasks.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print("wrote tasks.jsonl:", len(rows), "tasks")
