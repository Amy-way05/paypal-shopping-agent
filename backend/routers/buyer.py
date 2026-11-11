"""Buyer side: savings report, better deal, Save For It, Post-Purchase Guardian
(API.md sections 1, 2, 3, 6)."""
import math
import time
from datetime import date

from fastapi import APIRouter

import mock_data as m
from errors import api_error
from routers.agent_pass import enforce, get_rules, run_check
from routers.orders import create_order_internal
from schemas import BetterDealRequest, ClaimRequest, GoalCreate, GoalPurchase, OrderCreate, SimulateWeek

router = APIRouter(prefix="/api", tags=["Buyer"])


# =============================================================== savings

@router.get("/savings/{buyer_id}")
def get_savings(buyer_id: str):
    return {"buyer_id": buyer_id, **m.clone(m.SAVINGS)}  # MOCK


# =========================================================== better deal

@router.post("/find-better-deal")
def find_better_deal(body: BetterDealRequest):
    # MOCK catalog: alternatives priced off the searched price.
    alts = []
    for a in m.ALT_MERCHANTS:
        price = round(body.price * a["price_factor"], 2)
        alts.append({
            "product_id": m.new_id("P_"), "product_name": body.product_name, "price": price,
            "merchant_id": a["merchant_id"], "merchant_name": a["merchant_name"],
            "rating": a["rating"], "delivery_days": a["delivery_days"],
            "dispute_rate": a["dispute_rate"], "on_time_rate": a["on_time_rate"],
            "savings": round(body.price - price, 2),
        })
    alts = sorted([a for a in alts if a["savings"] > 0], key=lambda a: a["price"])[:3]

    median = round(body.price * m.NETWORK_MEDIAN_FACTOR, 2)
    your_pick = {"product_name": body.product_name, "price": round(body.price, 2),
                 "merchant_name": body.merchant_name or body.merchant_id}
    network = {"median_price": median, "percentile": m.NETWORK_PERCENTILE,
               "overpaying": m.NETWORK_PERCENTILE > 65}

    if not alts:
        return {"your_pick": your_pick, "network": network, "alternatives": [], "best_option": None,
                "potential_savings": 0, "source": "local_catalog", "agent_pass": None,
                "agent_message": "You already have the best price we can find.",
                "message": "You already have the best price we can find."}

    best = alts[0]
    check = run_check(body.buyer_id, best["price"], body.category, best["merchant_id"])
    msg = (f"Same {body.product_name.lower()} for ${best['price']:,.2f} at {best['merchant_name']}: "
           f"rated {best['rating']}/10 with {best['delivery_days']}-day delivery. "
           f"That's ${best['savings']:,.2f} less.")  # template; Gemini in Step 8
    return {
        "your_pick": your_pick, "network": network, "alternatives": alts,
        "best_option": best["product_id"], "potential_savings": best["savings"],
        "source": "local_catalog",
        "agent_pass": {"decision": check["decision"], "reason": check["reason"]},
        "agent_message": msg,
    }


# =========================================================== save for it

def _financing(final_price):
    return [
        {"type": "pay_in_4", "label": "Pay in 4", "installments": 4,
         "installment_amount": round(final_price / 4, 2), "frequency": "every 2 weeks", "interest": 0},
        {"type": "pay_monthly_6", "label": "Pay Monthly", "installments": 6,
         "installment_amount": round(final_price / 6, 2), "frequency": "monthly", "interest": 0},
    ]


