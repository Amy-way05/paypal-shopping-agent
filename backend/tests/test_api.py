"""API tests: every endpoint in API.md responds with the contract shape, and
numbers trace back to data/ (Amrutha's models) or session activity.

Run from backend/:  python -m pytest -q
"""
import pytest
from fastapi.testclient import TestClient

import state as m
from main import app
from services import models_adapter as data

data.ensure_ready()
c = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    m.reset_state()


def test_health():
    j = c.get("/health").json()
    assert j["status"] == "ok" and j["paypal_env"] == "sandbox"


# ---- savings ----

def test_savings_from_data():
    j = c.get("/api/savings/B001").json()
    assert set(j["breakdown"]) == {"price_drop", "overcharge", "better_deal", "save_for_it"}
    assert round(sum(v["total"] for v in j["breakdown"].values()), 2) == j["total_saved"]
    hist = data.history("B001")
    assert j["total_saved"] == round(sum(h["amount"] for h in hist), 2)
    assert {"trend", "recent_actions", "analytics", "this_month"} <= set(j)
    assert j["analytics"]["top_merchant"]["merchant_name"] == "TechHaven"


def test_unknown_buyer_404():
    assert c.get("/api/savings/0011").status_code == 404


# ---- better deal ----

def test_better_deal_same_product():
    j = c.post("/api/find-better-deal", json={"buyer_id": "B001", "product_name": "sony headphones",
                                              "price": 349.99, "category": "electronics",
                                              "merchant_id": "M007"}).json()
    assert j["matched_product"] == "Sony WH-1000XM5 Headphones"
    assert j["alternatives"] and all(a["product_name"] == j["matched_product"] for a in j["alternatives"])
    assert all(a["merchant_id"] != "M007" for a in j["alternatives"])
    best = j["alternatives"][0]
    assert j["potential_savings"] == round(349.99 - best["price"], 2)
    assert {"rating", "delivery_days"} <= set(best)


def test_better_deal_not_in_catalog():
    j = c.post("/api/find-better-deal", json={"buyer_id": "B001", "product_name": "Quantum Toaster",
                                              "price": 50, "category": "home"}).json()
    assert j["alternatives"] == [] and j["best_option"] is None


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


def test_monthly_spend_comes_from_data():
    j = c.get("/api/agent-pass/B001").json()
    assert j["spent_this_month"] == data.buyer_spend("B001")["this_month"]


def test_agent_pass_get_put_actions():
    assert c.get("/api/agent-pass/B001").json()["auto_approve_limit"] == 50
    j = c.put("/api/agent-pass/B001", json={"auto_approve_limit": 100}).json()
    assert j["auto_approve_limit"] == 100 and j["max_unplanned_purchase"] == 150
    assert c.put("/api/agent-pass/B001", json={"auto_approve_limit": 500}).status_code == 400
    order(18)
    assert len(c.get("/api/agent-pass/B001/actions").json()["actions"]) >= 1


# ---- Orders ----

def order(amount, confirmed=False, **kw):
    body = {"buyer_id": "B001", "product_name": "Thing", "category": "electronics",
            "amount": amount, "confirmed": confirmed, **kw}
    return c.post("/api/orders", json=body)


def test_orders_flow_and_savings_event():
    r = order(18, original_price=24, source="better_deal")
    assert r.status_code == 201 and r.json()["paypal_mode"] == "simulated"
    oid = r.json()["order_id"]
    assert c.get(f"/api/orders/{oid}").json()["status"] == "CREATED"
    cap = c.post(f"/api/orders/{oid}/capture").json()
    assert cap["status"] == "COMPLETED" and cap["saved"] == 6.00
    s = c.get("/api/savings/B001").json()
    assert s["breakdown"]["better_deal"]["total"] == 6.00
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
    assert c.get("/api/savings/B001").json()["breakdown"]["save_for_it"]["total"] == 150.00


