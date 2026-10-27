# Env #1: where the reference solver disagreed with the design intent in the task authors' specs

expected_feasible / binding are set by solver.py (exhaustive search of the plan space + rule relaxation), not by hand. the authors' original flags are kept in each task's meta (design_intent_*).

| task | intent | solver | why |
|---|---|---|---|
| IN-TRIP-029 | feasible | infeasible R-BUD,R-DATE | no plan in the search space |