def goal_view(g):
    """Derive the computed fields of a goal (status, progress, financing...)."""
    coupon = g.get("best_coupon")
    final_price = round(g["current_price"] - (coupon["discount"] if coupon else 0), 2)
    saved = round(g["saved_so_far"], 2)
    remaining = max(final_price - saved, 0)

    if g.get("purchased"):
        status = "purchased"
    elif saved >= final_price:
        status = "ready"
    elif final_price <= g["all_time_low"] and final_price < g["target_price"]:
        status = "deal_found"
    else:
        status = "saving"

    vs_target = round(max(g["target_price"] - final_price, 0), 2)
    if status == "ready":
        msg = (f"Goal hit! Your {g['product_name']} is ${final_price:,.2f} today"
               + (f" with code {coupon['code']}" if coupon else "")
               + (f": ${vs_target:,.2f} under your target." if vs_target else ".") + " Buy now?")
    elif status == "deal_found":
        msg = (f"Your {g['product_name']} just hit its lowest price (${final_price:,.2f}). "
               f"Can't wait? Pay in 4: ${final_price / 4:,.2f} every 2 weeks.")
    elif status == "purchased":
        msg = f"Bought! Buyer Protection is on for your {g['product_name']}."
    else:
        msg = f"Saving ${g['weekly_amount']:,.2f} a week. I'm watching the price and coupons for you."

    return {
        "goal_id": g["goal_id"], "buyer_id": g["buyer_id"], "product_name": g["product_name"],
        "category": g["category"], "merchant_name": g.get("merchant_name"),
        "target_price": g["target_price"], "current_price": g["current_price"],
        "best_coupon": coupon, "final_price": final_price, "savings_vs_target": vs_target,
        "all_time_low": g["all_time_low"], "weekly_amount": g["weekly_amount"],
        "saved_so_far": saved,
        "progress_pct": min(100, int(saved / final_price * 100)) if final_price else 100,
        "weeks_remaining": math.ceil(remaining / g["weekly_amount"]) if remaining else 0,
        "status": status,
        "price_history": g["price_history"],
        "financing_options": [] if status == "purchased" else _financing(final_price),
        "credit_card_offer": None if status == "purchased" else {
            "label": "PayPal credit card", "cashback_pct": m.CREDIT_CARD_CASHBACK_PCT,
            "estimated_cashback": round(final_price * m.CREDIT_CARD_CASHBACK_PCT / 100, 2),
            "note": "Cashback rate to be verified against current card terms"},
        "agent_message": msg,
    }


def _goal(goal_id):
    g = m.STATE["goals"].get(goal_id)
    if not g:
        raise api_error(404, "NOT_FOUND", f"Goal {goal_id} not found")
    return g


@router.post("/save-for-it/create")
def create_goal(body: GoalCreate):
    goal_id = m.new_id("G_")
    m.STATE["goals"][goal_id] = {
        "goal_id": goal_id, "buyer_id": body.buyer_id, "product_name": body.product_name,
        "product_id": body.product_id, "category": body.category, "merchant_name": None,
        "target_price": round(body.target_price, 2), "current_price": round(body.target_price, 2),  # MOCK price
        "best_coupon": None, "all_time_low": round(body.target_price, 2),
        "weekly_amount": round(body.weekly_amount, 2), "saved_so_far": 0.0, "purchased": False,
        "price_history": [{"date": date.today().isoformat(), "price": round(body.target_price, 2)}],
    }
    return goal_view(m.STATE["goals"][goal_id])


@router.get("/save-for-it/status/{goal_id}")
def goal_status(goal_id: str):
    return goal_view(_goal(goal_id))


@router.get("/save-for-it/goals/{buyer_id}")
def list_goals(buyer_id: str):
    goals = [goal_view(g) for g in m.STATE["goals"].values() if g["buyer_id"] == buyer_id]
    if not goals:
        return {"goals": [], "message": "No goals yet. Tell the agent what you're saving for."}
    return {"goals": goals}


@router.post("/save-for-it/purchase/{goal_id}")
def purchase_goal(goal_id: str, body: GoalPurchase):
    g = _goal(goal_id)
    view = goal_view(g)
    if view["status"] == "purchased":
        raise api_error(400, "BAD_REQUEST", f"Goal {goal_id} is already purchased")
    order = OrderCreate(
        buyer_id=g["buyer_id"], product_id=g.get("product_id"), product_name=g["product_name"],
        category=g["category"], amount=view["final_price"], original_price=g["target_price"],
        payment_option=body.payment_option, source="save_for_it", goal_id=goal_id, confirmed=body.confirmed,
    )
    return create_order_internal(order, merchant_name=g.get("merchant_name"))


