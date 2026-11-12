"""
Churn predictor (merchant side) — random forest on RFM features.

Uses a time-split approach so recency is a legitimate feature:
- Features computed from transactions BEFORE the split date
- Label: did this buyer return to this merchant AFTER the split date?

This avoids the label-leak trap where days_since_purchase IS the label.

Target AUC: 0.70+.

Usage:
    from churn_predictor import train, run
    metrics = train(data_dir="../data", model_path="churn_model.joblib")
    at_risk = run("M007", data_dir="../data", model_path="churn_model.joblib")
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from constants import CHURN_MODEL_TARGET_AUC, RANDOM_SEED

TODAY = pd.Timestamp("2026-11-09")
CHURN_DAYS = 60
# Time-split: features from before this date, label from after.
# Midpoint of the ~8-month transaction window gives enough data on both sides.
SPLIT_DATE = pd.Timestamp("2026-08-15")


def _build_rfm(txns: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Build RFM features per buyer-merchant pair, measured as of a date."""
    txns = txns.copy()
    txns["purchase_date"] = pd.to_datetime(txns["purchase_date"])

    rfm = txns.groupby(["customer_id", "merchant_id"]).agg(
        last_purchase=("purchase_date", "max"),
        order_count=("transaction_id", "count"),
        total_spend=("amount_charged", "sum"),
        avg_order_value=("amount_charged", "mean"),
        first_purchase=("purchase_date", "min"),
        categories_bought=("category", "nunique"),
    ).reset_index()

    rfm["days_since_purchase"] = (as_of - rfm["last_purchase"]).dt.days
    rfm["customer_tenure_days"] = (rfm["last_purchase"] - rfm["first_purchase"]).dt.days
    rfm["purchase_frequency"] = np.where(
        rfm["customer_tenure_days"] > 0,
        rfm["order_count"] / (rfm["customer_tenure_days"] / 30),
        rfm["order_count"],
    )

    def avg_gap(group):
        dates = group.sort_values()
        if len(dates) < 2:
            return 999.0
        return dates.diff().dropna().dt.days.mean()

    gaps = txns.groupby(["customer_id", "merchant_id"])["purchase_date"].apply(avg_gap)
    gaps.name = "avg_purchase_gap"
    rfm = rfm.merge(gaps, on=["customer_id", "merchant_id"], how="left")

    return rfm


def _get_feature_cols():
    # days_since_purchase is legitimate here: in training it's measured at
    # SPLIT_DATE, while the label comes from the period AFTER SPLIT_DATE.
    return [
        "days_since_purchase",
        "order_count",
        "total_spend",
        "avg_order_value",
        "customer_tenure_days",
        "purchase_frequency",
        "categories_bought",
        "avg_purchase_gap",
    ]


def train(data_dir: str = "../data", model_path: str = "churn_model.joblib",
          seed: int = RANDOM_SEED) -> dict:
    """Train churn predictor using time-split. Returns metrics."""
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")
    txns["purchase_date"] = pd.to_datetime(txns["purchase_date"])

    # Split: features from before SPLIT_DATE, label from after
    obs_txns = txns[txns.purchase_date < SPLIT_DATE]
    outcome_txns = txns[txns.purchase_date >= SPLIT_DATE]

    rfm = _build_rfm(obs_txns, as_of=SPLIT_DATE)
    feature_cols = _get_feature_cols()

    # Label: did NOT return after split = churned
    returned = set(
        outcome_txns.groupby(["customer_id", "merchant_id"])
        .size().reset_index()[["customer_id", "merchant_id"]]
        .apply(tuple, axis=1)
    )
    rfm["churned"] = rfm.apply(
        lambda r: 0 if (r.customer_id, r.merchant_id) in returned else 1, axis=1
    )

    X = rfm[feature_cols].fillna(0)
    y = rfm["churned"]

    if y.nunique() < 2:
        print("WARNING: only one class in labels, cannot train")
        return {"auc": 0, "precision": 0, "recall": 0, "meets_target": False}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.1,
        random_state=seed, subsample=0.8, min_samples_leaf=10,
    )
    model.fit(X_train_s, y_train)

    y_proba = model.predict_proba(X_test_s)[:, 1]
    y_pred = model.predict(X_test_s)

    auc = round(roc_auc_score(y_test, y_proba), 4)
    precision = round(precision_score(y_test, y_pred, zero_division=0), 4)
    recall = round(recall_score(y_test, y_pred, zero_division=0), 4)

    joblib.dump({"model": model, "scaler": scaler, "feature_cols": feature_cols}, model_path)

    metrics = {
        "auc": auc, "precision": precision, "recall": recall,
        "target_auc": CHURN_MODEL_TARGET_AUC,
        "meets_target": auc >= CHURN_MODEL_TARGET_AUC,
        "note": "on synthetic data, time-split validation",
    }
    print(f"Churn predictor trained: AUC={auc} precision={precision} recall={recall}")
    print(f"Target AUC: {CHURN_MODEL_TARGET_AUC}  {'MET' if metrics['meets_target'] else 'MISSED'}")
    return metrics


def _risk_tier(prob: float) -> str:
    if prob >= 0.7:
        return "high"
    elif prob >= 0.4:
        return "medium"
    return "low"


def run(merchant_id: str, data_dir: str = "../data",
        model_path: str = "churn_model.joblib",
        min_risk: str = "medium") -> list[dict]:
    """
    Get at-risk customers for a merchant, ranked by churn probability.

    Returns list of dicts matching API contract for
    GET /api/merchant/dashboard/{merchant_id}:
        customer_id, churn_probability, risk_tier, days_since_purchase,
        total_spend, order_count, last_category
    """
    data = Path(data_dir)
    txns = pd.read_csv(data / "transactions.csv")

    merchant_txns = txns[txns.merchant_id == merchant_id]
    if merchant_txns.empty:
        return []

    # Current RFM (as of today) for inference
    rfm = _build_rfm(merchant_txns, as_of=TODAY)
    feature_cols = _get_feature_cols()

    bundle = joblib.load(model_path)
    model = bundle["model"]
    scaler = bundle["scaler"]

    X = rfm[feature_cols].fillna(0)
    X_scaled = scaler.transform(X)
    probas = model.predict_proba(X_scaled)[:, 1]

    # Last category per customer
    txns_sorted = merchant_txns.sort_values("purchase_date")
    last_category = txns_sorted.groupby("customer_id")["category"].last()

    risk_cutoff = {"low": 0.0, "medium": 0.4, "high": 0.7}.get(min_risk, 0.4)

    results = []
    for i, (_, row) in enumerate(rfm.iterrows()):
        prob = round(min(float(probas[i]), 0.99), 2)  # cap at 0.99, never show 1.0
        tier = _risk_tier(prob)

        if prob < risk_cutoff:
            continue

        results.append({
            "customer_id": row.customer_id,
            "churn_probability": prob,
            "risk_tier": tier,
            "days_since_purchase": int(row.days_since_purchase),
            "total_spend": round(float(row.total_spend), 2),
            "order_count": int(row.order_count),
            "last_category": last_category.get(row.customer_id, "unknown"),
        })

    results.sort(key=lambda r: r["churn_probability"], reverse=True)
    return results


if __name__ == "__main__":
    metrics = train()
    print()
    results = run("M007")
    print(f"M007 (TechHaven): {len(results)} at-risk customers\n")
    for r in results[:5]:
        print(f"  {r['customer_id']}: {r['risk_tier']} ({r['churn_probability']}) "
              f"| {r['days_since_purchase']}d ago | ${r['total_spend']:.2f} | "
              f"{r['order_count']} orders | {r['last_category']}")
