"""Form Desk world: read-only tools over one task's synthetic input and the env's (simplified) format rules.
The agent never sees gold, the oracle or `meta`."""
from __future__ import annotations
import copy, re
from ...core.world import World, tool, ToolError
from . import data as D

class FormWorld(World):
    env_name = "form"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        self.inp = copy.deepcopy(task.params["world"])

    def snapshot(self) -> dict:
        return {"input": self.inp}

    @tool("The input for this task: a document's text, an address string, a PIN and state, a phrase, or a date, as given in the request. Some requests already contain everything in the prompt.")
    def get_input(self) -> dict:
        return {"input": copy.deepcopy(self.inp)}

    @tool("The env's format rules (simplified, not live systems): PAN, IFSC and mobile patterns, minors rule, postal zones, financial-year and advance-tax rules.")
    def get_policy(self) -> dict:
        return {"policy": {
            "pan": "5 letters, 4 digits, 1 letter; the 4th letter is a holder type from A B C F G H L J P T. Upper case only.",
            "ifsc": "4 letters, then the digit 0, then 6 letters or digits. Upper case.",
            "mobile": "10 digits starting with 6, 7, 8 or 9 after removing spaces and dashes and a single leading 0 (11 digits) or +91 / 91 (12 digits). Any other length is invalid.",
            "minor": "Under 18 on the given date. A minor needs a guardian and cannot open a current account (env rule).",
            "postal_zones": D.ZONES,
            "financial_year": "April to March, written YYYY-YY (e.g. 2026-27). Income earned before 1 April 2026: Income-tax Act, 1961; the assessment year is the next financial year. Income earned on or after 1 April 2026: Income-tax Act, 2025, which uses a single 'tax year' (the same April-March year) and has no assessment year. Advance-tax dates: 15 June, 15 September, 15 December, 15 March (simplified).",
            "address": "house = the first part of the address, up to the first comma or semicolon, as written, without surrounding spaces (\"Shop 12, Rose Apartments, Pune\" gives house \"Shop 12\"). city = the city named in the address, normal capitalisation. state = the full state name (infer it from the city or PIN zone if only an abbreviation or nothing is written). pin = the 6-digit PIN, or null if it is not exactly 6 digits.",
            "invalid_values": "A value that fails its format rule must be reported as null, never repaired or guessed.",
            "note": "Names, numbers and addresses are synthetic. These are env rules, not claims about live systems."}}

    @tool("Check a PAN against the env's format rule. Says nothing about whether the PAN exists.", {"pan": {"type": "string", "description": "PAN as written"}})
    def validate_pan(self, pan: str) -> dict:
        ok = bool(re.match(D.PAN_PATTERN, str(pan)))
        return {"valid": ok, "reason": None if ok else "does not match 5 letters + 4 digits + 1 letter with a valid 4th letter, upper case"}

    @tool("Check an IFSC against the env's format rule. Says nothing about whether the branch exists.", {"ifsc": {"type": "string", "description": "IFSC as written"}})
    def validate_ifsc(self, ifsc: str) -> dict:
        ok = bool(re.match(D.IFSC_PATTERN, str(ifsc)))
        return {"valid": ok, "reason": None if ok else "must be 4 letters, 0, then 6 letters or digits"}

    @tool("Normalise a mobile number as written (spaces, dashes, 0 or +91 prefix) and check the 10-digit rule.", {"number": {"type": "string", "description": "mobile as written"}})
    def validate_mobile(self, number: str) -> dict:
        from .oracle import normalise_mobile
        digits = normalise_mobile(str(number))
        ok = bool(re.match(D.MOBILE_PATTERN, digits))
        return {"normalised": digits, "valid": ok}

    @tool("Postal zone of a 6-digit PIN: its first digit and the states in that zone (env table, simplified).", {"pin": {"type": "string", "description": "6-digit PIN"}})
    def pin_zone(self, pin: str) -> dict:
        p = str(pin).strip()
        if not re.fullmatch(r"\d{6}", p):
            raise ToolError("a PIN has exactly 6 digits")
        z = p[0]
        if z not in D.ZONES:
            raise ToolError(f"zone {z} is not in this env's table")
        return {"pin": p, "zone": z, "states": D.ZONES[z]}
