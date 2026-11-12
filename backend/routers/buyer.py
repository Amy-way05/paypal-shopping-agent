"""Buyer side: savings report, better deal, Save For It, Post-Purchase Guardian
(API.md sections 1, 2, 3, 6). Data comes from Amrutha's models via
services/models_adapter.py; session activity comes from state.STATE."""
import math
import time
from datetime import date

from fastapi import APIRouter

import state as m
from errors import api_error
from routers.agent_pass import enforce, get_rules, get_spend, run_check
from routers.orders import create_order_internal
from schemas import BetterDealRequest, ClaimRequest, GoalCreate, GoalPurchase, OrderCreate, SimulateWeek
from services import models_adapter as data

router = APIRouter(prefix="/api", tags=["Buyer"])

SAVINGS_LABELS = {
    "price_drop": "Price drop recovered",
    "overcharge": "Overcharge caught",
    "better_deal": "Better deal found",
    "save_for_it": "Save For It discount",
}
# PayPal Cashback Mastercard: 3% back on PayPal purchases (verify current terms before quoting).
CREDIT_CARD_CASHBACK_PCT = 3


def _require_buyer(buyer_id):
    if not data.buyer_exists(buyer_id) and not any(e["buyer_id"] == buyer_id for e in m.STATE["events"]):
        raise api_error(404, "NOT_FOUND", f"Buyer {buyer_id} not found")


# =============================================================== savings

def _savings_events(buyer_id):
    """Everything the agent saved: dataset history + this session's events."""
    events = []
    for h in data.history(buyer_id):
        events.append({"action_id": f"A_{h['transaction_id'][2:]}", "type": h["type"], "title": h["title"],
                       "amount": h["amount"], "item": h["item"], "merchant_name": h["merchant_name"],
                       "status": "recovered", "date": h["date"], "timestamp": f"{h['date']}T12:00:00Z",
                       "category": h["category"]})
    for e in m.STATE["events"]:
        if e["buyer_id"] == buyer_id:
            events.append({**e, "date": e["timestamp"][:10]})
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events


def _month_key(d):
    return d[:7]


@router.get("/savings/{buyer_id}")
def get_savings(buyer_id: str):
    _require_buyer(buyer_id)
    events = _savings_events(buyer_id)
    month = date.today().strftime("%Y-%m")

    breakdown = {}
    for kind, label in SAVINGS_LABELS.items():
        ev = [e for e in events if e["type"] == kind]
        latest = ev[0] if ev else None
        breakdown[kind] = {
            "label": label, "total": round(sum(e["amount"] for e in ev), 2), "count": len(ev),
            "latest": {"item": latest["item"], "merchant_name": latest["merchant_name"],
                       "amount": latest["amount"], "date": latest["date"]} if latest else None,
        }
    total = round(sum(b["total"] for b in breakdown.values()), 2)
    # Only real savings count toward the numbers (a late refund coming back is the buyer's own money),
    # so total, this month, trend and per-category always agree.
    saved = [e for e in events if e["type"] in SAVINGS_LABELS]
    this_month = round(sum(e["amount"] for e in saved if _month_key(e["date"]) == month), 2)

    # last 6 months, zero-filled
    y, mo = date.today().year, date.today().month
    months = []
    for _ in range(6):
        months.insert(0, f"{y:04d}-{mo:02d}")
        y, mo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    trend = [{"month": k, "amount": round(sum(e["amount"] for e in saved if _month_key(e["date"]) == k), 2)}
             for k in months]

    spend = data.buyer_spend(buyer_id) if data.buyer_exists(buyer_id) else None
    spend_month = get_spend(buyer_id)["month"]
    saved_by_cat = {}
    for e in saved:
        if e.get("category"):
            saved_by_cat[e["category"]] = saved_by_cat.get(e["category"], 0) + e["amount"]
    alerts = data.active_alerts(buyer_id) if spend else []
    open_alerts = [a for a in alerts if a["alert_id"] not in m.STATE["claimed"]
                   and not any(e.get("alert_id") == a["alert_id"] for e in m.STATE["events"])]

    return {
        "buyer_id": buyer_id,
        "total_saved": total,
        "this_month": this_month,
        "breakdown": breakdown,
        "trend": trend,
        "recent_actions": [{k: e[k] for k in ("action_id", "type", "title", "amount", "status", "timestamp")}
                           for e in events[:10]],
        "analytics": {
            "spend_this_month": round(spend_month, 2),
            "spend_by_category": [{"category": c, "amount": a, "saved": round(saved_by_cat.get(c, 0), 2)}
                                  for c, a in (spend["by_category"].items() if spend else [])],
            "purchases_watched": data.purchases_watched(buyer_id) if spend else 0,
            "active_alerts": len(open_alerts),
            "top_merchant": spend["top_merchant"] if spend else None,
            "savings_rate_pct": min(round(this_month / spend_month * 100, 1), 100.0) if spend_month > 0 else 0,
        },
        "data_as_of": data.DATA_TODAY.isoformat(),
    }


