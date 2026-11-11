"""
Generate the master dataset: merchants.csv, products.json, transactions.csv,
price_changes.csv, coupons.json.

Column names match the API contract (API.md) exactly:
    customer_id, merchant_id, order_total, amount_charged, ...
so nothing needs renaming when this feeds the FastAPI backend.

Usage:
    python generate_data.py                  # writes to ./data/
    python generate_data.py --out ../data     # custom output dir
    python generate_data.py --seed 7          # different seed (default 42)

Reproducible: same seed -> byte-identical output. This matters for the demo
video — re-running this script the night before should not change the
numbers that are already on screen in a recording.
"""
import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from constants import (
    CATEGORIES, N_MERCHANTS, N_PRODUCTS, N_TRANSACTIONS, N_COUPONS,
    PRICE_DROP_RATE, OVERCHARGE_RATE, DELIVERY_DELAY_RATE, LATE_REFUND_RATE,
    PRICE_DROP_WINDOW_DAYS, OVERCHARGE_TAX_BUFFER_PCT, RANDOM_SEED,
)

TODAY = datetime(2026, 11, 9)
TXN_WINDOW_DAYS = 240  # ~8 months of purchase history

# ---------------------------------------------------------------------------
# Name banks (no faker dependency — keeps this runnable offline, no network
# needed on anyone's machine, and no extra install for teammates)
# ---------------------------------------------------------------------------
MERCHANT_PREFIXES = [
    "Tech", "Gadget", "Style", "Home", "Urban", "Prime", "Swift", "Golden",
    "Nova", "Blue", "Metro", "Pure", "Nest", "Echo", "Vivid", "Bright",
    "North", "Summit", "Clever", "Rapid",
]
MERCHANT_SUFFIXES = [
    "Haven", "Grove", "Loop", "Nest", "Market", "Supply", "Goods", "Depot",
    "Collective", "Outlet", "Hub", "Works", "Trading", "Co", "Studio",
]

PRODUCT_CATALOG = {
    "electronics": [
        ("Sony WH-1000XM5 Headphones", 349.99),
        ("Apple AirPods Pro", 249.00),
        ("Samsung 55\" QLED TV", 799.00),
        ("Logitech MX Master 3S Mouse", 99.99),
        ("Anker PowerCore 20000", 49.99),
        ("Kindle Paperwhite", 139.99),
        ("Bose QuietComfort Ultra", 429.00),
        ("Dell 27\" Monitor", 289.00),
    ],
    "home": [
        ("Instant Pot Duo 7-in-1", 99.00),
        ("Dyson V8 Vacuum", 379.00),
        ("Ninja Air Fryer", 119.99),
        ("Cast Iron Skillet Set", 59.00),
        ("Weighted Blanket", 69.99),
        ("Memory Foam Pillow", 39.99),
    ],
    "apparel": [
        ("Denim Jacket", 60.00),
        ("Running Shoes", 89.99),
        ("Wool Sweater", 54.00),
        ("Leather Belt", 29.99),
        ("Rain Jacket", 74.99),
    ],
    "beauty": [
        ("Vitamin C Serum", 24.99),
        ("Electric Toothbrush", 44.99),
        ("Hair Dryer", 59.99),
    ],
    "sporting_goods": [
        ("Yoga Mat", 34.99),
        ("Adjustable Dumbbells", 149.00),
        ("Resistance Bands Set", 19.99),
    ],
    "books": [
        ("Bestseller Hardcover", 27.99),
        ("Cookbook", 22.00),
    ],
    "toys": [
        ("Lego Set", 59.99),
        ("Board Game", 34.99),
    ],
    "grocery": [
        ("Coffee Beans 2lb", 18.99),
        ("Protein Powder", 39.99),
    ],
    "furniture": [
        ("Office Chair", 199.00),
        ("Standing Desk", 329.00),
    ],
    "pet_supplies": [
        ("Dog Bed", 44.99),
        ("Cat Tree", 89.99),
    ],
}

