"""Merchant side (API.md section 7). # MOCK churn data until Amrutha's model output is wired."""
from fastapi import APIRouter

import mock_data as m
from errors import api_error
from schemas import OfferOutcome, SendOffer

router = APIRouter(prefix="/api/merchant", tags=["Merchant"])


def _customer(customer_id):
    return next((c for c in m.MERCHANT_DASHBOARD["churn_risk"] if c["customer_id"] == customer_id), None)


@router.get("/dashboard/{merchant_id}")
def dashboard(merchant_id: str):
    d = m.clone(m.MERCHANT_DASHBOARD)
    offers = [o for o in m.STATE["offers"].values() if o["merchant_id"] == merchant_id]
    status_by_customer = {o["customer_id"]: (o["outcome"] or "sent") for o in offers}
    for row in d["churn_risk"]:
        row["offer_status"] = status_by_customer.get(row["customer_id"])
    return {"merchant_id": merchant_id, **d}


@router.post("/send-offer")
def send_offer(body: SendOffer):
    c = _customer(body.customer_id)
    if not c:
        raise api_error(404, "NOT_FOUND", f"Customer {body.customer_id} not found")
    discount = body.discount_pct or m.TIER_DISCOUNT[c["risk_tier"]]
    first = c["customer_name"].split()[0]
    merchant_name = m.MERCHANT_DASHBOARD["merchant_name"]
    offer_id = m.new_id("O_")
    m.STATE["offers"][offer_id] = {"offer_id": offer_id, "merchant_id": body.merchant_id,
                                   "customer_id": c["customer_id"], "customer_name": c["customer_name"],
                                   "outcome": None}
    return {
        "offer_id": offer_id,
        "customer_id": c["customer_id"],
        "customer_name": c["customer_name"],
        "discount_pct": discount,
        "message": (f"{discount}% off your next order, {first}! We miss you at {merchant_name}. "
                    f"Valid for 14 days."),  # template; Gemini in Step 8
        "message_source": "template",
        "invoice_id": "INV2-" + m.paypal_like_id()[:16],  # MOCK: PayPal Invoicing in a later step
        "invoice_status": "SENT",
        "sent_at": m.now_iso(),
    }


@router.post("/offer-outcome/{offer_id}")
def offer_outcome(offer_id: str, body: OfferOutcome):
    offer = m.STATE["offers"].get(offer_id)
    if not offer:
        raise api_error(404, "NOT_FOUND", f"Offer {offer_id} not found")
    offer["outcome"] = body.outcome
    m.STATE["feedback_rows"] += 1
    won = round(body.order_amount or 0, 2) if body.outcome == "redeemed" else 0
    return {
        "offer_id": offer_id,
        "outcome": body.outcome,
        "revenue_won_back": won,
        "feedback_rows_logged": m.STATE["feedback_rows"],
        "message": "Outcome logged. It will be used when the churn model is retrained.",
    }
