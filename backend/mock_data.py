"""# MOCK — example data copied from API.md v0.2, plus in-memory state.

Everything in this file is replaced by real data / SQLite in later steps.
Numbers here are placeholders for frontend development, NOT demo numbers.
"""
import copy
import random
import string
from datetime import datetime, timezone

DEMO_BUYER = "B001"
DEMO_MERCHANT = "M001"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix, n=4):
    return prefix + "".join(random.choices("0123456789abcdef", k=n))


def paypal_like_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=17))


# ---------------------------------------------------------------- savings
# MOCK
SAVINGS = {
    "total_saved": 847.00,
    "this_month": 165.00,
    "breakdown": {
        "price_drop": {
            "label": "Price drop recovered", "total": 312.40, "count": 11,
            "latest": {"item": "Headphones", "merchant_name": "SoundLab", "amount": 18.00, "date": "2026-10-29"},
        },
        "overcharge": {
            "label": "Overcharge caught", "total": 188.60, "count": 9,
            "latest": {"item": "Online order", "merchant_name": "ShopRight", "amount": 9.00, "date": "2026-11-02"},
        },
        "better_deal": {
            "label": "Better deal found", "total": 196.00, "count": 23,
            "latest": {"item": "Insoles", "merchant_name": "StrideShop", "amount": 6.00, "date": "2026-11-05"},
        },
        "save_for_it": {
            "label": "Save For It discount", "total": 150.00, "count": 1,
            "latest": {"item": "Laptop", "merchant_name": "TechHaven", "amount": 150.00, "date": "2026-11-04"},
        },
    },
    "trend": [
        {"month": "2026-06", "amount": 92.10},
        {"month": "2026-07", "amount": 140.55},
        {"month": "2026-08", "amount": 201.30},
        {"month": "2026-09", "amount": 118.05},
        {"month": "2026-10", "amount": 130.00},
        {"month": "2026-11", "amount": 165.00},
    ],
    "recent_actions": [
        {"action_id": "A_104", "type": "better_deal", "title": "Better deal on insoles at StrideShop",
         "amount": 6.00, "status": "recovered", "timestamp": "2026-11-05T09:20:00Z"},
        {"action_id": "A_103", "type": "save_for_it", "title": "Laptop bought $150 under target",
         "amount": 150.00, "status": "recovered", "timestamp": "2026-11-04T18:41:00Z"},
        {"action_id": "A_102", "type": "overcharge", "title": "Overcharge disputed with ShopRight",
         "amount": 9.00, "status": "recovered", "timestamp": "2026-11-02T12:05:00Z"},
        {"action_id": "A_101", "type": "price_drop", "title": "Auto price-match from SoundLab",
         "amount": 18.00, "status": "recovered", "timestamp": "2026-10-29T16:02:00Z"},
    ],
    "analytics": {
        "spend_this_month": 1240.75,
        "spend_by_category": [
            {"category": "electronics", "amount": 612.40, "saved": 58.99},
            {"category": "home", "amount": 310.15, "saved": 18.00},
            {"category": "sports", "amount": 188.20, "saved": 6.00},
            {"category": "fashion", "amount": 130.00, "saved": 9.00},
        ],
        "purchases_watched": 42,
        "active_alerts": 2,
        "top_merchant": {"merchant_name": "TechHaven", "amount": 409.00},
        "savings_rate_pct": 13.3,
    },
}

# ------------------------------------------------------------ better deal
# MOCK: alternatives are priced as a fraction of the price you searched,
# so any search returns something sensible until the real catalog is wired.
ALT_MERCHANTS = [
    {"merchant_id": "M007", "merchant_name": "StrideShop", "price_factor": 0.75, "rating": 9.1,
     "delivery_days": 2, "dispute_rate": 0.012, "on_time_rate": 0.96},
    {"merchant_id": "M012", "merchant_name": "ValueVault", "price_factor": 0.81, "rating": 8.6,
     "delivery_days": 4, "dispute_rate": 0.018, "on_time_rate": 0.92},
    {"merchant_id": "M021", "merchant_name": "PrimeCart", "price_factor": 0.875, "rating": 8.9,
     "delivery_days": 1, "dispute_rate": 0.009, "on_time_rate": 0.98},
]
NETWORK_MEDIAN_FACTOR = 0.81  # MOCK
NETWORK_PERCENTILE = 88  # MOCK