def test_create_goal_custom_and_catalog():
    g = c.post("/api/save-for-it/create", json={"buyer_id": "B001", "product_name": "Mystery Gadget",
                                                "category": "electronics", "target_price": 1200,
                                                "weekly_amount": 50}).json()
    assert g["status"] == "saving" and g["weeks_remaining"] == 24 and g["price_source"] == "your_target"
    g2 = c.post(f"/api/save-for-it/simulate-week/{g['goal_id']}", json={"weeks": 2}).json()
    assert g2["saved_so_far"] == 100.00
    v = c.post("/api/save-for-it/create", json={"buyer_id": "B001", "product_name": "dyson vacuum",
                                                "category": "home", "target_price": 400,
                                                "weekly_amount": 25}).json()
    listing = data.catalog_listing("Dyson V8 Vacuum")
    assert v["price_source"] == "catalog" and v["current_price"] == listing["price"]
    assert len(c.get("/api/save-for-it/goals/B001").json()["goals"]) == 3
    assert c.get("/api/save-for-it/status/G_nope").status_code == 404


# ---- Guardian ----

def test_guardian_scan_progress():
    assert c.get("/api/post-purchase/results/B001").json()["scan_status"] == "idle"
    before = c.get("/api/savings/B001").json()["total_saved"]
    assert c.post("/api/post-purchase/scan/B001").status_code == 202
    m.STATE["scans"]["B001"]["started_at"] -= 100  # fast-forward
    j = c.get("/api/post-purchase/results/B001").json()
    assert j["scan_status"] == "complete"
    expected = data.active_alerts("B001")
    assert len(j["alerts"]) == len(expected)
    assert {a["type"] for a in j["alerts"]} == {"price_drop", "overcharge", "delivery_delay", "late_refund"}
    assert j["total_recoverable"] == round(sum(a["recoverable_amount"] for a in expected), 2)
    assert all(a["status"] == "recovered" for a in j["alerts"] if a["recoverable_amount"])
    # recovered price drops + overcharges count as savings; refunds (own money) don't
    gained = sum(a["recoverable_amount"] for a in expected if a["type"] in ("price_drop", "overcharge"))
    assert c.get("/api/savings/B001").json()["total_saved"] == round(before + gained, 2)


def test_claim():
    alert = data.active_alerts("B001")[0]
    c.put("/api/agent-pass/B001", json={"autonomous_claims": False})
    assert c.post(f"/api/post-purchase/claim/{alert['alert_id']}", json={}).status_code == 409
    j = c.post(f"/api/post-purchase/claim/{alert['alert_id']}", json={"confirmed": True}).json()
    assert j["status"] == "resolved" and j["recoverable_amount"] == alert["recoverable_amount"]
    assert c.post("/api/post-purchase/claim/AL_999", json={}).status_code == 404


# ---- Merchant ----

def test_merchant_flow():
    d = c.get("/api/merchant/dashboard/M007").json()
    assert d["merchant_name"] == "TechHaven"
    probs = [r["churn_probability"] for r in d["churn_risk"]]
    assert probs and probs == sorted(probs, reverse=True)
    top = d["churn_risk"][0]
    o = c.post("/api/merchant/send-offer", json={"merchant_id": "M007", "customer_id": top["customer_id"]}).json()
    assert o["discount_pct"] == {"high": 20, "medium": 15, "low": 10}[top["risk_tier"]]
    assert top["customer_name"].split()[0] in o["message"] and o["invoice_status"] == "SIMULATED"
    out = c.post(f"/api/merchant/offer-outcome/{o['offer_id']}",
                 json={"outcome": "redeemed", "order_amount": 189}).json()
    assert out["revenue_won_back"] == 189.00
    d = c.get("/api/merchant/dashboard/M007").json()
    assert d["summary"]["revenue_won_back"] == 189.00
    assert next(r for r in d["churn_risk"] if r["customer_id"] == top["customer_id"])["offer_status"] == "redeemed"
    assert c.get("/api/merchant/dashboard/M999").status_code == 404


# ---- Agent (template fallback, LLM off) + demo ----

def test_agent_chat_fallback():
    j = c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "instant pot for $120"}).json()
    assert j["session_id"] and j["reply_source"] == "template"
    assert j["tool_calls"][0]["tool"] == "find_better_deal"
    assert j["pending_confirmation"] or any(card["type"] == "order" for card in j["cards"])
    j = c.post("/api/agent/chat", json={"buyer_id": "B001", "message": "how much have I saved?"}).json()
    assert "$" in j["reply"]


def test_reset():
    assert c.post("/api/demo/reset").json() == {"status": "reset", "buyer_id": "B001", "merchant_id": "M007"}


def test_all_contract_paths_exist():
    paths = set(app.openapi()["paths"])
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
