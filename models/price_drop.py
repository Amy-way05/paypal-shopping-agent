"""
Price-drop detector — rule-based.

Joins transactions with price_changes.csv and finds every purchase where
the merchant dropped the price within PRICE_DROP_WINDOW_DAYS (7 days).
Calculates recoverable amount per transaction.

This is a rule, not an ML model. Calling it what it is — per team decision
(Hetav's review: "using ML language for threshold checks adds complexity
without value on synthetic data").

Usage:
    from price_drop import run
    alerts = run("B001", data_dir="../data")
"""
from pathlib import Path

import pandas as pd

from constants import PRICE_DROP_WINDOW_DAYS


def run(buyer_id: str, data_dir: str = "../data") -> list[dict]:
    """
    Find price-drop recovery opportunities for a specific buyer.

    Returns a list of dicts matching the API contract shape for
    POST /api/post-purchase/results alert type "price_drop":
        transaction_id, type, title, details, merchant_id, merchant_name,
        product_name, purchase_date, amount_paid, reference_price,
        recoverable_amount
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    pcs = pd.read_csv(data / "price_changes.csv")
    merchants = pd.read_csv(data / "merchants.csv")

    # filter to this buyer's transactions
    buyer_txns = txns[txns.customer_id == buyer_id].copy()
    if buyer_txns.empty:
        return []

    buyer_txns["purchase_date"] = pd.to_datetime(buyer_txns["purchase_date"])
    pcs["change_date"] = pd.to_datetime(pcs["change_date"])

    # join on transaction_id (each price change is tied to a specific purchase)
    merged = buyer_txns.merge(
        pcs, on=["transaction_id", "product_id", "merchant_id"], how="inner"
    )

    # keep only drops within the window AND where new_price < old_price
    merged = merged[
        (merged.change_date > merged.purchase_date)
        & (merged.change_date <= merged.purchase_date + pd.Timedelta(days=PRICE_DROP_WINDOW_DAYS))
        & (merged.new_price < merged.old_price)
    ]

    if merged.empty:
        return []

    # enrich with merchant names
    merchant_names = merchants.set_index("merchant_id")["merchant_name"]

    alerts = []
    for _, row in merged.iterrows():
        merchant_name = merchant_names.get(row.merchant_id, row.merchant_id)
        recoverable = round(row.amount_charged - row.new_price, 2)
        if recoverable <= 0:
            continue

        alerts.append({
            "transaction_id": row.transaction_id,
            "type": "price_drop",
            "title": f"Price dropped on your {row.product_name}",
            "details": (
                f"You paid ${row.amount_charged:.2f} on "
                f"{row.purchase_date.strftime('%b %-d')}. "
                f"{merchant_name} dropped it to ${row.new_price:.2f} on "
                f"{row.change_date.strftime('%b %-d')}."
            ),
            "merchant_id": row.merchant_id,
            "merchant_name": merchant_name,
            "product_name": row.product_name,
            "purchase_date": row.purchase_date.strftime("%Y-%m-%d"),
            "amount_paid": round(float(row.amount_charged), 2),
            "reference_price": round(float(row.new_price), 2),
            "recoverable_amount": recoverable,
        })

    # sort by recoverable amount descending (biggest savings first)
    alerts.sort(key=lambda a: a["recoverable_amount"], reverse=True)
    return alerts


if __name__ == "__main__":
    # quick demo: run for B001 and print
    results = run("B001")
    print(f"Found {len(results)} price-drop alerts for B001:\n")
    for a in results:
        print(f"  {a['title']}")
        print(f"  {a['details']}")
        print(f"  Recoverable: ${a['recoverable_amount']:.2f}")
        print()
