# Form Desk (Navital Gym env #4)
**Simplified rules, not real-world claims.** Form Desk is a small simulated setting for Indian form-filling tasks. Its rules are a documented simplification of public identifier formats and conventions; nothing here is a live system, and nothing is financial or tax advice. Not affiliated with or endorsed by NPCI, RBI, GSTN/CBIC, Indian Railways/IRCTC, India Post, UIDAI or any bank; names appear only to describe the workflow.
**Rules last checked: 25 October 2026** (review gate 2026-10-25: PAN pattern, IFSC pattern, mobile rule (a leading +91 / 91 / 0 is stripped; any other length is invalid, never repaired), PIN-zone table, financial-year and advance-tax dates).
**Standard Form Desk is saturated for the strongest model we ran** (Sonnet 5.5 solved all 50 tasks after the address-field definitions were added), so it separates weaker models but not the top. A harder companion split is in `../form_multidoc/` (experimental, reported separately).

## What the agent does
Fills KYC fields from messy document text, parses Indian addresses, checks a PIN against a state's postal zone, converts Indian number idioms ("सवा दो लाख", "2.5 lakh") to integers, and gives the financial year, assessment year and next advance-tax date. 50 tasks: KYC 15, address 12, PIN/state 8, numbers 10, fiscal-year dates 5.
## How it is graded
One rule per answer field; the expected value comes from an independent oracle (`oracle.py`), never from the task file. Invalid values (a PAN, IFSC or mobile that fails its format rule) must be reported as `null`, not repaired. A submission wrong in one field loses exactly that rule. No model decides any score.
## Data and provenance
Synthetic names, documents and addresses. PAN/IFSC/mobile/PIN are public formats; the 14 city–PIN pairs are well-known first-level PINs. **No Aadhaar numbers exist anywhere in this env.** No customer data. The postal-zone table lists the states used by the tasks and is not complete (for example it omits Sikkim, the other North-Eastern states and Ladakh). "Minors cannot open current accounts" is an env rule.
## Run
```
python3 -m navital_gym.envs.form.build_tasks         # rebuild tasks.jsonl from the task source file
python3 -m unittest tests.test_form                  # 14 tests
python3 -m navital_gym.cli --env form --agent empty --agent shotgun --agent naive --agent oracle
```
Scripted baselines on 2026-10-25 (pass@1, k=1), overall and per kind (solved / tasks). Kinds: KYC 15, address 12, PIN/state 8, numbers 10, fiscal year 5.
| agent | overall | KYC | address | PIN/state | numbers | fiscal year |
|---|---|---|---|---|---|---|
| empty | 0.00 | 0 | 0 | 0 | 0 | 0 |
| shotgun (fixed guesses) | 0.08 | 0 | 0 | 4 | 0 | 0 |
| naive (weak: no validation, shallow parsing) | 0.32 | 2 | 5 | 4 | 3 | 2 |
| reject_only (reports every identifier and PIN as invalid or null, every amount as 0) | 0.18 | 2 | 3 | 4 | 0 | 0 |
| oracle | 1.00 | 15 | 12 | 8 | 10 | 5 |

`naive` copies identifiers without validating them, trusts the state abbreviation, always says a PIN is consistent, parses only digit-style amounts and treats the calendar year as the financial year; it is not the oracle. **The mix is deliberately weighted toward invalid identifiers (13 of 15 KYC documents have an invalid PAN, IFSC or mobile; 7 of 12 addresses lack a state abbreviation or have a malformed PIN); it is not a real-world rate.** The tasks were rebalanced on 2026-10-25 after qa found a validation-skipping agent solved 76%. PIN/state pairs are 4 consistent : 4 inconsistent. Scripted agents, not models. No model results yet.

## Limits
Exact-match grading is strict by design. The world has no seeded randomness (the input is the task), so seeds do not change it. Task text is English except the Hindi idiom items.
## Licence
Code Apache-2.0, task data CC-BY-4.0.
