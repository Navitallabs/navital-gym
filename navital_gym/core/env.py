"""Env = tasks + world class + grader. Gym-style reset/step on top of the World's tool API."""
from __future__ import annotations
from typing import Any
from .schema import Task

class Env:
    name = "base"
    instructions = ""            # appended to every prompt: output format, how to say "infeasible"

    def __init__(self, tasks: list[Task], world_cls, grader, seed: int = 0):
        self.tasks = {t.id: t for t in tasks}
        self.world_cls, self.grader, self.seed = world_cls, grader, seed
        self.task: Task | None = None
        self.world = None
        self.done = False

    def format_check(self, sub) -> str | None:
        """Cheap shape check the runner uses to offer ONE repair retry. Return an error text, or None if the answer is readable. Envs override."""
        return None if isinstance(sub, dict) else "the answer must be one JSON object"

    def task_ids(self):
        return list(self.tasks)

    def make_world(self, task: Task):
        return self.world_cls(task, self.seed)

    def reset(self, task_id: str) -> dict:
        self.task = self.tasks[task_id]
        self.world = self.make_world(self.task)
        self.done = False
        pub = self.task.public()   # the only task data the agent sees
        return {"prompt": pub["prompt"] + "\n\n" + self.instructions, "tools": self.world.tool_specs(), "id": pub["id"], "lang": pub["lang"]}

    def step(self, action: dict) -> dict:
        """action: {"tool": name, "args": {...}} (observation = tool result) or {"finalize": submission} (graded, done)."""
        if self.done:
            return {"obs": {"error": "episode finished"}, "done": True, "reward": 0.0, "info": {}}
        if "finalize" in action:
            sc = self.grader.grade(self.task, action["finalize"])
            self.done = True
            return {"obs": {"graded": True}, "done": True, "reward": sc.score, "info": sc.to_dict()}
        return {"obs": self.world.call(str(action.get("tool", "")), action.get("args")), "done": False, "reward": 0.0, "info": {}}

    def grade(self, task: Task, submission: Any):
        return self.grader.grade(task, submission)

    def contract_grade(self, task_dict: dict, submission: Any) -> dict:
        """qa's adapter contract: grade(task: dict, submission) -> {"score", "solved", "rules"}. Never raises."""
        try:
            task = Task.from_dict(task_dict)
        except Exception:
            return {"score": 0.0, "solved": False, "rules": {}}
        sc = self.grader.grade(task, submission).to_dict()
        return {"score": sc["score"], "solved": sc["solved"], "rules": sc["rules"], "verdict": sc["verdict"], "soft": sc["soft"]}
