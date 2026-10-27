# navital-grader-harness (T-099c, qa)
Shared grader-correctness harness for every Navital env. Stdlib only. `./run.sh module:function --path DIR --env NAME`.

Grader contract (backend: please expose this adapter in the core): `grade(task: dict, submission: Any) -> {"score": 0..1, "solved": bool, "rules": {rule_id: bool}}`.

Per env, drop case files in `cases/<env>/*.json` (format in navital_qa/conformance.py docstring):
- `solved` (hand-solved, must score as expected), `violation` (breaks exactly the named rules; `passes_all_but` enforces purity), `infeasible_claim`.
- Auto cheats from every solved case: empty/null/wrong types/prompt copy/huge input/status flip/duplicated days must not solve and must score < 0.5 (a crash counts as FAIL: graders must degrade to 0). Agent-claimed fields (total_cost, score, solved...) zeroed/dropped/forged must leave the result IDENTICAL. Env opts in to `required_fields` and `id_field` checks via `expect`.
- Determinism: reruns identical, JSON key order irrelevant, inputs not mutated.
`tests/test_harness.py` proves the harness itself: it passes a correct grader and fails 7 deliberately bad ones (trusts total_cost, trusts claimed score, crashes on garbage, nondeterministic, key-order dependent, mutates input, impure violation).
Case files for every env (trip, upi, gst, form, form_multidoc, support, and their easy sets) are in `cases/<env>/`.

## GST Desk (env #3, qa owns world + grader) — status 2026-10-25
Code: `navital_gym/envs/gst/` (oracle.py independent reference solver, rules.py one rule per answer field, world.py tools get_documents/get_policy/lookup_rate/validate_gstin/calendar_info).
- `python3 -I build_gst_cases.py` writes cases/gst/ (9 tasks, answers HAND-computed, asserted equal to the stored gold; one single-field violation per rule).
- `./run.sh gst_adapter:grade --path adapters --env gst` -> cheating 99/99, correctness 167/167, determinism 111/111.
- `python3 -I gst_checks.py` -> all 50 gold answers score 1.0 and oracle == gold; every single-field perturbation fails exactly one rule; no gold/meta/designer note in anything the agent sees; world fingerprints deterministic; a grader that ignores blocked ITC categories is caught.

## Gates added 2026-10-25 (all envs: trip, gst, form, support)
- `./run.sh <env>_adapter:grade --path adapters --env <env>`: hand-solved correctness + cheating + determinism (gst/form/support; trip pending backend's stable world).
- `python3 -I degenerate_gate.py`: degenerate agents (empty, reject_only, accept_only, prior = majority vote with no reading, trip claim_all = "infeasible" with every rule as binding) must each solve <= 25% of an env and of its core split; per-kind WARNs. Current: all PASS (worst: Support prior 24% of all, 12/50 of core; GST prior 18%; Form prior 16%; trip 0%).
- `python3 -I env_checks.py form|support|...`: gold == oracle, single-field perturbations fail exactly one rule, null-required fields, the Support no-action floor (8% core with the best constant decision/reason), per-split summary.
- `python3 -I adapter_leak_check.py` (any python): shared OpenEnv path + AST audit of the adapters.
- `.venv/bin/python -I harness/adapter_live_leak.py`: LIVE check of the three real adapters (OpenEnv, Inspect, verifiers) for all 205 tasks: observations, sample inputs/metadata/targets, task data, tool lists, tool outputs, finalize reply, state. Mutation-tested (an injected gold hint is caught on all three paths).
- Hand-solved cases pin task data: when the tasks are regenerated the builders (build_gst_cases.py, build_form_support_cases.py) assert hand answers == stored gold and fail loudly; re-solve by hand, do not copy the oracle.

## Trip hand-solved cases (2026-10-25, qa)
`python3 -I build_trip_cases.py` -> cases/trip (9 tasks: 5 feasible plans hand-solved from the world tools and different from the solver's picks: IN-TRIP-005/041/043/044/045; 4 infeasible claims reasoned from the rules: 042 R-QUOTA, 049 R-OPEN, 051/053 R-BUD). 34 single-edit violations, failing rules predicted before running (all matched except where my first guess ignored a clash I had created, noted in the builder). Run: `./run.sh trip_adapter:grade --path adapters --env trip`.
FINDING (FIXED upstream in 75e9480: arriving in the end city now counts as visited; the bare-ticket plan is a hand case that must solve): the five rail-booking tasks (IN-TRIP-041..045) say only "Book rail from X to Y" but R-ROUTE also needs a hotel night or a SIGHT in the destination, and a 1-day trip has no night. A plan with just the ticket fails R-ROUTE; the solver adds a sight. The agent instructions do not say this. Either count arriving at the end city as visited, or say in the instructions/prompt that a named city is only "visited" with a night or a sight there.
Harness change: plan-shaped cheats (duplicated days, forged status flips...) only have to NOT SOLVE; they may keep partial rule credit (a duplicated-days plan scores 0.78 because 7 of 9 rules still pass). Structural garbage must still score < 0.5. Partial credit is by design in the core Grader (score = fraction of rules passed), but it means a reward based on `score` pays 0.78 for a plan that is wrong; RL users should use `solved`.

## Form Desk: hard (form_multidoc, 2026-10-26)
40 tasks (multi_doc, pan_name, record_conflicts, ocr_repair, batch; 8 each) built by the task authors. All 40 were solved by hand from the prompt and get_policy text only, before comparing with any gold (`cases/form_multidoc_src/hand-solves*.json`, workings in the comments of build_form_multidoc_cases.py); all 40 agree with the gold and grader. `python3 -I build_form_multidoc_cases.py` writes cases/form_multidoc (one hand-solved case plus one single-field violation per rule, per task); `./run.sh form_multidoc_adapter:grade --path adapters --env form_multidoc` -> cheating 440/440, correctness 805/805, determinism 531/531. Degenerate gate: empty 0%, reject_only 0%, prior 15% (pan_name 3/8). Leak checks (shared and live adapters) pass.
