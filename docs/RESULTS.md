# Baseline results

Each row is ONE run (k=1). The task count is in the table: a 15-task sample has a wide error bar (one task is 6.7 points) and a 5-task sample a very wide one. Easy and standard tasks are separate tiers. Columns: pass@1 = tasks solved by the first run (one format-repair retry is allowed); strict = solved with no repair retry; format fail = the answer was not a readable, valid-format submission; errors = provider failures (not wrong answers); length cut-off = number of UNSOLVED tasks whose first attempt hit the model's output-token limit before a final answer (the one format-repair retry is allowed, and a task it still solved is not counted; a model with many cut-offs may be under-scored; Sarvam's limit is 32,000 tokens and a reasoning model can spend all of it thinking); partial credit (first run of each task, like pass@1) = mean fraction of scored rules passed (a well-formed empty answer earns 0). Every row was re-graded without calling any model (scripts/regrade.py); the `graded` column is the id of the grading code.

**Degenerate-baseline note (GST).** On the public GST standard set the built-in `careless` baseline (it reads everything but leaves freight untaxed and ignores the turnover-tiered late-fee cap: two built-in slips) scores 80%. The "every non-oracle baseline solves under 25%" gate therefore holds only for the private held-out sets (where `careless` scores 23%), not for the public GST set.

**Degenerate-baseline note (support).** Since v1.0.1 the reply language is a hard rule on all 76 support tasks (Tamil and Bengali by script, Marathi also by two Marathi marker words; Hindi and Hinglish as before). In v1.0.0 it was hard only for the 50-task Hindi and Hinglish core and the 26 Tamil, Bengali and Marathi tasks were solved on state alone, so the built-in `english` baseline (right actions, English reply) solved 33% of the full split; it now solves 0%. The built-in `noop_lang` floor (reads nothing, no action, one fixed sentence in the right language) solves 5% of the 76 tasks. Every non-oracle scripted baseline is under 25% on the core, the experimental tasks and the full split. Rows graded under v1.0.0 were re-graded by replay at the v1.0.1 grader, so every support row follows the hard rule. For Hindi, Marathi, Bengali and Tamil at least 70% of the reply's letters must be in the customer's script, so a reply in the right language that is heavily mixed with English words fails by design (the same threshold has applied to the Hindi core since v1.0.0). The check is a heuristic and is not a native-speaker review.

**Note on the Sarvam final answer (json_object).** The run settings of every row say `json_mode_on_final: true`. For Sarvam this was not applied on the final call: Sarvam rejects a tool-free call once the history holds tool messages, so the harness re-sends the tools with `tool_choice: none` and drops `response_format`. In a later test of that combination (tools + `tool_choice: none` + `response_format: json_object`, tool-message history) Sarvam accepted the call (HTTP 200) but returned empty content in 3 of 3 calls, while 2 of 2 calls without `response_format` returned valid JSON. We did not change the harness for this: the Sarvam rows were run as described here, and the cut-off column above counts the tasks the output limit ended.

**Note on est. USD.** The estimate is only computed for Anthropic and OpenAI, whose per-token prices are in our price table. Gemini and Groq runs used free tiers (0.00). Sarvam's price is not in our price table, so the 0.00 on Sarvam rows means *not estimated*, not that the run was free. The Claude Sonnet 5.5 form and GST rows were first priced at the lower Haiku-level default; their est. USD was multiplied by 2.5 (the Sonnet-to-default price ratio, the same for input and output tokens) to the Sonnet rate. Claude Opus 5.5 rows are not estimated: its price is not in our price table yet.

**Verify it.** The grading code is identified by the git tree id of `navital_gym/` at the release tag v1.1.0. Check with `git rev-parse v1.1.0:navital_gym`: it must start with the id in the `graded` column.

## Small and mid-size models

Most people testing will use models like these, so they come first. Many score low.

