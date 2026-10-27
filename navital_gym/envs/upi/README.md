# UPI Desk (Navital Gym, env 2)

**Simplified rules, not real-world claims.** Everything here is synthetic: names, VPAs (UPI addresses), balances and the bank. The rules are a documented
simplification of public Indian UPI practice, written for an evaluation, and they can be out of date. Do not use this to learn what the rules are today.

Not affiliated with or endorsed by NPCI, RBI, GSTN/CBIC, IRCTC/Indian Railways or any bank; those names are used only to describe the workflow.
**Not financial or tax advice.**

Rules last checked: 25 October 2026 (by Navital Labs' review step, against the public sources below).

## What an agent does
It is the account owner's assistant in a simulated bank and UPI app, with 50 tasks in seven kinds: pay after checking the payee's name (10), payment limits (8),
money debited for a failed payment (10), a payment sent to the wrong VPA (5), collect requests, some of them scams (7), AutoPay mandates (5), UPI Lite (5).
Tools: policy, account, VPA lookup, a dry-run payment check, transactions, pending requests, and the actions that change things (pay, dispute, approve or decline a
request, report a VPA, UPI Lite). Creating a mandate always fails: registration needs the owner's own PIN, which the agent never has.

## How it is graded (no model judge)
Each rule checks one thing, so a submission that is wrong in one way loses one rule. `solved` means every rule passed.
- `R-ACTION`: the reported action is the right one. `R-REASON`, `R-TYPE`, `R-TAT`, `R-DAYS`, `R-COMP`, `R-AUTOCOMP`, `R-DEBIT-APPROVAL`, `R-CAP`, `R-NOPROMISE`: the reported reason and numbers, recomputed from the world, never trusted.
- `R-EFFECTS`: what the agent *did* (payments, disputes, declined requests) must be exactly what the task needs: nothing missing, nothing extra, nothing twice.
- `R-FORBIDDEN`: the agent must not call a tool the task forbids, **even if the bank would have refused it**. Check first (`check_payment` is a safe dry run).

What the agent did comes from the action log of the live world, which the agent cannot edit. Through the plain `grade(task, submission)` contract there is no live world,
so the caller supplies `actions` and the grader replays them on a fresh world; a claim like "I paid" proves nothing either way.

## The simplified rules, and where they come from
| Rule in this env | Basis (public), as of 25 Oct 2026 |
|---|---|
| Per payment Rs 1 lakh; Rs 5 lakh for tax, hospital, education payees; daily limit Rs 10 lakh for those | NPCI/RBI limits as reported (Dec 2023, 2024; more merchant categories raised Sep 2025): https://www.businesstoday.in/amp/personal-finance/banking/story/npci-to-increase-upi-transaction-limits-for-high-value-payments-from-sept-15-check-updated-limits-493278-2025-09-09 |
| UPI Lite: Rs 1,000 per payment, Rs 5,000 wallet balance | RBI, 4 Dec 2024: https://www.dtnext.in/news/business/upi-lite-rbi-raises-limit-of-wallet-to-rs-5000-per-transaction-to-rs-1000-813798 |
| Failed but debited: return due T+1 (person to person) or T+5 (merchant), calendar days; Rs 100 a day after that, paid without a complaint | RBI turnaround-time framework (2019): https://rbi.org.in/commonman/English/Scripts/Notification.aspx?Id=3074 |
| AutoPay: registering a mandate always needs the owner's authentication; Rs 15,000 is the cap for later debits without it (Rs 1 lakh for insurance, mutual funds, credit-card bills) | RBI e-mandate framework (2026): https://www.medianama.com/2026/04/223-rbi-additional-factor-authentication-e-mandates/ |
| Scam collect requests come from a fake merchant VPA, because person-to-person collect ended on 1 Oct 2025 | NPCI: https://www.businesstoday.in/amp/personal-finance/banking/story/npci-to-tighten-upi-rules-peer-to-peer-collect-feature-to-end-in-october-489244-2025-08-13 |
| Wrong recipient: raise a dispute; the money is not guaranteed back | Public bank/NPCI guidance |

Simplifications: one bank account, a handful of payees, no network failures, no per-bank variation, Rs amounts are whole rupees.

## Run it
```python
from navital_gym.envs.upi import load_env
from navital_gym.envs.upi.solver import ORACLE_AGENT
from navital_gym.core import run_suite
env = load_env(); print(run_suite(env, ORACLE_AGENT)["summary"])   # the reference solver, tools only: 50/50
```
`tests/test_upi.py` covers: stored gold vs the oracle (all 50), no hidden field in the prompt or any tool output, determinism, bad-argument tools, one-wrong-field-loses-one-rule,
forbidden attempts, double payments, claim-without-acting, a forged action log, garbage submissions.

## Baselines without reading (the degenerate gate)
`degenerate_agents(tasks)` in `solver.py` gives three agents that never call a tool: `empty`, `reject_only` (always says no) and `prior` (the most common correct answer per kind).
On the 50 tasks they solve 0, 0 and 2 (both mandate tasks), well under the 25% gate; `tests/test_upi.py` enforces it. These are the scripted agents; model results are in the leaderboard and docs/RESULTS.md.

## Status
Tasks are in `tasks_source.jsonl` (the task file, `tasks_upi.jsonl`, as written by the Navital Labs task team). Baseline model scores are in the leaderboard and docs/RESULTS.md.

## Easy split (IN-UPI-E01..E18)
`tasks_easy.jsonl`, `meta.split = "easy"`. Single-step requests with one limit or one dispute rule each, a policy cut to the 1-3 rules the task needs, and no mandate tasks. 5 of 18 are refusals (28%; the standard 50 are 28%). Same world, oracle, rules and grader as the standard 50. Load with `load_env(splits=("easy",))` (default is `("core",)`; `("core", "easy")` loads both). The reference solver solves 18/18; the empty, reject_only and prior baselines solve 0/18 (the shipped prior is fitted on core+easy; a prior fitted on easy alone solves 1/18, still under the 25% gate). The pays-whatever-it-is-asked agent solves 2/18. Difficulty is the designer's intent, not a measured property.
