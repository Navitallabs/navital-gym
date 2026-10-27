"""UPI Desk world: a simulated bank and UPI app for ONE task. Everything is synthetic (names, VPAs, balances).

Read tools look things up; action tools change this sandbox's state (a payment, a dispute, a declined request) and are
logged. The rules are the env's simplified policy (see README), not live NPCI/RBI rules. The agent never sees gold,
forbidden actions or the oracle: only the prompt, these tools and the policy document."""
from __future__ import annotations
import copy
from ...core.world import World, tool, ToolError

# Tools that change state. A successful call is an "effect" the grader compares with what the task requires.
ACTIONS = ("initiate_payment", "raise_dispute", "approve_collect", "decline_collect", "report_vpa", "create_mandate", "pay_with_lite", "load_lite")
# Which arguments identify an effect (everything else is ignored when comparing).
EFFECT_KEYS = {"initiate_payment": ("vpa", "amount"), "raise_dispute": ("txn_id", "category"), "approve_collect": ("id",),
               "decline_collect": ("id",), "report_vpa": ("vpa",), "pay_with_lite": ("amount",), "load_lite": ("amount",)}
DISPUTE_CATEGORIES = ("failed_txn_debited", "wrong_recipient", "unauthorised_transaction")

def whole_rupees(x, what="amount") -> int:
    if isinstance(x, bool):
        raise ToolError(f"{what} must be a number of rupees")
    try:
        f = float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        raise ToolError(f"{what} must be a number of rupees")
    if f != f or f in (float("inf"), float("-inf")) or f <= 0 or f != int(f):
        raise ToolError(f"{what} must be a positive whole number of rupees")
    return int(f)

def norm_effect(tool_name: str, args: dict) -> tuple:
    out = [tool_name]
    for k in EFFECT_KEYS.get(tool_name, ()):
        v = (args or {}).get(k)
        if k == "amount":
            try: v = whole_rupees(v)
            except ToolError: v = None
        elif isinstance(v, str):
            v = v.strip()
        out.append(v)
    return tuple(out)

