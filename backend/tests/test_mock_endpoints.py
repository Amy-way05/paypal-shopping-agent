"""Smoke tests: every endpoint in API.md v0.2 responds with the contract shape.

Run from backend/:  python -m pytest -q
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mock_data as m  # noqa: E402
from main import app  # noqa: E402

c = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    m.reset_state()


def test_health():
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_savings_shape():
    j = c.get("/api/savings/B001").json()
    assert set(j["breakdown"]) == {"price_drop", "overcharge", "better_deal", "save_for_it"}
    assert round(sum(v["total"] for v in j["breakdown"].values()), 2) == j["total_saved"]
    assert {"trend", "recent_actions", "analytics", "this_month"} <= set(j)


def test_better_deal_insoles():
    j = c.post("/api/find-better-deal", json={"buyer_id": "B001", "product_name": "Running Insoles",
                                              "price": 24.00, "category": "sports"}).json()
    assert j["alternatives"][0]["price"] == 18.00
    assert j["potential_savings"] == 6.00
    assert j["agent_pass"]["decision"] == "APPROVE"
    assert {"rating", "delivery_days"} <= set(j["alternatives"][0])


def test_bad_request_is_400():
    r = c.post("/api/find-better-deal", json={"buyer_id": "B001", "price": -1, "category": "x"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_REQUEST"


# ---- Agent Pass demo story: $18 approve, laptop confirm, random $200 block ----

def check(amount, planned=False, category="electronics"):
    return c.post("/api/agent-pass/check", json={"buyer_id": "B001", "amount": amount,
                                                 "category": category, "planned": planned}).json()


def test_agent_pass_story():
    assert check(18)["decision"] == "APPROVE"
    assert check(1050, planned=True)["decision"] == "NEEDS_CONFIRMATION"
    assert check(200)["decision"] == "BLOCK"
    assert check(80)["decision"] == "NEEDS_CONFIRMATION"
    assert check(10, category="gambling")["decision"] == "BLOCK"


def test_agent_pass_get_put_actions():
    assert c.get("/api/agent-pass/B001").json()["auto_approve_limit"] == 50
    j = c.put("/api/agent-pass/B001", json={"auto_approve_limit": 100}).json()
    assert j["auto_approve_limit"] == 100 and j["max_unplanned_purchase"] == 150
    assert c.put("/api/agent-pass/B001", json={"auto_approve_limit": 500}).status_code == 400
    assert len(c.get("/api/agent-pass/B001/actions").json()["actions"]) >= 1


# ---- Orders ----

def order(amount, confirmed=False, **kw):
    body = {"buyer_id": "B001", "product_name": "Thing", "category": "electronics",
            "amount": amount, "confirmed": confirmed, **kw}
    return c.post("/api/orders", json=body)


def test_orders_flow():
    r = order(18, original_price=24, source="better_deal")
    assert r.status_code == 201
    oid = r.json()["order_id"]
    assert "sandbox.paypal.com" in r.json()["approve_url"]
    assert c.get(f"/api/orders/{oid}").json()["status"] == "CREATED"
    cap = c.post(f"/api/orders/{oid}/capture").json()
    assert cap["status"] == "COMPLETED" and cap["saved"] == 6.00
    assert c.get("/api/orders/NOPE").status_code == 404


def test_orders_agent_pass_gates():
    r = order(200)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "AGENT_PASS_BLOCKED"
    r = order(80)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NEEDS_CONFIRMATION"
    assert order(80, confirmed=True).status_code == 201


def test_pay_later_plan():
    j = order(100, confirmed=True, payment_option="pay_in_4").json()
    assert j["installment_plan"]["installments"] == 4
    assert j["installment_plan"]["installment_amount"] == 25.00


# ---- Save For It ----

def test_demo_goal_ready_and_purchase():
    g = c.get("/api/save-for-it/status/G_7f3a").json()
    assert g["status"] == "ready" and g["final_price"] == 1050.00 and g["savings_vs_target"] == 150.00
    assert g["financing_options"][0]["installment_amount"] == 262.50
    r = c.post("/api/save-for-it/purchase/G_7f3a", json={"payment_option": "pay_in_4"})
    assert r.status_code == 409
    r = c.post("/api/save-for-it/purchase/G_7f3a", json={"payment_option": "pay_in_4", "confirmed": True})
    assert r.status_code == 200
    c.post(f"/api/orders/{r.json()['order_id']}/capture")
    assert c.get("/api/save-for-it/status/G_7f3a").json()["status"] == "purchased"


def test_create_goal_and_simulate_week():
    g = c.post("/api/save-for-it/create", json={"buyer_id": "B001", "product_name": "Laptop",
                                                "category": "electronics", "target_price": 1200,
                                                "weekly_amount": 50}).json()
    assert g["status"] == "saving" and g["weeks_remaining"] == 24
    g2 = c.post(f"/api/save-for-it/simulate-week/{g['goal_id']}", json={"weeks": 2}).json()
    assert g2["saved_so_far"] == 100.00
    assert len(c.get("/api/save-for-it/goals/B001").json()["goals"]) == 2
    assert c.get("/api/save-for-it/status/G_nope").status_code == 404


# ---- Guardian ----

def test_guardian_scan_progress():
    assert c.get("/api/post-purchase/results/B001").json()["scan_status"] == "idle"
    assert c.post("/api/post-purchase/scan/B001").status_code == 202
    m.STATE["scans"]["B001"]["started_at"] -= 100  # fast-forward
    j = c.get("/api/post-purchase/results/B001").json()
    assert j["scan_status"] == "complete"
    assert {a["type"] for a in j["alerts"]} == {"price_drop", "overcharge", "delivery_delay", "late_refund"}
    assert j["total_recoverable"] == 66.99 and j["total_recovered"] == 27.00


def test_claim():
    c.put("/api/agent-pass/B001", json={"autonomous_claims": False})
    assert c.post("/api/post-purchase/claim/AL_301", json={}).status_code == 409
    j = c.post("/api/post-purchase/claim/AL_301", json={"confirmed": True}).json()
    assert j["status"] == "resolved" and j["recoverable_amount"] == 18.00
    assert c.post("/api/post-purchase/claim/AL_999", json={}).status_code == 404


# ---- Merchant ----

def test_merchant_flow():
    d = c.get("/api/merchant/dashboard/M001").json()
    probs = [r["churn_probability"] for r in d["churn_risk"]]
    assert probs == sorted(probs, reverse=True)
    o = c.post("/api/merchant/send-offer", json={"merchant_id": "M001", "customer_id": "B214"}).json()
    assert o["discount_pct"] == 20 and "Sarah" in o["message"]
    out = c.post(f"/api/merchant/offer-outcome/{o['offer_id']}",
                 json={"outcome": "redeemed", "order_amount": 189}).json()
    assert out["revenue_won_back"] == 189.00
    d = c.get("/api/merchant/dashboard/M001").json()
    assert next(r for r in d["churn_risk"] if r["customer_id"] == "B214")["offer_status"] == "redeemed"


# ---- Agent + demo ----

def test_agent_chat_and_reset():
    j = c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "insoles $24"}).json()
    assert j["session_id"] and len(j["tool_calls"]) == 3
    assert c.post("/api/demo/reset").json()["status"] == "reset"


def test_all_contract_paths_exist():
    paths = {p for p in app.openapi()["paths"]}
    expected = {
        "/health", "/api/savings/{buyer_id}", "/api/find-better-deal",
        "/api/save-for-it/create", "/api/save-for-it/status/{goal_id}", "/api/save-for-it/goals/{buyer_id}",
        "/api/save-for-it/purchase/{goal_id}", "/api/save-for-it/simulate-week/{goal_id}",
        "/api/agent-pass/{buyer_id}", "/api/agent-pass/check", "/api/agent-pass/{buyer_id}/actions",
        "/api/orders", "/api/orders/{order_id}/capture", "/api/orders/{order_id}",
        "/api/post-purchase/scan/{buyer_id}", "/api/post-purchase/results/{buyer_id}",
        "/api/post-purchase/claim/{alert_id}", "/api/merchant/dashboard/{merchant_id}",
        "/api/merchant/send-offer", "/api/merchant/offer-outcome/{offer_id}",
        "/api/agent/chat", "/api/demo/reset",
    }
    assert expected <= paths
