"""
Overpayment comparator — stats-based.

Takes a product category + price, compares against the network median
from transactions.csv, flags if above the 65th percentile, and queries
products.json for up to 3 cheaper alternatives from low-dispute merchants.

Usage:
    from overpayment import run
    result = run("electronics", 349.99, data_dir="../data")
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from constants import OVERPAYMENT_PERCENTILE


# Dispute rate ceiling for "trusted" merchants when surfacing alternatives
MAX_DISPUTE_RATE_FOR_ALT = 0.05


def run(category: str, price: float, data_dir: str = "../data",
        product_name: str | None = None,
        exclude_merchant_id: str | None = None) -> dict:
    """
    Check whether a price is above the network median for its category,
    and find cheaper alternatives from trusted merchants.

    If product_name is provided, prioritizes the SAME product at different
    merchants/prices (the realistic scenario: "you're buying Sony headphones
    at Store A for $349, Store B has them for $309"). Falls back to
    same-category alternatives only if no same-product matches exist.

    Returns a dict matching the API contract shape for
    POST /api/find-better-deal response:
        network: {median_price, percentile, overpaying}
        alternatives: [{product_id, product_name, price, merchant_id,
                        merchant_name, dispute_rate, on_time_rate, savings}]
        best_option: product_id or None
        potential_savings: float
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    merchants = pd.read_csv(data / "merchants.csv")
    with open(data / "products.json") as f:
        products = json.load(f)

    # --- Network stats for this category ---
    cat_txns = txns[txns.category == category]["order_total"]

    if cat_txns.empty:
        return {
            "network": {"median_price": None, "percentile": None, "overpaying": False},
            "alternatives": [],
            "best_option": None,
            "potential_savings": 0.0,
        }

    median_price = round(float(cat_txns.median()), 2)
    percentile = round(float(stats.percentileofscore(cat_txns, price, kind="rank")))
    overpaying = percentile > OVERPAYMENT_PERCENTILE

    # --- Find cheaper alternatives from low-dispute merchants ---
    merchant_lookup = merchants.set_index("merchant_id").to_dict("index")

    def _find_candidates(name_filter: str | None = None) -> list[dict]:
        """Find cheaper products, optionally filtered by exact product name."""
        results = []
        for p in products:
            if p["category"] != category:
                continue
            if p["price"] >= price:
                continue
            if exclude_merchant_id and p["merchant_id"] == exclude_merchant_id:
                continue
            if name_filter and p["product_name"] != name_filter:
                continue

            m = merchant_lookup.get(p["merchant_id"])
            if not m:
                continue
            if m["dispute_rate"] > MAX_DISPUTE_RATE_FOR_ALT:
                continue

            savings = round(price - p["price"], 2)
            results.append({
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "price": p["price"],
                "merchant_id": p["merchant_id"],
                "merchant_name": m["merchant_name"],
                "dispute_rate": m["dispute_rate"],
                "on_time_rate": m["on_time_rate"],
                "savings": savings,
            })
        return results

    # Prefer same-product matches (same headphones at a cheaper store),
    # fall back to same-category only if no same-product alternatives exist
    candidates = []
    if product_name:
        candidates = _find_candidates(name_filter=product_name)
    if not candidates:
        candidates = _find_candidates(name_filter=None)

    # sort by savings descending, take top 3
    candidates.sort(key=lambda c: c["savings"], reverse=True)
    top_3 = candidates[:3]

    best_option = top_3[0]["product_id"] if top_3 else None
    potential_savings = top_3[0]["savings"] if top_3 else 0.0

    return {
        "network": {
            "median_price": median_price,
            "percentile": percentile,
            "overpaying": overpaying,
        },
        "alternatives": top_3,
        "best_option": best_option,
        "potential_savings": potential_savings,
    }


if __name__ == "__main__":
    # Demo: same scenario as API.md Flow A — Sony headphones at $349.99
    result = run("electronics", 349.99, product_name="Sony WH-1000XM5 Headphones")
    net = result["network"]
    print(f"Your price:    $349.99")
    print(f"Network median: ${net['median_price']}")
    print(f"Percentile:     {net['percentile']}th")
    print(f"Overpaying:     {net['overpaying']}")
    print(f"\nTop alternatives:")
    for alt in result["alternatives"]:
        print(f"  {alt['product_name']} @ ${alt['price']:.2f} from {alt['merchant_name']}")
        print(f"    Savings: ${alt['savings']:.2f} | Dispute: {alt['dispute_rate']} | On-time: {alt['on_time_rate']}")
    print(f"\nBest option: {result['best_option']}")
    print(f"Potential savings: ${result['potential_savings']:.2f}")
