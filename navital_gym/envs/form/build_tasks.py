"""Builds tasks.jsonl (core Task format) from the task authors' file tasks_forms.jsonl.
`python -m navital_gym.envs.form.build_tasks [path/to/tasks_forms.jsonl]` rewrites tasks.jsonl. The agent-facing prompt gets one added line
naming the answer fields; nothing else in a prompt is changed. gold_answer is kept in meta only to cross-check the oracle (check_gold)."""
import json, os, sys
from . import rules

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.environ.get("NAVITAL_FORM_SRC", "tasks_forms.jsonl")   # the authoring source file (not shipped); pass a path or set NAVITAL_FORM_SRC

def build(src=DEFAULT_SRC):
    out = []
    for line in open(src, encoding="utf-8"):
        row = json.loads(line)
        kind = row["kind"]
        fields = rules.answer_fields(kind)
        prompt = row["prompt"] + "\n\nAnswer fields: " + ", ".join(fields) + "."
        out.append({"id": row["id"], "family": kind, "difficulty": row["difficulty"], "lang": row["lang"], "prompt": prompt,
                    "params": {"world": row["world"]}, "rules": list(rules.rule_ids_for(kind)), "expected_feasible": True,
                    "binding_constraint": [], "traps": [], "meta": {"kind": kind, "gold_answer": row["gold_answer"]}})
    return out

if __name__ == "__main__":
    rows = build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
    with open(os.path.join(HERE, "tasks.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print("wrote tasks.jsonl:", len(rows), "tasks")
