"""Builds tasks_easy.jsonl: the GST Desk EASY split (18 tasks, ids IN-GST-E01..E18, meta.split = "easy").
One rule per task, a short policy that states only that rule, one clear answer. Same graders as the standard split (the new kinds easy_tax and easy_days_late
sit beside the standard ones). The gold below is computed here with plain arithmetic and is cross-checked against the independent oracle by check_gold.
Rates, thresholds and dates are env rules as in the standard split (simplified, not live GST law). All data is synthetic.
usage: python -m navital_gym.envs.gst.build_easy"""
import datetime as dt, json, os
from decimal import Decimal as Dc

HERE = os.path.dirname(os.path.abspath(__file__))

def group(n: int) -> str:   # Indian digit grouping
    s = str(n)
    if len(s) <= 3: return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])

ROWS = []
def add(kind, prompt, world, rules, gold):
    ROWS.append({"id": f"IN-GST-E{len(ROWS) + 1:02d}", "env": "gst-desk", "kind": kind, "difficulty": 1, "lang": "en", "prompt": prompt, "rules": rules,
                 "world": world, "gold_answer": gold, "forbidden_actions": [], "split": "easy"})

POS_RULE = {"rule": "A sale inside one state (the supplier and the delivery are in the same state) is charged CGST+SGST. A sale between two different states is charged IGST.", "pos_basis": "bill_to"}
for sup, buy in (("Gujarat", "Delhi"), ("Karnataka", "Karnataka")):
    add("place_of_supply", f"A supplier in {sup} sells goods to a buyer in {buy}. The goods are delivered to the buyer in {buy}. Which tax applies? "
        f"Answer field: tax_type = exactly IGST or CGST+SGST.", {"supplier_state": sup, "bill_to": buy, "ship_to": buy}, POS_RULE,
        {"tax_type": "IGST" if sup != buy else "CGST+SGST"})

add("threshold", f"A consignment of goods worth Rs {group(62000)} will move by road. Is an e-way bill required? Answer field: required = true or false.",
    {"consignment_value": 62000}, {"eway_bill_value_threshold": 50000, "rule": "An e-way bill is required when the value of the goods being moved is more than Rs 50,000."}, {"required": 62000 > 50000})
add("threshold", f"Aggregate turnover last year was Rs {group(25000000)}. Must this business issue e-invoices? Answer field: required = true or false.",
    {"turnover": 25000000}, {"einvoice_turnover_threshold": 50000000, "rule": "E-invoices are required when the business's aggregate turnover in the last year was more than Rs 5 crore (Rs 5,00,00,000)."}, {"required": 25000000 > 50000000})

TAX_RULE = {"rule": "GST on a sale = quantity x unit price x GST rate / 100. Give the amount in rupees, up to 2 decimals."}
for qty, item, price, rate in ((4, "phone chargers", 450, 18), (10, "cotton shirts", 800, 5), (2, "mixers", 3500, 18), (25, "packets of rice", 60, 0),
                               (3, "school bags", 1200, 18), (7, "towels", 250, 5), (1, "television", 24500, 18)):
    tax = (Dc(qty) * Dc(price) * Dc(rate) / Dc(100)).quantize(Dc("0.01"))
    add("easy_tax", f"A shop sells {qty} {item} at Rs {group(price)} each. GST on them is {rate}%. How much GST is charged on the whole sale, in rupees? "
        f"Answer field: tax = a number (rupees, up to 2 decimals).", {"item": item, "qty": qty, "unit_price": price, "rate_pct": rate}, TAX_RULE, {"tax": str(tax)})

LATE_RULE = {"gstr3b_due_day": 20, "rule": "The GSTR-3B return for a month is due on the 20th of the next month, even if that day is a weekend or a holiday. Days late = the number of days after the due date; 0 if it was filed on or before the due date."}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
for period, filed in (("2026-09", "2026-10-24"), ("2026-10", "2026-11-20"), ("2026-11", "2026-12-27"), ("2026-08", "2026-10-02"),
                      ("2026-09", "2026-11-14"), ("2026-12", "2027-01-23"), ("2026-06", "2026-08-05")):
    y, m = int(period[:4]), int(period[5:])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    due = dt.date(ny, nm, 20); late = max(0, (dt.date.fromisoformat(filed) - due).days)
    add("easy_days_late", f"The GSTR-3B return for {MONTHS[m - 1]} {y} was filed on {filed}. How many days late was it (0 if it was on time)? Answer field: days_late = a whole number.",
        {"period": period, "filed_on": filed}, LATE_RULE, {"days_late": late})

if __name__ == "__main__":
    with open(os.path.join(HERE, "tasks_easy.jsonl"), "w", encoding="utf-8") as f:
        for r in ROWS: f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print("wrote tasks_easy.jsonl:", len(ROWS), "tasks")
