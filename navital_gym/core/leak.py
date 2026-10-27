"""Hidden-field firewall. The agent may see a task's prompt and the tools; it must never see the grader-only
fields (feasibility flag, binding rules, designer traps, checks) in the prompt or in any tool output.
`find_leaks` is used by the test-suite on every task, and can be run on any transcript."""
from __future__ import annotations
import json, re

# Words that tell the agent the answer. Checked in the task prompt and in tool output, not in env instructions.
TELLS = re.compile(r"budget impossible|impossible|designer note|expected_feasible|binding_constraint|infeasible task|cannot be done|"
                   r"should not exist|beyond the 60-day|not feasible", re.I)

# Grader-only field names. The agent receives ONLY: the prompt, the world through tools, and the env's policy/instructions doc.
HIDDEN_KEYS = ("expected_feasible", "binding_constraint", "binding", "traps", "gold_answer", "forbidden_actions", "grader_notes", "checks", "hidden")

def hidden_strings(task) -> list[str]:
    out = []
    for t in task.traps:
        t = re.sub(r"^designer note[^:]*:\s*", "", t, flags=re.I).strip()
        if len(t) >= 6 and t.lower() not in ("none", "prompt language"):
            out.append(t)
    return out

def find_leaks(task, text: str, where: str = "text") -> list[str]:
    """Problems found in `text` (a prompt, or a JSON-dumped tool output)."""
    leaks = []
    low = text.lower()
    for s in hidden_strings(task):
        if s.lower() in low:
            leaks.append(f"{where}: contains hidden trap text {s!r}")
    m = TELLS.search(text)
    if m:
        leaks.append(f"{where}: contains a tell {m.group(0)!r}")
    for key in HIDDEN_KEYS:
        if f'"{key}"' in text:
            leaks.append(f"{where}: exposes hidden key {key!r}")
    return leaks

def leaks_in_observation(task, obs: dict) -> list[str]:
    """obs as returned by Env.reset: the prompt must be clean; tool specs must not carry task data."""
    prompt = obs["prompt"].split("\n\n")[0]
    return find_leaks(task, prompt, "prompt") + find_leaks(task, json.dumps(obs["tools"]), "tool specs")
