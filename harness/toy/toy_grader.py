"""Tiny reference grader (budget + dates) used only to prove the harness catches bad graders."""
def grade(task, sub):
    rules = {"R-FMT": False, "R-BUD": False, "R-DATE": False}
    def done(score=0.0):
        passed = sum(rules.values())
        return {"score": 0.0 if not rules["R-FMT"] else passed / len(rules), "solved": all(rules.values()), "rules": rules}
    if not isinstance(sub, dict) or sub.get("status") != "plan" or not isinstance(sub.get("days"), list) or not sub["days"]:
        return done()
    try:
        cost = sum(float(l["fare"]) for d in sub["days"] for l in d.get("legs", [])) + sum(float(d.get("stay_cost", 0)) for d in sub["days"])
        dates = [d["date"] for d in sub["days"]]
    except (KeyError, TypeError, ValueError):
        return done()
    rules["R-FMT"] = True
    rules["R-BUD"] = cost <= task["params"]["budget_inr"]          # recomputed, agent total_cost ignored
    rules["R-DATE"] = len(dates) == task["params"]["days"] and dates[0] == task["params"]["start"]
    return done()
