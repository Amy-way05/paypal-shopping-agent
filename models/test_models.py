"""
Unit tests for all models. Run with:
    cd models
    python -m pytest test_models.py -v

Each test verifies:
    1. The model returns the correct shape
    2. The demo buyer (B001) gets expected results
    3. Edge cases (nonexistent buyer/merchant) return []
"""
import json
import os

import pytest

# Paths — tests run from inside models/
DATA_DIR = "../data"
DELAY_MODEL = "delay_model.joblib"
CHURN_MODEL = "churn_model.joblib"


def _ensure_models_trained():
    """Train models if joblib files don't exist."""
    if not os.path.exists(DELAY_MODEL):
        from delay_predictor import train as train_delay
        train_delay(data_dir=DATA_DIR, model_path=DELAY_MODEL)
    if not os.path.exists(CHURN_MODEL):
        from churn_predictor import train as train_churn
        train_churn(data_dir=DATA_DIR, model_path=CHURN_MODEL)


@pytest.fixture(autouse=True, scope="session")
def setup():
    _ensure_models_trained()


# --- Price-drop detector ---
class TestPriceDrop:
    def test_b001_has_alerts(self):
        from price_drop import run
        results = run("B001", data_dir=DATA_DIR)
        assert len(results) > 0

    def test_instant_pot_18(self):
        from price_drop import run
        results = run("B001", data_dir=DATA_DIR)
        demo = [a for a in results if "Instant Pot" in a["product_name"]]
        assert len(demo) == 1
        assert demo[0]["recoverable_amount"] == 18.00
        assert demo[0]["merchant_name"] == "HomeNest"

    def test_output_shape(self):
        from price_drop import run
        results = run("B001", data_dir=DATA_DIR)
        required = {"transaction_id", "type", "title", "details", "merchant_id",
                     "merchant_name", "product_name", "purchase_date",
                     "amount_paid", "reference_price", "recoverable_amount"}
        assert required.issubset(set(results[0].keys()))

    def test_nonexistent_buyer(self):
        from price_drop import run
        assert run("B999", data_dir=DATA_DIR) == []


# --- Overcharge detector ---
class TestOvercharge:
    def test_denim_jacket_12_40(self):
        from overcharge import run
        results = run("B001", data_dir=DATA_DIR)
        demo = [a for a in results if "Denim Jacket" in a["product_name"]]
        assert len(demo) == 1
        assert demo[0]["recoverable_amount"] == 12.40
        assert demo[0]["merchant_name"] == "StyleLoop"

    def test_no_false_positives(self):
        from overcharge import run
        results = run("B001", data_dir=DATA_DIR)
        for a in results:
            assert a["amount_paid"] > a["reference_price"] * 1.05

    def test_nonexistent_buyer(self):
        from overcharge import run
        assert run("B999", data_dir=DATA_DIR) == []


# --- Refund tracker ---
class TestRefundTracker:
    def test_b001_has_alerts(self):
        from refund_tracker import run
        results = run("B001", data_dir=DATA_DIR)
        assert len(results) > 0

    def test_no_negative_amounts(self):
        from refund_tracker import run
        results = run("B001", data_dir=DATA_DIR)
        for a in results:
            assert a["recoverable_amount"] > 0

    def test_nonexistent_buyer(self):
        from refund_tracker import run
        assert run("B999", data_dir=DATA_DIR) == []


# --- Overpayment comparator ---
class TestOverpayment:
    def test_sony_headphones(self):
        from overpayment import run
        result = run("electronics", 349.99, data_dir=DATA_DIR,
                     product_name="Sony WH-1000XM5 Headphones")
        assert result["network"]["median_price"] is not None
        assert result["network"]["percentile"] is not None
        assert len(result["alternatives"]) >= 1
        # Alternatives should be same product
        for alt in result["alternatives"]:
            assert alt["product_name"] == "Sony WH-1000XM5 Headphones"
            assert alt["price"] < 349.99

    def test_nonexistent_category(self):
        from overpayment import run
        result = run("nonexistent", 100.0, data_dir=DATA_DIR)
        assert result["network"]["overpaying"] is False
        assert result["alternatives"] == []


# --- Delivery delay predictor ---
class TestDelayPredictor:
    def test_b001_has_alerts(self):
        from delay_predictor import run
        results = run("B001", data_dir=DATA_DIR, model_path=DELAY_MODEL)
        assert len(results) > 0

    def test_output_shape(self):
        from delay_predictor import run
        results = run("B001", data_dir=DATA_DIR, model_path=DELAY_MODEL)
        required = {"transaction_id", "type", "title", "details", "merchant_id",
                     "merchant_name", "product_name", "purchase_date",
                     "delay_probability", "risk_level", "promised_date"}
        assert required.issubset(set(results[0].keys()))

    def test_probabilities_valid(self):
        from delay_predictor import run
        results = run("B001", data_dir=DATA_DIR, model_path=DELAY_MODEL)
        for a in results:
            assert 0 <= a["delay_probability"] <= 1
            assert a["risk_level"] in ("medium", "high")

    def test_nonexistent_buyer(self):
        from delay_predictor import run
        assert run("B999", data_dir=DATA_DIR, model_path=DELAY_MODEL) == []


# --- Churn predictor ---
class TestChurnPredictor:
    def test_m007_has_results(self):
        from churn_predictor import run
        results = run("M007", data_dir=DATA_DIR, model_path=CHURN_MODEL)
        assert len(results) > 0

    def test_b001_not_flagged(self):
        from churn_predictor import run
        results = run("M007", data_dir=DATA_DIR, model_path=CHURN_MODEL)
        b001 = [r for r in results if r["customer_id"] == "B001"]
        assert len(b001) == 0, "B001 bought 5 days ago, should not be at-risk"

    def test_output_shape(self):
        from churn_predictor import run
        results = run("M007", data_dir=DATA_DIR, model_path=CHURN_MODEL)
        required = {"customer_id", "churn_probability", "risk_tier",
                     "days_since_purchase", "total_spend", "order_count",
                     "last_category"}
        assert required.issubset(set(results[0].keys()))

    def test_nonexistent_merchant(self):
        from churn_predictor import run
        assert run("M999", data_dir=DATA_DIR, model_path=CHURN_MODEL) == []


# --- Savings aggregator ---
class TestSavingsAggregator:
    def test_b001_totals(self):
        from savings_aggregator import run
        result = run("B001", data_dir=DATA_DIR)
        assert result["total_saved"] > 0
        # Breakdown should sum to total
        bd_sum = sum(result["breakdown"].values())
        assert abs(bd_sum - result["total_saved"]) < 0.01

    def test_this_month_leq_total(self):
        from savings_aggregator import run
        result = run("B001", data_dir=DATA_DIR)
        assert result["this_month"] <= result["total_saved"]

    def test_output_shape(self):
        from savings_aggregator import run
        result = run("B001", data_dir=DATA_DIR)
        assert "total_saved" in result
        assert "this_month" in result
        assert "breakdown" in result
        assert "trend" in result
        assert "recent_actions" in result

    def test_nonexistent_buyer(self):
        from savings_aggregator import run
        result = run("B999", data_dir=DATA_DIR)
        assert result["total_saved"] == 0.0
        assert result["recent_actions"] == []
