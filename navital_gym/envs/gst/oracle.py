"""Reference solver ("oracle") for GST Desk. It reads a task row's `world` and `rules` and returns the answer the
env's simplified rules imply. The grader (rules.py) checks submissions against this, not against the stored
gold_answer, so a wrong gold in a task file shows up as an oracle/gold disagreement (see check_gold in __init__.py).
All arithmetic is Decimal; nothing here touches the clock, the network or randomness."""
from __future__ import annotations
import datetime as dt
from decimal import Decimal as Dc, ROUND_HALF_UP

def q2(x: Dc) -> Dc:
    return x.quantize(Dc("0.01"), rounding=ROUND_HALF_UP)

def q0(x: Dc) -> Dc:
    return x.quantize(Dc("1"), rounding=ROUND_HALF_UP)

def invoice(world: dict, rules: dict) -> dict:
    rates = {k: Dc(str(v)) for k, v in rules["rates"].items()}
    lines = world["lines"]
    top = max(rates[l["hsn"]] for l in lines)
    goods = Dc(0); tax = Dc(0)
    for l in lines:
        value = q2(Dc(str(l["qty"])) * Dc(str(l["unit_price"])) * (Dc(1) - Dc(str(l.get("disc_pct", 0))) / Dc(100)))
        goods += value
        tax += q2(value * rates[l["hsn"]] / Dc(100))
    freight = q2(Dc(str(world.get("freight", 0))))
    tax += q2(freight * top / Dc(100))
    taxable = q2(goods + freight)
    inter = world["supplier"]["state"] != world["place_of_supply"]
    if inter:
        igst, cgst, sgst = q2(tax), Dc(0), Dc(0)
    else:
        cgst = q2(tax / 2); sgst = q2(tax - cgst); igst = Dc(0)
    gross = taxable + cgst + sgst + igst
    total = q0(gross)
    return {"taxable_value": taxable, "cgst": cgst, "sgst": sgst, "igst": igst,
            "round_off": q2(total - gross), "invoice_total": total, "tax_type": "IGST" if inter else "CGST+SGST"}

def place_of_supply(world: dict, rules: dict) -> dict:
    basis = rules.get("pos_basis", "bill_to")   # IGST s.10(1)(b): third-party direction -> the billed party's state
    state = world["bill_to"] if basis == "bill_to" else world["ship_to"]
    return {"tax_type": "IGST" if world["supplier_state"] != state else "CGST+SGST"}

def itc(world: dict, rules: dict) -> dict:
    blocked = set(rules["blocked_itc_categories"])
    ok = [r for r in world["purchase_register"] if r["in_gstr2b"] and r["goods_received"] and r["category"] not in blocked]
    return {"eligible_itc": sum(Dc(str(r["tax"])) for r in ok), "eligible_invoices": sorted(r["inv"] for r in ok)}

def due_date(period: str, rules: dict) -> dt.date:
    y, m = int(period[:4]), int(period[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    d = dt.date(y, m, int(rules["gstr3b_due_day"]))
    if rules.get("due_date_shift_on_holiday"):   # off by default: the law has no automatic shift (review 2026-10-25)
        hol = set(rules.get("holidays", []))
        while d.weekday() >= 5 or d.isoformat() in hol:
            d += dt.timedelta(days=1)
    return d

def late_fee_cap(world: dict, rules: dict):
    """Cap for a non-nil return: tiered by the filer's annual turnover ([limit, cap] rows, limit null = no upper bound)."""
    if "late_fee_cap_by_turnover" not in rules:
        return rules["late_fee_cap"]
    turnover = Dc(str(world["annual_turnover"]))
    for limit, cap in rules["late_fee_cap_by_turnover"]:
        if limit is None or turnover <= Dc(str(limit)):
            return cap
    raise ValueError("no cap tier")

def late_filing(world: dict, rules: dict) -> dict:
    due = due_date(world["period"], rules)
    days = max(0, (dt.date.fromisoformat(world["filed_on"]) - due).days)
    nil = bool(world["nil_return"])
    per = Dc(str(rules["late_fee_per_day_nil" if nil else "late_fee_per_day"]))
    cap = Dc(str(rules["late_fee_cap_nil"] if nil else late_fee_cap(world, rules)))
    fee = min(per * days, cap)
    interest = q2(Dc(str(world["net_tax"])) * Dc(str(rules["interest_pct_pa"])) / Dc(100) * Dc(days) / Dc(365))
    return {"due_date": due.isoformat(), "days_late": days, "late_fee": fee, "interest": interest}

def threshold(world: dict, rules: dict, prompt: str) -> dict:
    p = prompt.lower()
    if "e-invoice" in p:
        return {"required": Dc(str(world["turnover"])) > Dc(str(rules["einvoice_turnover_threshold"]))}
    if "e-way" in p:
        return {"required": Dc(str(world["consignment_value"])) > Dc(str(rules["eway_bill_value_threshold"]))}
    if "composition" in p:
        return {"eligible": Dc(str(world["turnover"])) <= Dc(str(rules["composition_turnover_max"]))}
    raise ValueError("unknown threshold question")

def easy_tax(world: dict, rules: dict) -> dict:
    """One sale line at a stated rate: tax = quantity x unit price x rate / 100, to 2 decimals half-up (easy split)."""
    value = Dc(str(world["qty"])) * Dc(str(world["unit_price"]))
    return {"tax": q2(value * Dc(str(world["rate_pct"])) / Dc(100))}

def easy_days_late(world: dict, rules: dict) -> dict:
    """Days after the GSTR-3B due date on which the return was filed; 0 if on time (easy split)."""
    due = due_date(world["period"], rules)
    return {"days_late": max(0, (dt.date.fromisoformat(world["filed_on"]) - due).days)}

def solve(kind: str, world: dict, rules: dict, prompt: str = "") -> dict:
    if kind == "invoice": return invoice(world, rules)
    if kind == "place_of_supply": return place_of_supply(world, rules)
    if kind == "itc_reconciliation": return itc(world, rules)
    if kind == "late_filing": return late_filing(world, rules)
    if kind == "threshold": return threshold(world, rules, prompt)
    if kind == "easy_tax": return easy_tax(world, rules)
    if kind == "easy_days_late": return easy_days_late(world, rules)
    raise ValueError(f"unknown kind {kind}")
