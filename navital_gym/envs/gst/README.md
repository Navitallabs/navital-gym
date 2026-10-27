# GST Desk (Navital Labs India Agent Suite, env 3)

Model results for this env are in the leaderboard and `docs/RESULTS.md`.

> **Read this first.**
> - **Not affiliated with, endorsed by, or connected to GSTN, CBIC, the GST Council or any government body.**
> - **Not tax advice.** This is a test environment for AI agents. Do not use it, or an agent's answers on it, to file returns or make tax decisions.
> - **Simplified rules.** The tasks use a deliberately simplified version of Indian GST, written down in full below and shipped inside every task. They are env rules, not claims about what the law says today, and they leave out much of the real law (no QRMP, no state-specific rules, no reverse charge, no cess, no 180-day or payment conditions on credit, no amendments, no composition-scheme maths).
> - **Rules as of 25 October 2026.** GST rates, thresholds, fees and notifications change often. Where a rule mirrors public practice, the source is listed under "Sources". Anything not listed is an env choice.
> - **All data is synthetic.** Businesses, GSTINs, invoices and registers are generated. GSTINs have a valid check character by the public mod-36 method on fake PAN-shaped bodies; none belongs to a real taxpayer. No customer data and no copied dataset is used.

## What it tests

An agent gets a short accounting question and must read the task's documents and policy through tools, do exact decimal arithmetic, and return a structured answer. Scoring is a deterministic check against a reference solver. There is no LLM judge anywhere in the score.

| Kind | Tasks | What the agent must produce |
|---|---|---|
| `invoice` | 15 | taxable value, CGST, SGST, IGST, round-off, invoice total, tax type |
| `place_of_supply` | 8 | which tax applies when the billed state and the delivery state differ |
| `itc_reconciliation` | 10 | eligible input tax credit and the invoices it comes from |
| `late_filing` | 10 | GSTR-3B due date, days late, late fee, interest |
| `threshold` | 7 | e-invoice / e-way bill required, or composition eligible (yes/no) |

50 tasks, all in English in v0. The `difficulty` field in the task file is the author's estimate, not a measurement.

## The simplified rules (these ship in every task as `get_policy`)

- **Rates by item code** (synthetic codes): `G-FOOD` 0%, `G-FAB` 5%, `G-TOY` 5%, `G-ELEC` 18%, `S-CONS` 18%, `G-LUX` 40%. (Slabs follow the 0/5/18/40 structure announced for 22 Sep 2025; the codes themselves are made up.)
- **Line tax**: line value = quantity x unit price x (1 - discount %), rounded to 2 decimals half-up; tax on each line rounded to 2 decimals half-up.
- **Freight and packing** on the invoice are taxed at the **highest rate among the invoice's lines**. *This is an env rule* (mixed-supply style). In real GST, freight on the same invoice is usually taxed at the principal supply's rate.
- **Intra-state** (supplier state = place of supply): CGST and SGST, each half of the total tax (CGST rounded half-up, SGST the remainder). **Inter-state**: IGST.
- **Rounding**: invoice total is rounded to the nearest rupee, with the difference shown as `round_off`.
- **Place of supply** when goods are delivered to a third person on the billed party's direction: the **billed party's** state (IGST Act s.10(1)(b)).
- **Input tax credit** is allowed only if the invoice appears in GSTR-2B, the goods were received, and the category is not blocked (`motor_vehicle_personal`, `food_beverage`, `club_membership`).
- **GSTR-3B due date**: the 20th of the next month. **It does not move for weekends or holidays** (the real due date changes only by official notification).
- **Late fee**: Rs 50 per day (Rs 20 per day for a nil return), capped by annual turnover: up to Rs 1.5 crore Rs 2,000; up to Rs 5 crore Rs 5,000; above that Rs 10,000; nil return Rs 500.
- **Interest**: 18% a year on the net tax paid late, times days late / 365, rounded to 2 decimals.
- **Thresholds**: e-invoice required above Rs 5 crore turnover; e-way bill required above Rs 50,000 consignment value; composition scheme allowed up to Rs 1.5 crore turnover. The tasks ask only the yes/no question stated.

## What the agent sees

Only the task `prompt` and these read-only tools. It never sees `gold_answer`, `meta`, the reference solver or any designer note (a test enforces this for all 50 tasks).

