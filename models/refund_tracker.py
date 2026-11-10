"""
Refund tracker — rule-based.

Filters transactions where a refund was requested but:
  - never received (refund_received_date is null), OR
  - received 7+ days after purchase (overdue per LATE_REFUND_OVERDUE_DAYS)

Usage:
    from refund_tracker import run
    alerts = run("B001", data_dir="../data")
"""
from pathlib import Path

import pandas as pd

from constants import LATE_REFUND_OVERDUE_DAYS


def run(buyer_id: str, data_dir: str = "../data") -> list[dict]:
    """
    Find overdue refund alerts for a specific buyer.

    Returns a list of dicts matching the API contract shape for
    POST /api/post-purchase/results alert type "late_refund":
        transaction_id, type, title, details, merchant_id, merchant_name,
        product_name, purchase_date, amount_paid, reference_price,
        recoverable_amount, days_overdue, refund_status
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    merchants = pd.read_csv(data / "merchants.csv")

    # filter to this buyer, only where refund was requested
    buyer_txns = txns[
        (txns.customer_id == buyer_id) & (txns.refund_requested == True)
    ].copy()

    if buyer_txns.empty:
        return []

    buyer_txns["purchase_date_dt"] = pd.to_datetime(buyer_txns["purchase_date"])
    buyer_txns["refund_received_dt"] = pd.to_datetime(
        buyer_txns["refund_received_date"], errors="coerce"
    )

    # today for calculating days overdue
    today = pd.Timestamp("2026-11-09")

    alerts = []
    merchant_names = merchants.set_index("merchant_id")["merchant_name"]

    for _, row in buyer_txns.iterrows():
        never_received = pd.isna(row.refund_received_dt)

        if never_received:
            days_waiting = (today - row.purchase_date_dt).days
            if days_waiting < LATE_REFUND_OVERDUE_DAYS:
                continue  # still within grace period
            days_overdue = days_waiting - LATE_REFUND_OVERDUE_DAYS
            refund_status = "never_received"
        else:
            days_to_refund = (row.refund_received_dt - row.purchase_date_dt).days
            if days_to_refund < LATE_REFUND_OVERDUE_DAYS:
                continue  # refund came on time
            days_overdue = days_to_refund - LATE_REFUND_OVERDUE_DAYS
            refund_status = "received_late"

        merchant_name = merchant_names.get(row.merchant_id, row.merchant_id)
        recoverable = round(float(row.amount_charged), 2)

        if refund_status == "never_received":
            title = f"Refund missing from {merchant_name}"
            details = (
                f"You requested a refund on ${recoverable:.2f} "
                f"({row.product_name}) {days_waiting} days ago. "
                f"Still nothing back — {days_overdue} days overdue."
            )
        else:
            title = f"Refund was late from {merchant_name}"
            details = (
                f"Refund of ${recoverable:.2f} ({row.product_name}) "
                f"took {(row.refund_received_dt - row.purchase_date_dt).days} days "
                f"— {days_overdue} days past the {LATE_REFUND_OVERDUE_DAYS}-day window."
            )

        alerts.append({
            "transaction_id": row.transaction_id,
            "type": "late_refund",
            "title": title,
            "details": details,
            "merchant_id": row.merchant_id,
            "merchant_name": merchant_name,
            "product_name": row.product_name,
            "purchase_date": row.purchase_date,
            "amount_paid": recoverable,
            "reference_price": 0.00,  # full amount is recoverable
            "recoverable_amount": recoverable,
            "days_overdue": days_overdue,
            "refund_status": refund_status,
        })

    # sort: never_received first (more urgent), then by days overdue
    alerts.sort(key=lambda a: (a["refund_status"] != "never_received", -a["days_overdue"]))
    return alerts


if __name__ == "__main__":
    results = run("B001")
    print(f"Found {len(results)} refund alerts for B001:\n")
    for a in results:
        print(f"  {a['title']}")
        print(f"  {a['details']}")
        print(f"  Status: {a['refund_status']} | Overdue: {a['days_overdue']}d | Amount: ${a['recoverable_amount']:.2f}")
        print()
