"""
Overcharge detector — rule-based.

Compares order_total vs amount_charged. Flags any charge exceeding the
order total by more than OVERCHARGE_TAX_BUFFER_PCT (5%) to account for
normal tax variation.

This is a threshold rule, not IsolationForest — per team decision.
On synthetic data where we planted the anomalies ourselves, wrapping a
simple comparison in ML adds complexity without value and a sharp judge
will see through it.

Usage:
    from overcharge import run
    alerts = run("B001", data_dir="../data")
"""
from pathlib import Path

import pandas as pd

from constants import OVERCHARGE_TAX_BUFFER_PCT


def run(buyer_id: str, data_dir: str = "../data") -> list[dict]:
    """
    Find overcharge alerts for a specific buyer.

    Returns a list of dicts matching the API contract shape for
    POST /api/post-purchase/results alert type "overcharge":
        transaction_id, type, title, details, merchant_id, merchant_name,
        product_name, purchase_date, amount_paid, reference_price,
        recoverable_amount
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    merchants = pd.read_csv(data / "merchants.csv")

    # filter to this buyer
    buyer_txns = txns[txns.customer_id == buyer_id].copy()
    if buyer_txns.empty:
        return []

    # flag: charged more than order_total * (1 + buffer%)
    threshold = 1 + OVERCHARGE_TAX_BUFFER_PCT / 100
    flagged = buyer_txns[buyer_txns.amount_charged > buyer_txns.order_total * threshold].copy()

    if flagged.empty:
        return []

    # enrich with merchant names
    merchant_names = merchants.set_index("merchant_id")["merchant_name"]

    alerts = []
    for _, row in flagged.iterrows():
        merchant_name = merchant_names.get(row.merchant_id, row.merchant_id)
        recoverable = round(row.amount_charged - row.order_total, 2)
        overcharge_pct = round((row.amount_charged / row.order_total - 1) * 100, 1)

        alerts.append({
            "transaction_id": row.transaction_id,
            "type": "overcharge",
            "title": f"Overcharged by {merchant_name}",
            "details": (
                f"Listed at ${row.order_total:.2f}, you were charged "
                f"${row.amount_charged:.2f} ({overcharge_pct}% over)."
            ),
            "merchant_id": row.merchant_id,
            "merchant_name": merchant_name,
            "product_name": row.product_name,
            "purchase_date": row.purchase_date,
            "amount_paid": round(float(row.amount_charged), 2),
            "reference_price": round(float(row.order_total), 2),
            "recoverable_amount": recoverable,
        })

    # sort by recoverable amount descending
    alerts.sort(key=lambda a: a["recoverable_amount"], reverse=True)
    return alerts


if __name__ == "__main__":
    results = run("B001")
    print(f"Found {len(results)} overcharge alerts for B001:\n")
    for a in results:
        print(f"  {a['title']}")
        print(f"  {a['details']}")
        print(f"  Recoverable: ${a['recoverable_amount']:.2f}")
        print()
