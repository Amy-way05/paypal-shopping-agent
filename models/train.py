"""
Train all ML models and log metrics.

Generates the dataset (if not already present), trains delay + churn models,
saves .joblib files, and writes metrics.json for the Devpost submission.

Usage:
    python train.py                      # train with default paths
    python train.py --data-dir ../data   # custom data directory
"""
import argparse
import json
from pathlib import Path

from generate_data import main as generate_main
from delay_predictor import train as train_delay
from churn_predictor import train as train_churn
from constants import RANDOM_SEED


def _json_default(o):
    """numpy scalars (e.g. numpy.bool_ from meets_target) -> plain Python for json."""
    return o.item() if hasattr(o, "item") else str(o)


def main():
    parser = argparse.ArgumentParser(description="Train all ML models")
    parser.add_argument("--data-dir", default="../data", help="Path to data directory")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--regenerate", action="store_true", help="Regenerate dataset first")
    args = parser.parse_args()

    data_dir = args.data_dir
    data_path = Path(data_dir)

    # Step 1: Generate data if needed
    if args.regenerate or not (data_path / "transactions.csv").exists():
        print("=" * 50)
        print("STEP 1: Generating dataset")
        print("=" * 50)
        generate_main()
        print()

    # Step 2: Train delay predictor
    print("=" * 50)
    print("STEP 2: Training delivery delay predictor")
    print("=" * 50)
    delay_metrics = train_delay(
        data_dir=data_dir,
        model_path="delay_model.joblib",
        seed=args.seed,
    )
    print()

    # Step 3: Train churn predictor
    print("=" * 50)
    print("STEP 3: Training churn predictor")
    print("=" * 50)
    churn_metrics = train_churn(
        data_dir=data_dir,
        model_path="churn_model.joblib",
        seed=args.seed,
    )
    print()

    # Step 4: Save metrics.json (task 11)
    print("=" * 50)
    print("STEP 4: Logging metrics")
    print("=" * 50)
    metrics = {
        "delay_predictor": {
            "model": "GradientBoostingClassifier",
            "auc": delay_metrics["auc"],
            "precision": delay_metrics["precision"],
            "recall": delay_metrics["recall"],
            "target_auc": delay_metrics["target_auc"],
            "meets_target": delay_metrics["meets_target"],
            "note": "on synthetic data",
        },
        "churn_predictor": {
            "model": "GradientBoostingClassifier + recency adjustment",
            "auc": churn_metrics["auc"],
            "precision": churn_metrics["precision"],
            "recall": churn_metrics["recall"],
            "target_auc": churn_metrics["target_auc"],
            "meets_target": churn_metrics["meets_target"],
            "note": "on synthetic data, time-split validation",
        },
        "rule_based_detectors": {
            "price_drop": "rule: merchant dropped price within 7 days of purchase",
            "overcharge": "rule: amount_charged > order_total * 1.05",
            "refund_tracker": "rule: refund requested, not received or 7+ days overdue",
            "overpayment": "stats: percentile rank against network median + product search",
            "note": "These are rules, not ML models. Reported honestly.",
        },
    }

    metrics_path = Path("metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2, default=_json_default)

    print(f"Metrics saved to {metrics_path}")
    print(json.dumps(metrics, indent=2, default=_json_default))
    print()
    print("=" * 50)
    print("DONE — all models trained, metrics logged")
    print("=" * 50)


if __name__ == "__main__":
    main()