| Tool | Returns |
|---|---|
| `get_documents` | the invoice or purchase register for the task (empty if the prompt has everything) |
| `get_policy` | the simplified rules above, as data |
| `lookup_rate(code)` | the rate for an item code |
| `validate_gstin(gstin)` | whether a GSTIN has the right shape and check character, and its state |
| `calendar_info(date)` | weekday and listed-holiday status (informational; due dates do not move) |

The agent finishes with `{"status": "plan", "answer": {...}}` (a bare answer object is also accepted). Numbers may be strings or numbers; dates are `YYYY-MM-DD`; yes/no is `true`/`false`.

## Scoring

- One rule per answer field, so an answer wrong in exactly one field fails exactly one rule. A task is **solved** only if every applicable rule passes. The score is the fraction of rules passed (1.0 when solved).
- Money, counts and tax amounts: exact decimal equality (no tolerance). Dates: exact. Text such as the tax type: case- and whitespace-insensitive but otherwise exact. Booleans must be real booleans. Invoice lists are compared as sets.
- A malformed answer scores 0 and never crashes the grader. Fields the agent claims about itself (score, solved, totals it computed) are ignored.
- Reference solver: an independent implementation of the rules above (`oracle.py`). The grader checks against it, and the stored `gold_answer` of every task is cross-checked against it (`check_gold`), so a wrong gold shows up as a disagreement.

## How it was tested

- All 50 stored gold answers score 1.0, and the reference solver matches all 50.
- 9 tasks were solved by hand (not from the solver or the gold) and score 1.0; for each, a copy wrong in only one field loses only that rule. Place of supply is covered in both directions, and the turnover-tiered late-fee cap and the nil-return cap are covered.
- Cheating attempts (empty, null, wrong types, copying the prompt, claimed scores, flipping to "infeasible") do not solve. A grader that ignores blocked credit categories is caught by the same suite.
- Re-running gives identical scores and identical world fingerprints; JSON key order does not matter; the grader never changes its inputs.
- Run it: `./run.sh gst_adapter:grade --path adapters --env gst` and `python3 -I gst_checks.py` from the `harness/` folder of the repository.

## Baselines
Scripted baseline agents (model results are in the leaderboard and docs/RESULTS.md, with exact model, sampling settings and k). On the 50 tasks, one run of each:

| agent | pass@1 | mean rule score | what it is |
|---|---|---|---|
| empty answer | 0.00 | 0.29 | floor. The nonzero mean is partial credit for a valid-format empty object (format gate counted as a passed rule) |
| reject_only | 0.08 | 0.45 | answers false / null / 0 / [] everywhere (worth 0.08 because some answers really are "no") |
| careless | 0.80 | 0.94 | reads the documents and does the arithmetic, but leaves freight untaxed and always applies the lowest late-fee cap: only the invoice-with-freight and late-fee tasks catch it |
| reference solver (oracle) | 1.00 | 1.00 | upper bound; reads hidden task data |

Use `solved`/pass@1, not the mean rule score, as the headline number: partial credit rewards a well-formed but wrong answer. Nothing here claims how hard the tasks are for any model.

## Known limitations

- English only; 50 tasks; one fixed set of rules (no versions by date).
- Synthetic item codes, not real HSN/SAC codes. State list is 8 states.
- Several real GST features are intentionally absent (see the box at the top). A real accountant would need to handle them.
- `gstr1_due_day` exists in the policy but no v0 task asks about GSTR-1.
- Exact-match text fields (e.g. `CGST+SGST`) are strict about spelling; the instructions give the expected form.

## Sources (for rules that mirror public practice; accessed 25 Oct 2026)

- GST rate slabs from 22 Sep 2025: Thomson Reuters, "Resetting the tax landscape: inside India GST 2.0" (Oct 2025); GST Council coverage (Sep 2025).
- Place of supply, bill-to/ship-to, IGST Act s.10(1)(b): ClearTax and Avalara explainers on third-party delivery.
- No automatic due-date shift; extensions only by notification: CBIC notifications on GSTR-3B extensions (e.g. Oct 2025).
- GSTR-3B late fee and caps: CBIC Notification 19/2021-Central Tax.

## Licence

Code: Apache-2.0 (`LICENSE`). Task data: CC BY 4.0 (`LICENSE-DATA`).
