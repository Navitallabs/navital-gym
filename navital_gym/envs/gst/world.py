"""GST Desk world: read-only tools over one task's synthetic documents and the env's (simplified) rules.
The agent sees the documents and the policy through tools; it never sees gold, the oracle or `meta`."""
from __future__ import annotations
import copy, datetime as dt, re
from ...core.world import World, tool, ToolError

CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_BODY = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]$")      # the 10-character PAN, then the entity number (1-9 or A-Z)
STATE_CODES = {7: "Delhi", 9: "Uttar Pradesh", 19: "West Bengal", 24: "Gujarat", 27: "Maharashtra", 29: "Karnataka", 32: "Kerala", 33: "Tamil Nadu"}

def gstin_check_char(base14: str) -> str:
    s = 0
    for i, c in enumerate(base14):
        p = CH.index(c) * (1 if i % 2 == 0 else 2)
        s += p // 36 + p % 36
    return CH[(36 - s % 36) % 36]

class GstWorld(World):
    env_name = "gst"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        self.docs = copy.deepcopy(task.params["world"])
        self.rules = copy.deepcopy(task.params["rules"])

    def snapshot(self) -> dict:
        return {"docs": self.docs, "rules": self.rules}

    @tool("The documents for this task: the invoice (supplier, buyer, lines, freight, place of supply) or the purchase register. Empty if the prompt already contains everything.")
    def get_documents(self) -> dict:
        d = copy.deepcopy(self.docs)
        d.pop("rule", None)   # a designer's rule note, not a document
        return {"documents": d}

    @tool("The env's tax policy for this snapshot: rates by item code, thresholds, filing days, late fee and interest, rounding. Simplified env rules, not live law.")
    def get_policy(self) -> dict:
        r = copy.deepcopy(self.rules)
        return {"policy": r}

    @tool("Tax rate in percent for an item code.", {"code": {"type": "string", "description": "item code, e.g. G-ELEC"}})
    def lookup_rate(self, code: str) -> dict:
        rates = self.rules.get("rates") or {}
        if not rates:
            raise ToolError("this task has no item-code table: the rate is stated in the question")
        if code not in rates:
            raise ToolError(f"unknown item code {code!r}")
        return {"code": code, "rate_pct": str(rates[code])}

    @tool("Validate a 15-character GSTIN (state code, PAN-shaped body, checksum). Says nothing about the business.", {"gstin": {"type": "string", "description": "15-character GSTIN"}})
    def validate_gstin(self, gstin: str) -> dict:
        g = str(gstin).strip().upper()
        if len(g) != 15 or any(c not in CH for c in g):
            return {"valid": False, "reason": "must be 15 letters/digits"}
        try:
            code = int(g[:2])
        except ValueError:
            code = -1
        shape = (1 <= code <= 38 or code in (97, 99)) and bool(GSTIN_BODY.match(g[2:13])) and g[13] == "Z"      # state code, PAN-shaped body, entity number, 'Z'
        ok = shape and gstin_check_char(g[:14]) == g[14]
        reason = None if ok else ("state code is not a valid GST state code" if not (1 <= code <= 38 or code in (97, 99)) else "the 10-character PAN part must look like AAAAA9999A" if not GSTIN_BODY.match(g[2:13]) else "the 14th character must be Z" if g[13] != "Z" else "wrong check character")
        return {"valid": bool(ok), "state_code": g[:2], "state": STATE_CODES.get(code), "pan": g[2:12], **({"reason": reason} if reason else {})}

    @tool("Weekday and holiday status of a date (YYYY-MM-DD). The policy states whether due dates move.", {"date": {"type": "string", "description": "YYYY-MM-DD"}})
    def calendar_info(self, date: str) -> dict:
        try:
            d = dt.date.fromisoformat(date)
        except (TypeError, ValueError):
            raise ToolError(f"bad date {date!r}, use YYYY-MM-DD")
        return {"date": d.isoformat(), "weekday": d.strftime("%A"), "is_weekend": d.weekday() >= 5,
                "is_listed_holiday": d.isoformat() in set(self.rules.get("holidays", []))}
