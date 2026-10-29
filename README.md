# Navital Gym

[![License: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-blue)](LICENSE) [![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey)](LICENSE-DATA) [![Release v1.0.0](https://img.shields.io/github/v/release/Navitallabs/navital-gym?label=release)](https://github.com/Navitallabs/navital-gym/releases) [![Leaderboard](https://img.shields.io/badge/leaderboard-navitallabs.com-orange)](https://navitallabs.com/labs/navital-gym)

Deterministic, auto-graded environments for AI agents doing tasks set in India: planning a trip around rail quotas and waitlists, GST invoicing, filling forms, answering customers in Hindi and other Indian languages. By [Navital Labs](https://navitallabs.com). Navital Gym is public and in active development: results are added as runs finish (see docs/RESULTS.md).

- **What:** six sets of sandboxed tasks (trip planning, UPI, GST, forms, multi-document forms, customer support in Hindi and Hinglish), each graded by written rules, never by an AI judge.
- **Why:** to measure whether an agent gets Indian-reality tasks right, with results anyone can reproduce and verify.
- **Try it:** `pip install -e . && navital-gym run --env trip --agent oracle` (prints 1.00), then see the [live leaderboard](https://navitallabs.com/labs/navital-gym) or [docs/RESULTS.md](docs/RESULTS.md).

> **Read this first.** Every environment uses a *simplified, documented* version of Indian practice and **synthetic data**. These are tests for AI agents, not statements about current law, railway, bank or tax rules. Not affiliated with or endorsed by NPCI, RBI, GSTN / CBIC, IRCTC / Indian Railways, any bank or any government body; names are used only to describe the workflow. Not financial or tax advice. Each env README states its own rules and an "as of" date.

## Why another gym
- **Exact grading, no LLM judge.** Each task is graded by deterministic rules that recompute everything from the sandbox world. Nothing the agent claims (cost, score, "solved") is trusted. Garbage input scores 0; the grader never crashes.
- **Honest about impossible requests.** Many tasks have no valid answer; the agent must say so and name why. Padding the claim with a wrong reason is marked wrong.
- **Hidden fields stay hidden.** The agent sees only the prompt, the tools and the policy text. Expected answers, feasibility and designer notes never reach it; a failing test enforces that for every task in every env.
- **Standard library only.** The core and every env run on plain Python 3.10+. Adapters for Inspect AI, verifiers and OpenEnv are optional extras.

## The suite
| env | what the agent does | tasks |
|---|---|---|
| `trip` | Indian trip planning under real constraints: trains with quotas / waitlists / classes, flights, road, hotels, seasons, permits | 55 (17 infeasible) |
| `gst` | GST Desk: invoicing and return computations from documents under written, simplified rules | 50 |
| `form` | Form Desk: filling and checking forms (KYC-style fields, addresses, numbers) | 50 |
| `support` | Bhasha Support Desk: e-commerce returns, refunds and privacy requests in Hindi / Hinglish; Tamil, Bengali and Marathi as a labelled experimental split | 50 core + 26 experimental |
| `form_multidoc` | Form Desk, multi-document: cross-checking identity documents and records (multi-document, PAN-name, record conflicts, OCR repair, batch) and reporting what disagrees | 40 |
| `upi` | UPI Desk: payment attempts and disputes under written, simplified rules | 50 |

Every env README carries its simplified rules and the sources of any real-world figure.

## Quickstart
```
pip install -e .
navital-gym list                                        # envs, task counts, baselines
navital-gym run --env trip --agent oracle               # a scripted reference agent: should print 1.00
navital-gym run --env trip --agent heuristic --k 3 --out runs/trip.json
python -m unittest discover -s tests                    # no dependencies needed
```
Run any model that speaks the OpenAI chat API with tool calling (Ollama, vLLM, LM Studio, hosted): `--agent "openai:qwen2.5:7b@http://localhost:11434/v1"` (the key is read from the provider's environment variable, `OPENAI_API_KEY` for `openai:` specs including a custom `@base_url`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`; never from the command line). Reports show pass@1, pass^k, per-rule failures, and separate tables per split (core / experimental) and kind (feasible / infeasible), so one mixed number is never the headline.

Python:
```python
from navital_gym.envs.trip import load_env
env = load_env()
obs = env.reset("IN-TRIP-002")            # prompt + tool specs; nothing hidden
out = env.world.call("search_trains", {"from_city": "Delhi", "to_city": "Agra", "date": "2026-12-05"})
```

## Adapters (optional extras)
| target | install | entry point |
|---|---|---|
| Inspect AI | `pip install -e ".[inspect]"` | `inspect eval navital_gym/adapters/inspect_task.py@trip --model ...` |
| verifiers (v1 API) | `pip install -e ".[verifiers]"` | `navital_gym.adapters.verifiers_env:load_environment` |
| OpenEnv | `pip install -e ".[openenv]"` | `navital_gym.adapters.openenv_env:make_app` (served over websocket) |
Each adapter has an offline end-to-end test with a scripted model. They are written against young APIs (verifiers 0.4.0 v1, openenv-core 0.3.0) and have not been run in a container or a hosted space.

## Results
<!-- RESULTS:START -->
Pass@1 on deterministic stratified samples or whole splits (k=1, one run per cell; n = tasks, so one task is 1/n of the cell: read small-n cells as indicative). 'easy' columns are the easy tier (designed so a 7B-30B model can sometimes solve them); the others are the standard tasks. Full tables with format failures, strict (no-repair) pass@1, partial credit, spend, dates and commits: [`docs/RESULTS.md`](docs/RESULTS.md). Every row was re-graded by the same grading code (`scripts/regrade.py`); check it with `git rev-parse v1.0.1:navital_gym` (see `docs/RESULTS.md`).

**Small and mid-size models: pass@1 (the typical user's models)**

| model | trip | form | form multi-document | gst | support | upi | trip easy | gst easy | support easy | upi easy |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | 0.31 (n=55) | 0.82 (n=50) | 0.98 (n=40) | 0.82 (n=50) | 0.24 (n=76) | 0.42 (n=50) | 0.67 (n=18) | 1.00 (n=18) | - | 0.61 (n=18) |
| gemini-3.1-flash-lite | 0.20 (n=15) | 0.60 (n=15) | - | - | 0.33 (n=15) | 0.60 (n=15) | - | - | - | - |
| gpt-4o-mini | 0.05 (n=55) | 0.54 (n=50) | 0.33 (n=40) | 0.50 (n=50) | 0.09 (n=76) | 0.18 (n=50) | 0.06 (n=18) | 0.94 (n=18) | - | 0.33 (n=18) |
| openai/gpt-oss-120b | - | - | - | - | - | - | - | 0.94 (n=18) | 0.00 (n=18) | - |
| openai/gpt-oss-20b | - | 0.80 (n=15) | - | - | - | - | - | 1.00 (n=18) | 0.00 (n=18) | - |
| sarvam-105b | 0.20 (n=55) | 0.82 (n=50) | 1.00 (n=40) | 0.78 (n=50) | 0.38 (n=76) | 0.52 (n=50) | - | 1.00 (n=18) | - | - |

**Small and mid-size models: partial credit (mean fraction of scored rules passed; shows progress where pass@1 is near zero)**

| model | trip | form | form multi-document | gst | support | upi | trip easy | gst easy | support easy | upi easy |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-4-5 | 0.73 | 0.90 | 0.99 | 0.91 | 0.70 | 0.67 | 0.95 | 1.00 | - | 0.83 |
| gemini-3.1-flash-lite | 0.58 | 0.82 | - | - | 0.73 | 0.87 | - | - | - | - |
| gpt-4o-mini | 0.28 | 0.83 | 0.61 | 0.69 | 0.55 | 0.47 | 0.59 | 0.94 | - | 0.59 |
| openai/gpt-oss-120b | - | - | - | - | - | - | - | 0.94 | 0.76 | - |
| openai/gpt-oss-20b | - | 0.87 | - | - | - | - | - | 1.00 | 0.73 | - |
| sarvam-105b | 0.54 | 0.95 | 1.00 | 0.87 | 0.77 | 0.77 | - | 1.00 | - | - |

**Larger model, for reference (what a strong model reaches)**

| model | trip | form | form multi-document | gst | support | upi | trip easy | gst easy | support easy | upi easy |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 0.58 (n=55) | 1.00 (n=50) | 1.00 (n=40) | 1.00 (n=50) | 0.66 (n=76) | 0.68 (n=50) | - | - | - | - |

Most of the models people will test are small or mid-size, so they come first. Many score low: that is the point of a hard benchmark, but a cell near zero says little, so read partial credit next to it. Samples are small and these are not the strongest agents available; they show that the environments separate models, not a leaderboard. Task difficulty labels are designer intent, not calibrated.
<!-- RESULTS:END -->

## Build your own env
`docs/ENV_AUTHORING.md` (a new env is mostly data plus rules on the shared core) and `docs/CORE-API.md` (the frozen core interfaces).

## Licences
Code: Apache-2.0 (`LICENSE`, copyright Navital Labs, see `NOTICE`). Task data: CC BY 4.0 (`LICENSE-DATA`), covering `navital_gym/envs/*/tasks*.jsonl` and `navital_gym/envs/*/FLAG_CHANGES.md`. Cite with `CITATION.cff`.
