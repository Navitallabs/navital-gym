# Baseline results

Each row is ONE run (k=1). The task count is in the table: a 15-task sample has a wide error bar (one task is 6.7 points) and a 5-task sample a very wide one. Easy and standard tasks are separate tiers. Columns: pass@1 = tasks solved by the first run (one format-repair retry is allowed); strict = solved with no repair retry; format fail = the answer was not a readable, valid-format submission; errors = provider failures (not wrong answers); partial credit (first run of each task, like pass@1) = mean fraction of scored rules passed (a well-formed empty answer earns 0). Every row was re-graded without calling any model (scripts/regrade.py); the `graded` column is the id of the grading code.

**Degenerate-baseline note (GST).** On the public GST standard set the built-in `careless` baseline (it reads everything but leaves freight untaxed and ignores the turnover-tiered late-fee cap: two built-in slips) scores 80%. The "every non-oracle baseline solves under 25%" gate therefore holds only for the private held-out sets (where `careless` scores 23%), not for the public GST set.

**Degenerate-baseline note (support).** In the support env the reply language is a hard rule only for the Hindi and Hinglish core (50 tasks). On the 26 experimental Tamil, Bengali and Marathi tasks the language is a soft score and a task is solved on state alone, so the built-in `english` baseline (right actions, English reply) solves 33% of the full 76-task split but 0% of the core. The "under 25%" gate holds for the core and for the private held-out support set (core only), not for the experimental tasks. The 76-task support rows (which include the experimental tasks) and the experimental split entries should be read with that in mind.

**Note on est. USD.** The estimate is only computed for Anthropic and OpenAI, whose per-token prices are in our price table. Gemini and Groq runs used free tiers (0.00). Sarvam's price is not in our price table, so the 0.00 on Sarvam rows means *not estimated*, not that the run was free. The Claude Sonnet 5.5 form and GST rows were first priced at the lower Haiku-level default; their est. USD was multiplied by 2.5 (the Sonnet-to-default price ratio, the same for input and output tokens) to the Sonnet rate.

**Verify it.** The grading code is identified by the git tree id of `navital_gym/` at the release tag v1.0.0. Check with `git rev-parse v1.0.0:navital_gym`: it must start with the id in the `graded` column.

## Small and mid-size models

Most people testing will use models like these, so they come first. Many score low.

