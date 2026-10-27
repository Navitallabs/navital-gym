# Writing a new Navital Gym env

An env is mostly **data plus rules** on the shared core. Copy `navital_gym/envs/trip/` as the pattern. Each env is a package `navital_gym/envs/<name>/`.

## 1. Files
| file | what |
|---|---|
| `tasks.jsonl` | one task per line (schema below). Data, CC BY 4.0. |
| `data.py` | static synthetic tables (rates, calendars, IDs). No customer data, no scraped or licensed datasets. |
| `world.py` | `class XWorld(World)`: builds the snapshot from `(task, seed)`, exposes tools with `@tool(...)`. Deterministic: use `self.h(...)` / `self.pick(...)`, never `random`, the clock or the network. |
| `rules.py` | one `Rule` per checkable requirement + `parse(sub)` + `make_grader()`. |
| `__init__.py` | `load_env()`, `INSTRUCTIONS` (output format + the rule list, i.e. the policy doc), `grade(task_dict, submission)`. |
| `solver.py` (strongly recommended) | an oracle that finds a valid submission or proves none exists; it confirms every task's `expected_feasible`. Write it independently of the rules where you can: two implementations that agree are the best grader test. |
| `baselines.py` | scripted agents (empty, shotgun, heuristic, oracle). |
| `tests/test_<name>.py` | see section 4. |

## 2. Task schema
```json
{"id": "IN-XXX-001", "family": "...", "difficulty": 1-5, "lang": "en|hi|hinglish|...", "prompt": "what the agent sees",
 "params": {"...": "structured facts the world and rules read; never shown to the agent"},
 "rules": ["R-FMT", "..."], "expected_feasible": true, "binding_constraint": ["R-..."], "traps": ["hidden designer notes"], "meta": {}}
```
The agent is shown **only** `Task.public()` (id, prompt, lang), the tools, and the policy text. `expected_feasible`, `binding_constraint`, `traps`, `gold_answer`, `forbidden_actions`, `grader_notes` are hidden: `core/leak.py` and a test enforce it. If a prompt contains a designer hint ("budget impossible"), the test fails.

## 3. Grader contract
`grade(task: dict, submission) -> {"score": 0..1, "solved": bool, "rules": {rule_id: bool}}`.
- Never raises on garbage (score 0). Never reads agent-claimed fields (`total_cost`, `score`, `solved`, `rules`): recompute from the world.
- Deterministic; does not mutate its inputs; key order in the submission does not matter.
- `solved` = every applicable hard rule passes. Soft scores (preferences, slack) are reported separately.
- Infeasible tasks: the agent answers `{"status": "infeasible", "binding": [...]}`. `binding` must match one of the task's `meta.binding_sets` exactly (name only the true reason). Any plan on an infeasible task scores 0.
- A rule gets `gate = True` if nothing else can be evaluated without it (format).
- Rule independence: a plan that breaks only rule R must fail R and nothing else (qa's harness checks this). Keep rules orthogonal; mark rules that merely restate the request `demand = True` so they are never reported as the binding reason.

## 4. Tests every env must have
1. every task's rule ids exist; ids unique;
2. **no hidden field reaches the agent**: `leaks_in_observation` for every task, plus tool output;
3. world determinism (fingerprint stable for one seed, differs across seeds);
4. oracle plans solve every feasible task; correct claims solve every infeasible task; shotgun claims and padded claims fail;
5. garbage submissions score 0 and never raise; forged claimed fields change nothing; inputs not mutated;
6. one single-violation case per rule fails exactly that rule.

## 5. Quality bar before launch
Rules stated as a documented simplification at the top of the README for the env (not claims about the real world); each public fact marked `(public)` or `(verify)`; data provenance written down; baselines (scripted + at least one open model) with the exact command that reproduces them.
