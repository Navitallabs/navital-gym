"""OpenEnv adapter (Meta PyTorch + Hugging Face OpenEnv). `pip install openenv-core`, then serve any Navital env over HTTP:
    NAVITAL_ENV=trip uvicorn navital_gym.adapters.openenv_env:app --port 8000
or from Python:  from navital_gym.adapters.openenv_env import make_app; app = make_app("trip")
Binding verified against openenv-core 0.3.0 (Environment / Action / Observation / State from openenv.core.env_server, create_app); see the tests.
Layers: `NavitalSession` is dependency-free (reset/step/state on navital_gym.core.env.Env) and is what the unit tests exercise without OpenEnv;
`NavitalOpenEnv` is the thin OpenEnv Environment on top of it and exists only when openenv-core is importable (`OPENENV_AVAILABLE`).
Protocol: reset(task_id=None | id | index, seed=None) builds a fresh sandbox world and returns the task prompt (which already carries the policy/output-format text),
the tool specs and the task id. step(action): {"tool": name, "args": {...}} -> observation = the tool result, reward 0, done False;
{"finalize": <submission JSON>} -> graded by the env's deterministic grader, reward = its score, done True. Stepping after done is refused (error obs, reward 0).
state() has the episode id, task id, step count, done flag and tool names called so far. Nothing hidden (expected_feasible, binding, traps, rules, params,
gold answers) is ever returned, and the grader `info` is not forwarded: only reward and done are.
Limits: only unit/in-process and one FastAPI TestClient pass are exercised by the tests; not tested in a container or on a Hugging Face Space.
The HTTP /reset and /step routes in OpenEnv are stateless per request unless the client uses the WebSocket session (the OpenEnv client does); per-session isolation
relies on one NavitalOpenEnv instance (and its own Env/world) per session. A tool's own output is passed through as-is, so env authors must keep task data out of tool results
(navital_gym.core.leak checks that)."""
from __future__ import annotations
import importlib, os, uuid
from typing import Any, Optional

def _load_env(name: str):
    return importlib.import_module(f"navital_gym.envs.{name}").load_env()

class NavitalSession:
    """Dependency-free reset/step/state over one Navital env. One instance = one agent session with its own world."""
    def __init__(self, env_name: str = "trip"):
        self.env_name = env_name
        self.env = _load_env(env_name)
        self.episode_id: Optional[str] = None
        self.task_id: Optional[str] = None
        self.step_count = 0
        self.done = False
        self.tools_called: list[str] = []
        self._started = False

    def _pick(self, task_id: Any, seed: Optional[int]) -> str:
        ids = self.env.task_ids()
        if task_id is None:
            return ids[(seed or 0) % len(ids)] if seed is not None else ids[0]
        if isinstance(task_id, int) or (isinstance(task_id, str) and task_id.isdigit() and task_id not in self.env.tasks):
            return ids[int(task_id) % len(ids)]
        if task_id not in self.env.tasks:
            raise KeyError(f"unknown task id {task_id!r}; known: {ids}")
        return task_id

    def reset(self, task_id: Any = None, seed: Optional[int] = None, episode_id: Optional[str] = None) -> dict:
        tid = self._pick(task_id, seed)
        obs = self.env.reset(tid)   # fresh world each time
        self.episode_id = episode_id or str(uuid.uuid4())
        self.task_id, self.step_count, self.done, self.tools_called, self._started = tid, 0, False, [], True
        return {"prompt": obs["prompt"], "tools": obs["tools"], "task_id": obs["id"], "lang": obs["lang"], "result": None,
                "done": False, "reward": None}

    def step(self, action: dict) -> dict:
        """Returns {"prompt"?, "result", "done", "reward"}; never the grader info."""
        if not self._started:
            return {"result": {"error": "call reset() first"}, "done": False, "reward": 0.0}
        if self.done:
            return {"result": {"error": "episode finished; call reset()"}, "done": True, "reward": 0.0}
        if not isinstance(action, dict) or ("finalize" in action) == ("tool" in action):
            return {"result": {"error": 'action must be exactly one of {"tool": name, "args": {...}} or {"finalize": submission}'}, "done": False, "reward": 0.0}
        self.step_count += 1
        if "tool" in action:
            self.tools_called.append(str(action["tool"]))
            action = {"tool": action["tool"], "args": action.get("args") or {}}
        out = self.env.step(action)
        self.done = bool(out["done"])
        return {"result": out["obs"], "done": self.done, "reward": float(out["reward"])}   # out["info"] (grader detail) deliberately dropped

    def state(self) -> dict:
        return {"episode_id": self.episode_id, "task_id": self.task_id, "step_count": self.step_count,
                "done": self.done, "tools_called": list(self.tools_called)}

try:
    from openenv.core.env_server import Action, Observation, State, Environment, create_app
    from pydantic import Field
    OPENENV_AVAILABLE = True
except ImportError:   # openenv-core not installed: the dependency-free session above still works
    OPENENV_AVAILABLE = False

if OPENENV_AVAILABLE:
    class NavitalAction(Action):
        """Exactly one of `tool` (+ `args`) or `finalize` (submission JSON, any shape; {} is a valid empty submission)."""
        tool: Optional[str] = Field(default=None, description="tool name to call")
        args: dict[str, Any] = Field(default_factory=dict, description="tool arguments")
        finalize: Any = Field(default=None, description="final submission JSON; presence (even {}) ends the episode")

        def to_dict(self) -> dict:
            if "finalize" in self.model_fields_set:
                d: dict = {"finalize": self.finalize}
                if self.tool is not None:
                    d["tool"] = self.tool   # ambiguous: the session refuses it
                return d
            return {"tool": self.tool, "args": self.args} if self.tool is not None else {}

    class NavitalObservation(Observation):
        prompt: Optional[str] = None                       # set on reset only
        tools: list[dict[str, Any]] = Field(default_factory=list)   # set on reset only
        task_id: Optional[str] = None
        lang: Optional[str] = None
        result: Any = None                                 # tool result / {"graded": True} / error

    class NavitalState(State):
        task_id: Optional[str] = None
        done: bool = False
        tools_called: list[str] = Field(default_factory=list)

    class NavitalOpenEnv(Environment[NavitalAction, NavitalObservation, NavitalState]):
        SUPPORTS_CONCURRENT_SESSIONS = True   # each instance owns its Env and world; no shared mutable state

        def __init__(self, env_name: Optional[str] = None):
            super().__init__()
            self.session = NavitalSession(env_name or os.environ.get("NAVITAL_ENV", "trip"))

        def reset(self, seed: Optional[int] = None, episode_id: Optional[str] = None, task_id: Any = None, **kwargs: Any) -> NavitalObservation:
            o = self.session.reset(task_id=task_id, seed=seed, episode_id=episode_id)
            return NavitalObservation(prompt=o["prompt"], tools=o["tools"], task_id=o["task_id"], lang=o["lang"], done=False, reward=None)

        def step(self, action: NavitalAction, timeout_s: Optional[float] = None, **kwargs: Any) -> NavitalObservation:
            o = self.session.step(action.to_dict())
            return NavitalObservation(result=o["result"], task_id=self.session.task_id, done=o["done"], reward=o["reward"])

        @property
        def state(self) -> NavitalState:
            return NavitalState(**self.session.state())

    def make_app(env_name: str = "trip"):
        return create_app(lambda: NavitalOpenEnv(env_name), NavitalAction, NavitalObservation, env_name=f"navital_{env_name}")

    app = make_app(os.environ.get("NAVITAL_ENV", "trip"))