# ----------------------------------------------------------- save for it
# MOCK: the demo goal from API.md
DEMO_GOAL = {
    "goal_id": "G_7f3a",
    "buyer_id": DEMO_BUYER,
    "product_name": "Dell XPS 14 Laptop",
    "product_id": "P_0410",
    "category": "electronics",
    "merchant_name": "TechHaven",
    "target_price": 1200.00,
    "current_price": 1070.00,
    "best_coupon": {"code": "TECH20", "description": "$20 off laptops", "discount": 20.00},
    "all_time_low": 1050.00,
    "weekly_amount": 50.00,
    "saved_so_far": 1050.00,
    "purchased": False,
    "price_history": [
        {"date": "2026-07-01", "price": 1200.00},
        {"date": "2026-09-15", "price": 1149.00},
        {"date": "2026-11-04", "price": 1070.00},
    ],
}
CREDIT_CARD_CASHBACK_PCT = 3  # MOCK: to be verified against current card terms

# ------------------------------------------------------------ guardian
# MOCK: `ready_after` = seconds after scan start when the check finishes,
# `resolve_after` / `recover_after` = when the status moves forward.
GUARDIAN_ALERTS = [
    {
        "ready_after": 1.5, "resolve_after": 3.0, "recover_after": 5.0,
        "alert": {
            "alert_id": "AL_301", "type": "price_drop", "title": "Price drop on your headphones",
            "details": "You paid $89.00 on Tuesday. SoundLab dropped it to $71.00 on Thursday.",
            "transaction_id": "T_08812", "merchant_name": "SoundLab", "product_name": "Wireless Headphones",
            "purchase_date": "2026-10-27", "amount_paid": 89.00, "reference_price": 71.00,
            "recoverable_amount": 18.00, "action_taken": "Auto price-match requested. You did nothing.",
            "recovery_method": "paypal_refund", "paypal_reference": "8MC585209K746392H",
        },
    },
    {
        "ready_after": 3.0, "resolve_after": 4.5, "recover_after": 7.0,
        "alert": {
            "alert_id": "AL_302", "type": "overcharge", "title": "Overcharged by ShopRight",
            "details": "Order total $45.00, you were charged $54.00. $9.00 gap.",
            "transaction_id": "T_09107", "merchant_name": "ShopRight", "product_name": "Online order",
            "purchase_date": "2026-11-02", "amount_paid": 54.00, "reference_price": 45.00,
            "recoverable_amount": 9.00, "action_taken": "Flagged and auto-disputed.",
            "recovery_method": "simulated", "paypal_reference": None,
        },
    },
    {
        "ready_after": 4.5, "resolve_after": 6.0, "recover_after": None,
        "alert": {
            "alert_id": "AL_303", "type": "delivery_delay", "title": "Your order is late",
            "details": "Promised 3-day shipping. Day 5, nothing arrived.",
            "transaction_id": "T_09230", "merchant_name": "HomeNest", "product_name": "Desk Lamp",
            "purchase_date": "2026-11-04", "promised_date": "2026-11-07", "days_late": 2,
            "recoverable_amount": 0, "action_taken": "Auto-contacted merchant.",
            "recovery_method": None, "paypal_reference": None,
        },
    },
    {
        "ready_after": 6.0, "resolve_after": 7.5, "recover_after": None,
        "alert": {
            "alert_id": "AL_304", "type": "late_refund", "title": "Refund overdue from StyleLoop",
            "details": "Merchant said 5–7 days. Day 10, no refund.",
            "transaction_id": "T_08744", "merchant_name": "StyleLoop", "product_name": "Denim Jacket (returned)",
            "purchase_date": "2026-10-20", "refund_requested_date": "2026-10-30", "days_overdue": 3,
            "recoverable_amount": 39.99, "action_taken": "Agent auto-escalated.",
            "recovery_method": "simulated", "paypal_reference": None,
        },
    },
]
GUARDIAN_CHECK_ORDER = ["price_drop", "overcharge", "delivery_delay", "late_refund"]

