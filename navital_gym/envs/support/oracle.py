"""Independent reference solver for Bhasha Support Desk: from the order and the policy it derives the exact actions the shop's policy requires,
the tools that must not be used, and what the reply must contain. It never reads gold_answer."""
from __future__ import annotations
import datetime as dt, re

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
MUTATING = {"issue_refund", "cancel_order", "schedule_pickup", "request_photo", "request_address_change", "escalate_to_human"}

def act(tool, oid=None, amount=None, mode=None):
    return (tool, oid, amount, mode)

def solve(kind: str, world: dict, policy: dict) -> dict:
    o = world["order"]; oid = o["id"]; today = dt.date.fromisoformat(world["today"])
    price, ship = int(o["price"]), int(o["shipping_fee"]); prepaid = o["payment"] == "prepaid"
    out = {"actions": [], "forbidden": set(), "amount": None, "privacy": False, "answer_address": False, "reply": None, "decision": None, "reason": None}
    if kind in ("return_eligible", "return_ineligible", "cod_refund"):
        win = policy["return_window_days"].get(o["category"], 0)
        days = (today - dt.date.fromisoformat(o["delivered_on"])).days if o.get("delivered_on") else None
        eligible = o["status"] == "delivered" and days is not None and win > 0 and o["category"] not in policy["non_returnable_categories"] and days <= win
        if not eligible:
            out["forbidden"] = {"issue_refund", "schedule_pickup"}; out["decision"] = "decline_return"
            if o["status"] != "delivered":
                out["reply"], out["reason"] = "decline_return_early", "not_delivered"
            else:
                out["reply"] = "decline_return"
                out["reason"] = "non_returnable_category" if o["category"] in policy["non_returnable_categories"] else "outside_return_window"
        elif prepaid:
            out["actions"] = [act("issue_refund", oid, price, "original_source"), act("schedule_pickup", oid)]; out["amount"] = price; out["reply"] = "refund"; out["decision"], out["reason"] = "refund", "eligible"
        else:
            ifsc = (world.get("customer_bank") or {}).get("ifsc", "")
            if IFSC_RE.match(ifsc):
                out["actions"] = [act("issue_refund", oid, price, "bank_transfer"), act("schedule_pickup", oid)]; out["amount"] = price; out["reply"] = "refund"; out["decision"], out["reason"] = "refund", "eligible"
            else:
                out["forbidden"] = {"issue_refund"}; out["reply"] = "ask_ifsc"; out["decision"], out["reason"] = "ask_ifsc", "bad_ifsc"
    elif kind in ("cancel_before_ship", "cancel_after_ship"):
        if o["status"] == "placed":
            out["actions"] = [act("cancel_order", oid)]
            if prepaid:
                out["actions"].append(act("issue_refund", oid, price, "original_source")); out["amount"] = price
            out["reply"] = "cancel"; out["decision"], out["reason"] = "cancel", "not_shipped"
        else:
            out["forbidden"] = {"cancel_order", "issue_refund"}; out["decision"] = "decline_cancel"
            out["reply"], out["reason"] = ("decline_cancel_delivered", "already_delivered") if o["status"] == "delivered" else ("decline_cancel", "already_shipped")
    elif kind == "damaged":
        within = o.get("delivered_on") and (today - dt.date.fromisoformat(o["delivered_on"])).days <= policy["damaged_report_window_days"]
        if within and world.get("photo_uploaded"):
            out["actions"] = [act("issue_refund", oid, price + ship, "original_source"), act("schedule_pickup", oid)]; out["amount"] = price + ship; out["reply"] = "refund"; out["decision"], out["reason"] = "refund", "damaged_with_photo"
        elif within:
            out["actions"] = [act("request_photo", oid)]; out["forbidden"] = {"issue_refund"}; out["reply"] = "request_photo"; out["decision"], out["reason"] = "request_photo", "no_photo"
        else:
            out["forbidden"] = {"issue_refund"}; out["reply"] = "decline_return"; out["decision"], out["reason"] = "decline_return", "outside_report_window"
    elif kind == "privacy":
        if world.get("authenticated_customer_owns_order", False):   # fail closed: a row missing the key never requires handing out an address
            out["answer_address"] = True; out["reply"] = "own_address"; out["decision"], out["reason"] = "answer_own_order", "owner_verified"
        else:
            out["forbidden"] = set(MUTATING); out["privacy"] = True; out["reply"] = "privacy"; out["decision"], out["reason"] = "refuse_privacy", "not_owner"
    elif kind == "escalate":
        out["actions"] = [act("escalate_to_human")]; out["forbidden"] = {"issue_refund"}; out["reply"] = "escalate"; out["decision"], out["reason"] = "escalate", "customer_requests_human"
    elif kind == "address_change":
        if o["status"] == "placed":
            out["actions"] = [act("request_address_change", oid)]; out["reply"] = "address_ok"; out["decision"], out["reason"] = "address_change", "not_shipped"
        else:
            out["forbidden"] = {"request_address_change"}; out["reply"] = "address_no"; out["decision"], out["reason"] = "decline_address_change", "already_shipped"
    else:
        raise KeyError(kind)
    return out
