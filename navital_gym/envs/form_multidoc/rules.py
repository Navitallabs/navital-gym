"""Form Desk: hard grader rules: one rule per answer field. The expected value comes from the independent oracle, never from the task file's gold_answer."""
from __future__ import annotations
from decimal import Decimal as Dc, InvalidOperation
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import oracle

def num(x):
    if isinstance(x, bool) or x is None: return None
    try: d = Dc(str(x).replace(",", "").strip()) if not isinstance(x, float) else Dc(repr(x))
    except (InvalidOperation, ValueError): return None
    return d if d.is_finite() else None

def expected(ctx: Ctx) -> dict:
    if "oracle" not in ctx.cache:
        t = ctx.task; ctx.cache["oracle"] = oracle.solve(t.meta["kind"], t.params["world"])
    return ctx.cache["oracle"]

class Fmt(Rule):
    id, gate, description = "R-FMT", True, "answer is a JSON object"
    def check(self, ctx): return RuleResult(isinstance(ctx.sub.get("answer"), dict), "answer must be an object")

EXACT = {"pan", "ifsc", "invalid_pans", "current_account_eligible"}   # identifiers and record ids: case-sensitive (whitespace still trimmed)

class Field(Rule):
    """answer[field] must equal the oracle's value: bools exact, integers exact, None means present and null, lists compared as sets of strings with no duplicates, pan, ifsc and record-id lists case-sensitive, other strings case/space-insensitive."""
    def __init__(self, rid, field, description=""): self.id, self.field, self.description = rid, field, description
    def check(self, ctx):
        want = expected(ctx)[self.field]; ans = ctx.sub["answer"]
        if want is None: return RuleResult(self.field in ans and ans[self.field] is None, f"{self.field} must be null")
        got = ans.get(self.field)
        if isinstance(want, bool): return RuleResult(isinstance(got, bool) and got == want, self.field)
        if isinstance(want, list):
            fold = (lambda x: x.strip()) if self.field in EXACT else (lambda x: x.strip().lower())
            ok = isinstance(got, list) and all(isinstance(x, str) for x in got) and len(set(fold(x) for x in got)) == len(got) and {fold(x) for x in got} == {fold(w) for w in want}
            return RuleResult(ok, self.field)
        if isinstance(want, int):
            g = num(got); return RuleResult(g is not None and g == Dc(want), self.field)
        if self.field in EXACT:
            return RuleResult(isinstance(got, str) and " ".join(got.split()) == " ".join(str(want).split()), self.field)
        return RuleResult(isinstance(got, str) and " ".join(got.split()).lower() == " ".join(str(want).split()).lower(), self.field)

FIELDS = {
    "multi_doc": [("R-CONFLICTS", "conflicts"), ("R-NAME", "name"), ("R-DOB", "dob"), ("R-REVIEW", "needs_manual_review")],
    "pan_name": [("R-MATCH", "pan_matches_name"), ("R-REASON", "reason")],
    "record_conflicts": [("R-INCONSISTENT", "inconsistent_fields"), ("R-AGE", "age"), ("R-MINOR", "minor")],
    "ocr_repair": [("R-PAN", "pan"), ("R-IFSC", "ifsc"), ("R-REPAIRED", "repaired")],
    "batch": [("R-MINORS", "minors"), ("R-INVALID-PANS", "invalid_pans"), ("R-ELIGIBLE", "current_account_eligible")],
}
def answer_fields(kind): return [f for _, f in FIELDS[kind]]
def rule_ids_for(kind): return ("R-FMT",) + tuple(r for r, _ in FIELDS[kind])
def all_rules():
    rules = {"R-FMT": Fmt()}
    for kind, fs in FIELDS.items():
        for rid, f in fs:
            if rid in rules and rules[rid].field != f:      # same id used by two families with different fields: keep fields apart
                raise ValueError(rid)
            rules[rid] = Field(rid, f)
    return rules
RULES = all_rules()

def parse(sub):
    if not isinstance(sub, dict): return None
    if "answer" in sub or "status" in sub: return {"status": sub.get("status", "plan"), "answer": sub.get("answer")}
    return {"status": "plan", "answer": sub}

def make_grader(world_factory) -> Grader: return Grader(RULES, world_factory, parse)
