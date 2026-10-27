"""Form Desk: hard world: read-only tools over one task's synthetic input and the env's (simplified) rules. The agent never sees gold, the oracle or `meta`."""
from __future__ import annotations
import copy, re
from ...core.world import World, tool, ToolError
from . import data as D

class FormMultidocWorld(World):
    env_name = "form_multidoc"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        self.inp = copy.deepcopy(task.params["world"])

    def snapshot(self) -> dict:
        return {"input": self.inp}

    @tool("The input for this task: the text of one or more documents, as described in the request.")
    def get_input(self) -> dict:
        return {"input": copy.deepcopy(self.inp)}

    @tool("The env's rules for this family of tasks (simplified, not live systems): comparison, PAN structure, consistency checks, OCR repair and batch rules.")
    def get_policy(self) -> dict:
        return {"policy": {
            "pan_format": "10 characters: 5 upper-case letters, 4 digits, 1 upper-case letter. The 4th letter is the holder type and must be one of A B C F G H L J P T. Lower case is invalid.",
            "ifsc_format": "11 characters: 4 upper-case letters, the digit 0, then 6 letters or digits (upper case).",
            "multi_document": "Compare the passbook and the application form with the PAN card. Names match when the surname is the same (ignoring case) and the given names are the same in number and order, where a given name written as a single letter matches any given name that starts with that letter. Dates match when they are the same calendar date, whatever their written format. PANs match only if identical. Dates in the documents may be written dd/mm/yyyy, dd-mm-yyyy or 'd Mon yyyy'. In documents that write given names first, the surname is the last word; the PAN card writes the surname first. Precedence: the PAN card is the reference document.",
            "pan_structure": "The 4th character of a PAN is the holder type: P for an individual, C for a company, F for a firm, T for a trust. The 5th character is the first letter of the surname for an individual, or the first letter of the entity name for any other holder type.",
            "record_checks": "age: the stated age must equal the age in completed years computed from the date of birth on the form date. minor: the Minor box must be Yes exactly when that computed age is under 18. pin_state: the first digit of the PIN is the postal zone and the state must be in that zone (zones: " + "; ".join(f"{z}: {', '.join(s)}" for z, s in D.ZONES.items()) + "). bank: the first four letters of the IFSC identify the bank (" + "; ".join(f"{c} = {b}" for c, b in D.BANKS.items()) + ") and must agree with the bank name on the form.",
            "ocr_repair": "OCR look-alikes: the letters O, I, S, B, Z are read as the digits 0, 1, 5, 8, 2 and the reverse. A character may be repaired only to fix its class: a digit in a letter position becomes its look-alike letter, a letter in a digit position becomes its look-alike digit; the 5th IFSC character must be 0 and an O there becomes 0. PAN positions 1-5 are letters, 6-9 digits, 10 a letter; IFSC positions 1-4 are letters, 5 is 0, 6-11 are letters or digits (never repaired). If any character cannot be fixed this way, or the repaired value still fails the format (for example its 4th letter is not a holder type), the field is null. Never guess any other repair. A field set to null is not listed in repaired.",
            "batch": "Age is in completed years on the reference date. A record is a minor if its age is under 18. A PAN is invalid if it does not fit the PAN format. A record is eligible for a current account only if it requests a current account, is 18 or older and has a valid PAN.",
            "dates": "Dates in answers are YYYY-MM-DD; yes/no are true/false; counts are whole numbers; lists are JSON arrays of strings with each item at most once, [] when empty.",
            "note": "Names, numbers and documents are synthetic. These are env rules, not claims about live systems."}}

    @tool("Check a PAN against the env's format rule. Says nothing about whether the PAN exists.", {"pan": {"type": "string", "description": "PAN as written"}})
    def validate_pan(self, pan: str) -> dict:
        ok = bool(re.match(D.PAN_PATTERN, str(pan)))
        return {"valid": ok, "reason": None if ok else "does not match 5 letters + 4 digits + 1 letter with a valid 4th letter, upper case"}

    @tool("Check an IFSC against the env's format rule. Says nothing about whether the branch exists.", {"ifsc": {"type": "string", "description": "IFSC as written"}})
    def validate_ifsc(self, ifsc: str) -> dict:
        ok = bool(re.match(D.IFSC_PATTERN, str(ifsc)))
        return {"valid": ok, "reason": None if ok else "must be 4 letters, 0, then 6 letters or digits"}

    @tool("Postal zone of a 6-digit PIN: its first digit and the states in that zone (env table, simplified).", {"pin": {"type": "string", "description": "6-digit PIN"}})
    def pin_zone(self, pin: str) -> dict:
        p = str(pin).strip()
        if not re.fullmatch(r"\d{6}", p): raise ToolError("a PIN has exactly 6 digits")
        z = p[0]
        if z not in D.ZONES: raise ToolError(f"zone {z} is not in this env's table")
        return {"pin": p, "zone": z, "states": D.ZONES[z]}
