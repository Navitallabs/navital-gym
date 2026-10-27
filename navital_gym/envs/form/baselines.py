"""Scripted agents for Form Desk: empty (answers nothing), shotgun (plausible but unchecked), naive (a weak agent: no validation, shallow parsing), oracle."""
from ...core.runner import ScriptedAgent
from . import oracle

def _kind(task): return task.meta["kind"]

def empty(obs, call, task): return {"status": "plan", "answer": {}}

def shotgun(obs, call, task):
    k = _kind(task)
    guess = {"kyc_fill": {"minor": False, "pan_valid": True, "mobile_valid": True, "ifsc_valid": True, "guardian_required": False, "account_type_allowed": True},
             "address_parse": {"state": "Maharashtra", "city": "Mumbai", "pin": "400001"},
             "pin_consistency": {"consistent": True}, "number_parse": {"value": 100000},
             "fiscal_year": {"financial_year": "2026-27", "assessment_year": "2027-28", "next_advance_tax_date": "2026-12-15"}}[k]
    return {"status": "plan", "answer": guess}

def naive(obs, call, task):
    """A weak, plausible agent: copies identifiers as written without validating them, trusts the state abbreviation, always says a PIN is consistent,
    parses only digit-style amounts, and treats the calendar year as the financial year. It is NOT the oracle."""
    import re, datetime as dt
    k = _kind(task); w = task.params["world"]
    if k == "kyc_fill":
        o = oracle.kyc(w); f = {l.split(":", 1)[0].strip(): l.split(":", 1)[1].strip() for l in w["document_text"].splitlines()}
        digits = re.sub(r"\D", "", f["MOBILE"])[-10:]
        return {"status": "plan", "answer": dict(o, pan=f["PAN"], pan_valid=True, mobile=digits, mobile_valid=True, ifsc=f["BANK IFSC"], ifsc_valid=True)}
    if k == "address_parse":
        parts = [p.strip() for p in re.split(r"[;,]", w["raw_address"]) if p.strip()]
        from . import data as D
        city_key = next(p.upper() for p in parts if p.upper() in D.CITIES)
        abbr = next((p for p in parts if p in D.STATE_ABBR), None)
        digits = re.findall(r"\d{5,6}", w["raw_address"])
        return {"status": "plan", "answer": {"house": parts[0], "city": D.CITIES[city_key][0], "state": D.STATE_ABBR.get(abbr), "pin": digits[-1] if digits else None}}
    if k == "pin_consistency": return {"status": "plan", "answer": {"consistent": True}}
    if k == "number_parse":
        m = re.search(r"([\d,.]+)\s*(lakh|crore)?", w["text"], re.I)
        try:
            v = float(m.group(1).replace(",", "")) * {"lakh": 100000, "crore": 10000000, None: 1}[m.group(2).lower() if m.group(2) else None]
        except (ValueError, AttributeError):
            v = 0
        return {"status": "plan", "answer": {"value": int(round(v))}}
    if k == "fiscal_year":
        d, m, y = (int(x) for x in w["date_dd_mm_yyyy"].split("/"))
        nxt = next(x for x in [dt.date(y, 6, 15), dt.date(y, 9, 15), dt.date(y, 12, 15), dt.date(y + 1, 3, 15)] if x >= dt.date(y, m, d))
        return {"status": "plan", "answer": {"financial_year": f"{y}-{str(y + 1)[-2:]}", "assessment_year": f"{y + 1}-{str(y + 2)[-2:]}", "next_advance_tax_date": nxt.isoformat()}}
    return {"status": "plan", "answer": {}}

def reject_only(obs, call, task):
    """The 'always reject' floor: reads the input shallowly but reports every identifier and PIN as invalid / null / inconsistent and every amount as 0."""
    k = _kind(task); w = task.params["world"]
    if k == "kyc_fill":
        o = oracle.kyc(w)
        return {"status": "plan", "answer": dict(o, pan=None, pan_valid=False, mobile=None, mobile_valid=False, ifsc=None, ifsc_valid=False)}
    if k == "address_parse":
        o = oracle.address(w); return {"status": "plan", "answer": dict(o, pin=None)}
    if k == "pin_consistency": return {"status": "plan", "answer": {"consistent": False}}
    if k == "number_parse": return {"status": "plan", "answer": {"value": 0}}
    return {"status": "plan", "answer": {}}

def oracle_agent(obs, call, task):
    return {"status": "plan", "answer": oracle.solve(_kind(task), task.params["world"])}

def get_baselines():
    return {n: ScriptedAgent(n, f) for n, f in [("empty", empty), ("shotgun", shotgun), ("naive", naive), ("reject_only", reject_only), ("oracle", oracle_agent)]}
