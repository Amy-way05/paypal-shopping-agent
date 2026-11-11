"""Orders (API.md section 5): real PayPal Sandbox orders.

Flow: POST /api/orders (Agent Pass gate -> PayPal create) -> buyer opens
approve_url and logs in with a SANDBOX personal account -> POST /capture.
With PAYPAL_MODE=off (tests / no keys) orders are simulated and say so.
"""
import os
from datetime import date, timedelta

from fastapi import APIRouter

import state as m
from errors import api_error
from routers.agent_pass import enforce, record_spend
from schemas import OrderCreate
from services import paypal_client as pp

router = APIRouter(prefix="/api/orders", tags=["Orders"])

PLANS = {
    "pay_in_4": {"installments": 4, "frequency": "every 2 weeks", "step_days": 14},
    "pay_monthly_6": {"installments": 6, "frequency": "monthly", "step_days": 30},
}


def installment_plan(amount, payment_option):
    """Pay Later schedule. Sandbox can't run real Pay Later, so the plan is
    computed here and attached to a normal PayPal order."""
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


def _paypal_error(e):
    return api_error(502, "PAYPAL_ERROR", f"PayPal: {e.message}", paypal_issue=e.name, debug_id=e.debug_id)


def create_order_internal(body: OrderCreate, merchant_name=None):
    """Shared by POST /api/orders, Save For It purchase and the agent chat."""
    planned = body.source == "save_for_it"
    agent_pass = enforce(body.buyer_id, body.amount, body.category, body.merchant_id, merchant_name,
                         action="purchase", planned=planned, confirmed=body.confirmed)

    amount = round(body.amount, 2)
    if pp.enabled():
        frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        tag = f" ({body.payment_option})" if body.payment_option != "pay_now" else ""
        try:
            order_id, status, approve_url = pp.create_order(
                amount, f"{body.product_name}{tag}", custom_id=f"{body.buyer_id}:{body.source}",
                return_url=f"{frontend}/checkout/return", cancel_url=f"{frontend}/checkout/cancel")
        except pp.PayPalError as e:
            raise _paypal_error(e)
        paypal_mode = "sandbox"
    else:
        order_id, status, paypal_mode = m.sim_id(), "CREATED", "simulated"
        approve_url = f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"

    m.STATE["orders"][order_id] = {
        "order_id": order_id, "status": status, "buyer_id": body.buyer_id, "amount": amount,
        "original_price": body.original_price, "payment_option": body.payment_option,
        "goal_id": body.goal_id, "source": body.source, "product_name": body.product_name,
        "merchant_name": merchant_name or body.merchant_id, "category": body.category,
        "paypal_mode": paypal_mode, "capture_id": None,
    }
    return {
        "order_id": order_id,
        "status": status,
        "approve_url": approve_url,
        "amount": amount,
        "payment_option": body.payment_option,
        "installment_plan": installment_plan(amount, body.payment_option),
        "agent_pass": agent_pass,
        "paypal_mode": paypal_mode,
    }


def _get(order_id):
    order = m.STATE["orders"].get(order_id)
    if not order:
        raise api_error(404, "NOT_FOUND", f"Order {order_id} not found")
    return order


def _record_savings(order, saved):
    goal = m.STATE["goals"].get(order.get("goal_id") or "")
    if goal:
        goal["purchased"] = True
    if saved <= 0 or order["source"] not in ("better_deal", "save_for_it", "agent"):
        return
    kind = "save_for_it" if order["source"] == "save_for_it" else "better_deal"
    title = (f"{order['product_name']} bought ${saved:,.2f} under target" if kind == "save_for_it"
             else f"Better deal on {order['product_name']}" +
             (f" at {order['merchant_name']}" if order.get("merchant_name") else ""))
    m.STATE["events"].append({
        "action_id": m.new_id("A_"), "buyer_id": order["buyer_id"], "type": kind, "title": title,
        "amount": saved, "item": order["product_name"], "merchant_name": order.get("merchant_name"),
        "status": "recovered", "timestamp": m.now_iso(), "order_id": order["order_id"],
    })


@router.post("", status_code=201)
def create_order(body: OrderCreate):
    return create_order_internal(body)


@router.post("/{order_id}/capture")
def capture_order(order_id: str):
    order = _get(order_id)
    if order["status"] != "COMPLETED":
        if order["paypal_mode"] == "sandbox":
            try:
                status, capture_id = pp.capture_order(order_id)
            except pp.PayPalError as e:
                if e.name == "ORDER_NOT_APPROVED":
                    raise api_error(409, "NOT_APPROVED",
                                    "The buyer hasn't approved this order in PayPal yet. Open approve_url first.")
                if e.name != "ORDER_ALREADY_CAPTURED":
                    raise _paypal_error(e)
                status, capture_id = "COMPLETED", None
        else:
            status, capture_id = "COMPLETED", m.sim_id()
        order.update(status=status, capture_id=capture_id)
        saved = round(max((order.get("original_price") or 0) - order["amount"], 0), 2)
        order["saved"] = saved
        record_spend(order["buyer_id"], order["amount"])
        _record_savings(order, saved)

    saved = order.get("saved", 0.0)
    return {
        "order_id": order_id,
        "status": order["status"],
        "capture_id": order["capture_id"],
        "amount": order["amount"],
        "saved": saved,
        "message": f"+${saved:,.2f} saved!" if saved else "Payment complete",
        "paypal_mode": order["paypal_mode"],
    }


@router.get("/{order_id}")
def get_order(order_id: str):
    o = _get(order_id)
    return {"order_id": o["order_id"], "status": o["status"], "amount": o["amount"],
            "payment_option": o["payment_option"], "paypal_mode": o["paypal_mode"]}
