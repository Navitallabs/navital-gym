"""Inspect AI adapter. `pip install inspect-ai`, then:
    inspect eval navital_gym/adapters/inspect_task.py@trip --model openai/gpt-4o-mini
or from Python:  from navital_gym.adapters.inspect_task import navital_task; navital_task("trip")
Each sample gets its own sandbox world (built from the task id) behind the same tools the other adapters use; the scorer runs the env's deterministic
grader on the final JSON in the model's last message. Score value is 1 for solved, 0 otherwise; the partial rule score is kept in metadata.
The model sees only the prompt, the tools and the env's policy text: never hidden task fields."""
from __future__ import annotations
import importlib, json
from typing import Any
from inspect_ai import Task as InspectTask, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, mean, scorer, stderr, CORRECT, INCORRECT
from inspect_ai.solver import Generate, TaskState, generate, solver
from inspect_ai.tool import ToolDef, ToolParams, ToolParam
from ..core.runner import extract_json

def _env(env_name: str):
    return importlib.import_module(f"navital_gym.envs.{env_name}").load_env()

def _runner(world, name):
    async def run(**kwargs: Any) -> str:
        return json.dumps(world.call(name, kwargs))
    return run

def _tools_for(world):
    out = []
    for name, fn in sorted(world.tools().items()):
        spec = fn._tool
        props = {k: ToolParam(type=v.get("type", "string"), description=v.get("description") or k.replace("_", " ")) for k, v in spec["params"].items()}
        req = [k for k, v in spec["params"].items() if not v.get("optional")]

        out.append(ToolDef(_runner(world, name), name=name, description=spec["description"], parameters=ToolParams(properties=props, required=req)).as_tool())
    return out

@solver
def navital_world(env_name: str):
    env = _env(env_name)
    async def solve(state: TaskState, gen: Generate):
        obs = env.reset(str(state.sample_id))
        state.tools = _tools_for(env.world)
        state.metadata["_navital_obs"] = obs["prompt"]
        return await gen(state, tool_calls="loop")
    return solve

@scorer(metrics=[accuracy(), stderr(), mean()])
def navital_grader(env_name: str):
    env = _env(env_name)
    async def score(state: TaskState, target: Target):
        sub = extract_json(state.output.completion or "")
        res = env.contract_grade(env.tasks[str(state.sample_id)].to_dict(), sub)
        return Score(value=CORRECT if res["solved"] else INCORRECT, answer=(state.output.completion or "")[:500],
                     explanation=res.get("verdict", ""), metadata={"rule_score": res["score"], "rules": res["rules"]})
    return score

def navital_task(env_name: str, limit_ids: list[str] | None = None) -> InspectTask:
    env = _env(env_name)
    samples = []
    for tid in (limit_ids or env.task_ids()):
        t = env.tasks[tid]
        samples.append(Sample(id=tid, input=t.prompt + "\n\n" + env.instructions, target="", metadata={"lang": t.lang}))
    return InspectTask(dataset=samples, solver=[navital_world(env_name)], scorer=navital_grader(env_name), message_limit=60)

@task
def trip():
    return navital_task("trip")
