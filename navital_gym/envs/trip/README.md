# Env #1: Indian trip planning under real constraints

> **Simplified rules, not real-world claims.** This is a simulation with synthetic prices, timetables, seat counts and hotels, built from public knowledge of Indian rail, road, air and tourism practice and simplified so it can be graded exactly. Nothing here states what a real railway, airline or hotel does today. Not affiliated with or endorsed by IRCTC / Indian Railways or any airline, hotel or tourism body; names are used only to describe the workflow. Rules as of 31 Oct 2026 (Tatkal Aadhaar OTP, Ladakh fee, general-quota window reviewed 31 Oct 2026).

An agent plans a multi-city trip from a short prompt ("Plan a 4-day trip Delhi -> Agra -> Jaipur starting 2026-12-05 for 2 adults and a child aged 8, total budget Rs 30,000, trains where possible") using tools over a fixed snapshot of a simulated India, and returns one JSON plan, or says the request is infeasible and names why. A deterministic grader recomputes everything from the world: no LLM judge, nothing the agent claims (total cost, score, solved) is trusted.

## What is in it
- **World** (`world.py`, `data.py`): 25 cities, 41 links, trains with IRCTC-style classes (SL, 3A, 2A, CC, 2S), quotas (General 60 days to 1 day ahead, Tatkal the day before, which needs the traveller's Aadhaar OTP so the agent can only mark `traveller_otp` and cannot complete it, Current same day), AVL / RAC / WL seat status, lower berths; flights; taxis and buses (with seasonal road closure); 6 hotels per city plus houseboats, with lift / ground-floor / diet flags and peak-season pricing; 48 sights with real closing days where public (e.g. Taj Mahal on Fridays), hours, seasons, permits.
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
- Food is a fixed per-person allowance by hotel tier; ticket prices and fares are synthetic. Nubra and Pangong need the Ladakh environment fee and Red Cross fee (Indian nationals; no Inner Line Permit since 2021); the Rs 400 is this env's figure (2021 reports: Rs 300 + Rs 100; check the LAHDC portal) and Pangong Lake has no separate ticket. Since v1.1 a night in Nubra or Pangong also needs the fee: this env treats it as one fee for the protected areas per trip, paid with any Nubra or Pangong visit marked `fee_paid: true` (a simplification; per-area and overnight-only details of the real fee are not modelled). Children's fares and Tatkal surcharges follow the simplified rules in `rules.py`. Child fares are simplified: a child aged 5-11 without a berth pays half the whole fare, including Tatkal legs. Real rules charge reservation and superfast charges in full and may not allow the concession on Tatkal; no task combines Tatkal with children.
- R-ALT (altitude pacing) is a simplified rule, not medical advice.
- Hindi / Hinglish prompts are a small share (5 of 55).
- The GN 1-60 day window (in reality General quota stays open until the chart is prepared; on the day itself this env allows Current only, which in reality opens when the chart is prepared, the previous evening for morning trains), the 60 / 30 / 120 minute buffers (plus 30 minutes before a sight after arriving in its city, and hill roads closing 20:00-05:00 from November to March) and all prices are this env's own rules, all stated in the prompt's rule list. IN-TRIP-023 and 043 stay Tatkal tasks because the general quota is sold out on those corridors and dates (a world state, `SOLD_OUT`).

- Sight data is synthetic and differs from reality in places: the Taj Mahal ticket is the foreigner fare (Indians pay much less), Ram Mandir darshan is shown as morning only, and Rohtang Pass has no permit flag. Prices and hours are labelled synthetic; the rules do not depend on these figures being real.

## Sources for rules that mirror public practice (accessed 31 Oct 2026)
- Advance reservation period 60 days from 1 Nov 2024: Railway Board circular of 16 Oct 2024 (reported: https://theprint.in/india/railways-reduces-time-limit-for-advance-train-reservation-to-60-days/2316015). General quota staying open until the chart is prepared is common IRCTC practice; no circular was found, so it is stated as an env simplification.
- Aadhaar authentication for online Tatkal from 1 Jul 2025 and Aadhaar OTP from 15 Jul 2025: https://thesouthfirst.com/news/from-1-july-aadhaar-authentication-mandatory-for-tatkal-bookings-on-irctc-website-and-app ; https://angelone.in/news/market-updates/irctc-tatkal-bookings-aadhaar-verification-required-from-july-1
- No Inner Line Permit for Indian nationals in Ladakh since 6 Aug 2021; environment fee and Red Cross fee instead (2021 reports Rs 300 + Rs 100): https://www.deccanherald.com/amp/story/india/indian-citizens-no-longer-need-inner-line-permit-to-visit-protected-areas-in-ladakh-1017167.html ; https://voiceofladakh.in/2021/08/indian-nationals-no-longer-need-permit-to-visit-protected-areas-of-ladakh/