# =========================================================== better deal

@router.post("/find-better-deal")
def find_better_deal(body: BetterDealRequest):
    merchant_id = body.merchant_id or data.merchant_id_by_name(body.merchant_name)
    res = data.better_deal(body.product_name, body.price, body.category, merchant_id)
    alts = [{**a, "savings": round(body.price - a["price"], 2)} for a in res["alternatives"]]

    your_merchant = (data.merchant(merchant_id) or {}).get("merchant_name") if merchant_id else None
    your_pick = {"product_name": body.product_name, "price": round(body.price, 2),
                 "merchant_name": body.merchant_name or your_merchant}
    base = {"your_pick": your_pick, "network": res["network"], "matched_product": res["matched_product"],
            "source": "local_catalog"}

    if not alts:
        msg = ("You already have the best price we can find." if res["matched_product"]
               else f"I couldn't find \"{body.product_name}\" at other stores in the catalog.")
        return {**base, "alternatives": [], "best_option": None, "potential_savings": 0,
                "agent_pass": None, "agent_message": msg, "message": msg}

    best = alts[0]
    check = run_check(body.buyer_id, best["price"], res["category"], best["merchant_id"])
    msg = (f"Same {best['product_name']} for ${best['price']:,.2f} at {best['merchant_name']}: "
           f"rated {best['rating']}/10 with {best['delivery_days']}-day delivery. "
           f"That's ${best['savings']:,.2f} less.")
    if check["decision"] == "APPROVE":
        msg += " It's within your Agent Pass limits, so I can buy it for you."
    return {**base, "alternatives": alts, "best_option": best["product_id"],
            "potential_savings": best["savings"],
            "agent_pass": {"decision": check["decision"], "reason": check["reason"]},
            "agent_message": msg}


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
        "price_source": g.get("price_source"),
        "financing_options": [] if status == "purchased" else _financing(final_price),
        "credit_card_offer": None if status == "purchased" else {
            "label": "PayPal credit card", "cashback_pct": CREDIT_CARD_CASHBACK_PCT,
            "estimated_cashback": round(final_price * CREDIT_CARD_CASHBACK_PCT / 100, 2),
            "note": "Cashback rate to be verified against current card terms"},
        "agent_message": msg,
    }


def _goal(goal_id):
    g = m.STATE["goals"].get(goal_id)
    if not g:
        raise api_error(404, "NOT_FOUND", f"Goal {goal_id} not found")
    return g


def create_goal_internal(buyer_id, product_name, category, target_price, weekly_amount, product_id=None):
    goal_id = m.new_id("G_")
    target = round(target_price, 2)
    name = data.resolve_product(product_name, data.normalize_category(category))
    listing = data.catalog_listing(name) if name else None
    if listing:
        coupon = data.best_coupon(listing["category"], listing["price"], listing["merchant_id"])
        g = {"product_name": listing["product_name"], "product_id": listing["product_id"],
             "category": listing["category"], "merchant_id": listing["merchant_id"],
             "merchant_name": listing["merchant_name"], "current_price": listing["price"],
             "all_time_low": listing["all_time_low"], "best_coupon": coupon, "price_source": "catalog",
             "price_history": listing["price_history"] or [{"date": date.today().isoformat(),
                                                             "price": listing["price"]}]}
    else:  # not in the catalog: track against the buyer's own target
        g = {"product_name": product_name, "product_id": product_id, "category": category,
             "merchant_id": None, "merchant_name": None, "current_price": target, "all_time_low": target,
             "best_coupon": None, "price_source": "your_target",
             "price_history": [{"date": date.today().isoformat(), "price": target}]}
    m.STATE["goals"][goal_id] = {**g, "goal_id": goal_id, "buyer_id": buyer_id, "target_price": target,
                                 "weekly_amount": round(weekly_amount, 2), "saved_so_far": 0.0,
                                 "purchased": False}
    return goal_view(m.STATE["goals"][goal_id])


@router.post("/save-for-it/create")
def create_goal(body: GoalCreate):
    return create_goal_internal(body.buyer_id, body.product_name, body.category, body.target_price,
                                body.weekly_amount, body.product_id)


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
        merchant_id=g.get("merchant_id"), category=g["category"], amount=view["final_price"],
        original_price=g["target_price"], payment_option=body.payment_option, source="save_for_it",
        goal_id=goal_id, confirmed=body.confirmed,
    )
    return create_order_internal(order, merchant_name=g.get("merchant_name"))


@router.post("/save-for-it/simulate-week/{goal_id}")
def simulate_week(goal_id: str, body: SimulateWeek = None):
    """Demo helper: move N weeks of auto-save into the goal."""
    g = _goal(goal_id)
    weeks = body.weeks if body else 1
    if not g.get("purchased"):
        g["saved_so_far"] = round(g["saved_so_far"] + g["weekly_amount"] * weeks, 2)
    return goal_view(g)


