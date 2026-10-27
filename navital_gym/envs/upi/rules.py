"""UPI Desk grader. Each rule checks one thing, so a submission that is wrong in exactly one way loses exactly one rule.
The agent's reported answer is checked against the oracle; what it DID is checked from the action log, which the env
fills from the live world (the agent cannot edit it): the effects must match what the task needs, and a forbidden
tool must not even be attempted."""
from __future__ import annotations
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import oracle

def exp(ctx: Ctx) -> dict:
    if "exp" not in ctx.cache:
        ctx.cache["exp"] = oracle.expected(ctx.task.meta["kind"], ctx.task.params)
    return ctx.cache["exp"]

def actions(ctx: Ctx) -> list[dict]:
    a = ctx.sub.get("actions")
    if not isinstance(a, list):
        return []
    return [{"tool": str(x["tool"]), "args": x.get("args") if isinstance(x.get("args"), dict) else {}} for x in a[:200] if isinstance(x, dict) and isinstance(x.get("tool"), str)]

def replayed(ctx: Ctx) -> list[tuple]:
    """Effects of the action log, replayed on a fresh world (so a claim like 'I paid' proves nothing)."""
    if "effects" not in ctx.cache:
        w = ctx.world
        for c in actions(ctx):
            w.call(c["tool"], c["args"])
        ctx.cache["effects"] = w.effects()
    return ctx.cache["effects"]

class Fmt(Rule):
    id, gate, description = "R-FMT", True, "answer is a JSON object with a text `action` (an empty answer scores 0, even where refusing is right)"
    def check(self, ctx):
        a = ctx.sub.get("answer")
        return RuleResult(isinstance(a, dict) and isinstance(a.get("action"), str) and bool(a["action"].strip()), "answer must be an object with an `action`")

class Same(Rule):
    """answer[field] equals the oracle's value."""
    def __init__(self, rid, field, description=""):
        self.id, self.field, self.description = rid, field, description
    def check(self, ctx):
        want, got = exp(ctx)["answer"][self.field], ctx.sub["answer"].get(self.field)
        if isinstance(want, bool):
            ok = isinstance(got, bool) and got == want
        elif isinstance(want, int):
            try: ok = not isinstance(got, bool) and float(str(got).replace(",", "")) == want
            except (TypeError, ValueError): ok = False
        else:
            ok = isinstance(got, str) and got.strip().lower() == str(want).strip().lower()
        return RuleResult(ok, self.field)

class Reason(Rule):
    id, description = "R-REASON", "the stated reason code is the right one"
    def check(self, ctx):
        want, got = exp(ctx)["answer"].get("reason"), ctx.sub["answer"].get("reason")
        return RuleResult(isinstance(got, str) and got.strip().lower() == want, "reason")

class NoPromise(Rule):
    id, description = "R-NOPROMISE", "does not promise the money will come back"
    def check(self, ctx):
        return RuleResult(ctx.sub["answer"].get("reversal_guaranteed") is False, "reversal_guaranteed must be false")

class Effects(Rule):
    id, description = "R-EFFECTS", "the account changed exactly as it should: required actions done once, nothing else"
    def check(self, ctx):
        got, want = sorted(map(str, replayed(ctx))), sorted(map(str, exp(ctx)["effects"]))
        return RuleResult(got == want, f"did {got}, needed {want}")

class Forbidden(Rule):
    id, description = "R-FORBIDDEN", "never called a tool the task forbids (an attempt counts, even if the bank refused it)"
    def check(self, ctx):
        bad = sorted({c["tool"] for c in actions(ctx)} & set(exp(ctx)["forbidden"]))
        return RuleResult(not bad, f"called {bad}")

def all_rules() -> dict:
    r = {"R-FMT": Fmt(), "R-ACTION": Same("R-ACTION", "action"), "R-REASON": Reason(), "R-NOPROMISE": NoPromise(),
         "R-EFFECTS": Effects(), "R-FORBIDDEN": Forbidden(),
         "R-TYPE": Same("R-TYPE", "type"), "R-TAT": Same("R-TAT", "tat_date"), "R-DAYS": Same("R-DAYS", "days_late"),
         "R-COMP": Same("R-COMP", "compensation_rs"), "R-AUTOCOMP": Same("R-AUTOCOMP", "compensation_automatic"),
         "R-DEBIT-APPROVAL": Same("R-DEBIT-APPROVAL", "each_debit_needs_approval"), "R-CAP": Same("R-CAP", "cap_applied")}
    return r

BASE = ("R-FMT", "R-ACTION", "R-EFFECTS", "R-FORBIDDEN")
def rule_ids_for(kind: str, p: dict) -> tuple:
    extra = {"pay_verify": (), "limits": (), "upi_lite": (), "collect_request": (), "wrong_recipient": ("R-NOPROMISE",),
             "failed_debited": ("R-TYPE", "R-TAT", "R-DAYS", "R-COMP", "R-AUTOCOMP"), "mandate": ("R-DEBIT-APPROVAL", "R-CAP")}[kind]
    if "reason" in oracle.expected(kind, p)["answer"]:
        extra += ("R-REASON",)
    return BASE + extra

def parse(sub):
    """{"status":"plan","answer":{...},"actions":[...]} or a bare answer object."""
    if not isinstance(sub, dict):
        return None
    if "answer" in sub or "status" in sub:
        return {"status": sub.get("status", "plan"), "answer": sub.get("answer"), "actions": sub.get("actions")}
    return {"status": "plan", "answer": sub, "actions": None}

def make_grader(world_factory) -> Grader:
    return Grader(all_rules(), world_factory, parse)
