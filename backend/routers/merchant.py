"""Merchant side (API.md section 7): churn risk from Amrutha's model, AI win-back
message (Gemini, template fallback), offer delivered as a PayPal Sandbox invoice."""
from fastapi import APIRouter

import state as m
from errors import api_error
from schemas import OfferOutcome, SendOffer
from services import llm
from services import models_adapter as data
from services import paypal_client as pp

router = APIRouter(prefix="/api/merchant", tags=["Merchant"])

TIER_DISCOUNT = {"high": 20, "medium": 15, "low": 10}  # win-back policy: bigger risk, bigger offer
DASHBOARD_ROWS = 25


def _merchant(merchant_id):
    info = data.merchant(merchant_id)
    if not info:
        raise api_error(404, "NOT_FOUND", f"Merchant {merchant_id} not found")
    return info


def _customer(merchant_id, customer_id):
    return next((c for c in data.churn(merchant_id) if c["customer_id"] == customer_id), None)


@router.get("/dashboard/{merchant_id}")
def dashboard(merchant_id: str):
    info = _merchant(merchant_id)
    rows = data.churn(merchant_id)
    at_risk = [r for r in rows if r["risk_tier"] in ("high", "medium")]
    offers = [o for o in m.STATE["offers"].values() if o["merchant_id"] == merchant_id]
    status_by_customer = {o["customer_id"]: (o["outcome"] or "sent") for o in offers}
    offer_id_by_customer = {o["customer_id"]: o["offer_id"] for o in offers}
    redeemed = [o for o in offers if o["outcome"] == "redeemed"]
    churn_rows = [{**{k: r[k] for k in ("customer_id", "customer_name", "churn_probability", "risk_tier",
                                         "days_since_purchase", "total_spend", "order_count",
                                         "last_category", "avg_order_value")},
                   "offer_status": status_by_customer.get(r["customer_id"]),
                   "offer_id": offer_id_by_customer.get(r["customer_id"])}
                  for r in rows[:DASHBOARD_ROWS]]
    met = data.metrics().get("churn_predictor", {})
    return {
        "merchant_id": merchant_id,
        "merchant_name": info["merchant_name"],
        "summary": {
            "at_risk_customers": len(at_risk),
            "recoverable_revenue": round(sum(r["avg_order_value"] for r in at_risk), 2),
            "offers_sent": len(offers),
            "offers_redeemed": len(redeemed),
            "win_back_rate_pct": round(len(redeemed) / len(offers) * 100) if offers else 0,
            "revenue_won_back": round(sum(o.get("order_amount") or 0 for o in redeemed), 2),
        },
        "churn_risk": churn_rows,
        "cross_sell": [{k: r[k] for k in ("product_a", "product_b", "co_purchase_rate", "pair_count",
                                          "suggested_bundle_discount_pct")}
                       for r in data.cross_sell(merchant_id)[:5]],
        "model_info": {"churn_model": met.get("model", "GradientBoostingClassifier"),
                       "auc": met.get("auc"), "precision": met.get("precision"),
                       "recall": met.get("recall"), "note": met.get("note", "Metrics on synthetic data")},
    }


@router.post("/send-offer")
def send_offer(body: SendOffer):
    info = _merchant(body.merchant_id)
    c = _customer(body.merchant_id, body.customer_id)
    if not c:
        raise api_error(404, "NOT_FOUND", f"Customer {body.customer_id} not found for {body.merchant_id}")
    discount = body.discount_pct or TIER_DISCOUNT[c["risk_tier"]]
    first = c["customer_name"].split()[0]
    category = c["last_category"].replace("_", " ")
    template = (f"{discount}% off your next order, {first}! We miss you at {info['merchant_name']}. "
                f"Valid for 14 days.")
    message, source = llm.generate(
        f"Write a warm 2-sentence win-back message from the store {info['merchant_name']} to a customer "
        f"named {first}. They last bought {category} {c['days_since_purchase']} days ago and have placed "
        f"{c['order_count']} orders. Offer exactly {discount}% off their next order, valid 14 days. "
        f"No emojis, no subject line, no placeholders.",
        fallback=template, max_tokens=120)

    invoice_id, invoice_status, invoice_error = None, "SIMULATED", None
    if pp.enabled():
        try:
            invoice_id, invoice_status = pp.send_offer_invoice(
                f"{c['customer_id'].lower()}@example.com", c["customer_name"],
                f"{info['merchant_name']}: your next {category} order", c["avg_order_value"], discount, message)
        except pp.PayPalError as e:
            invoice_error = f"{e.name}: {e.message}"

    offer_id = m.new_id("O_")
    m.STATE["offers"][offer_id] = {"offer_id": offer_id, "merchant_id": body.merchant_id,
                                   "customer_id": c["customer_id"], "customer_name": c["customer_name"],
                                   "discount_pct": discount, "outcome": None, "order_amount": None}
    return {
        "offer_id": offer_id,
        "customer_id": c["customer_id"],
        "customer_name": c["customer_name"],
        "discount_pct": discount,
        "message": message,
        "message_source": source,
        "invoice_id": invoice_id,
        "invoice_status": invoice_status,
        "invoice_error": invoice_error,
        "sent_at": m.now_iso(),
    }


@router.post("/offer-outcome/{offer_id}")
def offer_outcome(offer_id: str, body: OfferOutcome):
    offer = m.STATE["offers"].get(offer_id)
    if not offer:
        raise api_error(404, "NOT_FOUND", f"Offer {offer_id} not found")
    offer["outcome"] = body.outcome
    won = round(body.order_amount or 0, 2) if body.outcome == "redeemed" else 0
    offer["order_amount"] = won
    logged = sum(1 for o in m.STATE["offers"].values() if o["outcome"])
    return {
        "offer_id": offer_id,
        "outcome": body.outcome,
        "revenue_won_back": won,
        "feedback_rows_logged": logged,
        "message": "Outcome logged. It will be used when the churn model is retrained.",
    }
