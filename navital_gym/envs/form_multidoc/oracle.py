"""Independent reference solver for Form Desk: hard. Reads only the task's input (world) and the policy tables, never gold_answer.
Written separately from the task generator."""
from __future__ import annotations
import re, datetime as dt
from . import data as D

PAN_RE, IFSC_RE = re.compile(D.PAN_PATTERN), re.compile(D.IFSC_PATTERN)

def _lines(text):
    out = {}
    for line in text.splitlines():
        k, sep, v = line.partition(":")
        if sep: out[k.strip().lower()] = v.strip()
    return out

def _date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if m: return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})", s)
    if m: return dt.date(int(m.group(3)), D.MONTHS.index(m.group(2).title()) + 1, int(m.group(1)))
    raise ValueError(s)

def _age(dob, on):
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))

def _given_match(a, b):
    return len(a) == len(b) and all(x.lower() == y.lower() or (len(x) == 1 and y.lower().startswith(x.lower())) or (len(y) == 1 and x.lower().startswith(y.lower())) for x, y in zip(a, b))

def multi_doc(world):
    docs = world["documents"]
    card, book, form = _lines(docs["pan_card"]), _lines(docs["passbook"]), _lines(docs["application_form"])
    ct = card["name (surname first)"].split(); csur, cgiv = ct[0], ct[1:]
    def person_last_surname(s): t = s.split(); return t[-1], t[:-1]
    conflicts = []
    ok = True
    for sur, giv in (person_last_surname(book["account holder"]), person_last_surname(form["applicant"])):
        if sur.lower() != csur.lower() or not _given_match(giv, cgiv): ok = False
    if not ok: conflicts.append("name")
    cdob = _date(card["date of birth"])
    if _date(book["date of birth"]) != cdob or _date(form["dob"]) != cdob: conflicts.append("dob")
    if book["pan on record"] != card["pan"] or form["pan"] != card["pan"]: conflicts.append("pan")
    conflicts.sort()
    return {"conflicts": conflicts, "name": " ".join(w.title() for w in cgiv + [csur]), "dob": cdob.isoformat(), "needs_manual_review": ("dob" in conflicts or "pan" in conflicts)}

def pan_name(world):
    f = _lines(world["document_text"]); name = f["applicant name"]; et = f["entity type"]; pan = f["pan quoted"]
    if pan[3] != D.HOLDER[et]: return {"pan_matches_name": False, "reason": "holder_type_mismatch"}
    ref = name.split()[-1] if et == "Individual" else name
    if pan[4].upper() != ref[0].upper(): return {"pan_matches_name": False, "reason": "surname_initial_mismatch"}
    return {"pan_matches_name": True, "reason": "ok"}

def record_conflicts(world):
    text = world["document_text"]; head = text.splitlines()[0]
    form_date = _date(re.search(r"form date ([\d/]+)", head).group(1)); f = _lines(text)
    true_age = _age(_date(f["date of birth"]), form_date); true_minor = true_age < 18
    bad = []
    if int(f["age (stated)"]) != true_age: bad.append("age")
    if (f["minor"].lower() == "yes") != true_minor: bad.append("minor")
    zone = f["pin"][0]
    if f["state"] not in D.ZONES.get(zone, []): bad.append("pin_state")
    if D.BANKS.get(f["ifsc"][:4]) != f["bank"]: bad.append("bank")
    return {"inconsistent_fields": sorted(bad), "age": true_age, "minor": true_minor}

def _repair(value, classes):
    """classes: one of 'L' (letter) / 'D' (digit) per position, or '0' for a literal zero, or 'A' (any alphanumeric, never repaired). Returns repaired string or None."""
    out = []
    for ch, c in zip(value, classes):
        if c == "L": ch = D.TO_LETTER.get(ch, ch) if ch.isdigit() else ch; ok = ch.isalpha() and ch.isupper()
        elif c == "D": ch = D.TO_DIGIT.get(ch, ch) if ch.isalpha() else ch; ok = ch.isdigit()
        elif c == "0": ch = "0" if ch in ("0", "O") else ch; ok = ch == "0"
        else: ok = ch.isalnum() and (ch.isdigit() or ch.isupper())
        if not ok: return None
        out.append(ch)
    return "".join(out)

def ocr_repair(world):
    f = _lines(world["document_text"]); pan0, ifsc0 = f["pan"], f["bank ifsc"]; rep = []
    pan = _repair(pan0, "LLLLLDDDDL") if len(pan0) == 10 else None
    if pan is not None and not PAN_RE.match(pan): pan = None
    ifsc = _repair(ifsc0, "LLLL0AAAAAA") if len(ifsc0) == 11 else None
    if ifsc is not None and not IFSC_RE.match(ifsc): ifsc = None
    if pan is not None and pan != pan0: rep.append("pan")
    if ifsc is not None and ifsc != ifsc0: rep.append("ifsc")
    return {"pan": pan, "ifsc": ifsc, "repaired": sorted(rep)}

def batch(world):
    lines = world["document_text"].splitlines(); ref = _date(re.search(r"reference date ([\d/]+)", lines[0]).group(1))
    minors, inv, elig = 0, [], []
    for ln in lines[1:]:
        m = re.match(r"(R\d+): .*? \| DOB ([\d/]+) \| PAN (\S+) \| account requested: (\w+)", ln)
        rid, dob, pan, acct = m.groups(); age = _age(_date(dob), ref); ok = bool(PAN_RE.match(pan))
        if age < 18: minors += 1
        if not ok: inv.append(rid)
        if acct == "current" and age >= 18 and ok: elig.append(rid)
    return {"minors": minors, "invalid_pans": inv, "current_account_eligible": elig}

def solve(kind, world):
    return {"multi_doc": multi_doc, "pan_name": pan_name, "record_conflicts": record_conflicts, "ocr_repair": ocr_repair, "batch": batch}[kind](world)