# =============================================================== guardian
# The four checks are rules over the buyer's purchases (data/). The scan
# reveals them one by one so the UI can animate; with autonomous claims on,
# the agent acts on each finding a moment later.

CHECK_ORDER = ["price_drop", "overcharge", "delivery_delay", "late_refund"]
READY_AFTER = {"price_drop": 1.5, "overcharge": 3.0, "delivery_delay": 4.5, "late_refund": 6.0}
RESOLVE_DELAY = 1.5   # seconds after a finding appears until the agent has acted
RECOVER_DELAY = 3.5   # seconds after acting until the (simulated) money lands


@router.post("/post-purchase/scan/{buyer_id}", status_code=202)
def start_scan(buyer_id: str):
    _require_buyer(buyer_id)
    scan_id = m.new_id("S_")
    m.STATE["scans"][buyer_id] = {"scan_id": scan_id, "started_at": time.time()}
    return {"scan_id": scan_id, "status": "running"}


def _alert_status(a, elapsed, rules, now):
    """detected -> resolved (agent acted) -> recovered (money back)."""
    claim = m.STATE["claimed"].get(a["alert_id"])
    acted_at = None
    if claim:
        acted_at = claim["at"]
    elif rules["autonomous_claims"]:
        acted_at = now - elapsed + READY_AFTER[a["type"]] + RESOLVE_DELAY
    if acted_at is None or now < acted_at:
        return "detected"
    if a["recoverable_amount"] and now >= acted_at + RECOVER_DELAY:
        return "recovered"
    return "resolved"


def _book_recovery(buyer_id, a):
    if any(e.get("alert_id") == a["alert_id"] for e in m.STATE["events"]):
        return
    if a["type"] not in ("price_drop", "overcharge", "late_refund"):
        return
    m.STATE["events"].append({
        "action_id": m.new_id("A_"), "buyer_id": buyer_id, "alert_id": a["alert_id"],
        # A recovered late refund is the buyer's own money: shown in the feed, not counted as savings.
        "type": a["type"] if a["type"] != "late_refund" else "refund_recovered",
        "title": a["title"], "amount": a["recoverable_amount"], "item": a["product_name"],
        "merchant_name": a["merchant_name"], "status": "recovered", "timestamp": m.now_iso(),
        "category": data.category_of(a["transaction_id"]),
    })


@router.get("/post-purchase/results/{buyer_id}")
def scan_results(buyer_id: str):
    scan = m.STATE["scans"].get(buyer_id)
    if not scan:
        return {"scan_status": "idle", "checks": {c: "pending" for c in CHECK_ORDER},
                "alerts": [], "total_recoverable": 0, "total_recovered": 0,
                "message": "Tap \"Scan my purchases\" and your agent will check everything you've bought."}

    rules = get_rules(buyer_id)
    now = time.time()
    elapsed = now - scan["started_at"]
    checks = {c: ("complete" if elapsed >= READY_AFTER[c] else "running") for c in CHECK_ORDER}
    alerts = []
    for a in data.active_alerts(buyer_id):
        if checks[a["type"]] != "complete":
            continue
        a = m.clone(a)
        a["status"] = _alert_status(a, elapsed, rules, now)
        claim = m.STATE["claimed"].get(a["alert_id"])
        if claim:
            a["paypal_reference"] = claim.get("paypal_reference")
        if a["status"] == "detected":
            a["action_taken"] = None
        if a["status"] == "recovered":
            _book_recovery(buyer_id, a)
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


def _find_alert(alert_id):
    for buyer_id in {m.DEMO_BUYER, *m.STATE["scans"].keys()}:
        for a in data.active_alerts(buyer_id):
            if a["alert_id"] == alert_id:
                return buyer_id, a
    return None, None


@router.post("/post-purchase/claim/{alert_id}")
def claim(alert_id: str, body: ClaimRequest = None):
    buyer_id, a = _find_alert(alert_id)
    if not a:
        raise api_error(404, "NOT_FOUND", f"Alert {alert_id} not found")
    enforce(buyer_id, a["recoverable_amount"], a["type"], a.get("merchant_id"), a["merchant_name"],
            action="claim", confirmed=bool(body and body.confirmed))
    m.STATE["claimed"].setdefault(alert_id, {"at": time.time(), "paypal_reference": None})
    m.STATE["scans"].setdefault(buyer_id, {"scan_id": m.new_id("S_"), "started_at": time.time() - 10})
    amount = a["recoverable_amount"]
    verb = data.ACTIONS[a["type"]][1].format(m=a["merchant_name"])
    return {
        "alert_id": alert_id,
        "status": "resolved",
        "action_taken": verb,
        "paypal_reference": None,
        "recovery_method": a["recovery_method"],
        "recoverable_amount": amount,
        "message": (f"{verb} ${amount:,.2f} on its way. We'll track it until it lands."
                    if amount else verb),
    }