# Demo entities referenced in API.md examples — seeded explicitly so the
# contract's example responses are backed by real rows, not placeholders.
# NOTE: API.md's merchant-dashboard example used "M001 / TechHaven" while the
# Flow A / Flow C examples use "M007 / TechHaven" for the same merchant name.
# Flagging that mismatch to Koushik separately; here M007 is canonical for
# TechHaven and M001 is a distinct demo merchant, matching the "Demo users"
# convention at the top of API.md (Merchant M001).
PINNED_MERCHANTS = [
    {"merchant_id": "M007", "merchant_name": "TechHaven", "category": "electronics",
     "dispute_rate": 0.012, "on_time_rate": 0.96, "avg_delivery_days": 2},
    {"merchant_id": "M014", "merchant_name": "GadgetGrove", "category": "electronics",
     "dispute_rate": 0.041, "on_time_rate": 0.88, "avg_delivery_days": 4},
    {"merchant_id": "M021", "merchant_name": "HomeNest", "category": "home",
     "dispute_rate": 0.028, "on_time_rate": 0.91, "avg_delivery_days": 3},
    {"merchant_id": "M033", "merchant_name": "StyleLoop", "category": "apparel",
     "dispute_rate": 0.065, "on_time_rate": 0.82, "avg_delivery_days": 5},
    {"merchant_id": "M001", "merchant_name": "Northside Electronics", "category": "electronics",
     "dispute_rate": 0.035, "on_time_rate": 0.89, "avg_delivery_days": 3},
]
DEMO_BUYER = "B001"


def make_merchants(rng: random.Random) -> pd.DataFrame:
    rows = list(PINNED_MERCHANTS)
    used_ids = {m["merchant_id"] for m in rows}
    used_names = {m["merchant_name"] for m in rows}
    next_num = 2
    while len(rows) < N_MERCHANTS:
        mid = f"M{next_num:03d}"
        next_num += 1
        if mid in used_ids:
            continue
        name = f"{rng.choice(MERCHANT_PREFIXES)}{rng.choice(MERCHANT_SUFFIXES)}"
        if name in used_names:
            continue
        used_ids.add(mid)
        used_names.add(name)
        category = rng.choice(CATEGORIES)
        # Realistic correlated profile: better on-time rate tends to come
        # with lower dispute rate, plus noise, so it's not a perfect line.
        quality = rng.betavariate(5, 2)  # skewed toward "decent" merchants
        on_time_rate = round(min(0.99, max(0.55, quality + rng.uniform(-0.08, 0.08))), 3)
        dispute_rate = round(min(0.15, max(0.005, (1 - quality) * 0.15 + rng.uniform(-0.02, 0.02))), 4)
        avg_delivery_days = round(max(1, (1 - quality) * 8 + rng.uniform(-1, 1)))
        rows.append({
            "merchant_id": mid, "merchant_name": name, "category": category,
            "dispute_rate": dispute_rate, "on_time_rate": on_time_rate,
            "avg_delivery_days": avg_delivery_days,
        })
    return pd.DataFrame(rows)


def make_products(rng: random.Random, merchants: pd.DataFrame) -> list[dict]:
    products = []
    pid = 1
    merchants_by_cat = {
        cat: merchants[merchants.category == cat]["merchant_id"].tolist()
        for cat in CATEGORIES
    }
    # Make sure every catalog item exists at its pinned merchant first, so
    # transactions can reference exact prices for the demo products.
    pinned_products = {
        ("TechHaven", "Sony WH-1000XM5 Headphones"): 349.99,
        ("TechHaven", "Bose QuietComfort Ultra"): 429.00,
        ("HomeNest", "Instant Pot Duo 7-in-1"): 99.00,
        ("HomeNest", "Ninja Air Fryer"): 119.99,
        ("StyleLoop", "Denim Jacket"): 60.00,
    }
    name_to_merchant = {m["merchant_name"]: m["merchant_id"] for m in PINNED_MERCHANTS}
    pinned_ids = {}
    for (mname, pname), price in pinned_products.items():
        mid = name_to_merchant[mname]
        p_id = f"P_{pid:04d}"
        pid += 1
        cat = merchants.loc[merchants.merchant_id == mid, "category"].iloc[0]
        products.append({"product_id": p_id, "product_name": pname, "category": cat,
                          "price": price, "merchant_id": mid})
        pinned_ids[(mname, pname)] = p_id

    while len(products) < N_PRODUCTS:
        cat = rng.choice(CATEGORIES)
        if not merchants_by_cat[cat]:
            continue
        mid = rng.choice(merchants_by_cat[cat])
        pname, base_price = rng.choice(PRODUCT_CATALOG[cat])
        # jitter price slightly per-merchant so the same product isn't
        # identically priced everywhere (needed for the overpayment comparator
        # to find real alternatives)
        price = round(base_price * rng.uniform(0.85, 1.25), 2)
        p_id = f"P_{pid:04d}"
        pid += 1
        products.append({"product_id": p_id, "product_name": pname, "category": cat,
                          "price": price, "merchant_id": mid})
    return products, pinned_ids


