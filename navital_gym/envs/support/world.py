"""Bhasha Support Desk world: one shop order, the shop's (invented) policy, and read-only tools. State changes are NOT tools: the agent lists
the actions it wants in its final submission and the grader compares them with the policy. The agent never sees gold, the oracle or `meta`."""
from __future__ import annotations
import copy, datetime as dt, re
from ...core.world import World, tool, ToolError

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

class SupportWorld(World):
    env_name = "support"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        w = task.params["world"]
        self.order = copy.deepcopy(w["order"])
        self.today = w["today"]
        self.owns = bool(w.get("authenticated_customer_owns_order", False))
        self.photo = bool(w.get("photo_uploaded", False))
        self.bank = copy.deepcopy(w.get("customer_bank"))
        self.policy = copy.deepcopy(task.params["policy"])

    def snapshot(self) -> dict:
        return {"order": self.order, "today": self.today, "owns": self.owns, "photo": self.photo, "bank": self.bank, "policy": self.policy}

    def _check(self, order_id):
        if str(order_id) != self.order["id"]:
            raise ToolError(f"unknown order {order_id!r}")

    @tool("The shop's policy for this snapshot: return windows, what cannot be returned, cancellation, damaged items, COD refunds, language rule. An invented policy, not consumer law.")
    def get_policy(self) -> dict:
        p = copy.deepcopy(self.policy)
        for k in ("marker_words", "script_check"):   # grader-only: an agent that sees the marker list could game the language rule
            p.pop(k, None)
        p["approved_returns_need_pickup"] = True
        p["actions_you_may_list"] = ["issue_refund(order_id, amount, mode: original_source|bank_transfer)", "cancel_order(order_id)", "schedule_pickup(order_id)",
                                     "request_photo(order_id)", "request_address_change(order_id)", "escalate_to_human(reason)"]
        p["today"] = self.today
        return {"policy": p}

    @tool("The order record: item, category, price, shipping fee, payment mode, status, delivery date, and whether it belongs to the customer you are talking to.",
          {"order_id": {"type": "string", "description": "order id, e.g. OD81000"}})
    def get_order(self, order_id: str) -> dict:
        self._check(order_id)
        o = copy.deepcopy(self.order)
        o["belongs_to_this_customer"] = self.owns
        return {"order": o}

    @tool("Days since delivery, the return window for the item's category, and whether the category can be returned at all.", {"order_id": {"type": "string", "description": "order id"}})
    def return_window_status(self, order_id: str) -> dict:
        self._check(order_id)
        if "return_window_days" not in self.policy or "non_returnable_categories" not in self.policy:
            raise ToolError("this task's policy has no return rules")    # the easy split trims the policy to the one rule a task needs
        o = self.order
        if o.get("delivered_on") is None:
            return {"delivered": False}
        days = (dt.date.fromisoformat(self.today) - dt.date.fromisoformat(o["delivered_on"])).days
        win = self.policy["return_window_days"].get(o["category"], 0)
        return {"delivered": True, "days_since_delivery": days, "window_days": win,
                "category_returnable": o["category"] not in self.policy["non_returnable_categories"], "within_window": days <= win}

    @tool("Whether the customer has uploaded a photo of the damaged item for this order.", {"order_id": {"type": "string", "description": "order id"}})
    def get_photo_status(self, order_id: str) -> dict:
        self._check(order_id)
        return {"photo_uploaded": self.photo}

    @tool("The bank details the customer gave for a refund of a cash-on-delivery order (account masked).")
    def get_customer_bank(self) -> dict:
        return {"bank": copy.deepcopy(self.bank)} if self.bank else {"bank": None}

    @tool("Check an IFSC against the env's format rule (4 letters, 0, 6 letters or digits).", {"ifsc": {"type": "string", "description": "IFSC as given"}})
    def validate_ifsc(self, ifsc: str) -> dict:
        return {"valid": bool(IFSC_RE.match(str(ifsc)))}