@router.post("/save-for-it/simulate-week/{goal_id}")
def simulate_week(goal_id: str, body: SimulateWeek = None):
    """Demo helper: move weekly savings in and re-check price (MOCK price stays the same)."""
    g = _goal(goal_id)
    weeks = body.weeks if body else 1
    if not g.get("purchased"):
        g["saved_so_far"] = round(g["saved_so_far"] + g["weekly_amount"] * weeks, 2)
    return goal_view(g)


# =============================================================== guardian
# MOCK: alerts appear over time after a scan so the frontend can build the
# polling feed + ticking counter. Real rules come in Step 7.

@router.post("/post-purchase/scan/{buyer_id}", status_code=202)
def start_scan(buyer_id: str):
    scan_id = m.new_id("S_")
    m.STATE["scans"][buyer_id] = {"scan_id": scan_id, "started_at": time.time()}
    return {"scan_id": scan_id, "status": "running"}


def _alert_status(item, elapsed, rules):
    a = item["alert"]
    if a["alert_id"] in m.STATE["claimed"] or rules["autonomous_claims"]:
        if item["recover_after"] is not None and elapsed >= item["recover_after"]:
            return "recovered"
        if a["alert_id"] in m.STATE["claimed"] or elapsed >= item["resolve_after"]:
            return "resolved"
    return "detected"


@router.get("/post-purchase/results/{buyer_id}")
def scan_results(buyer_id: str):
    scan = m.STATE["scans"].get(buyer_id)
    if not scan:
        return {"scan_status": "idle", "checks": {c: "pending" for c in m.GUARDIAN_CHECK_ORDER},
                "alerts": [], "total_recoverable": 0, "total_recovered": 0,
                "message": "Tap \"Scan my purchases\" and your agent will check everything you've bought."}

    rules = get_rules(buyer_id)
    elapsed = time.time() - scan["started_at"]
    alerts, checks = [], {}
    for item in m.GUARDIAN_ALERTS:
        a = m.clone(item["alert"])
        done = elapsed >= item["ready_after"]
        checks[a["type"]] = "complete" if done else "running"
        if not done:
            continue
        a["status"] = _alert_status(item, elapsed, rules)
        if a["status"] == "detected":
            a["action_taken"] = None
        a["detected_at"] = m.now_iso()
        alerts.append(a)

    complete = all(v == "complete" for v in checks.values())
    return {
        "scan_status": "complete" if complete else "running",
        "checks": checks,
        "alerts": alerts,
        "total_recoverable": round(sum(a["recoverable_amount"] for a in alerts), 2),
        "total_recovered": round(sum(a["recoverable_amount"] for a in alerts if a["status"] == "recovered"), 2),
        "message": None if alerts or not complete else "All clear. Nothing to recover right now.",
    }


@router.post("/post-purchase/claim/{alert_id}")
def claim(alert_id: str, body: ClaimRequest = None):
    item = next((i for i in m.GUARDIAN_ALERTS if i["alert"]["alert_id"] == alert_id), None)
    if not item:
        raise api_error(404, "NOT_FOUND", f"Alert {alert_id} not found")
    a = item["alert"]
    enforce(m.DEMO_BUYER, a["recoverable_amount"], a["type"], merchant_name=a["merchant_name"],
            action="claim", confirmed=bool(body and body.confirmed))
    m.STATE["claimed"].add(alert_id)
    amount = a["recoverable_amount"]
    return {
        "alert_id": alert_id,
        "status": "resolved",
        "action_taken": a["action_taken"],
        "paypal_reference": a["paypal_reference"],
        "recoverable_amount": amount,
        "message": (f"Request for ${amount:,.2f} filed with {a['merchant_name']}. We'll track it until it lands."
                    if amount else f"We've contacted {a['merchant_name']} about your order."),
    }
