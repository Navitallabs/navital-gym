"""Sandbox world pattern.

A World is a deterministic, read-only snapshot built from (seed, task) with a registry of tools. Tools are
the only way an agent touches it; every call is logged. Nothing in a world touches the network, the clock
or a real system. The same (seed, task, tool call) always returns the same JSON.
"""
from __future__ import annotations
import copy, hashlib, json
from typing import Any, Callable

class ToolError(Exception):
    """A tool refused the call (bad id, bad date...). The agent sees {"error": ...}; it is not a crash."""

def tool(description: str, params: dict | None = None):
    """Mark a World method as an agent-visible tool. params: {name: {"type": ..., "description": ...}} (JSON Schema properties)."""
    def deco(fn):
        fn._tool = {"description": description, "params": params or {}}
        return fn
    return deco

class World:
    env_name = "base"

    def __init__(self, task, seed: int = 0):
        self.task = task
        self.seed = seed
        self.calls: list[dict] = []
        self.finalized: Any = None

    # ---- deterministic randomness: a pure function of (seed, labels); never random.random()
    def h(self, *labels) -> int:
        s = ":".join([self.env_name, str(self.seed), *map(str, labels)])
        return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")

    def pick(self, lo: int, hi: int, *labels) -> int:
        return lo + self.h(*labels) % (hi - lo + 1)

    # ---- tools
    def tools(self) -> dict[str, Callable]:
        return {n: getattr(self, n) for n in dir(self) if getattr(getattr(self, n, None), "_tool", None)}

    def tool_specs(self) -> list[dict]:
        """OpenAI-style function specs, usable by any tool-calling model and by the adapters."""
        specs = []
        for name, fn in sorted(self.tools().items()):
            t = fn._tool
            specs.append({"type": "function", "function": {"name": name, "description": t["description"],
                          "parameters": {"type": "object",
                                         "properties": {k: {kk: vv for kk, vv in v.items() if kk != "optional"} for k, v in t["params"].items()},   # strict providers reject unknown schema keys
                                         "required": [k for k, v in t["params"].items() if not v.get("optional")]}}})
        return specs

    def call(self, name: str, args: dict | None = None) -> dict:
        args = args if isinstance(args, dict) else {}
        fn = self.tools().get(name)
        rec = {"tool": name, "args": copy.deepcopy(args)}
        if fn is None:
            out = {"error": f"unknown tool {name!r}", "tools": sorted(self.tools())}
        else:
            try:
                out = fn(**{k: v for k, v in args.items()})
            except ToolError as e:
                out = {"error": str(e)}
            except TypeError as e:
                out = {"error": f"bad arguments: {e}"}
            except (ValueError, ArithmeticError) as e:      # v1.1: e.g. a date at the edge of the calendar overflows; the agent gets an error, not a crash
                out = {"error": f"bad arguments: {e}"}
        rec["ok"] = "error" not in out
        self.calls.append(rec)
        return out

    def fingerprint(self) -> str:
        """Hash of the world's data; two builds with the same inputs must match (determinism check)."""
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True).encode()).hexdigest()[:16]

    def snapshot(self) -> dict:
        raise NotImplementedError
