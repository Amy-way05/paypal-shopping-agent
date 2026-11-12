"""Regression tests for the bugs found in the pre-demo QA pass, plus credential validation.

Run from backend/:  python -m pytest -q
"""
import time

import pytest
from fastapi.testclient import TestClient

import state as m
from main import app
from routers import buyer
from services import config_check
from services import models_adapter as data

data.ensure_ready()
c = TestClient(app)

ORDER = {"buyer_id": "B001", "product_id": "P_0007", "product_name": "Running Insoles", "merchant_id": "M042",
         "category": "sporting_goods", "amount": 18, "original_price": 24, "payment_option": "pay_now",
         "source": "better_deal", "goal_id": None, "confirmed": False}


@pytest.fixture(autouse=True)
def fresh_state():
    m.reset_state()


def _run_guardian_and_claim_all(monkeypatch):
    monkeypatch.setattr(buyer, "READY_AFTER", {k: 0 for k in buyer.READY_AFTER})
    monkeypatch.setattr(buyer, "RESOLVE_DELAY", 0)
    monkeypatch.setattr(buyer, "RECOVER_DELAY", 0)
    c.post("/api/post-purchase/scan/B001")
    time.sleep(0.05)
    for a in c.get("/api/post-purchase/results/B001").json()["alerts"]:
        c.post(f"/api/post-purchase/claim/{a['alert_id']}", json={"confirmed": True})
    time.sleep(0.05)
    c.get("/api/post-purchase/results/B001")


def test_savings_numbers_agree_after_guardian(monkeypatch):
    _run_guardian_and_claim_all(monkeypatch)
    s = c.get("/api/savings/B001").json()
    assert s["this_month"] <= s["total_saved"]
    assert round(sum(t["amount"] for t in s["trend"]), 2) <= s["total_saved"]
    assert sum(x["saved"] for x in s["analytics"]["spend_by_category"]) <= s["total_saved"] + 0.01
    assert 0 <= s["analytics"]["savings_rate_pct"] <= 100


def test_typical_price_is_per_product():
    laptop = c.post("/api/find-better-deal", json={"buyer_id": "B001", "product_name": "dell xps laptop",
                                                   "price": 1496, "category": "electronics"}).json()
    pods = c.post("/api/find-better-deal", json={"buyer_id": "B001", "product_name": "airpods pro",
                                                 "price": 295, "category": "electronics"}).json()
    assert laptop["network"]["median_price"] > 1000
    assert 150 < pods["network"]["median_price"] < 350
    assert laptop["network"]["overpaying"] is True


def test_order_uses_store_name_not_id():
    o = c.post("/api/orders", json=ORDER).json()
    assert m.STATE["orders"][o["order_id"]]["merchant_name"] == "StrideShop"
    log = c.get("/api/agent-pass/B001/actions").json()["actions"]
    assert log[0]["merchant_name"] == "StrideShop"


def test_order_rejects_unknown_buyer_and_goal():
    r = c.post("/api/orders", json={**ORDER, "buyer_id": "NOPE"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "NOT_FOUND"
    r = c.post("/api/orders", json={**ORDER, "goal_id": "G_nope"})
    assert r.status_code == 404


def test_dashboard_rows_carry_offer_id():
    row = c.get("/api/merchant/dashboard/M007").json()["churn_risk"][0]
    assert "offer_id" in row and row["offer_id"] is None
    off = c.post("/api/merchant/send-offer", json={"merchant_id": "M007", "customer_id": row["customer_id"]}).json()
    row2 = next(r for r in c.get("/api/merchant/dashboard/M007").json()["churn_risk"]
                if r["customer_id"] == row["customer_id"])
    assert row2["offer_id"] == off["offer_id"] and row2["offer_status"] == "sent"


def test_chat_rejects_empty_and_unknown_buyer():
    assert c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "   ", "session_id": None}).status_code == 400
    assert c.post("/api/agent/chat", json={"buyer_id": "NOPE", "message": "hi", "session_id": None}).status_code == 404


