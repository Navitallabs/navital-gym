"""Scripted agents for GST Desk: oracle (upper bound), empty, reject_only (always says no / null), careless (reads everything but
leaves freight untaxed and ignores the turnover-tiered late-fee cap)."""
from ...core.runner import ScriptedAgent
from . import oracle

def _w(task): return task.params["world"], task.params["rules"], task.meta["kind"]

def _plain(x):
    from decimal import Decimal
    if isinstance(x, Decimal):
        return int(x) if x == x.to_integral_value() and abs(x) < 10**12 and "." not in str(x) else str(x)
    if isinstance(x, list): return [_plain(i) for i in x]
    return x

def oracle_agent(obs, call, task):
    w, r, k = _w(task)
    return {"status": "plan", "answer": {a: _plain(b) for a, b in oracle.solve(k, w, r, task.prompt).items()}}

def empty(obs, call, task): return {"status": "plan", "answer": {}}

def reject_only(obs, call, task):
    w, r, k = _w(task)
    shape = oracle.solve(k, w, r, task.prompt)
    return {"status": "plan", "answer": {a: (False if isinstance(b, bool) else [] if isinstance(b, list) else 0 if isinstance(b, (int, float)) or hasattr(b, "quantize") else None) for a, b in shape.items()}}

def careless(obs, call, task):
    """Right procedure, two common slips: freight carried untaxed (invoice) and the lowest late-fee cap always used."""
    w, r, k = _w(task)
    r2 = dict(r)
    if k == "invoice":
        w2 = dict(w, freight=0)
        got = oracle.solve(k, w2, r2)
        fr = oracle.q2(oracle.Dc(str(w.get("freight", 0))))
        got["taxable_value"] = got["taxable_value"] + fr
        gross = got["taxable_value"] + got["cgst"] + got["sgst"] + got["igst"]
        got["invoice_total"] = oracle.q0(gross); got["round_off"] = oracle.q2(got["invoice_total"] - gross)
    elif k == "late_filing" and "late_fee_cap_by_turnover" in r2:
        r2["late_fee_cap_by_turnover"] = [[None, r2["late_fee_cap_by_turnover"][0][1]]]
        got = oracle.solve(k, w, r2)
    else:
        got = oracle.solve(k, w, r2, task.prompt)
    return {"status": "plan", "answer": {a: _plain(b) for a, b in got.items()}}

def get_baselines():
    return {n: ScriptedAgent(n, f) for n, f in [("empty", empty), ("reject_only", reject_only), ("careless", careless), ("oracle", oracle_agent)]}
