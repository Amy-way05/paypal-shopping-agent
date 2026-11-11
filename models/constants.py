"""
Shared constants for dataset generation and all downstream models.

Single source of truth so thresholds never drift between the data generator,
the rule-based detectors, and the ML models. If a number changes, change it
here only.
"""

RANDOM_SEED = 42

# --- Dataset size (task board: Data + AI models #1) ---
N_MERCHANTS = 50
N_PRODUCTS = 520          # "500+ products for catalog fallback"
N_TRANSACTIONS = 10_000
N_COUPONS = 200

# --- Baked-in anomaly rates (task board #1) ---
PRICE_DROP_RATE = 0.15
OVERCHARGE_RATE = 0.08
DELIVERY_DELAY_RATE = 0.12
LATE_REFUND_RATE = 0.05

# --- Rule thresholds (used by rule-based detectors, tasks #2-4, #6) ---
OVERPAYMENT_PERCENTILE = 65          # "flags if above 65th percentile"
OVERCHARGE_TAX_BUFFER_PCT = 5.0      # charge > order_total * 1.05 => overcharge
PRICE_DROP_WINDOW_DAYS = 7           # price drop within 7 days of purchase
LATE_REFUND_OVERDUE_DAYS = 7         # refund requested, 7+ days overdue

# --- ML targets (task board #5 delay, #7 churn) ---
DELAY_MODEL_TARGET_AUC = 0.75
CHURN_MODEL_TARGET_AUC = 0.70
# Label/feature noise so these are real models, not rule-lookups wearing a
# model costume (per team discussion after Hetav's review). Flips this
# fraction of labels / jitters this fraction of a feature's scale.
LABEL_NOISE_RATE = 0.08
FEATURE_NOISE_SCALE = 0.10

# --- Categories (shared across merchants, products, transactions) ---
CATEGORIES = [
    "electronics", "home", "apparel", "beauty", "sporting_goods",
    "books", "toys", "grocery", "furniture", "pet_supplies",
]

# --- Empty-state messages (API.md convention: lists come back as [] with
# a message string, never null) ---
EMPTY_STATE_MESSAGES = {
    "no_alternatives": "You already have the best price we could find for this.",
    "no_post_purchase_alerts": "Nothing to flag right now — we're still watching your recent purchases.",
    "no_save_for_it_goals": "No active savings goals yet. Start one to let the agent watch for a price drop.",
    "no_churn_risk": "No customers currently flagged as at-risk.",
    "no_cross_sell": "Not enough co-purchase history yet to suggest bundles.",
}