def make_coupons(rng: random.Random, merchants: pd.DataFrame) -> list[dict]:
    coupons = []
    for i in range(N_COUPONS):
        m = merchants.sample(1, random_state=rng.randint(0, 10_000)).iloc[0]
        expires = TODAY + timedelta(days=rng.randint(3, 90))
        coupons.append({
            "code": f"SAVE{rng.randint(10, 99)}{m['merchant_id']}",
            "merchant_id": m["merchant_id"],
            "discount_pct": rng.choice([5, 10, 15, 20, 25]),
            "category": m["category"],
            "expires": expires.strftime("%Y-%m-%d"),
        })
    return coupons


def make_transactions_and_price_changes(rng: random.Random, np_rng: np.random.Generator,
                                         merchants: pd.DataFrame, products: list[dict],
                                         pinned_ids: dict):
    products_df = pd.DataFrame(products)
    merchants_idx = merchants.set_index("merchant_id")
    n_buyers = 300
    buyer_ids = [DEMO_BUYER] + [f"B{str(i).zfill(3)}" for i in range(2, n_buyers + 1)]
    # Power-law buyer weights: most buyers have few transactions, a handful
    # are heavy shoppers. Exponent 0.45 gives a realistic long tail
    # (many with 5-15 txns, some with 80+) for the churn model's RFM features.
    buyer_weights = np.array([1.0 / (i + 1) ** 0.45 for i in range(len(buyer_ids))])
    buyer_weights[0] = np.median(buyer_weights)  # B001 gets median weight (~30 txns)
    buyer_weights /= buyer_weights.sum()

    transactions = []
    price_changes = []
    txn_id = 1
    pc_id = 1

    # Guarantee the exact demo transactions API.md's examples reference,
    # so those example responses are reproducible from real data.
    demo_rows = [
        dict(product_key=("TechHaven", "Sony WH-1000XM5 Headphones"),
             customer_id="B001", days_ago=5, order_total=349.99, amount_charged=349.99,
             delivered_late=False, refund_requested=False),
        dict(product_key=("HomeNest", "Instant Pot Duo 7-in-1"),
             customer_id="B001", days_ago=7, order_total=99.00, amount_charged=99.00,
             delivered_late=False, refund_requested=False, price_drop_after=(6, 81.00)),
        dict(product_key=("StyleLoop", "Denim Jacket"),
             customer_id="B001", days_ago=12, order_total=60.00, amount_charged=72.40,
             delivered_late=False, refund_requested=False),
        # Late refund: B001 requested refund 10 days ago, still nothing back
        dict(product_key=("TechHaven", "Bose QuietComfort Ultra"),
             customer_id="B001", days_ago=10, order_total=429.00, amount_charged=429.00,
             delivered_late=False, refund_requested=True),
        # Delivery delay: B001's order promised in 2 days, now 5 days late
        dict(product_key=("HomeNest", "Ninja Air Fryer"),
             customer_id="B001", days_ago=7, order_total=119.99, amount_charged=119.99,
             delivered_late=True, refund_requested=False),
    ]
    reverse_pinned = {v: k for k, v in pinned_ids.items()}

    def add_transaction(product_id, customer_id, purchase_date, order_total,
                         amount_charged, promised_days, actual_days,
                         refund_requested, refund_received_date):
        nonlocal txn_id
        row = products_df.loc[products_df.product_id == product_id].iloc[0]
        transactions.append({
            "transaction_id": f"T_{txn_id:05d}",
            "customer_id": customer_id,
            "merchant_id": row.merchant_id,
            "product_id": product_id,
            "product_name": row.product_name,
            "category": row.category,
            "purchase_date": purchase_date.strftime("%Y-%m-%d"),
            "order_total": round(order_total, 2),
            "amount_charged": round(amount_charged, 2),
            "delivery_promised_days": promised_days,
            "delivery_actual_days": actual_days,
            "refund_requested": refund_requested,
            "refund_received_date": refund_received_date.strftime("%Y-%m-%d") if refund_received_date else None,
        })
        txn_id += 1

    for d in demo_rows:
        pid_ = pinned_ids[d["product_key"]]
        purchase_date = TODAY - timedelta(days=d["days_ago"])
        promised = merchants_idx.loc[products_df.loc[products_df.product_id == pid_, "merchant_id"].iloc[0], "avg_delivery_days"]
        add_transaction(pid_, d["customer_id"], purchase_date, d["order_total"],
                         d["amount_charged"], int(promised),
                         int(promised) + (4 if d["delivered_late"] else 0),
                         d["refund_requested"], None)
        if "price_drop_after" in d:
            drop_days_after, new_price = d["price_drop_after"]
            change_date = purchase_date + timedelta(days=drop_days_after)
            row = products_df.loc[products_df.product_id == pid_].iloc[0]
            price_changes.append({
                "price_change_id": f"PC_{pc_id:04d}", "product_id": pid_,
                "merchant_id": row.merchant_id, "old_price": d["order_total"],
                "new_price": new_price, "change_date": change_date.strftime("%Y-%m-%d"),
                "transaction_id": f"T_{txn_id - 1:05d}",  # ties to the demo txn just added
            })
            pc_id += 1

    n_remaining = N_TRANSACTIONS - len(transactions)
    for _ in range(n_remaining):
        buyer = np_rng.choice(buyer_ids, p=buyer_weights)
        product = products_df.sample(1, random_state=rng.randint(0, 1_000_000)).iloc[0]
        merchant = merchants_idx.loc[product.merchant_id]
        days_ago = rng.randint(1, TXN_WINDOW_DAYS)
        purchase_date = TODAY - timedelta(days=days_ago)
        order_total = float(product.price)

        is_overcharge = rng.random() < OVERCHARGE_RATE
        if is_overcharge:
            bump_pct = rng.uniform(OVERCHARGE_TAX_BUFFER_PCT / 100 + 0.01, 0.25)
            amount_charged = order_total * (1 + bump_pct)
        else:
            amount_charged = order_total

        promised_days = int(merchant.avg_delivery_days)
        # Delay probability is driven by merchant on_time_rate — this is the
        # real signal the ML model learns. A merchant with 96% on-time rate
        # delays ~3% of orders; one with 60% on-time delays ~32%.
        # Scaling factor 0.8 gives ~12% overall rate given our merchant mix.
        # Delay probability driven by merchant quality + category + promise gap.
        # Signal is clear enough for logistic regression to learn (AUC 0.75+).
        # This is synthetic data and we report it as such in the writeup.
        # Score-based delay: a continuous "delay score" from features, plus
        # controlled noise, thresholded to get a binary outcome. The model
        # learns the score function; the noise controls achievable AUC.
        quality = merchant.on_time_rate
        cat_risk = {"furniture": 1.2, "electronics": 0.6, "pet_supplies": 0.3, "apparel": 0.2}.get(product.category, 0)
        weekend = 0.5 if purchase_date.weekday() >= 5 else 0
        holiday = 0.7 if purchase_date.month in (11, 12) else 0
        # Score: higher = more likely to delay. Range roughly -1 to +3.
        delay_score = (1 - quality) * 4.0 + cat_risk + weekend + holiday
        # Add noise — this controls how learnable the outcome is.
        # std=0.8 gives AUC ~0.75-0.80 (good signal with realistic variance)
        delay_score += np_rng.normal(0, 0.8)
        is_delayed = delay_score > 2.5  # threshold tuned for ~12% rate
        base_actual = promised_days + (rng.randint(3, 8) if is_delayed else 0)
        actual_days = max(0, base_actual)

        refund_requested = rng.random() < 0.10
        is_late_refund = refund_requested and (rng.random() < (LATE_REFUND_RATE / 0.10))
        refund_received_date = None
        if refund_requested and not is_late_refund:
            refund_received_date = purchase_date + timedelta(days=rng.randint(2, 6))
        # if is_late_refund: stays None (never received) or very overdue
        elif refund_requested and is_late_refund and rng.random() < 0.5:
            refund_received_date = purchase_date + timedelta(days=rng.randint(8, 20))

        add_transaction(product.product_id, buyer, purchase_date, order_total,
                         amount_charged, promised_days, actual_days,
                         refund_requested, refund_received_date)

        if rng.random() < PRICE_DROP_RATE:
            change_date = purchase_date + timedelta(days=rng.randint(1, PRICE_DROP_WINDOW_DAYS))
            if change_date <= TODAY:
                new_price = round(order_total * rng.uniform(0.70, 0.95), 2)
                price_changes.append({
                    "price_change_id": f"PC_{pc_id:04d}", "product_id": product.product_id,
                    "merchant_id": product.merchant_id, "old_price": order_total,
                    "new_price": new_price, "change_date": change_date.strftime("%Y-%m-%d"),
                    "transaction_id": f"T_{txn_id - 1:05d}",  # ties this drop to one specific purchase
                })
                pc_id += 1

    # --- Churn simulation ---
    # Create tiered churn behavior so the model learns from MULTIPLE features
    # (order count, spend, category breadth), not just one threshold.
    txn_df = pd.DataFrame(transactions)
    txn_df["purchase_date_dt"] = pd.to_datetime(txn_df["purchase_date"])

    pair_stats = txn_df.groupby(["customer_id", "merchant_id"]).agg(
        count=("transaction_id", "count"),
        spend=("amount_charged", "sum"),
        cats=("category", "nunique"),
    ).reset_index()

    spend_median = pair_stats["spend"].median()

    # Compute churn probability per pair based on engagement profile
    # Lower engagement → higher churn probability → bigger date shift
    churn_rs = random.Random(rng.randint(0, 100000))
    shift_map = {}
    for _, row in pair_stats.iterrows():
        if row.customer_id == "B001":
            continue  # protect demo buyer
        # Churn score: 0 (loyal) to 1 (will churn)
        count_score = max(0, 1 - row["count"] / 5)  # 1 order → 0.8, 5+ → 0
        spend_score = max(0, 1 - row.spend / (spend_median * 2))  # low spend → high
        cat_score = max(0, 1 - row.cats / 3)  # single category → higher churn
        churn_score = 0.5 * count_score + 0.3 * spend_score + 0.2 * cat_score
        # Probabilistic: churn_score determines likelihood of shifting
        if churn_rs.random() < churn_score * 0.85:
            shift = int(60 + churn_score * 120)  # worse engagement → bigger shift
            shift_map[(row.customer_id, row.merchant_id)] = shift

    new_transactions = []
    for t_row in transactions:
        pair = (t_row["customer_id"], t_row["merchant_id"])
        if pair in shift_map:
            old_date = pd.to_datetime(t_row["purchase_date"])
            shifted = old_date - timedelta(days=shift_map[pair])
            t_row = dict(t_row)
            t_row["purchase_date"] = shifted.strftime("%Y-%m-%d")
        new_transactions.append(t_row)

    return pd.DataFrame(new_transactions), pd.DataFrame(price_changes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    merchants = make_merchants(rng)
    products, pinned_ids = make_products(rng, merchants)
    coupons = make_coupons(rng, merchants)
    transactions, price_changes = make_transactions_and_price_changes(
        rng, np_rng, merchants, products, pinned_ids
    )

    merchants.to_csv(out_dir / "merchants.csv", index=False)
    transactions.to_csv(out_dir / "transactions.csv", index=False)
    price_changes.to_csv(out_dir / "price_changes.csv", index=False)
    with open(out_dir / "coupons.json", "w") as f:
        json.dump(coupons, f, indent=2)
    with open(out_dir / "products.json", "w") as f:
        json.dump(products, f, indent=2)

    print(f"merchants.csv       {len(merchants)} rows")
    print(f"products.json       {len(products)} rows")
    print(f"transactions.csv    {len(transactions)} rows")
    print(f"price_changes.csv   {len(price_changes)} rows")
    print(f"coupons.json        {len(coupons)} rows")
    print(f"\nWritten to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
