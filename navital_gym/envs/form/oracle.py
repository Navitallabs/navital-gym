"""Independent reference solver for Form Desk. It reads only the task's input (world) and the policy tables, never gold_answer.
Written separately from the task generator (gen_forms.py) so that agreement between the two is a real test."""
from __future__ import annotations
import re, datetime as dt
from fractions import Fraction
from . import data as D

PAN_RE, IFSC_RE, MOB_RE = re.compile(D.PAN_PATTERN), re.compile(D.IFSC_PATTERN), re.compile(D.MOBILE_PATTERN)

def normalise_mobile(raw: str) -> str:
    """Strip only a leading +91 / 91 / 0 country or trunk prefix; any other extra or missing digits stay and make the number invalid."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits

def kyc(world: dict) -> dict:
    doc = world["document_text"]; today = dt.date.fromisoformat(world["today"])
    f = {}
    for line in doc.splitlines():
        k, _, v = line.partition(":")
        f[k.strip().upper()] = v.strip()
    parts = f["NAME"].split()
    name = " ".join(parts[1:] + parts[:1]).title()          # the document puts the surname first
    d, m, y = (int(x) for x in f["DOB"].split("/"))
    dob = dt.date(y, m, d)
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    pan = f["PAN"]; mob = normalise_mobile(f["MOBILE"]); ifsc = f["BANK IFSC"]; acct = f["REQUESTED ACCOUNT"].lower()
    minor = age < 18
    return {"full_name": name, "dob": dob.isoformat(), "age": age, "minor": minor, "guardian_required": minor,
            "pan": pan if PAN_RE.match(pan) else None, "pan_valid": bool(PAN_RE.match(pan)),
            "mobile": mob if MOB_RE.match(mob) else None, "mobile_valid": bool(MOB_RE.match(mob)),
            "ifsc": ifsc if IFSC_RE.match(ifsc) else None, "ifsc_valid": bool(IFSC_RE.match(ifsc)),
            "account_type_allowed": not (minor and acct == "current")}

def address(world: dict) -> dict:
    raw = world["raw_address"]
    parts = [p.strip() for p in re.split(r"[;,]", raw) if p.strip()]
    m = re.search(r"\b(\d{6})\b", raw)
    pin = m.group(1) if m else None          # a malformed PIN is reported as null, never repaired
    city_key = next(p.upper() for p in parts if p.upper() in D.CITIES)
    disp, state, _ = D.CITIES[city_key]
    return {"house": parts[0], "city": disp, "state": state, "pin": pin}

def pin_consistency(world: dict) -> dict:
    z = D.zone_of_state(world["state"])
    return {"consistent": world["pin"][0] == z, "expected_first_digit": z}

_UNITS = {"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "पचहत्तर": 75, "पचास": 50, "सौ": 100,
          "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_MULT = {"हज़ार": 1000, "हजार": 1000, "hazaar": 1000, "thousand": 1000, "लाख": 100000, "lakh": 100000, "lac": 100000, "करोड़": 10000000, "करोड": 10000000, "crore": 10000000}

def _num(tok: str):
    t = tok.replace(",", "")
    if t in _UNITS:
        return Fraction(_UNITS[t])
    return Fraction(t)

def number(text: str) -> int:
    t = text.strip().replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    toks = t.replace("-", " ").split()
    if len(toks) == 1:
        return int(_num(toks[0]))
    mult = _MULT[toks[-1].lower()] if toks[-1].lower() in _MULT else _MULT[toks[-1]]
    head = toks[:-1]
    if head == ["डेढ़"]: val = Fraction(3, 2)
    elif head == ["ढाई"]: val = Fraction(5, 2)
    elif head == ["सवा"]: val = Fraction(5, 4)
    elif head[0] == "सवा": val = _num(head[1]) + Fraction(1, 4)
    elif head[0] == "साढ़े": val = _num(head[1]) + Fraction(1, 2)
    elif head[0] == "पौने": val = _num(head[1]) - Fraction(1, 4)
    elif len(head) == 4 and head[1:3] == ["and", "a"] and head[3] == "half": val = _num(head[0]) + Fraction(1, 2)
    elif head[1:] == ["and", "a", "half"]: val = _num(head[0]) + Fraction(1, 2)
    else: val = _num(head[0])
    out = val * mult
    assert out.denominator == 1, text
    return int(out)

def _fy_start(d: dt.date) -> int:
    return d.year if d.month >= 4 else d.year - 1

def fiscal(world: dict) -> dict:
    dd, mm, yyyy = (int(x) for x in world["date_dd_mm_yyyy"].split("/"))
    d = dt.date(yyyy, mm, dd); s = _fy_start(d)
    cand = [dt.date(s, 6, 15), dt.date(s, 9, 15), dt.date(s, 12, 15), dt.date(s + 1, 3, 15), dt.date(s + 1, 6, 15)]
    nxt = next(x for x in cand if x >= d)
    return {"financial_year": f"{s}-{str(s + 1)[-2:]}", "assessment_year": f"{s + 1}-{str(s + 2)[-2:]}", "next_advance_tax_date": nxt.isoformat()}

def solve(kind: str, world: dict) -> dict:
    if kind == "kyc_fill": return kyc(world)
    if kind == "address_parse": return address(world)
    if kind == "pin_consistency": return pin_consistency(world)
    if kind == "number_parse": return {"value": number(world["text"])}
    if kind == "fiscal_year": return fiscal(world)
    raise KeyError(kind)