| env | model (provider) | tasks | pass@1 | strict | format fail | errors | length cut-off | partial credit | est. USD | date | graded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| form | claude-haiku-4-5 (anthropic) | 50 | 0.94 | 0.92 | 0% | 0% | 0 | 0.97 | 0.54 | - | 1543b5103be5 |
| form | sarvam-105b (sarvam) | 50 | 0.98 | 0.98 | 0% | 0% | 0 | 1.00 | 0.00 | - | 1543b5103be5 |
| form multi-document | claude-haiku-4-5 (anthropic) | 40 | 0.98 | 0.98 | 0% | 0% | 0 | 0.99 | 0.84 | - | 1543b5103be5 |
| form multi-document | sarvam-105b (sarvam) | 40 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | 0.00 | - | 1543b5103be5 |
| gst | claude-haiku-4-5 (anthropic) | 50 | 0.84 | 0.84 | 0% | 0% | 0 | 0.93 | 0.63 | - | 1543b5103be5 |
| gst | sarvam-105b (sarvam) | 50 | 0.82 | 0.82 | 0% | 0% | 0 | 0.91 | 0.00 | - | 1543b5103be5 |
| support | claude-haiku-4-5 (anthropic) | 76 | 0.42 | 0.39 | 0% | 0% | 0 | 0.74 | 1.08 | - | 1543b5103be5 |
| support | sarvam-105b (sarvam) | 76 | 0.54 | 0.54 | 0% | 0% | 0 | 0.87 | 0.00 | - | 1543b5103be5 |
| trip | claude-haiku-4-5 (anthropic) | 55 | 0.35 | 0.33 | 7% | 0% | 0 | 0.66 | 9.87 | - | 1543b5103be5 |
| upi | claude-haiku-4-5 (anthropic) | 50 | 0.52 | 0.52 | 0% | 0% | 0 | 0.73 | 0.95 | - | 1543b5103be5 |
| upi | gemini-3.1-flash-lite (gemini) | 50 | 0.78 | 0.78 | 0% | 0% | 0 | 0.92 | 0.00 | - | 1543b5103be5 |
| upi | sarvam-105b (sarvam) | 50 | 0.58 | 0.58 | 10% | 0% | 0 | 0.75 | 0.00 | - | 1543b5103be5 |

## Larger models, for reference (Claude Sonnet 5.5 and Opus 5.5)

What strong models reach. Not the typical user's model.

| env | model (provider) | tasks | pass@1 | strict | format fail | errors | length cut-off | partial credit | est. USD | date | graded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| form | claude-opus-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | - | - | 1543b5103be5 |
| form | claude-sonnet-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | 1.23 | - | 1543b5103be5 |
| form multi-document | claude-opus-5-5 (anthropic) | 40 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | - | - | 1543b5103be5 |
| form multi-document | claude-sonnet-5-5 (anthropic) | 40 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | 1.05 | - | 1543b5103be5 |
| gst | claude-opus-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | - | - | 1543b5103be5 |
| gst | claude-sonnet-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | 1.52 | - | 1543b5103be5 |
| support | claude-opus-5-5 (anthropic) | 76 | 0.97 | 0.97 | 0% | 0% | 0 | 0.99 | - | - | 1543b5103be5 |
| support | claude-sonnet-5-5 (anthropic) | 76 | 0.91 | 0.91 | 0% | 0% | 0 | 0.98 | 2.85 | - | 1543b5103be5 |
| trip | claude-opus-5-5 (anthropic) | 55 | 0.93 | 0.67 | 0% | 0% | 0 | 0.99 | - | - | 1543b5103be5 |
| trip | claude-sonnet-5-5 (anthropic) | 55 | 0.84 | 0.55 | 0% | 0% | 0 | 0.97 | 17.14 | - | 1543b5103be5 |
| upi | claude-opus-5-5 (anthropic) | 50 | 1.00 | 1.00 | 0% | 0% | 0 | 1.00 | - | - | 1543b5103be5 |
| upi | claude-sonnet-5-5 (anthropic) | 50 | 0.94 | 0.94 | 0% | 0% | 0 | 0.98 | 2.72 | - | 1543b5103be5 |

## Do the difficulty labels separate small and mid-size models?

Tasks solved / tried by the designers' difficulty label (designer intent, not calibrated; all shown rows together). If the columns are close the labels do not predict who solves what.

| model | difficulty 1-2 | difficulty 3 | difficulty 4-5 |
|---|---|---|---|
| claude-haiku-4-5 | 35/65 | 77/117 | 93/139 |
| gemini-3.1-flash-lite | 10/11 | 9/14 | 20/25 |
| sarvam-105b | 39/54 | 69/90 | 92/122 |

## Not shown

Runs that are incomplete (still running, or cut short by a daily free-tier limit) or where at least a fifth of the tasks ended in provider errors say nothing yet about the model:

- support / gemini-3.1-flash-lite (gemini): incomplete, 51 of 76 tasks

