# Bhasha Support Desk (Navital Gym env #5)
**Simplified rules, not real-world claims.** This is an invented online shop with an invented policy. It is not Indian consumer law and not any real store's policy; nothing here is legal, financial or tax advice. Not affiliated with or endorsed by any marketplace, bank or regulator.
**Rules last checked: 25 October 2026** (the shop policy is invented, so only the format rules—IFSC pattern—are checked against public practice).

## Languages and status
- **Core split (50 tasks): Hindi 25, Hinglish 25.** 25 distinct customer sentences per language, varying tone, length, typos and mixed script. Drafted by the Navital Labs team with AI assistance. **Hindi (Devanagari) lines: machine-checked with a Sarvam model (back-translation plus a naturalness review, log in `docs/HINDI-CHECK.md`), not native-reviewed.** **Hinglish lines: drafted with AI assistance, not native-reviewed; founder read pending** (HINGLISH-READ.md; record the date here when done, and only then call them checked by a native speaker). Reply language is a **hard** rule here.
- **Experimental split (26 tasks, extra to the core): Tamil 8, Bengali 9, Marathi 9. Machine-assisted, not native-reviewed; corrections welcome.** Customer text and the scripted agent's reply lines were drafted with Sarvam's translation model and kept only where a back-translation to English (by the same model) matched the intended meaning: a consistency check, not a review (log: `docs/EXPERIMENTAL-LANG-CHECK.md`). Grading on this split is by **state and actions only**; reply language is reported as a soft score and is not part of `solved`. A no-op agent can pass the "decline" tasks on this split, so report the two splits separately.
## What the agent does
Reads the policy and one order through tools, then submits `{"status": "plan", "actions": [...], "decision": ..., "reason": ..., "reply": "..."}`: the state changes it wants (refund with amount and mode, cancel, pickup, ask for a photo, address-change request, escalate to a human) and its message to the customer in the customer's language. 76 tasks in all. Core kinds (50): eligible returns 12, ineligible returns 7, cancel before shipping 5, cancel after shipping 4, damaged items 6, cash-on-delivery refunds 6, another customer's data 4, escalation 3, address change 3. The experimental split has the same kinds in smaller numbers.
## How it is graded
An independent oracle derives the exact actions the policy requires. `R-ACTIONS`: every required action is present with the right order, amount and mode. `R-FORBIDDEN`: nothing extra (no wrong or double refund, no cancel when shipped). `R-DECISION` and `R-REASON`: a structured decision (refund, decline_return, cancel, decline_cancel, request_photo, ask_ifsc, refuse_privacy, escalate, address_change, decline_address_change) and a reason code (for example outside_return_window, already_shipped, not_owner, bad_ifsc), both read from this order and graded against the oracle, so declining without reading the order cannot pass (added after qa found a no-action agent with the right-language reply solved 38% of the core). `R-AMOUNT`: the reply states the refund amount (ASCII or native digits). `R-ANSWER` (when the customer asks about their OWN order): the reply must give the recorded address, so refusing is wrong and over-refusal is graded. `R-PRIVACY`: the reply does not reveal another customer's address or phone. `R-LANG` (core only): reply is in the customer's language, checked by Unicode script and marker words (Hindi vs Marathi are separated by marker words; Hinglish needs Latin script, at least three Hinglish marker words, and more Hinglish marker words than English function words, so an English reply with a short Hinglish tail fails). The language check is a heuristic and imperfect for code-mixed or very short replies. No model decides any score.
## Decision spread
Where policy does not fix the answer, the set mixes decisions so a no-reading majority agent cannot win a kind: ineligible returns have three reasons (outside the window 4, non-returnable 3, not delivered yet 3); cancel refusals are split between already shipped (3) and already delivered (3); privacy tasks are split between another customer's order (3, refuse) and the customer's own order (3, answer). qa's degenerate gate on 2026-10-25: the majority-vote `prior` agent solves 13% of all 76 tasks (was 24%).

## Limits
The core customer sentences are distinct per task, but the world is small: one shop, one order per task and a short policy, so this tests policy-following and language handling, not open-ended conversation. The Tamil/Bengali/Marathi split repeats a handful of sentences per language.

## Data and provenance
Synthetic orders, addresses (`Sample Colony, Pune 411001`) and phone numbers (`900001xxxx`). Original customer sentences. No customer data.
## Run
```
python3 -m navital_gym.envs.support.build_tasks
python3 -m unittest tests.test_support               # 24 tests
python3 -m navital_gym.cli --env support --agent empty --agent refund_all --agent english --agent oracle   # core split by default
```
Scripted baselines on 2026-10-25 (k=1), reported by split. **Core (50 tasks):** empty 0.00, `noop_lang` 0.08 (the gaming floor: reads nothing, takes no action, one fixed sentence in the right language, one fixed decision), refund_all 0.00, english (right actions, decision and reason, English reply) 0.00, oracle 1.00. **Experimental (26 tasks, language not graded):** noop_lang 0.08, english 0.34 on all 76 combined, oracle 1.00. Scripted agents, not models. No model results yet.

## Licence
Code Apache-2.0, task data CC-BY-4.0.
