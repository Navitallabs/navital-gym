"""verifiers (v1 API) adapter. `pip install verifiers`, then:
    import verifiers.v1 as vf
    from navital_gym.adapters.verifiers_env import load_environment
    env = load_environment("trip")            # a vf.SingleAgentEnv over the Navital tasks
This is the entry point verifiers / the Prime Environments Hub call (`load_environment(env_name="trip", **kwargs)`).
Every Navital task becomes a verifiers task whose prompt is the task prompt plus the env's policy text. The agent reaches the
Navital world only through MCP tools: a task-scoped tool server (NavitalToolset, one subprocess per rollout) builds a fresh
sandbox world from the task id and serves exactly `world.tool_specs()`. The reward is the env's deterministic grader run on the
LAST JSON object in the final assistant message; `solved` is recorded as a second metric.
The model sees only the prompt, the tools and the policy text. The task data that rides on traces holds the public prompt and the
task id only; hidden fields (expected_feasible, binding, traps, rules, params) are read from the Navital env host-side at scoring
time, and inside the tool-server process to build the world. They never enter TaskData.

Honest limits: (1) the tool server is launched as `python -m navital_gym.adapters.verifiers_env` with the host's interpreter, so
navital_gym must be importable there (pip install it, or set PYTHONPATH); (2) verifiers loads a taskset by top-level module name, so load_environment registers the alias `navital_gym_vf` in sys.modules (in-process only; a separate env-server process must call load_environment itself); (3) the default agent seat is the `null` chat harness in
a local `subprocess` runtime (verifiers' own default is a cloud `prime` sandbox, which this env does not need); override with
`agent=...` if you want something else; (4) written against verifiers 0.4.0's v1 API, which is young and may move.
"""
from __future__ import annotations
import functools, importlib, json
from collections.abc import Iterator
from typing import Any

import verifiers.v1 as vf
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, Tool

from ..core.runner import extract_json

MODULE = "navital_gym.adapters.verifiers_env"
ALIAS = "navital_gym_vf"  # verifiers resolves a taskset id as a TOP-LEVEL module name (a dotted id breaks its loader)


@functools.lru_cache(maxsize=None)
def _navital_env(env_name: str):
    """The Navital Env for `env_name`, loaded once per process (read-only use: never call reset() on this shared instance)."""
    return importlib.import_module(f"navital_gym.envs.{env_name}").load_env()


class NavitalConfig(vf.TasksetConfig):
    env_name: str = "trip"
    """Which Navital env (navital_gym.envs.<env_name>)."""
    ids: list[str] | None = None
    """Optional subset of task ids (default: every task)."""


class NavitalData(vf.TaskData):
    """Public task data only. Deliberately no hidden fields: this model is serialised onto traces and sent to the tool server."""
    env_name: str = "trip"


class NavitalToolset(vf.Toolset[vf.ToolsetConfig]):
    """Serves the Navital world's tools for ONE rollout (task-scoped server, so one fresh world per rollout)."""
    TOOL_PREFIX = None  # advertise tools bare (get_x, not navital_toolset_get_x)

    world = None

    async def setup_task(self, task) -> None:
        env = _navital_env(task.env_name)
        self.world = env.make_world(env.tasks[task.id])

    def register(self, mcp: MCPServer) -> None:
        # The catalog is rollout-specific, so replace the protocol handlers instead of registering static tools.
        server: Any = mcp
        server.list_tools = self._with_state(self.list_tools)
        server.call_tool = self._with_state(self.call_tool)

    async def list_tools(self) -> list[Tool]:
        out = []
        for spec in self.world.tool_specs():
            f = spec["function"]
            out.append(Tool(name=f["name"], description=f["description"], input_schema=f["parameters"]))
        return out

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Context | None = None) -> CallToolResult:
        res = self.world.call(name, arguments)
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(res))], is_error="error" in res)


class NavitalTask(vf.Task[NavitalData]):
    @classmethod
    def toolsets(cls, config) -> list[vf.Toolset]:
        return [NavitalToolset(vf.ToolsetConfig())]

    def _grade(self, trace) -> dict:
        env = _navital_env(self.data.env_name)
        task_dict = env.tasks[self.data.id].to_dict()  # hidden fields live only here, host-side
        return env.contract_grade(task_dict, extract_json(trace.last_reply or ""))

    @vf.reward
    async def navital_score(self, trace) -> float:
        return float(self._grade(trace)["score"])

    @vf.metric
    async def solved(self, trace) -> float:
        return 1.0 if self._grade(trace)["solved"] else 0.0


class NavitalTaskset(vf.Taskset[NavitalTask, NavitalConfig]):
    def load(self) -> Iterator[NavitalTask]:
        env = _navital_env(self.config.env_name)
        for tid in (self.config.ids or env.task_ids()):
            pub = env.tasks[tid].public()  # the only task data the agent sees
            yield NavitalTask(
                NavitalData(id=tid, name=tid, env_name=self.config.env_name, prompt=pub["prompt"] + "\n\n" + env.instructions),
                self.config.task,
            )


def load_environment(env_name: str = "trip", **kwargs: Any) -> vf.Env:
    """kwargs: `ids` (task id subset), `agent` (a dict or vf.AgentConfig overriding the default seat), and any other
    vf.SingleAgentEnvConfig field (e.g. `timeout`, `retries`)."""
    import sys
    sys.modules.setdefault(ALIAS, sys.modules[__name__] if __name__ != "__main__" else importlib.import_module(MODULE))
    agent = kwargs.pop("agent", None) or {}
    if isinstance(agent, vf.AgentConfig):
        agent = agent.model_dump(exclude_unset=True)
    agent = {"harness": {"id": "null"}, "runtime": {"type": "subprocess"}, **agent}
    ids = kwargs.pop("ids", None)
    cfg = vf.SingleAgentEnvConfig.model_validate({
        "taskset": {"id": ALIAS, "env_name": env_name, "ids": ids},
        "agent": agent, **kwargs})
    return vf.SingleAgentEnv(cfg)


__all__ = ["NavitalTaskset", "NavitalTask", "NavitalToolset", "NavitalData", "NavitalConfig", "load_environment"]

if __name__ == "__main__":  # how verifiers launches the per-rollout tool server
    NavitalToolset.run()
