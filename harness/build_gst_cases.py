"""Builds cases/gst/*.json. SOLVED answers are hand-computed by qa (literals below, worked in the comments),
NOT taken from the oracle or from gold_answer; the build asserts they equal gold so a disagreement is loud."""
import json, sys, copy
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..") if "adapters" in __file__ else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import gst
TASKS = {t.id: t for t in gst.load_tasks(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "navital_gym", "envs", "gst", "tasks.jsonl"))}
R = lambda **kw: {"status": "plan", "answer": kw}
# id -> (hand-solved answer, {rule id: (field, wrong value)} single-field violations)
HAND = {
 # 24*1850=44400 +250 freight=44650; LUX 40%: 17760 + freight 100 = 17860; intra: 8930 each; gross 62510
 "IN-GST-001": (dict(taxable_value="44650.00", cgst="8930.00", sgst="8930.00", igst="0", round_off="0.00", invoice_total="62510", tax_type="CGST+SGST"),
   {"R-TAXABLE": ("taxable_value", "44400.00"), "R-CGST": ("cgst", "8929.00"), "R-SGST": ("sgst", "8931.00"), "R-IGST": ("igst", "17860.00"),
    "R-ROUNDOFF": ("round_off", "0.50"), "R-TOTAL": ("invoice_total", "62511"), "R-TAXTYPE": ("tax_type", "IGST")}),
 # 5*450=2250 -10% = 2025; FAB 5% = 101.25 IGST (TN->Gujarat); gross 2126.25 -> 2126, round_off -0.25
 "IN-GST-002": (dict(taxable_value="2025.00", cgst="0", sgst="0", igst="101.25", round_off="-0.25", invoice_total="2126", tax_type="IGST"),
   {"R-TAXABLE": ("taxable_value", "2250.00"), "R-IGST": ("igst", "112.50"), "R-ROUNDOFF": ("round_off", "0.25"), "R-TOTAL": ("invoice_total", "2127"), "R-TAXTYPE": ("tax_type", "CGST+SGST")}),
 # 10*120=1200; TOY 5% = 60 IGST (Kerala->Gujarat); total 1260
 "IN-GST-006": (dict(taxable_value="1200.00", cgst="0", sgst="0", igst="60.00", round_off="0.00", invoice_total="1260", tax_type="IGST"),
   {"R-IGST": ("igst", "60.50"), "R-TOTAL": ("invoice_total", "1261")}),
 # 21600 + 1898.10 = 23498.10; ELEC 18%: 3888 + 341.66 (341.658 half-up) = 4229.66; 2114.83 each; gross 27727.76 -> 27728, +0.24
 "IN-GST-007": (dict(taxable_value="23498.10", cgst="2114.83", sgst="2114.83", igst="0", round_off="0.24", invoice_total="27728", tax_type="CGST+SGST"),
   {"R-CGST": ("cgst", "2114.82"), "R-SGST": ("sgst", "2114.84"), "R-ROUNDOFF": ("round_off", "-0.24"), "R-TOTAL": ("invoice_total", "27727")}),
 # P00 900 + P03 540 + P05 180 = 1620; P02 blocked category, P01/P04 not in GSTR-2B
 "IN-GST-024": (dict(eligible_itc=1620, eligible_invoices=["P00", "P03", "P05"]),
   {"R-ITC-AMOUNT": ("eligible_itc", 1800), "R-ITC-INVOICES": ("eligible_invoices", ["P00", "P02", "P03", "P05"])}),
 # due 2026-10-20; filed 2026-12-04 = 45 days; turnover 3cr -> cap tier 5000; 50*45=2250; interest 48000*.18*45/365 = 1065.2054 -> 1065.21
 "IN-GST-036": (dict(due_date="2026-10-20", days_late=45, late_fee=2250, interest="1065.21"),
   {"R-DUE": ("due_date", "2026-10-21"), "R-DAYS": ("days_late", 44), "R-FEE": ("late_fee", 2000), "R-INTEREST": ("interest", "1065.20")}),
 # nil return, 45 days late: 20*45=900 capped at nil cap 500; no tax so no interest
 "IN-GST-038": (dict(due_date="2026-10-20", days_late=45, late_fee=500, interest="0.00"),
   {"R-FEE": ("late_fee", 900), "R-DAYS": ("days_late", 0)}),
 # e-invoice is required only ABOVE Rs 5 crore; exactly 5,00,00,000 is not above -> False
 "IN-GST-046": (dict(required=False), {"R-REQUIRED": ("required", True)}),
 # e-way bill is required above Rs 50,000; 50,001 is above -> True
 "IN-GST-047": (dict(required=True), {"R-REQUIRED": ("required", False)}),
 # composition is allowed up to and including Rs 1.5 crore; exactly 1,50,00,000 -> eligible
 "IN-GST-049": (dict(eligible=True), {"R-ELIGIBLE": ("eligible", False)}),
 # Delhi supplier, billed Tamil Nadu, delivered Delhi: place of supply = BILLED state -> IGST
 "IN-GST-017": (dict(tax_type="IGST"), {"R-TAXTYPE": ("tax_type", "CGST+SGST")}),
 # Kerala supplier, billed Kerala, delivered West Bengal: POS = billed state Kerala -> CGST+SGST
 "IN-GST-016": (dict(tax_type="CGST+SGST"), {"R-TAXTYPE": ("tax_type", "IGST")}),
}
def num_eq(a, b):
    from decimal import Decimal as D
    try: return D(str(a)) == D(str(b))
    except Exception: return a == b
n = 0
for tid, (ans, viol) in HAND.items():
    t = TASKS[tid]; gold = t.meta["gold_answer"]
    for k, v in ans.items():
        if k in gold:
            g = gold[k]
            ok = (sorted(g) == sorted(v)) if isinstance(v, list) else num_eq(g, v) if not isinstance(v, str) or v[:1].isdigit() or v[:1] == "-" else g == v
            assert ok, f"HAND answer disagrees with gold in {tid}.{k}: hand={v!r} gold={g!r}"
    cases = [{"name": "hand_solved", "kind": "solved", "submission": R(**ans), "expect": {"solved": True, "min_score": 1.0, "required_fields": ["answer"]}}]
    for rid, (field, bad) in viol.items():
        sub = copy.deepcopy(ans); sub[field] = bad
        cases.append({"name": f"only_{rid}", "kind": "violation", "submission": R(**sub),
                      "expect": {"solved": False, "max_score": 0.99, "fails": [rid], "passes_all_but": [rid]}})
    td = t.to_dict()
    json.dump({"env": "gst", "task_id": tid, "task": td, "cases": cases}, open(f"cases/gst/{tid}.json", "w"), indent=1, ensure_ascii=False)
    n += 1
print("wrote", n, "case files")
