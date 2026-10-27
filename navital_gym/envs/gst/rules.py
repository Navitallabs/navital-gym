"""GST Desk grader rules. One rule per answer field, so a submission that is wrong in exactly one field loses
exactly one rule. The expected value comes from the oracle (independent of the task file's gold_answer)."""
from __future__ import annotations
from decimal import Decimal as Dc, InvalidOperation
from ...core.grader import Rule, RuleResult, Grader, Ctx
from . import oracle

def num(x):
    """Decimal from an int/str/float answer; bool and everything else is not a number."""
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
        ctx.cache["oracle"] = oracle.solve(t.meta["kind"], t.params["world"], t.params["rules"], t.prompt)
    return ctx.cache["oracle"]

class Fmt(Rule):
    id, gate, description = "R-FMT", True, "answer is a JSON object"
    def check(self, ctx):
        return RuleResult(isinstance(ctx.sub.get("answer"), dict), "answer must be an object")

class Field(Rule):
    """answer[field] must equal the oracle's value (numbers: exact Decimal; strings: case/space-insensitive; bools exact)."""
    def __init__(self, rid, field, description=""):
        self.id, self.field, self.description = rid, field, description
    def check(self, ctx):
        want, got = expected(ctx)[self.field], ctx.sub["answer"].get(self.field)
        if isinstance(want, bool):
            return RuleResult(isinstance(got, bool) and got == want, f"{self.field}")
        if isinstance(want, (Dc, int)):
            g = num(got)
            return RuleResult(g is not None and g == Dc(str(want)), f"{self.field}")
        if isinstance(want, list):
            return RuleResult(isinstance(got, list) and sorted(map(str, got)) == sorted(map(str, want)), f"{self.field}")
        return RuleResult(isinstance(got, str) and got.strip().lower() == str(want).strip().lower(), f"{self.field}")

# kind -> [(rule id, answer field)]
FIELDS = {
    "invoice": [("R-TAXABLE", "taxable_value"), ("R-CGST", "cgst"), ("R-SGST", "sgst"), ("R-IGST", "igst"),
                ("R-ROUNDOFF", "round_off"), ("R-TOTAL", "invoice_total"), ("R-TAXTYPE", "tax_type")],
    "place_of_supply": [("R-TAXTYPE", "tax_type")],
    "itc_reconciliation": [("R-ITC-AMOUNT", "eligible_itc"), ("R-ITC-INVOICES", "eligible_invoices")],
    "easy_tax": [("R-TAX", "tax")],
    "easy_days_late": [("R-DAYS", "days_late")],
    "late_filing": [("R-DUE", "due_date"), ("R-DAYS", "days_late"), ("R-FEE", "late_fee"), ("R-INTEREST", "interest")],
}
def rule_ids_for(kind: str, prompt: str = "") -> tuple:
    if kind == "threshold":
        return ("R-FMT", "R-ELIGIBLE" if "composition" in prompt.lower() else "R-REQUIRED")
    return ("R-FMT",) + tuple(r for r, _ in FIELDS[kind])

def all_rules() -> dict:
    rules = {"R-FMT": Fmt(), "R-REQUIRED": Field("R-REQUIRED", "required"), "R-ELIGIBLE": Field("R-ELIGIBLE", "eligible")}
    for kind, fs in FIELDS.items():
        for rid, f in fs:
            rules.setdefault(rid, Field(rid, f))
    return rules

def parse(sub):
    """Accept {"status":"plan","answer":{...}} or a bare answer object. Anything else is not a submission."""
    if not isinstance(sub, dict):
        return None
    if "answer" in sub or "status" in sub:
        return {"status": sub.get("status", "plan"), "answer": sub.get("answer")}
    return {"status": "plan", "answer": sub}

def make_grader(world_factory) -> Grader:
    return Grader(all_rules(), world_factory, parse)
