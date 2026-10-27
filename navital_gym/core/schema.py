"""Task schema shared by every env. A task is data: nothing here is env-specific."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any

class TaskError(ValueError):
    pass

@dataclass(frozen=True)
class Task:
    id: str
    family: str
    difficulty: int
    lang: str                      # en | hi | hinglish | ta | ...
    prompt: str                    # what the agent sees
    params: dict                   # structured facts the world and rules read
    rules: tuple                   # rule ids that apply to this task
    expected_feasible: bool = True
    binding: tuple = ()            # rule ids that make an infeasible task infeasible (hidden from the agent)
    traps: tuple = ()              # designer notes (hidden from the agent)
    snapshot_date: str | None = None
    meta: dict = field(default_factory=dict)

    # Grader-only. Nothing below may reach an agent (see core/leak.py; a test enforces it for every task).
    HIDDEN = ("expected_feasible", "binding", "traps", "rules", "params", "meta", "snapshot_date", "difficulty", "family", "gold_answer", "forbidden_actions", "grader_notes")

    def public(self) -> dict:
        """The ONLY thing an agent is shown about a task. `params` stay server-side: the world reads them to build
        itself and the rules read them to grade, but the agent learns facts only through the prompt and the tools."""
        return {"id": self.id, "prompt": self.prompt, "lang": self.lang}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rules"] = list(self.rules); d["binding"] = list(self.binding); d["traps"] = list(self.traps)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Task":
        try:
            p = dict(d.get("params") or {})
            return Task(
                id=str(d["id"]), family=str(d.get("family", "")), difficulty=int(d.get("difficulty", 1)),
                lang=str(d.get("lang", "en")), prompt=str(d["prompt"]), params=p,
                rules=tuple(d.get("rules") or ()), expected_feasible=bool(d.get("expected_feasible", True)),
                binding=tuple(d.get("binding_constraint", d.get("binding", ())) or ()),
                traps=tuple(d.get("traps") or ()), snapshot_date=p.get("snapshot_date") or d.get("snapshot_date"),
                meta=dict(d.get("meta") or {}),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise TaskError(f"bad task: {e}") from e

def load_tasks(path: str) -> list[Task]:
    out, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            t = Task.from_dict(json.loads(line))
            if t.id in seen:
                raise TaskError(f"duplicate task id {t.id} (line {n})")
            seen.add(t.id); out.append(t)
    return out
