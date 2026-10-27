# Form Desk: hard (experimental split)
A harder companion to Form Desk, added because the standard Form Desk is **saturated for the strongest model we ran** (Sonnet 5.5 solves all 50 tasks after the address-field definition fix). "Harder" was a design goal, and the measured results are mixed: on the 40 standard tasks, one run each, gpt-4o-mini solves 0.33 (0.54 on Form Desk), but Claude Haiku 4.5 (0.98) and Sarvam 105B (1.00) score higher here than on Form Desk (0.82 each), and Claude Sonnet 5.5 solves all of both. See docs/RESULTS.md.

40 tasks, 5 families x 8. Every answer field is defined in the prompt. Exact-match grading, one rule per answer field, from an independent oracle. No language model judges anything. All people, documents and numbers are synthetic; no Aadhaar numbers.

| Family | What the agent gets | What it must do |
|---|---|---|
| `multi_doc` | PAN card, passbook header and application form for one applicant | find which of name, dob, pan disagree with the PAN card (names compared by surname and given names or initials, dates in three written formats), report the card's name and dob, and flag manual review |
| `pan_name` | applicant name, entity type and quoted PAN | check the PAN's holder-type and first-letter structure against the name and entity type |
| `record_conflicts` | one form with DOB, stated age, minor box, PIN, state, IFSC, bank | find which checks fail (age, minor, pin_state, bank) and give the true age and minor flag |
| `ocr_repair` | OCR text with look-alike mistakes in a PAN and an IFSC | repair a character only where the format and the look-alike table make the fix unique, otherwise return null |
| `batch` | six applicant records | count minors, list invalid PANs, list records eligible for a current account |

Rules are env rules (simplified; the PAN structure and IFSC bank-code facts are public format facts, to be dated and verified by review). Lists are graded as sets with each item at most once. Reported separately from the 50 core Form tasks, never mixed with them.
Private held-out set: the generator (not part of this repository) takes a private seed from `FORM_HARD_SEED`, which is never committed; the committed tasks do not depend on it (tested).
Status: oracle agrees with the generator on all 40; qa hand-solved all 40 independently from the prompt and policy and agreed on all 40; scripted floors empty 0%, reject_only 0%, prior 15%. Model results are in the leaderboard and `docs/RESULTS.md`.
Use: `from navital_gym.envs.form_multidoc import load_env, grade`; rebuild tasks with `python -m navital_gym.envs.form_multidoc.build_tasks`. Tests: `tests/test_form_multidoc.py`.
