# API Contract — PayPal Shopping Agent

> **Status: DRAFT v0.1** — proposed by backend (Koushik), needs review from frontend (Hetav).
> Once agreed, backend serves these exact paths and shapes. Any change after that gets announced in Teams first.

## Conventions

| Item | Rule |
|---|---|
| Base URL (local) | `http://localhost:8000` |
| Base URL (deployed) | Render URL, TBD |
| Interactive docs | `http://localhost:8000/docs` |
| Format | JSON in, JSON out |
| Money | Number, USD, 2 decimals (`129.99`) |
| Dates | ISO 8601 strings (`"2026-11-09"` or `"2026-11-09T14:30:00Z"`) |
| IDs | Strings (`"B001"`, `"M001"`, `"G_7f3a"`) |
| Demo users | Buyer `B001`, Merchant `M001` |
| Empty data | Lists come back as `[]` with a `message` string for the empty state, never `null` |

All numbers in the examples below are **examples only**. Real responses are computed from the data.

### Errors

Every error uses FastAPI's shape:

```json
{ "detail": { "code": "NOT_FOUND", "message": "Goal G_999 not found" } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Missing or invalid field |
| 403 | `AGENT_PASS_BLOCKED` | Agent Pass rules block the action (includes `reason`) |
| 404 | `NOT_FOUND` | Unknown buyer / goal / order / alert |
| 409 | `NEEDS_CONFIRMATION` | Agent Pass needs the user to confirm; resend with `"confirmed": true` |
| 502 | `PAYPAL_ERROR` | PayPal Sandbox call failed |

Agent Pass 403 example:

```json
{
  "detail": {
    "code": "AGENT_PASS_BLOCKED",
    "decision": "BLOCK",
    "reason": "Category 'gambling' is blocked in your Agent Pass rules"
  }
}
```

---

## 0. Health

### `GET /health`

```json
{ "status": "ok", "service": "paypal-shopping-agent", "paypal_env": "sandbox",
  "paypal_configured": true, "gemini_configured": true }