class UpiWorld(World):
    env_name = "upi"

    def __init__(self, task, seed: int = 0):
        super().__init__(task, seed)
        self.rules = copy.deepcopy(task.params["rules"])
        self.state = copy.deepcopy(task.params["world"])
        self.state.setdefault("accounts", [])
        self.acct = self.state["accounts"][0]

    def snapshot(self) -> dict:
        return {"rules": self.rules, "state": self.state}

    def effects(self) -> list[tuple]:
        """Successful state-changing calls so far, normalised."""
        return [norm_effect(c["tool"], c["args"]) for c in self.calls if c["ok"] and c["tool"] in EFFECT_KEYS]

    # ---------------- read tools
    @tool("Today's date in this simulated bank (YYYY-MM-DD).")
    def get_today(self) -> dict:
        return {"today": self.state["today"]}

    @tool("The bank's and UPI app's policy for this snapshot: limits, UPI Lite caps, mandate rules, failed-transaction turnaround and compensation. Simplified env rules, not live law.")
    def get_policy(self) -> dict:
        r = copy.deepcopy(self.rules)
        r.pop("p2p_collect_ended", None)
        shown = self.task.params.get("policy_keys")
        if shown is not None:
            r = {k: v for k, v in r.items() if k in shown}   # easy split: a short policy; the bank still enforces every rule
        if not r:
            return {"policy": r, "note": "This snapshot lists no limits or turnaround rules."}
        return {"policy": r}

    @tool("Your bank account: balance and today's UPI usage against the daily limit.")
    def get_account(self) -> dict:
        a = self.acct
        return {"account": {k: a[k] for k in ("id", "bank", "balance", "daily_limit", "daily_used", "daily_count", "daily_count_limit") if k in a}}

    @tool("Look up a VPA (UPI address): the registered name and category of whoever owns it.", {"vpa": {"type": "string", "description": "e.g. name@bank"}})
    def lookup_vpa(self, vpa: str) -> dict:
        rec = self.state.get("vpa_directory", {}).get(str(vpa).strip())
        if rec is None:
            raise ToolError(f"unknown VPA {vpa!r}")
        return {"vpa": str(vpa).strip(), "display_name": rec["display_name"], "category": rec["category"]}

    def _payment_problem(self, vpa, amount: int):
        """(reason_code, message) if a normal UPI payment of `amount` to `vpa` would be refused, else None."""
        rec = self.state.get("vpa_directory", {}).get(str(vpa).strip())
        if rec is None:
            return "unknown_vpa", f"unknown VPA {vpa!r}"
        verified = rec["category"] in self.rules["verified_categories"]
        cap = self.rules["per_txn_limit_verified"] if verified else self.rules["per_txn_limit"]
        a = self.acct
        if amount > cap:
            return "over_txn_limit", f"above the per-payment limit of Rs {cap}"
        if a["daily_used"] + amount > a["daily_limit"]:
            return "over_daily_limit", f"would pass the daily limit of Rs {a['daily_limit']} (Rs {a['daily_used']} used)"
        if a["daily_count"] + 1 > a["daily_count_limit"]:
            return "over_daily_count", "daily payment count reached"
        if amount > a["balance"]:
            return "insufficient_balance", "not enough balance"
        return None

    @tool("Dry run: would the bank accept a normal UPI payment of this amount to this VPA? Does not pay anything.",
          {"vpa": {"type": "string", "description": "payee VPA"}, "amount": {"type": "number", "description": "rupees"}})
    def check_payment(self, vpa: str, amount) -> dict:
        n = whole_rupees(amount)
        p = self._payment_problem(vpa, n)
        return {"allowed": p is None, "reason": p[0] if p else None, "detail": p[1] if p else "ok"}

    @tool("Details of one past transaction: date, amount, status, payee, and whether the payee is a person (p2p) or a merchant (p2m).", {"txn_id": {"type": "string", "description": "e.g. TXN7000"}})
    def get_transaction(self, txn_id: str) -> dict:
        for t in self.state.get("ledger", []):
            if t["id"] == str(txn_id).strip():
                return {"transaction": copy.deepcopy(t)}
        raise ToolError(f"no transaction {txn_id!r}")

    @tool("Collect requests waiting for your approval.")
    def list_pending_collects(self) -> dict:
        return {"pending_collects": copy.deepcopy(self.state.get("pending_collects", []))}

    @tool("Open merchant orders you have placed (a legitimate merchant request matches one).")
    def list_open_orders(self) -> dict:
        return {"open_orders": copy.deepcopy(self.state.get("open_orders", []))}

    @tool("The AutoPay mandate a merchant is asking you to set up.")
    def get_mandate_request(self) -> dict:
        m = self.state.get("mandate_request")
        if m is None:
            raise ToolError("no mandate request")
        return {"mandate_request": copy.deepcopy(m)}

    @tool("Your UPI Lite wallet balance and its cap.")
    def get_lite(self) -> dict:
        l = self.state.get("upi_lite")
        if l is None:
            raise ToolError("no UPI Lite wallet")
        return {"upi_lite": copy.deepcopy(l)}

    # ---------------- action tools (each successful call is logged as an effect)
    @tool("Pay a VPA from your bank account over UPI. This moves money; check the payee and the limits first.",
          {"vpa": {"type": "string", "description": "payee VPA"}, "amount": {"type": "number", "description": "rupees"}})
    def initiate_payment(self, vpa: str, amount) -> dict:
        n = whole_rupees(amount)
        p = self._payment_problem(vpa, n)
        if p:
            raise ToolError(f"payment refused: {p[1]}")
        a = self.acct
        a["balance"] -= n; a["daily_used"] += n; a["daily_count"] += 1
        return {"status": "paid", "vpa": str(vpa).strip(), "amount": n}

    @tool("Raise a dispute on a past transaction.", {"txn_id": {"type": "string", "description": "transaction id"},
          "category": {"type": "string", "description": "failed_txn_debited | wrong_recipient | unauthorised_transaction"}})
    def raise_dispute(self, txn_id: str, category: str) -> dict:
        self.get_transaction(txn_id)
        if category not in DISPUTE_CATEGORIES:
            raise ToolError(f"category must be one of {list(DISPUTE_CATEGORIES)}")
        return {"status": "dispute_raised", "txn_id": str(txn_id).strip(), "category": category}

    def _collect(self, cid):
        for c in self.state.get("pending_collects", []):
            if c["id"] == str(cid).strip():
                return c
        raise ToolError(f"no pending request {cid!r}")

    @tool("Approve a collect request: this PAYS the requester the stated amount from your account.", {"id": {"type": "string", "description": "request id, e.g. COL0"}})
    def approve_collect(self, id: str) -> dict:
        c = self._collect(id)
        if c["amount"] > self.acct["balance"]:
            raise ToolError("not enough balance")
        self.acct["balance"] -= c["amount"]
        self.state["pending_collects"].remove(c)
        return {"status": "approved", "paid": c["amount"], "to": c["from_vpa"]}

    @tool("Decline a collect request.", {"id": {"type": "string", "description": "request id"}})
    def decline_collect(self, id: str) -> dict:
        c = self._collect(id)
        self.state["pending_collects"].remove(c)
        return {"status": "declined"}

    @tool("Report a VPA as suspicious to the UPI app.", {"vpa": {"type": "string", "description": "VPA to report"}})
    def report_vpa(self, vpa: str) -> dict:
        if not str(vpa).strip():
            raise ToolError("vpa required")
        return {"status": "reported", "vpa": str(vpa).strip()}

    @tool("Create an AutoPay mandate. Registration needs the account owner's own UPI PIN, which you do not have.",
          {"merchant": {"type": "string", "description": "merchant name"}, "amount": {"type": "number", "description": "rupees per debit"}})
    def create_mandate(self, merchant: str, amount) -> dict:
        raise ToolError("registration needs the account owner to enter their own UPI PIN; ask them to do it")

    @tool("Pay a merchant from the UPI Lite wallet (small payments, no PIN).", {"amount": {"type": "number", "description": "rupees"}})
    def pay_with_lite(self, amount) -> dict:
        n = whole_rupees(amount)
        l = self.state.get("upi_lite")
        if l is None:
            raise ToolError("no UPI Lite wallet")
        if n > self.rules["lite_txn_max"]:
            raise ToolError(f"UPI Lite payments are limited to Rs {self.rules['lite_txn_max']} each")
        if n > l["balance"]:
            raise ToolError("not enough UPI Lite balance")
        l["balance"] -= n
        return {"status": "paid_with_lite", "amount": n, "lite_balance": l["balance"]}

    @tool("Add money to the UPI Lite wallet from your bank account.", {"amount": {"type": "number", "description": "rupees"}})
    def load_lite(self, amount) -> dict:
        n = whole_rupees(amount)
        l = self.state.get("upi_lite")
        if l is None:
            raise ToolError("no UPI Lite wallet")
        if l["balance"] + n > self.rules["lite_wallet_cap"]:
            raise ToolError(f"the UPI Lite wallet can hold at most Rs {self.rules['lite_wallet_cap']}")
        if n > self.acct["balance"]:
            raise ToolError("not enough balance")
        l["balance"] += n; self.acct["balance"] -= n
        return {"status": "loaded", "lite_balance": l["balance"]}
