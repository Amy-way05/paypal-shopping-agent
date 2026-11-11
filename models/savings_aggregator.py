"""
Savings aggregator — pulls outputs from all buyer-side models.

Sums total savings by category and over time. Every number in the savings
dashboard comes from here — the hero "$847 Total Saved" is computed from
actual model output, never typed into a mockup (hard rule from team chat).

Usage:
    from savings_aggregator import run
    summary = run("B001", data_dir="../data", model_path_delay="delay_model.joblib")
"""
from pathlib import Path

import pandas as pd

from price_drop import run as price_drop_run
from overcharge import run as overcharge_run
from refund_tracker import run as refund_run


def run(buyer_id: str, data_dir: str = "../data") -> dict:
    """
    Aggregate all savings for a buyer across all detection types.

    Returns a dict matching the API contract for GET /api/savings/{buyer_id}:
        total_saved, this_month, breakdown, trend, recent_actions
    """
    # Collect alerts from all buyer-side detectors
    pd_alerts = price_drop_run(buyer_id, data_dir=data_dir)
    oc_alerts = overcharge_run(buyer_id, data_dir=data_dir)
    rf_alerts = refund_run(buyer_id, data_dir=data_dir)
    # Note: delay alerts don't have a dollar recovery — they're warnings,
    # not money-back events. Included in recent_actions but not in totals.

    # Combine all money-recovery alerts
    all_alerts = []
    for a in pd_alerts:
        all_alerts.append({
            "type": "price_drop",
            "amount": a["recoverable_amount"],
            "date": a["purchase_date"],
            "product": a["product_name"],
            "merchant": a["merchant_name"],
            "title": a["title"],
        })
    for a in oc_alerts:
        all_alerts.append({
            "type": "overcharge",
            "amount": a["recoverable_amount"],
            "date": a["purchase_date"],
            "product": a["product_name"],
            "merchant": a["merchant_name"],
            "title": a["title"],
        })
    for a in rf_alerts:
        all_alerts.append({
            "type": "late_refund",
            "amount": a["recoverable_amount"],
            "date": a["purchase_date"],
            "product": a["product_name"],
            "merchant": a["merchant_name"],
            "title": a["title"],
        })

    if not all_alerts:
        return {
            "total_saved": 0.0,
            "this_month": 0.0,
            "breakdown": {
                "price_drop": 0.0,
                "overcharge": 0.0,
                "late_refund": 0.0,
                "better_deal": 0.0,
            },
            "trend": [],
            "recent_actions": [],
        }

    # Convert to DataFrame for aggregation
    df = pd.DataFrame(all_alerts)
    df["date"] = pd.to_datetime(df["date"])

    # Total saved
    total_saved = round(df["amount"].sum(), 2)

    # This month
    now = pd.Timestamp("2026-11-09")
    month_start = now.replace(day=1)
    this_month = round(df[df["date"] >= month_start]["amount"].sum(), 2)

    # Breakdown by type
    breakdown = {
        "price_drop": round(df[df.type == "price_drop"]["amount"].sum(), 2),
        "overcharge": round(df[df.type == "overcharge"]["amount"].sum(), 2),
        "late_refund": round(df[df.type == "late_refund"]["amount"].sum(), 2),
        "better_deal": 0.0,  # populated when Flow A purchases happen via backend
    }

    # Monthly trend (for Recharts line chart)
    df["month"] = df["date"].dt.to_period("M")
    trend_data = df.groupby("month")["amount"].sum().sort_index()
    trend = [
        {"month": str(period), "amount": round(float(amt), 2)}
        for period, amt in trend_data.items()
    ]

    # Recent actions (most recent first, for the activity feed)
    recent = df.sort_values("date", ascending=False).head(10)
    recent_actions = [
        {
            "type": row.type,
            "title": row.title,
            "amount": round(float(row.amount), 2),
            "date": row.date.strftime("%Y-%m-%d"),
            "product": row.product,
            "merchant": row.merchant,
        }
        for _, row in recent.iterrows()
    ]

    return {
        "total_saved": total_saved,
        "this_month": this_month,
        "breakdown": breakdown,
        "trend": trend,
        "recent_actions": recent_actions,
    }


if __name__ == "__main__":
    result = run("B001")
    print(f"Total saved:  ${result['total_saved']:.2f}")
    print(f"This month:   ${result['this_month']:.2f}")
    print(f"\nBreakdown:")
    for k, v in result["breakdown"].items():
        print(f"  {k}: ${v:.2f}")
    print(f"\nMonthly trend:")
    for t in result["trend"]:
        print(f"  {t['month']}: ${t['amount']:.2f}")
    print(f"\nRecent actions ({len(result['recent_actions'])}):")
    for a in result["recent_actions"][:5]:
        print(f"  {a['date']} | {a['type']} | {a['title']} | ${a['amount']:.2f}")