```

---

## 1. Savings Dashboard (home screen)

### `GET /api/savings/{buyer_id}`

```json
{
  "buyer_id": "B001",
  "total_saved": 847.32,
  "this_month": 64.10,
  "breakdown": {
    "price_drop": 312.40,
    "overcharge": 188.92,
    "better_deal": 236.00,
    "save_for_it": 110.00
  },
  "trend": [
    { "month": "2026-06", "amount": 92.10 },
    { "month": "2026-07", "amount": 140.55 },
    { "month": "2026-08", "amount": 201.30 },
    { "month": "2026-09", "amount": 168.07 },
    { "month": "2026-10", "amount": 181.20 },
    { "month": "2026-11", "amount": 64.10 }
  ],
  "recent_actions": [
    {
      "action_id": "A_102",
      "type": "price_drop",
      "title": "Price drop refund from TechHaven",
      "amount": 18.00,
      "status": "recovered",
      "timestamp": "2026-11-08T16:02:00Z"
    }
  ],
  "analytics": {
    "spend_this_month": 1240.75,
    "spend_by_category": [
      { "category": "electronics", "amount": 612.40, "saved": 58.99 },
      { "category": "home", "amount": 310.15, "saved": 18.00 }
    ],
    "purchases_watched": 42,
    "active_alerts": 2,
    "top_merchant": { "merchant_name": "TechHaven", "amount": 409.00 },
    "savings_rate_pct": 5.2
  }
}
```

`type` is one of `price_drop | overcharge | better_deal | save_for_it`.
`status` is one of `detected | resolved | recovered`.
`analytics` powers the "why you open PayPal daily" section: `purchases_watched` = purchases the Guardian is monitoring, `savings_rate_pct` = `this_month / spend_this_month × 100`.

---

## 2. Flow A — Better Deal Before You Pay

### `POST /api/find-better-deal`

Request:

```json
{
  "buyer_id": "B001",
  "product_name": "Sony WH-1000XM5 Headphones",
  "price": 349.99,
  "category": "electronics",
  "merchant_id": "M014"
}
```

`merchant_id` is optional.

Response:

```json
{
  "your_pick": {
    "product_name": "Sony WH-1000XM5 Headphones",
    "price": 349.99,
    "merchant_id": "M014",
    "merchant_name": "GadgetGrove"
  },
  "network": {
    "median_price": 318.50,
    "percentile": 82,
    "overpaying": true
  },
  "alternatives": [
    {
      "product_id": "P_0231",
      "product_name": "Sony WH-1000XM5 Headphones",
      "price": 309.00,
      "merchant_id": "M007",
      "merchant_name": "TechHaven",
      "dispute_rate": 0.012,
      "on_time_rate": 0.96,
      "savings": 40.99
    }
  ],
  "best_option": "P_0231",
  "potential_savings": 40.99,
  "agent_pass": {
    "decision": "APPROVE",
    "reason": "Within your $400 auto-approve limit"
  },
  "agent_message": "You're paying more than 82% of PayPal shoppers for these. TechHaven has the same model for $309 with a 1.2% dispute rate. Want me to switch?"
}
```

- `percentile`: where your price sits in the network (0–100). `overpaying` is true when above the 65th percentile.
- `alternatives`: up to 3, sorted cheapest first, only low-dispute merchants. Empty `[]` plus `"message"` when you already have the best price.
- `agent_pass.decision`: `APPROVE | NEEDS_CONFIRMATION | BLOCK` for buying the best option.
- `agent_message`: written by Gemini, or a template if Gemini is unavailable.

To buy the better option, call `POST /api/orders` (section 5) with `"source": "better_deal"`.

---

## 3. Flow B — Save For It

Goal `status` values:

| status | Meaning |
|---|---|
| `saving` | Still saving toward the goal |
| `deal_found` | Price hit an all-time low before savings finished: offer Pay in 4 / Pay Monthly |
| `ready` | `saved_so_far >= current_price` |
| `purchased` | Bought |

### `POST /api/save-for-it/create`

Request:

```json
{
  "buyer_id": "B001",
  "product_name": "Bose QuietComfort Ultra",
  "product_id": "P_0410",
  "category": "electronics",
  "target_price": 429.00,
  "weekly_amount": 25.00
}
```

`product_id` is optional. Response is the full goal (same shape as `status` below), `status: "saving"`.

### `GET /api/save-for-it/status/{goal_id}`

```json
{
  "goal_id": "G_7f3a",
  "buyer_id": "B001",
  "product_name": "Bose QuietComfort Ultra",
  "category": "electronics",
  "target_price": 429.00,
  "current_price": 349.00,
  "all_time_low": 349.00,
  "weekly_amount": 25.00,
  "saved_so_far": 150.00,
  "progress_pct": 43,
  "weeks_remaining": 8,
  "status": "deal_found",
  "price_history": [
    { "date": "2026-10-01", "price": 429.00 },
    { "date": "2026-10-15", "price": 399.00 },
    { "date": "2026-11-08", "price": 349.00 }
  ],
  "financing_options": [
    {
      "type": "pay_in_4",
      "label": "Pay in 4",
      "installments": 4,
      "installment_amount": 87.25,
      "frequency": "every 2 weeks",
      "interest": 0
    },
    {
      "type": "pay_monthly_6",
      "label": "Pay Monthly",
      "installments": 6,
      "installment_amount": 58.17,
      "frequency": "monthly",
      "interest": 0
    }
  ],
  "credit_card_offer": {
    "label": "PayPal credit card",
    "cashback_pct": 3,
    "estimated_cashback": 10.47,
    "note": "Cashback rate to be verified against current card terms"
  },
  "agent_message": "Your Bose headphones just hit their lowest price ever ($349, down $80). Instead of waiting 8 more weeks, you could get them now with Pay in 4: $87.25 every 2 weeks."
}
```

- `progress_pct` = `saved_so_far / current_price` (capped at 100).
- `financing_options` and `credit_card_offer` are `[]` / `null` unless `status` is `deal_found` or `ready`.
- `price_history` drives the sparkline.
- Pay Later and credit card are **simulated** in Sandbox (we calculate the plan and tag the order).

### `GET /api/save-for-it/goals/{buyer_id}`

```json
{ "goals": [ { "...": "same shape as status above" } ] }
```

### `POST /api/save-for-it/purchase/{goal_id}`

Request:

```json
{ "payment_option": "pay_in_4", "confirmed": false }
```

`payment_option`: `pay_now | pay_in_4 | pay_monthly_6`.
Runs Agent Pass first. Response is the same as `POST /api/orders` (section 5), and the goal becomes `purchased`.

---

## 4. Agent Pass (spending rules)

Every order and every claim goes through Agent Pass first.

### `GET /api/agent-pass/{buyer_id}`

```json
{
  "buyer_id": "B001",
  "autonomous_enabled": true,
  "auto_approve_limit": 100.00,
  "max_daily_spend": 300.00,
  "monthly_limit": 1000.00,
  "blocked_categories": ["gambling"],
  "approved_merchants": ["M007", "M012"],
  "spent_today": 45.00,
  "spent_this_month": 412.50
}
```

### `PUT /api/agent-pass/{buyer_id}`

Request: any subset of the editable fields (`autonomous_enabled`, `auto_approve_limit` 0–200, `max_daily_spend`, `monthly_limit`, `blocked_categories`, `approved_merchants`).
Response: full rules object, same shape as GET.

### `POST /api/agent-pass/check`

Request:

```json
{
  "buyer_id": "B001",
  "amount": 309.00,
  "category": "electronics",
  "merchant_id": "M007",
  "action": "purchase"
}
```

`action`: `purchase | claim`. Response:

```json
{
  "decision": "NEEDS_CONFIRMATION",
  "reason": "$309.00 is above your $100.00 auto-approve limit",
  "remaining_today": 255.00,
  "remaining_this_month": 587.50
}
```

Decision logic (in order):
1. Category blocked → `BLOCK`
2. Would exceed daily or monthly limit → `BLOCK`
3. Autonomous purchases off, or amount above auto-approve limit, or merchant not approved → `NEEDS_CONFIRMATION`
4. Otherwise → `APPROVE`

This endpoint always returns **200** (it's a preview). The 403 / 409 errors happen on the real actions (orders, purchase, claim).

### `GET /api/agent-pass/{buyer_id}/actions`

Recent agent actions log for the settings screen.

```json
{
  "actions": [
    {
      "action_id": "AP_55",
      "action": "purchase",
      "amount": 309.00,
      "category": "electronics",
      "merchant_name": "TechHaven",
      "decision": "NEEDS_CONFIRMATION",
      "reason": "$309.00 is above your $100.00 auto-approve limit",
      "timestamp": "2026-11-09T10:12:00Z"
    }
  ]
}
```

---

## 5. Orders (PayPal Sandbox)

### `POST /api/orders`

Request:

```json
{
  "buyer_id": "B001",
  "product_id": "P_0231",
  "product_name": "Sony WH-1000XM5 Headphones",
  "merchant_id": "M007",
  "category": "electronics",
  "amount": 309.00,
  "original_price": 349.99,
  "payment_option": "pay_now",
  "source": "better_deal",
  "confirmed": false
}
```

- `payment_option`: `pay_now | pay_in_4 | pay_monthly_6`
- `source`: `better_deal | save_for_it | direct`
- `original_price` is optional; when set, `original_price - amount` counts as a `better_deal` saving after capture.
- `confirmed`: set `true` after the user taps "Confirm" on a `NEEDS_CONFIRMATION` response.

Response `201`:

```json
{
  "order_id": "5O190127TN364715T",
  "status": "CREATED",
  "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=5O190127TN364715T",
  "amount": 309.00,
  "payment_option": "pay_now",
  "installment_plan": null,
  "agent_pass": { "decision": "APPROVE", "reason": "User confirmed" }
}
```

For `pay_in_4` / `pay_monthly_6`, `installment_plan` is filled:

```json
"installment_plan": {
  "installments": 4,
  "installment_amount": 77.25,
  "frequency": "every 2 weeks",
  "schedule": ["2026-11-09", "2026-11-23", "2026-12-07", "2026-12-21"]
}
```

Errors: `403 AGENT_PASS_BLOCKED`, `409 NEEDS_CONFIRMATION`, `502 PAYPAL_ERROR`.

**Frontend flow:** open `approve_url` (new tab or popup) → user logs in with the **sandbox buyer** account and approves → call capture.

### `POST /api/orders/{order_id}/capture`

No body. Response:

```json
{
  "order_id": "5O190127TN364715T",
  "status": "COMPLETED",
  "capture_id": "3C679366HH908993F",
  "amount": 309.00,
  "saved": 40.99,
  "message": "+$40.99 saved!"
}
```

`saved` drives the "+$X saved!" animation (0 if no saving). Error `409` with code `NOT_APPROVED` if the buyer hasn't approved in PayPal yet.

### `GET /api/orders/{order_id}`

```json
{ "order_id": "5O190127TN364715T", "status": "APPROVED", "amount": 309.00, "payment_option": "pay_now" }
```

`status`: `CREATED | APPROVED | COMPLETED`.

---

## 6. Flow C — Post-Purchase Guardian

Alert `type` values: `price_drop` and `overcharge` (must-have); `late_refund` and `delivery_delay` (stretch).
Alert `status`: `detected → resolved (claim filed) → recovered (money back)`.

Detection is **rules on the data**, not ML:
- `price_drop`: merchant dropped the price within 7 days of purchase → recoverable = paid − new price
- `overcharge`: amount charged > listed price by more than 5% (tax buffer) → recoverable = charged − listed price
- `late_refund`: refund requested, not received after 7+ days

### `POST /api/post-purchase/scan/{buyer_id}`

Starts the scan in the background. Response `202`:

```json
{ "scan_id": "S_1a2b", "status": "running" }
```

### `GET /api/post-purchase/results/{buyer_id}`

Poll every 3 seconds until `scan_status` is `complete`.

```json
{
  "scan_status": "complete",
  "checks": {
    "price_drop": "complete",
    "overcharge": "complete",
    "late_refund": "complete",
    "delivery_delay": "skipped"
  },
  "alerts": [
    {
      "alert_id": "AL_301",
      "type": "price_drop",
      "title": "Price dropped on your Instant Pot",
      "details": "You paid $99.00 on Nov 2. HomeNest dropped it to $81.00 on Nov 6.",
      "transaction_id": "T_08812",
      "merchant_id": "M021",
      "merchant_name": "HomeNest",
      "product_name": "Instant Pot Duo 7-in-1",
      "purchase_date": "2026-11-02",
      "amount_paid": 99.00,
      "reference_price": 81.00,
      "recoverable_amount": 18.00,
      "status": "detected",
      "detected_at": "2026-11-09T10:15:00Z"
    },
    {
      "alert_id": "AL_302",
      "type": "overcharge",
      "title": "Overcharged by StyleLoop",
      "details": "Listed at $60.00, you were charged $72.40 (20.7% over).",
      "transaction_id": "T_09107",
      "merchant_id": "M033",
      "merchant_name": "StyleLoop",
      "product_name": "Denim Jacket",
      "purchase_date": "2026-10-28",
      "amount_paid": 72.40,
      "reference_price": 60.00,
      "recoverable_amount": 12.40,
      "status": "detected",
      "detected_at": "2026-11-09T10:15:01Z"
    }
  ],
  "total_recoverable": 30.40,
  "total_recovered": 0.00,
  "message": null
}
```

`scan_status`: `idle | running | complete`. Alerts appear as each check finishes, so the feed can fill in live. When nothing is found: `"alerts": []` with a `message`.

### `POST /api/post-purchase/claim/{alert_id}`

Request:

```json
{ "confirmed": false }
```

Runs Agent Pass (`action: "claim"`), then files the refund/dispute in Sandbox. Response:

```json
{
  "alert_id": "AL_301",
  "claim_id": "C_4410",
  "status": "resolved",
  "paypal_reference": "8MC585209K746392H",
  "recoverable_amount": 18.00,
  "message": "Refund request for $18.00 filed with HomeNest. We'll track it until it lands."
}
```

When the sandbox refund completes, the alert's `status` becomes `recovered` and the amount is added to `/api/savings`.

---

## 7. Merchant Side ("For Your Business")

### `GET /api/merchant/dashboard/{merchant_id}`

```json
{
  "merchant_id": "M001",
  "merchant_name": "TechHaven",
  "summary": {
    "at_risk_customers": 37,
    "recoverable_revenue": 12480.00,
    "offers_sent": 5
  },
  "churn_risk": [
    {
      "customer_id": "B214",
      "customer_name": "Jordan Lee",
      "churn_probability": 0.87,
      "risk_tier": "high",
      "days_since_purchase": 74,
      "total_spend": 1240.50,
      "order_count": 9,
      "last_category": "electronics"
    }
  ],
  "cross_sell": [
    {
      "product_a": "Laptops",
      "product_b": "Laptop Bags",
      "co_purchase_rate": 0.34,
      "suggested_bundle_discount_pct": 10
    }
  ],
  "model_info": {
    "churn_model": "random_forest",
    "auc": 0.74,
    "note": "Metrics on synthetic data"
  }
}
```

- `churn_risk`: sorted by `churn_probability` descending. `risk_tier`: `high (>= 0.7) | medium (0.4–0.7) | low (< 0.4)`.
- `cross_sell` is a stretch goal and may be `[]`.
- `recoverable_revenue`: sum of yearly spend of at-risk customers.

### `POST /api/merchant/send-offer`

Request:

```json
{ "merchant_id": "M001", "customer_id": "B214", "discount_pct": 15 }
```

`discount_pct` is optional (backend picks one from the risk tier).

Response:

```json
{
  "offer_id": "O_9001",
  "customer_id": "B214",
  "customer_name": "Jordan Lee",
  "discount_pct": 15,
  "message": "Hi Jordan, we miss you at TechHaven! Here's 15% off your next electronics order, valid for 14 days.",
  "message_source": "gemini",
  "invoice_id": "INV2-ABCD-1234-EFGH-5678",
  "invoice_status": "SENT",
  "sent_at": "2026-11-09T11:00:00Z"
}
```

- `message_source`: `gemini | template` (template when Gemini is down).
- `invoice_id` / `invoice_status` come from PayPal Sandbox Invoicing. If invoicing fails, `invoice_status: "FAILED"` and the offer is still recorded.

### `POST /api/merchant/offer-outcome/{offer_id}` — customer returns loop

Records what happened to an offer, so every interaction becomes training data for the next churn model run.

Request:

```json
{ "outcome": "redeemed", "order_amount": 189.00 }
```

`outcome`: `redeemed | opened | ignored`. `order_amount` only for `redeemed`.

Response:

```json
{
  "offer_id": "O_9001",
  "outcome": "redeemed",
  "revenue_won_back": 189.00,
  "feedback_rows_logged": 128,
  "message": "Outcome logged. It will be used when the churn model is retrained."
}
```

The merchant dashboard `summary` also gets these fields from the logged outcomes:

```json
"offers_redeemed": 2,
"win_back_rate_pct": 40,
"revenue_won_back": 342.00
```

For the demo, the outcome can be triggered with a "Simulate customer response" button. The retrain itself is a script Amrutha runs (`feedback_rows_logged` shows how much new data is waiting).

---

## Endpoint summary

| Method | Path | Screen |
|---|---|---|
| GET | `/health` | — |
| GET | `/api/savings/{buyer_id}` | Savings dashboard |
| POST | `/api/find-better-deal` | Flow A |
| POST | `/api/save-for-it/create` | Flow B |
| GET | `/api/save-for-it/status/{goal_id}` | Flow B |
| GET | `/api/save-for-it/goals/{buyer_id}` | Flow B |
| POST | `/api/save-for-it/purchase/{goal_id}` | Flow B |
| GET | `/api/agent-pass/{buyer_id}` | Agent Pass settings |
| PUT | `/api/agent-pass/{buyer_id}` | Agent Pass settings |
| POST | `/api/agent-pass/check` | Flow A / B / C indicator |
| GET | `/api/agent-pass/{buyer_id}/actions` | Agent Pass settings |
| POST | `/api/orders` | Flow A / B |
| POST | `/api/orders/{order_id}/capture` | Flow A / B |
| GET | `/api/orders/{order_id}` | Flow A / B |
| POST | `/api/post-purchase/scan/{buyer_id}` | Flow C |
| GET | `/api/post-purchase/results/{buyer_id}` | Flow C |
| POST | `/api/post-purchase/claim/{alert_id}` | Flow C |
| GET | `/api/merchant/dashboard/{merchant_id}` | Merchant dashboard |
| POST | `/api/merchant/send-offer` | Merchant dashboard |
| POST | `/api/merchant/offer-outcome/{offer_id}` | Merchant dashboard (returns loop) |

## Open questions for review

1. **Hetav:** does every screen have what it needs? Anything missing or named awkwardly?
2. **Hetav:** OK with opening `approve_url` in a popup/new tab for PayPal approval, then calling capture?
3. **Amrutha:** churn output columns: can you produce `customer_id, churn_probability, days_since_purchase, total_spend, order_count`? Do transactions have `listed_price` vs `amount_charged` and a price-change date for the rules?
4. **Team:** confirm the PayPal credit card cashback % before it goes in the demo.
5. **Amrutha:** delivery delay is in our pitch but marked stretch here. Will the delay model be ready? If yes, `delivery_delay` alerts become must-have with fields `delay_probability`, `risk_level`, `promised_date`.
6. **Team:** "Customer returns loop" is planned as outcome logging plus an offline retrain script (not live retraining). OK?
