"""AI agent chat (API.md section 8).

# MOCK: canned agent run for frontend development. Step 8+ replaces this with
Gemini function calling over the same tools.
"""
from fastapi import APIRouter

import mock_data as m
from schemas import AgentChat

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/chat")
def chat(body: AgentChat):
    session_id = body.session_id or m.new_id("CH_")
    order_id = m.paypal_like_id()
    return {  # MOCK
        "session_id": session_id,
        "reply": ("Found the same insoles for $18 at StrideShop (rated 9.1/10, 2-day delivery). "
                  "That's under your $50 auto-approve limit, so I've created the order: approve it in "
                  "PayPal and you'll save $6."),
        "reply_source": "template",
        "tool_calls": [
            {"tool": "find_better_deal", "summary": "Best option $18.00 at StrideShop (save $6.00)"},
            {"tool": "check_agent_pass", "summary": "APPROVE: under $50.00 auto-approve limit"},
            {"tool": "create_order", "summary": f"Sandbox order {order_id} created"},
        ],
        "cards": [
            {"type": "better_deal", "data": {
                "your_pick": {"product_name": "Running Insoles", "price": 24.00, "merchant_name": "FootFirst"},
                "best_option": {"product_name": "Running Insoles", "price": 18.00, "merchant_name": "StrideShop",
                                "rating": 9.1, "delivery_days": 2},
                "potential_savings": 6.00}},
            {"type": "order", "data": {
                "order_id": order_id, "status": "CREATED",
                "approve_url": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
                "amount": 18.00, "payment_option": "pay_now"}},
        ],
        "pending_confirmation": None,
    }