| env | model (provider) | tasks | pass@1 | strict | format fail | errors | partial credit | est. USD | date | graded |
|---|---|---|---|---|---|---|---|---|---|---|
| form | claude-haiku-4-5 (anthropic) | 50 | 0.82 | 0.82 | 0% | 0% | 0.90 | 0.52 | 2026-10-27 | 123c1450dab5 |
| form | gemini-3.1-flash-lite (gemini) | 15 | 0.60 | 0.60 | 0% | 0% | 0.82 | 0.00 | 2026-10-27 | 123c1450dab5 |
| form | gpt-4o-mini (openai) | 50 | 0.54 | 0.54 | 0% | 0% | 0.83 | 0.15 | 2026-10-27 | 123c1450dab5 |
| form | openai/gpt-oss-20b (groq) | 15 | 0.80 | 0.80 | 0% | 0% | 0.87 | 0.00 | 2026-10-27 | 123c1450dab5 |
| form | sarvam-105b (sarvam) | 50 | 0.82 | 0.82 | 2% | 0% | 0.95 | 0.00 | 2026-10-27 | 123c1450dab5 |
| form multi-document | claude-haiku-4-5 (anthropic) | 40 | 0.98 | 0.98 | 0% | 0% | 0.99 | 0.84 | 2026-10-27 | 123c1450dab5 |
| form multi-document | gpt-4o-mini (openai) | 40 | 0.33 | 0.33 | 0% | 0% | 0.61 | 0.96 | 2026-10-27 | 123c1450dab5 |
| form multi-document | sarvam-105b (sarvam) | 40 | 1.00 | 1.00 | 0% | 0% | 1.00 | 0.00 | 2026-10-27 | 123c1450dab5 |
| gst | claude-haiku-4-5 (anthropic) | 50 | 0.82 | 0.82 | 0% | 0% | 0.91 | 0.63 | 2026-10-27 | 123c1450dab5 |
| gst | gpt-4o-mini (openai) | 50 | 0.50 | 0.50 | 0% | 0% | 0.69 | 0.11 | 2026-10-27 | 123c1450dab5 |
| gst | sarvam-105b (sarvam) | 50 | 0.78 | 0.78 | 0% | 0% | 0.87 | 0.00 | 2026-10-27 | 123c1450dab5 |
| support | claude-haiku-4-5 (anthropic) | 76 | 0.24 | 0.21 | 0% | 0% | 0.69 | 1.06 | 2026-10-27 | 123c1450dab5 |
| support | gemini-3.1-flash-lite (gemini) | 15 | 0.33 | 0.27 | 0% | 0% | 0.73 | 0.00 | 2026-10-27 | 123c1450dab5 |
| support | gpt-4o-mini (openai) | 76 | 0.09 | 0.09 | 0% | 0% | 0.51 | 0.32 | 2026-10-27 | 123c1450dab5 |
| support | sarvam-105b (sarvam) | 76 | 0.43 | 0.43 | 0% | 0% | 0.78 | 0.00 | 2026-10-27 | 123c1450dab5 |
| trip | claude-haiku-4-5 (anthropic) | 55 | 0.31 | 0.29 | 0% | 0% | 0.73 | 8.40 | 2026-10-27 | 123c1450dab5 |
| trip | gemini-3.1-flash-lite (gemini) | 15 | 0.20 | 0.20 | 7% | 0% | 0.58 | 0.00 | 2026-10-27 | 123c1450dab5 |
| trip | gpt-4o-mini (openai) | 55 | 0.05 | 0.05 | 7% | 0% | 0.28 | 2.30 | 2026-10-27 | 123c1450dab5 |
| trip | sarvam-105b (sarvam) | 55 | 0.20 | 0.15 | 13% | 0% | 0.54 | 0.00 | 2026-10-27 | 123c1450dab5 |
| upi | claude-haiku-4-5 (anthropic) | 50 | 0.42 | 0.42 | 0% | 0% | 0.67 | 0.96 | 2026-10-27 | 123c1450dab5 |
| upi | gemini-3.1-flash-lite (gemini) | 15 | 0.60 | 0.60 | 0% | 0% | 0.87 | 0.00 | 2026-10-27 | 123c1450dab5 |
| upi | gpt-4o-mini (openai) | 50 | 0.18 | 0.18 | 16% | 0% | 0.47 | 0.22 | 2026-10-27 | 123c1450dab5 |
| upi | sarvam-105b (sarvam) | 50 | 0.52 | 0.52 | 6% | 0% | 0.77 | 0.00 | 2026-10-27 | 123c1450dab5 |
| gst (easy) | claude-haiku-4-5 (anthropic) | 18 | 1.00 | 1.00 | 0% | 0% | 1.00 | 0.12 | 2026-10-27 | 123c1450dab5 |
| gst (easy) | gpt-4o-mini (openai) | 18 | 0.94 | 0.94 | 0% | 0% | 0.94 | 0.02 | 2026-10-27 | 123c1450dab5 |
| gst (easy) | openai/gpt-oss-120b (groq) | 18 | 0.94 | 0.94 | 6% | 0% | 0.94 | 0.00 | 2026-10-27 | 123c1450dab5 |
| gst (easy) | openai/gpt-oss-20b (groq) | 18 | 1.00 | 0.94 | 0% | 0% | 1.00 | 0.00 | 2026-10-27 | 123c1450dab5 |
| gst (easy) | sarvam-105b (sarvam) | 18 | 1.00 | 1.00 | 0% | 0% | 1.00 | 0.00 | 2026-10-27 | 123c1450dab5 |
| support (easy) | openai/gpt-oss-120b (groq) | 18 | 0.00 | 0.00 | 0% | 0% | 0.76 | 0.00 | 2026-10-27 | 123c1450dab5 |
| support (easy) | openai/gpt-oss-20b (groq) | 18 | 0.00 | 0.00 | 0% | 0% | 0.73 | 0.00 | 2026-10-27 | 123c1450dab5 |
| trip (easy) | claude-haiku-4-5 (anthropic) | 18 | 0.67 | 0.67 | 0% | 0% | 0.95 | 0.95 | 2026-10-27 | 123c1450dab5 |
| trip (easy) | gpt-4o-mini (openai) | 18 | 0.06 | 0.00 | 0% | 0% | 0.59 | 0.22 | 2026-10-27 | 123c1450dab5 |
| upi (easy) | claude-haiku-4-5 (anthropic) | 18 | 0.61 | 0.56 | 0% | 0% | 0.83 | 0.33 | 2026-10-27 | 123c1450dab5 |
| upi (easy) | gpt-4o-mini (openai) | 18 | 0.33 | 0.33 | 28% | 0% | 0.59 | 0.06 | 2026-10-27 | 123c1450dab5 |

## Larger model, for reference (Claude Sonnet 5.5)

What a strong model reaches. Not the typical user's model.

| env | model (provider) | tasks | pass@1 | strict | format fail | errors | partial credit | est. USD | date | graded |
|---|---|---|---|---|---|---|---|---|---|---|
| form | claude-sonnet-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 1.00 | 1.19 | 2026-10-27 | 123c1450dab5 |
| form multi-document | claude-sonnet-5-5 (anthropic) | 40 | 1.00 | 1.00 | 0% | 0% | 1.00 | 1.05 | 2026-10-27 | 123c1450dab5 |
| gst | claude-sonnet-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 1.00 | 1.53 | 2026-10-27 | 123c1450dab5 |
| support | claude-sonnet-5-5 (anthropic) | 76 | 0.66 | 0.66 | 0% | 0% | 0.90 | 2.71 | 2026-10-27 | 123c1450dab5 |
| trip | claude-sonnet-5-5 (anthropic) | 55 | 0.58 | 0.49 | 0% | 0% | 0.92 | 14.64 | 2026-10-27 | 123c1450dab5 |
| upi | claude-sonnet-5-5 (anthropic) | 50 | 0.68 | 0.68 | 0% | 0% | 0.92 | 2.69 | 2026-10-27 | 123c1450dab5 |

## Do the difficulty labels separate small and mid-size models?

Tasks solved / tried by the designers' difficulty label (designer intent, not calibrated; all shown rows together). If the columns are close the labels do not predict who solves what.

| model | difficulty 1-2 | difficulty 3 | difficulty 4-5 |
|---|---|---|---|
| claude-haiku-4-5 | 64/119 | 62/117 | 92/139 |
| gemini-3.1-flash-lite | 6/17 | 11/27 | 9/16 |
| gpt-4o-mini | 43/119 | 35/117 | 30/139 |
| openai/gpt-oss-120b | 17/36 | 0/0 | 0/0 |
| openai/gpt-oss-20b | 20/38 | 7/9 | 3/4 |
| sarvam-105b | 49/83 | 67/117 | 92/139 |

