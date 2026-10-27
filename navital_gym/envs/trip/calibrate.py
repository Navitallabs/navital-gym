"""Budget calibration from the world, not from guesses. best_cost(task): cheapest plan the solver can find (iterative tightening under a node cap,
so an UPPER bound on the true minimum). Impossible-budget variants use a budget far below it and are then PROVEN infeasible by verdict()
(the budget lower bound prunes the search). `python -m navital_gym.envs.trip.calibrate [ids]` prints the table."""
import os, sys
from dataclasses import replace
from ...core import load_tasks
from .solver import Solver
from . import rules as R

def cost_of(task, plan):
    from ...core.grader import Ctx
    from .world import TripWorld
    ctx = Ctx(task=task, world=TripWorld(task, 0), sub=plan)
    return R.recompute_cost(ctx)

def best_cost(task, node_limit=30000, hi=500000):
    best, budget = None, hi
    for _ in range(40):
        p = dict(task.params); p["budget_inr"] = budget
        t = replace(task, params=p)
        plan = Solver(t, node_limit=node_limit).solve()
        if not plan:
            break
        best = cost_of(t, plan)
        budget = int(best) - 1
    return best

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    only = set(sys.argv[1:])
    for t in load_tasks(os.path.join(here, "tasks.jsonl")):
        if t.params.get("budget_inr") and t.expected_feasible and (not only or t.id[-3:] in only):
            bc = best_cost(t)
            print(t.id[-3:], "budget", t.params["budget_inr"], "best found cost", round(bc) if bc else None, f"slack {1 - bc / t.params['budget_inr']:.0%}" if bc else "", flush=True)
