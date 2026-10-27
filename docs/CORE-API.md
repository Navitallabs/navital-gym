# Core API v0.1 (frozen 4 Nov 2026 per the plan; changes after this need a version bump and a note here)

Everything below is importable from `navital_gym.core` unless noted. Standard library only.

## Task (`core/schema.py`)
`Task(id, family, difficulty, lang, prompt, params, rules, expected_feasible, binding, traps, snapshot_date, meta)`; `Task.from_dict(d)` (accepts `binding_constraint` as an alias of `binding`), `to_dict()`, `load_tasks(path)` (JSONL, duplicate ids rejected).
- `Task.public()` -> `{"id", "prompt", "lang"}`: **the only task data an agent is ever shown.** `Task.HIDDEN` lists the grader-only fields (feasibility, binding rules, traps, params, rules, gold answers, forbidden actions, grader notes).
- `meta["split"]` (default `core`; e.g. `experimental`) and `meta["kind"]` (default feasible/infeasible) drive the report breakdowns.

## World (`core/world.py`)
`class XWorld(World)`: `env_name`, `__init__(task, seed)`, `snapshot()`, `@tool(description, {param: {"type", "description", "optional"}})` methods. `world.call(name, args) -> dict` (a `ToolError` or bad arguments become `{"error": ...}`; never a crash), `world.tool_specs()` (OpenAI function format), `world.fingerprint()`, deterministic randomness only through `world.h(*labels)` / `world.pick(lo, hi, *labels)`. A world never touches the network or the clock.

## Grader (`core/grader.py`)
`Rule` (`id`, `description`, `gate`, `check(ctx) -> RuleResult(passed, detail)`), `Ctx(task, world, sub, cache)`, `Grader(rules, world_factory, parse, soft=None, infeasible_check=None)`, `grader.grade(task, submission) -> Score(score, solved, valid, rules, details, soft, verdict)`.
- Never raises (garbage scores 0); recomputes from the world, never trusts claimed fields; a failed `gate` rule stops grading; `solved` needs every applicable rule; on an infeasible task any plan scores 0.
- `summarize(results, tasks=None)` -> pass@1, pass^k, mean score, per-rule failures, and with `tasks`: `by_split`, `by_kind`.

## Env (`core/env.py`)
`Env(tasks, world_cls, grader, seed)`: `reset(task_id) -> {"prompt", "tools", "id", "lang"}` (prompt = task prompt + the env's `instructions`), `step({"tool", "args"} | {"finalize": submission}) -> {"obs", "done", "reward", "info"}`, `contract_grade(task_dict, submission) -> {"score", "solved", "rules", ...}` (the contract qa's harness uses; never raises).

## Runner and CLI (`core/runner.py`, `python -m navital_gym.cli`)
`run_suite(env, agent, task_ids, k, progress, transcripts)`, `format_report(reports)`, `ScriptedAgent`, `OpenAICompatAgent(model, base_url, api_key, max_turns, timeout, temperature)`, `extract_json(text)`. CLI: `--env`, `--agent` (scripted name or `openai:<model>@<base_url>`), `--k`, `--tasks`, `--out` (also writes transcripts), `--temperature`. Keys come from the provider's environment variable (`OPENAI_API_KEY` for `openai:` specs, including a custom `@base_url`).

## Leak check (`core/leak.py`)
`find_leaks(task, text)`, `leaks_in_observation(task, obs)`, `HIDDEN_KEYS`. Every env's tests must run it over all its tasks (see `docs/ENV_AUTHORING.md`).

## An env package (`navital_gym/envs/<name>/`) must expose
`load_env(seed=0) -> Env`, `grade(task_dict, submission)`, `get_baselines() -> {name: Agent}` (the CLI looks these up), and ship `tasks.jsonl`, a README with the simplified-rules disclaimer, and tests.

## Adapters (`navital_gym/adapters/`, optional extras)
`inspect_task.navital_task(env_name)`, `verifiers_env.load_environment(env_name)`, `openenv_env.make_app(env_name)` / `NavitalSession`.
