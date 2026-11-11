"""In-memory runtime state (what happened during this demo session) + helpers.

Data about buyers, merchants, products and purchases comes from data/ via
services/models_adapter.py. This module only holds what the API creates while
it runs (rules, orders, goals, claims, offers). POST /api/demo/reset clears it.

In-memory on purpose: the demo resets cleanly and Render's free disk is wiped
on every restart anyway.
"""
import copy
import random
import string
from datetime import datetime, timezone

DEMO_BUYER = "B001"
DEMO_MERCHANT = "M007"  # TechHaven in data/merchants.csv


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix, n=4):
    return prefix + "".join(random.choices("0123456789abcdef", k=n))


def sim_id():
    """ID for a simulated PayPal object (only used when PAYPAL_MODE=off)."""
    return "SIM" + "".join(random.choices(string.ascii_uppercase + string.digits, k=14))


def clone(obj):
    return copy.deepcopy(obj)


# DEMO SEED: the buyer's saved-up laptop goal from the demo script. A goal is
# user input, so it's seeded rather than computed. The laptop isn't in the
# synthetic catalog, so its price/coupon are part of the seed too; goals
# created through the API price themselves from the catalog.
DEMO_GOAL = {
    "goal_id": "G_7f3a",
    "buyer_id": DEMO_BUYER,
    "product_name": "Dell XPS 14 Laptop",
    "product_id": None,
    "category": "electronics",
    "merchant_id": "M007",
    "merchant_name": "TechHaven",
    "target_price": 1200.00,
    "current_price": 1070.00,
    "best_coupon": {"code": "TECH20", "description": "$20 off laptops", "discount": 20.00},
    "all_time_low": 1050.00,
    "weekly_amount": 50.00,
    "saved_so_far": 1050.00,
    "purchased": False,
    "price_source": "demo_seed",
    "price_history": [
        {"date": "2026-07-01", "price": 1200.00},
        {"date": "2026-09-15", "price": 1149.00},
        {"date": "2026-11-04", "price": 1070.00},
    ],
}

STATE = {}


def reset_state():
    STATE.clear()
    STATE.update({
        "rules": {},          # buyer_id -> Agent Pass rules
        "spend": {},          # buyer_id -> {"today", "month"} spent through the agent
        "actions": {},        # buyer_id -> Agent Pass decision log
        "goals": {DEMO_GOAL["goal_id"]: copy.deepcopy(DEMO_GOAL)},
        "orders": {},         # order_id -> order
        "scans": {},          # buyer_id -> {"scan_id", "started_at"}
        "claimed": {},        # alert_id -> claim result
        "events": [],         # savings events created this session (better deal, save for it, recoveries)
        "offers": {},         # offer_id -> win-back offer
        "chats": {},          # session_id -> Gemini history
    })


reset_state()
