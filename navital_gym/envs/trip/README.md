# Env #1: Indian trip planning under real constraints

> **Simplified rules, not real-world claims.** This is a simulation with synthetic prices, timetables, seat counts and hotels, built from public knowledge of Indian rail, road, air and tourism practice and simplified so it can be graded exactly. Nothing here states what a real railway, airline or hotel does today. Not affiliated with or endorsed by IRCTC / Indian Railways or any airline, hotel or tourism body; names are used only to describe the workflow. Rules as of 25 Oct 2026.

An agent plans a multi-city trip from a short prompt ("Plan a 4-day trip Delhi -> Agra -> Jaipur starting 2026-12-05 for 2 adults and a child aged 8, total budget Rs 30,000, trains where possible") using tools over a fixed snapshot of a simulated India, and returns one JSON plan, or says the request is infeasible and names why. A deterministic grader recomputes everything from the world: no LLM judge, nothing the agent claims (total cost, score, solved) is trusted.

## What is in it
- **World** (`world.py`, `data.py`): 25 cities, 41 links, trains with IRCTC-style classes (SL, 3A, 2A, CC, 2S), quotas (General 2-60 days ahead, Tatkal the day before, Current same day), AVL / RAC / WL seat status, lower berths; flights; taxis and buses (with seasonal road closure); 6 hotels per city plus houseboats, with lift / ground-floor / diet flags and peak-season pricing; 48 sights with real closing days where public (e.g. Taj Mahal on Fridays), hours, seasons, permits.
- **Tools** (read-only until you answer): `calendar_info`, `search_trains`, `train_availability`, `search_flights`, `search_transfers`, `search_hotels`, `attraction_info`, `list_attractions`, `permit_info`, `finalize_plan`.
- **Tasks** (`tasks.jsonl`, CC BY 4.0): 55 tasks in 10 families (Golden Triangle, Rajasthan, Kerala, Himachal winter, Goa, pilgrimage, Ladakh, North-East, rail booking logic, Hindi / Hinglish prompts); 38 feasible, 17 infeasible. Feasibility is **set by the reference solver, not by hand** (`FLAG_CHANGES.md` lists where it differs from the task designer's intent and why).
- **Rules** (`rules.py`, 17 deterministic rules): R-FMT, R-DATE, R-CONN, R-QUOTA, R-AVAIL, R-OPEN, R-SEASON, R-REST, R-OCC, R-BUD, R-DIET, R-ACC, R-NIGHT, R-HRS, R-ALT, R-PERMIT, R-ROUTE. The agent is told all of them. A plan is **solved** only if every applicable rule passes. A plan that breaks one rule fails that rule and (by test) no other.
- **Infeasible tasks**: answer `{"status": "infeasible", "binding": [...]}`. It counts only if the named rules are a non-empty subset of the true reason; padding with a rule that is not part of the reason is wrong. Any plan given for an infeasible task scores 0.
- **Oracle** (`solver.py`): searches stop order x nights x one service per hop x cheapest compatible hotel x earliest activity slot and checks each candidate with the real grader, so a plan it returns is valid by construction. It confirms every feasible task and, by exhaustive search plus rule relaxation, every infeasible one. It is an upper bound, not a fair baseline (it sees hidden task parameters).

## Run it
```
python -m unittest discover -s tests                                   # no dependencies
python -m navital_gym.cli --env trip --agent heuristic --agent oracle  # scripted baselines
python -m navital_gym.cli --env trip --agent "openai:qwen2.5:7b@http://localhost:11434/v1" --k 3 --out runs/trip-qwen.json   # any OpenAI-compatible endpoint (Ollama etc.)
```
Adapters: `navital_gym/adapters/` has Inspect AI, verifiers (v1 API) and OpenEnv wrappers (optional extras).

## Baselines (k = 3 runs per task; pass@1 = first run solved, pass^3 = all three solved)
| agent | pass@1 | pass^3 | mean rule score | note |
|---|---|---|---|---|
| empty answer | 0.00 | 0.00 | 0.00 | floor |
| always "infeasible" with 3 guessed rules | 0.00 | 0.00 | 0.00 | the claim guard works |
| lazy heuristic planner (reads the prompt, first service of each hop, cheapest hotel) | 0.00 | 0.00 | 0.43 | no checks on seats, quota, diet, rest days |
| reference solver (oracle) | 1.00 | 1.00 | 1.00 | upper bound |
Open-model results are added below as they are run, with exact model, sampling settings and commit (`runs/*.json` keep them).

## Known limitations
- "Infeasible" means no plan in the solver's search space (direct links or links via a hub, one leg per hop, one hotel per night). It is exhaustive within that space, not a proof over all conceivable plans.
- Food is a fixed per-person allowance by hotel tier; ticket prices, fares and permits are synthetic. Children's fares and Tatkal surcharges follow the simplified rules in `rules.py`.
- R-ALT (altitude pacing) is a simplified rule, not medical advice.
- Hindi / Hinglish prompts are a small share (5 of 55).
- The GN 2-60 day window, the 60 / 30 / 120 minute buffers and all prices are this env's own rules.
