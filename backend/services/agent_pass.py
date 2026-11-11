"""Agent Pass rules engine: the decision logic from API.md section 4.

`decide()` is real logic (pure function). Where the rules are stored is a
separate concern: in-memory runtime state (see state.STATE).
"""

APPROVE = "APPROVE"
NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
BLOCK = "BLOCK"

DEFAULT_RULES = {
    "autonomous_enabled": True,
    "autonomous_claims": True,
    "auto_approve_limit": 50.00,
    "max_unplanned_purchase": 150.00,
    "max_daily_spend": 300.00,
    "monthly_limit": 2000.00,
    "blocked_categories": ["gambling"],
    "approved_merchants": [],
}


def _usd(x):
    return f"${x:,.2f}"


def decide(rules, amount, category, merchant_id=None, action="purchase", planned=False,
           spent_today=0.0, spent_this_month=0.0):
    """Return (decision, reason). Rules are checked in the order listed in API.md."""
    if action == "claim":
        if rules["autonomous_claims"]:
            return APPROVE, "Autonomous claims are on"
        return NEEDS_CONFIRMATION, "Autonomous claims are off: tap to claim"

    blocked = [c.lower() for c in rules["blocked_categories"]]
    if category and category.lower() in blocked:
        return BLOCK, f"Category '{category}' is blocked in your Agent Pass rules"

    if not planned and amount > rules["max_unplanned_purchase"]:
        return BLOCK, f"{_usd(amount)} unplanned purchase is over your {_usd(rules['max_unplanned_purchase'])} limit"

    if spent_this_month + amount > rules["monthly_limit"]:
        return BLOCK, f"{_usd(amount)} would go over your {_usd(rules['monthly_limit'])} monthly limit"

    if not planned and spent_today + amount > rules["max_daily_spend"]:
        return BLOCK, f"{_usd(amount)} would go over your {_usd(rules['max_daily_spend'])} daily limit"

    if planned:
        return NEEDS_CONFIRMATION, "Save For It purchase: Buy now?"

    if not rules["autonomous_enabled"]:
        return NEEDS_CONFIRMATION, "Autonomous purchases are off: please confirm"

    if amount > rules["auto_approve_limit"]:
        return NEEDS_CONFIRMATION, f"{_usd(amount)} is above your {_usd(rules['auto_approve_limit'])} auto-approve limit"

    approved = rules["approved_merchants"]
    if approved and merchant_id not in approved:
        return NEEDS_CONFIRMATION, "Merchant is not on your approved list"

    return APPROVE, f"{_usd(amount)} is under your {_usd(rules['auto_approve_limit'])} auto-approve limit"
