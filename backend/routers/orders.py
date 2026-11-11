"""Orders (API.md section 5).

# MOCK: orders are fake (no PayPal call yet). Step 5 swaps in services/paypal_client.py.
"""
from datetime import date, timedelta

from fastapi import APIRouter

import mock_data as m
from errors import api_error
from routers.agent_pass import enforce, record_spend
from schemas import OrderCreate

router = APIRouter(prefix="/api/orders", tags=["Orders"])

PLANS = {
    "pay_in_4": {"installments": 4, "frequency": "every 2 weeks", "step_days": 14},
    "pay_monthly_6": {"installments": 6, "frequency": "monthly", "step_days": 30},
}


def installment_plan(amount, payment_option):
    """Simulated Pay Later schedule (Sandbox can't run real Pay Later)."""
    plan = PLANS.get(payment_option)
    if not plan:
        return None
    today = date.today()
    return {
        "installments": plan["installments"],
        "installment_amount": round(amount / plan["installments"], 2),
        "frequency": plan["frequency"],
        "schedule": [(today + timedelta(days=i * plan["step_days"])).isoformat()
                     for i in range(plan["installments"])],
    }


def create_order_internal(body: OrderCreate, merchant_name=None):
    """Shared by POST /api/orders and Save For It purchase."""
    planned = body.source == "save_for_it"
    agent_pass = enforce(body.buyer_id, body.amount, body.category, body.merchant_id, merchant_name,
                         action="purchase", planned=planned, confirmed=body.confirmed)

    order_id = m.paypal_like_id()  # MOCK
    m.STATE["orders"][order_id] = {
        "order_id": order_id, "status": "CREATED", "buyer_id": body.buyer_id,
        "amount": round(body.amount, 2), "original_price": body.original_price,
        "payment_option": body.payment_option, "goal_id": body.goal_id,
    }
    return {
        "order_id": order_id,
        "status": "CREATED",
        "approve_url": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
        "amount": round(body.amount, 2),
        "payment_option": body.payment_option,
        "installment_plan": installment_plan(body.amount, body.payment_option),
        "agent_pass": agent_pass,
    }


def _get(order_id):
    order = m.STATE["orders"].get(order_id)
    if not order:
        raise api_error(404, "NOT_FOUND", f"Order {order_id} not found")
    return order


@router.post("", status_code=201)
def create_order(body: OrderCreate):
    return create_order_internal(body)


@router.post("/{order_id}/capture")
def capture_order(order_id: str):
    order = _get(order_id)
    if order["status"] != "COMPLETED":
        # MOCK: real version gets 409 NOT_APPROVED from PayPal if buyer hasn't approved yet.
        order["status"] = "COMPLETED"
        order["capture_id"] = m.paypal_like_id()
        record_spend(order["buyer_id"], order["amount"])
        goal = m.STATE["goals"].get(order.get("goal_id") or "")
        if goal:
            goal["purchased"] = True

    saved = 0.0
    if order.get("original_price"):
        saved = round(max(order["original_price"] - order["amount"], 0), 2)
    return {
        "order_id": order_id,
        "status": "COMPLETED",
        "capture_id": order["capture_id"],
        "amount": order["amount"],
        "saved": saved,
        "message": f"+${saved:,.2f} saved!" if saved else "Payment complete",
    }


@router.get("/{order_id}")
def get_order(order_id: str):
    o = _get(order_id)
    return {"order_id": o["order_id"], "status": o["status"], "amount": o["amount"],
            "payment_option": o["payment_option"]}
