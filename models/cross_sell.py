"""
Cross-sell scorer (merchant side) — co-purchase analysis.

Finds which product categories get bought together by the same buyer
within 30 days. Returns product pairs with co-purchase rates and
suggested bundle discounts.

This is a stretch goal (cut second per ground rules). Built with pure
pandas rather than mlxtend Apriori — simpler, fewer dependencies, and
the dataset is small enough that the full matrix fits in memory.

Usage:
    from cross_sell import run
    pairs = run("M007", data_dir="../data")
"""
from pathlib import Path

import pandas as pd

CO_PURCHASE_WINDOW_DAYS = 30


def run(merchant_id: str, data_dir: str = "../data",
        min_support: float = 0.02, top_n: int = 10) -> list[dict]:
    """
    Find co-purchase patterns for a merchant's customers.

    Returns a list of dicts matching the API contract for
    GET /api/merchant/dashboard/{merchant_id} cross-sell section:
        category_a, category_b, co_purchase_rate, pair_count,
        suggested_bundle_discount_pct
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    txns["purchase_date"] = pd.to_datetime(txns["purchase_date"])

    # Get all buyers who have purchased from this merchant
    merchant_buyers = txns[txns.merchant_id == merchant_id]["customer_id"].unique()
    if len(merchant_buyers) == 0:
        return []

    # Get ALL transactions from those buyers (across all merchants)
    # because cross-sell is about what else these customers buy
    buyer_txns = txns[txns.customer_id.isin(merchant_buyers)].copy()
    buyer_txns = buyer_txns.sort_values(["customer_id", "purchase_date"])

    # Find co-purchases: same buyer, different categories, within 30 days
    pairs = {}
    total_buyers = len(merchant_buyers)

    for buyer_id in merchant_buyers:
        bt = buyer_txns[buyer_txns.customer_id == buyer_id]
        if len(bt) < 2:
            continue

        # Find unique category pairs within the time window
        buyer_pairs = set()
        dates_cats = list(zip(bt.purchase_date, bt.category))

        for i in range(len(dates_cats)):
            for j in range(i + 1, len(dates_cats)):
                date_i, cat_i = dates_cats[i]
                date_j, cat_j = dates_cats[j]

                if cat_i == cat_j:
                    continue
                if abs((date_j - date_i).days) > CO_PURCHASE_WINDOW_DAYS:
                    continue

                # Alphabetical order so (A,B) == (B,A)
                pair = tuple(sorted([cat_i, cat_j]))
                buyer_pairs.add(pair)

        for pair in buyer_pairs:
            pairs[pair] = pairs.get(pair, 0) + 1

    if not pairs:
        return []

    # Compute support (fraction of buyers who co-purchased this pair)
    results = []
    for (cat_a, cat_b), count in pairs.items():
        support = count / total_buyers
        if support < min_support:
            continue

        # Suggested discount: higher co-purchase rate → smaller discount needed
        # (they already buy together), lower rate → bigger incentive
        if support >= 0.15:
            discount = 5
        elif support >= 0.08:
            discount = 10
        else:
            discount = 15

        results.append({
            "category_a": cat_a,
            "category_b": cat_b,
            "co_purchase_rate": round(support, 3),
            "pair_count": count,
            "suggested_bundle_discount_pct": discount,
        })

    results.sort(key=lambda r: r["co_purchase_rate"], reverse=True)
    return results[:top_n]


if __name__ == "__main__":
    # Demo: TechHaven (M007)
    results = run("M007")
    print(f"M007 (TechHaven): {len(results)} cross-sell pairs\n")
    for r in results:
        print(f"  {r['category_a']} + {r['category_b']}: "
              f"{r['co_purchase_rate']:.1%} ({r['pair_count']} buyers) "
              f"→ suggest {r['suggested_bundle_discount_pct']}% bundle discount")
