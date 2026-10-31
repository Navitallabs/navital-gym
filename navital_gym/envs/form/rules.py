"""Form Desk grader rules: one rule per answer field, so a submission wrong in exactly one field loses exactly one rule.
The expected value comes from the independent oracle, never from the task file's gold_answer."""
from __future__ import annotations
from decimal import Decimal as Dc, InvalidOperation
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import oracle

def num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        d = Dc(str(x).replace(",", "").strip()) if not isinstance(x, float) else Dc(repr(x))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None

def expected(ctx: Ctx) -> dict:
    if "oracle" not in ctx.cache:
        t = ctx.task
        ctx.cache["oracle"] = oracle.solve(t.meta["kind"], t.params["world"])
    return ctx.cache["oracle"]

class Fmt(Rule):
    id, gate, description = "R-FMT", True, "answer is a JSON object"
    def check(self, ctx):
        return RuleResult(isinstance(ctx.sub.get("answer"), dict), "answer must be an object")

EXACT = {"pan", "ifsc", "full_name"}   # compared case-sensitively (whitespace still trimmed); full_name must be Title Case as the prompt asks

class Field(Rule):
    """answer[field] must equal the oracle's value: bools exact, numbers exact (Decimal), None means the key must be present and null, strings case/space-insensitive."""
    def __init__(self, rid, field, description=""):
        self.id, self.field, self.description = rid, field, description
    def check(self, ctx):
        want = expected(ctx)[self.field]
        ans = ctx.sub["answer"]
        if want is None:
            return RuleResult(self.field in ans and ans[self.field] is None, f"{self.field} must be null")
        got = ans.get(self.field)
        if self.field in ("governing_act", "pin") and isinstance(got, int) and not isinstance(got, bool):
            got = str(got)      # 1961 / 2025 or a PIN code written as a number is the same answer (the instructions say whole numbers as numbers)
        if isinstance(want, bool):
            return RuleResult(isinstance(got, bool) and got == want, self.field)
        if isinstance(want, int):
            g = num(got)
            return RuleResult(g is not None and g == Dc(want), self.field)
        if self.field in EXACT:   # identifiers: case-sensitive, a lower-case PAN or IFSC is invalid under the policy
            return RuleResult(isinstance(got, str) and " ".join(got.split()) == " ".join(str(want).split()), self.field)
        return RuleResult(isinstance(got, str) and " ".join(got.split()).lower() == " ".join(str(want).split()).lower(), self.field)

# kind -> [(rule id, answer field)]
FIELDS = {
    "kyc_fill": [("R-NAME", "full_name"), ("R-DOB", "dob"), ("R-AGE", "age"), ("R-MINOR", "minor"), ("R-GUARDIAN", "guardian_required"),
                 ("R-PAN", "pan"), ("R-PAN-VALID", "pan_valid"), ("R-MOBILE", "mobile"), ("R-MOBILE-VALID", "mobile_valid"),
                 ("R-IFSC", "ifsc"), ("R-IFSC-VALID", "ifsc_valid"), ("R-ACCOUNT", "account_type_allowed")],
    "address_parse": [("R-HOUSE", "house"), ("R-CITY", "city"), ("R-STATE", "state"), ("R-PIN", "pin")],
    "pin_consistency": [("R-CONSISTENT", "consistent")],
    "number_parse": [("R-VALUE", "value")],
    "fiscal_year": [("R-FY", "financial_year"), ("R-ACT", "governing_act"), ("R-AY", "assessment_year"), ("R-ADV-TAX", "next_advance_tax_date")],
}
def answer_fields(kind: str) -> list:
    return [f for _, f in FIELDS[kind]]

def rule_ids_for(kind: str) -> tuple:
    return ("R-FMT",) + tuple(r for r, _ in FIELDS[kind])

def all_rules() -> dict:
    rules = {"R-FMT": Fmt()}
    for kind, fs in FIELDS.items():
        for rid, f in fs:
            rules[rid] = Field(rid, f)
    return rules
RULES = all_rules()

def parse(sub):
    """Accept {"status":"plan","answer":{...}} or a bare answer object. Anything else is not a submission."""
    if not isinstance(sub, dict):
        return None
    if "answer" in sub or "status" in sub:
        return {"status": sub.get("status", "plan"), "answer": sub.get("answer")}
    return {"status": "plan", "answer": sub}

def make_grader(world_factory) -> Grader:
    return Grader(RULES, world_factory, parse)
