"""Scripted agents for Form Desk: hard: empty, reject_only (the 'nothing is wrong' answer), prior (the most common answer shape), oracle."""
from ...core.runner import ScriptedAgent
from . import oracle

def _kind(task): return task.meta["kind"]
def empty(obs, call, task): return {"status": "plan", "answer": {}}

NOTHING = {"multi_doc": {"conflicts": [], "name": "", "dob": "1990-01-01", "needs_manual_review": False},
           "pan_name": {"pan_matches_name": True, "reason": "ok"},
           "record_conflicts": {"inconsistent_fields": [], "age": 30, "minor": False},
           "ocr_repair": {"pan": None, "ifsc": None, "repaired": []},
           "batch": {"minors": 0, "invalid_pans": [], "current_account_eligible": []}}
def reject_only(obs, call, task):
    """The 'nothing is wrong' floor: reports no conflicts, no repairs, no invalid or minor records, without reading anything."""
    return {"status": "plan", "answer": dict(NOTHING[_kind(task)])}

def prior(obs, call, task):
    """The 'most common answer' floor: for each family the modal value of each field across the public tasks (computed lazily from the oracle outputs)."""
    from collections import Counter
    import json
    global _PRIOR
    try: _PRIOR
    except NameError:
        _PRIOR = {}
        from . import TASKS_PATH
        by = {}
        for l in open(TASKS_PATH, encoding="utf-8"):
            r = json.loads(l); by.setdefault(r["meta"]["kind"], []).append(oracle.solve(r["meta"]["kind"], r["params"]["world"]))
        for k, outs in by.items():
            _PRIOR[k] = {f: json.loads(Counter(json.dumps(o[f], sort_keys=True) for o in outs).most_common(1)[0][0]) for f in outs[0]}
    return {"status": "plan", "answer": dict(_PRIOR[_kind(task)])}

def oracle_agent(obs, call, task):
    return {"status": "plan", "answer": oracle.solve(_kind(task), task.params["world"])}

def get_baselines():
    return {n: ScriptedAgent(n, f) for n, f in [("empty", empty), ("reject_only", reject_only), ("prior", prior), ("oracle", oracle_agent)]}