# ------------------------------------------------------------ merchant
# MOCK
MERCHANT_DASHBOARD = {
    "merchant_name": "TechHaven",
    "summary": {
        "at_risk_customers": 340,
        "recoverable_revenue": 48210.00,
        "offers_sent": 5,
        "offers_redeemed": 2,
        "win_back_rate_pct": 40,
        "revenue_won_back": 342.00,
    },
    "churn_risk": [
        {"customer_id": "B214", "customer_name": "Sarah Kim", "churn_probability": 0.87, "risk_tier": "high",
         "days_since_purchase": 74, "total_spend": 1240.50, "order_count": 9, "last_category": "electronics"},
        {"customer_id": "B118", "customer_name": "Marcus Chen", "churn_probability": 0.82, "risk_tier": "high",
         "days_since_purchase": 66, "total_spend": 980.00, "order_count": 7, "last_category": "electronics"},
        {"customer_id": "B305", "customer_name": "Priya Patel", "churn_probability": 0.76, "risk_tier": "high",
         "days_since_purchase": 59, "total_spend": 2105.75, "order_count": 14, "last_category": "accessories"},
        {"customer_id": "B077", "customer_name": "Diego Alvarez", "churn_probability": 0.64, "risk_tier": "medium",
         "days_since_purchase": 48, "total_spend": 540.20, "order_count": 5, "last_category": "audio"},
        {"customer_id": "B451", "customer_name": "Emily Nguyen", "churn_probability": 0.58, "risk_tier": "medium",
         "days_since_purchase": 41, "total_spend": 760.00, "order_count": 6, "last_category": "electronics"},
        {"customer_id": "B239", "customer_name": "Omar Haddad", "churn_probability": 0.47, "risk_tier": "medium",
         "days_since_purchase": 37, "total_spend": 315.40, "order_count": 3, "last_category": "gaming"},
        {"customer_id": "B162", "customer_name": "Hannah Brooks", "churn_probability": 0.31, "risk_tier": "low",
         "days_since_purchase": 22, "total_spend": 1890.00, "order_count": 12, "last_category": "electronics"},
        {"customer_id": "B390", "customer_name": "Liam O'Connor", "churn_probability": 0.18, "risk_tier": "low",
         "days_since_purchase": 9, "total_spend": 420.60, "order_count": 4, "last_category": "accessories"},
    ],
    "cross_sell": [
        {"product_a": "Laptops", "product_b": "Laptop Bags", "co_purchase_rate": 0.34, "suggested_bundle_discount_pct": 10},
        {"product_a": "Headphones", "product_b": "Phone Cases", "co_purchase_rate": 0.21, "suggested_bundle_discount_pct": 8},
        {"product_a": "Monitors", "product_b": "HDMI Cables", "co_purchase_rate": 0.47, "suggested_bundle_discount_pct": 12},
    ],
    "model_info": {"churn_model": "random_forest", "auc": 0.74, "note": "Metrics on synthetic data"},
}
TIER_DISCOUNT = {"high": 20, "medium": 15, "low": 10}  # MOCK

# ------------------------------------------------------- in-memory state
# MOCK: replaced by SQLite (db.py) in Step 4+.
STATE = {}


def reset_state():
    STATE.clear()
    STATE.update({
        "rules": {},        # buyer_id -> rules dict
        "spend": {},        # buyer_id -> {"today": float, "month": float}
        "actions": {},      # buyer_id -> [agent pass log entries]
        "goals": {DEMO_GOAL["goal_id"]: copy.deepcopy(DEMO_GOAL)},
        "orders": {},       # order_id -> order dict
        "scans": {},        # buyer_id -> {"scan_id", "started_at"}
        "claimed": set(),   # alert_ids claimed manually
        "offers": {"O_9001": {"offer_id": "O_9001", "merchant_id": DEMO_MERCHANT, "customer_id": "B214",
                              "customer_name": "Sarah Kim", "outcome": None}},
        "feedback_rows": 127,
    })
    STATE["spend"][DEMO_BUYER] = {"today": 18.00, "month": 412.50}
    STATE["actions"][DEMO_BUYER] = [{
        "action_id": "AP_55", "action": "purchase", "amount": 200.00, "category": "electronics",
        "merchant_name": "GadgetGrove", "decision": "BLOCK",
        "reason": "$200.00 unplanned purchase is over your $150.00 limit", "timestamp": "2026-11-09T10:12:00Z",
    }]


reset_state()


def clone(obj):
    return copy.deepcopy(obj)