def test_chat_creates_one_goal_per_message():
    before = len(c.get("/api/save-for-it/goals/B001").json()["goals"])
    j = c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "save for a standing desk at $300",
                                        "session_id": None}).json()
    after = len(c.get("/api/save-for-it/goals/B001").json()["goals"])
    assert after == before + 1
    assert sum(1 for t in j["tool_calls"] if t["tool"] == "create_savings_goal") == 1


def test_chat_order_card_has_paypal_mode():
    j = c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "running insoles for $24",
                                        "session_id": None}).json()
    cards = [x for x in j["cards"] if x["type"] == "order"]
    assert cards and cards[0]["data"]["paypal_mode"] == "simulated"


# ---- credential / config validation (no network: PAYPAL_MODE is off in conftest unless changed)

def _cfg(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return config_check.run()


def test_config_ok_when_off(monkeypatch):
    r = _cfg(monkeypatch, PAYPAL_MODE="off", LLM_MODE="off")
    assert r["paypal"].startswith("off") and r["gemini"].startswith("off")


def test_config_flags_missing_and_placeholder_keys(monkeypatch):
    r = _cfg(monkeypatch, PAYPAL_MODE="sandbox", PAYPAL_CLIENT_ID="", PAYPAL_SECRET="your_secret",
             LLM_MODE="on", GEMINI_API_KEY="<key>")
    assert r["paypal"].startswith("error") and "PAYPAL_CLIENT_ID is missing" in r["paypal"]
    assert "PAYPAL_SECRET is missing" in r["paypal"]
    assert r["gemini"].startswith("error")


def test_config_flags_same_id_and_secret(monkeypatch):
    k = "A" * 40
    r = _cfg(monkeypatch, PAYPAL_MODE="sandbox", PAYPAL_CLIENT_ID=k, PAYPAL_SECRET=k, LLM_MODE="off")
    assert "same value" in r["paypal"]


def test_config_bad_paypal_keys_reported_not_crashing(monkeypatch):
    from services import paypal_client as pp

    def boom():
        raise pp.PayPalError(401, "AUTH_FAILED", "PayPal rejected the Client ID / Secret")
    monkeypatch.setattr(pp, "get_access_token", boom)
    r = _cfg(monkeypatch, PAYPAL_MODE="sandbox", PAYPAL_CLIENT_ID="A" * 40, PAYPAL_SECRET="B" * 40, LLM_MODE="off")
    assert r["paypal"].startswith("error") and "rejected" in r["paypal"]


def test_config_warns_on_whitespace_and_cors_mismatch(monkeypatch):
    r = _cfg(monkeypatch, PAYPAL_MODE="off", LLM_MODE="on", GEMINI_API_KEY="  " + "k" * 39 + " ",
             FRONTEND_URL="https://app.example.com", CORS_ORIGINS="http://localhost:5173")
    assert r["gemini"].startswith("ok")
    assert any("spaces or quotes" in w for w in r["warnings"])
    assert any("not in CORS_ORIGINS" in w for w in r["warnings"])
    r = _cfg(monkeypatch, FRONTEND_URL="https://app.example.com", CORS_ORIGINS="https://app.example.com/")
    assert not any("CORS" in w for w in r["warnings"])


def test_paypal_network_failure_is_502_not_500(monkeypatch):
    import requests
    from services import paypal_client as pp

    def down(*a, **k):
        raise requests.ConnectionError("no network")
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "A" * 40)
    monkeypatch.setenv("PAYPAL_SECRET", "B" * 40)
    monkeypatch.setattr(pp, "_token", {"value": None, "expires_at": 0.0})
    monkeypatch.setattr(requests, "request", down)
    r = c.post("/api/orders", json=ORDER)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "PAYPAL_ERROR"


def test_health_shows_config_without_secrets(monkeypatch):
    _cfg(monkeypatch, PAYPAL_MODE="off", LLM_MODE="off", GEMINI_API_KEY="SECRET_VALUE_123456789012345678901")
    j = c.get("/health").json()
    assert "config" in j and "SECRET_VALUE" not in str(j)
