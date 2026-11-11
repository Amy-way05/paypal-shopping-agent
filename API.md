# API Contract — PayPal Shopping Agent

> **Status: v0.3 (LIVE)**: every endpoint below is real. Data comes from Amrutha's models (synthetic dataset in `data/`), payments go through PayPal **Sandbox**, messages come from Gemini with a template fallback.
> Any change gets announced in Teams first.

## What changed in v0.3 (vs v0.2): additive only, no field removed or renamed

1. **Demo merchant is now `M007` (TechHaven)**, matching `data/merchants.csv`. `M001` is "Northside Electronics". `POST /api/demo/reset` returns `merchant_id: "M007"`.
2. **No more mock numbers.** Savings, better deal, Guardian alerts, churn and cross-sell are computed from `data/` via `backend/services/models_adapter.py`. Example values below are illustrative; the real ones differ.
3. **Orders are real PayPal Sandbox orders.** The buyer must open `approve_url` and log in with a **sandbox personal account** before `capture`; capturing earlier returns **409 `NOT_APPROVED`**. New field `paypal_mode`: `"sandbox"` or `"simulated"` (simulated only when PayPal is switched off).
4. **Better deal = same product, other stores.** Free text is matched to the catalog (`"sony headphones"` → `"Sony WH-1000XM5 Headphones"`); new field `matched_product` (`null` if the item isn't in the catalog → `alternatives: []` + `message`). `rating` is a 0–10 trust score computed from the merchant's on-time and dispute rates.
5. **Savings:** total = price drops + overcharges + better deals + Save For It. **Late refunds are not counted as savings** (it's the buyer's own money); when recovered they show in `recent_actions` with type `refund_recovered`. New field `data_as_of`. Unknown buyer → **404**.
6. **Guardian:** alert IDs look like `AL_00002P`. Alerts can include `merchant_id`, and delivery alerts can include `delay_probability` (from the ML delay model). `recovery_method` is `"simulated"` for purchases in the synthetic history (they have no real PayPal capture to refund).
7. **Save For It:** new field `price_source`: `"catalog"` (priced from `products.json` + best merchant coupon), `"your_target"` (not in catalog), or `"demo_seed"` (the demo laptop goal `G_7f3a`).
8. **Merchant:** churn rows add `avg_order_value`; cross-sell rows add `pair_count`. `send-offer` adds `invoice_error`; `invoice_id` is `null` and `invoice_status: "SIMULATED"` until Invoicing is enabled on the PayPal app. `message_source` is the Gemini model name or `"template"`. Unknown merchant/customer → 404.
9. **Agent chat:** `reply_source` is the Gemini model used, or `"template"` when Gemini is unavailable. `pending_confirmation` = `{tool, reason, args}`. To confirm, `POST /api/orders` with `args` (already has `confirmed: true`).

## What changed in v0.2 (vs v0.1)

Aligned to the final "How the AI shopping agent works" diagram:

1. **Guardian: all 4 checks are core** (price drop, overcharge, delivery watch, refund tracker), all plain rules. The scan now **acts automatically** (files claims / contacts merchant) when Agent Pass allows it.
2. **Agent Pass:** default auto-approve is **$50**; new `max_unplanned_purchase` (**$150**) so a random $200 item is **BLOCKED**; Save For It purchases are "planned" and always ask "Buy now?"; new `autonomous_claims` toggle.
3. **Better Deal:** alternatives now include `rating` (0–10) and `delivery_days`.
4. **Save For It:** coupons (`best_coupon`, `final_price`); Pay Later shown any time ("Can't wait?"), not only on a deal; new demo helper to simulate a week of saving.
5. **Savings report:** each breakdown card has `total`, `count`, and `latest` (item, merchant, date).
6. **New `POST /api/agent/chat`:** Gemini picks and calls the tools (better deal, Agent Pass, orders, goals, scan) itself.
7. **New `POST /api/demo/reset`:** puts demo data back to the starting state so the demo is repeatable.

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
| Demo users | Buyer `B001`, Merchant `M007` TechHaven (no login) |
| Empty data | Lists come back as `[]` with a `message` string for the empty state, never `null` |

All numbers in the examples are **examples only**. Real responses are computed from the data.

### Errors

Every error uses FastAPI's shape:

```json
{ "detail": { "code": "NOT_FOUND", "message": "Goal G_999 not found" } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Missing or invalid field |
| 403 | `AGENT_PASS_BLOCKED` | Agent Pass rules block the action (includes `decision` and `reason`) |
| 404 | `NOT_FOUND` | Unknown buyer / goal / order / alert / offer |
| 409 | `NEEDS_CONFIRMATION` | Agent Pass needs the user to confirm; resend with `"confirmed": true` |
| 409 | `NOT_APPROVED` | Capture called before the buyer approved in PayPal |
| 502 | `PAYPAL_ERROR` | PayPal Sandbox call failed |

Agent Pass 403 example:

```json
{
  "detail": {
    "code": "AGENT_PASS_BLOCKED",
    "decision": "BLOCK",
    "reason": "$200.00 unplanned purchase is over your $150.00 limit"
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

## 1. Savings Report (home screen)

"The reason you open PayPal every day." The total only goes up.

### `GET /api/savings/{buyer_id}`

```json
{
  "buyer_id": "B001",
  "total_saved": 847.00,
  "this_month": 165.00,
  "breakdown": {
    "price_drop": {
      "label": "Price drop recovered",
      "total": 312.40,
      "count": 11,
      "latest": { "item": "Headphones", "merchant_name": "SoundLab", "amount": 18.00, "date": "2026-10-29" }
    },
    "overcharge": {
      "label": "Overcharge caught",
      "total": 188.60,
      "count": 9,
      "latest": { "item": "Online order", "merchant_name": "ShopRight", "amount": 9.00, "date": "2026-11-02" }
    },
    "better_deal": {
      "label": "Better deal found",
      "total": 196.00,
      "count": 23,
      "latest": { "item": "Insoles", "merchant_name": "StrideShop", "amount": 6.00, "date": "2026-11-05" }
    },
    "save_for_it": {
      "label": "Save For It discount",
      "total": 150.00,
      "count": 1,
      "latest": { "item": "Laptop", "merchant_name": "TechHaven", "amount": 150.00, "date": "2026-11-04" }
    }
  },
  "trend": [
    { "month": "2026-06", "amount": 92.10 },
    { "month": "2026-07", "amount": 140.55 },
    { "month": "2026-08", "amount": 201.30 },
    { "month": "2026-09", "amount": 118.05 },
    { "month": "2026-10", "amount": 130.00 },
    { "month": "2026-11", "amount": 165.00 }
  ],
  "recent_actions": [
    {
      "action_id": "A_102",
      "type": "price_drop",
      "title": "Auto price-match from SoundLab",
      "amount": 18.00,
      "status": "recovered",
      "timestamp": "2026-10-29T16:02:00Z"
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
    "savings_rate_pct": 13.3
  }
}
```

- `breakdown` keys are always these four. A card with no savings yet has `total: 0`, `count: 0`, `latest: null`.
- `latest.amount` is the most recent single saving of that type; `total` is all-time. Frontend chooses which to show big on the card.
- `this_month` = sum of savings dated in the current month.
- `recent_actions[].type`: `price_drop | overcharge | better_deal | save_for_it | delivery | refund`. `status`: `detected | resolved | recovered`.
- `analytics.savings_rate_pct` = `this_month / spend_this_month × 100`. `purchases_watched` = purchases the Guardian is monitoring.

---

## 2. Flow A — Better Deal Before You Pay

"PayPal isn't predicting what you need. It's making sure you never overpay for what you already decided to buy."

### `POST /api/find-better-deal`

Request:

```json
{
  "buyer_id": "B001",
  "product_name": "Running Insoles",
  "price": 24.00,
  "category": "sports",
  "merchant_name": "FootFirst"
}
```

`merchant_name` (or `merchant_id`) is optional.

Response:

```json
{
  "your_pick": {
    "product_name": "Running Insoles",
    "price": 24.00,
    "merchant_name": "FootFirst"
  },
  "network": {
    "median_price": 19.50,
    "percentile": 88,
    "overpaying": true
  },
  "alternatives": [
    {
      "product_id": "P_0231",
      "product_name": "Running Insoles",
      "price": 18.00,
      "merchant_id": "M007",
      "merchant_name": "StrideShop",
      "rating": 9.1,
      "delivery_days": 2,
      "dispute_rate": 0.012,
      "on_time_rate": 0.96,
      "savings": 6.00
    }
  ],
  "best_option": "P_0231",
  "potential_savings": 6.00,
  "source": "local_catalog",
  "agent_pass": {
    "decision": "APPROVE",
    "reason": "$18.00 is under your $50.00 auto-approve limit"
  },
  "agent_message": "Same insoles for $18 at StrideShop: rated 9.1/10 with 2-day delivery. That's $6 less than FootFirst."
}
```

- `percentile`: where your price sits in the network (0–100). `overpaying` is true above the 65th percentile.
- `alternatives`: up to 3, cheapest first, only low-dispute merchants. `rating` is 0–10. Empty `[]` plus `"message"` when you already have the best price.
- `source`: `channel3 | local_catalog`.
- `agent_pass`: decision for buying `best_option` (see section 4).
- `agent_message`: Gemini, or a template if Gemini is unavailable.

To buy it: `POST /api/orders` with `"source": "better_deal"` and `"original_price": 24.00`.

---

## 3. Flow B — Save For It

"I want this $1,200 laptop." Auto-save weekly, watch the price + coupons, buy at the perfect moment.

Goal `status`:

| status | Meaning |
|---|---|
| `saving` | Still saving |
| `deal_found` | Price hit its all-time low before savings finished (good moment for Pay Later) |
| `ready` | `saved_so_far >= final_price`: agent asks "Buy now?" |
| `purchased` | Bought |

Pay Later options are always included ("Can't wait?"), calculated on the current `final_price`.

### `POST /api/save-for-it/create`

Request:

```json
{
  "buyer_id": "B001",
  "product_name": "Dell XPS 14 Laptop",
  "product_id": "P_0410",
  "category": "electronics",
  "target_price": 1200.00,
  "weekly_amount": 50.00
}
```

`product_id` optional. Response: the full goal (same shape as status), `status: "saving"`.

### `GET /api/save-for-it/status/{goal_id}`

```json
{
  "goal_id": "G_7f3a",
  "buyer_id": "B001",
  "product_name": "Dell XPS 14 Laptop",
  "category": "electronics",
  "merchant_name": "TechHaven",
  "target_price": 1200.00,
  "current_price": 1070.00,
  "best_coupon": { "code": "TECH20", "description": "$20 off laptops", "discount": 20.00 },
  "final_price": 1050.00,
  "savings_vs_target": 150.00,
  "all_time_low": 1050.00,
  "weekly_amount": 50.00,
  "saved_so_far": 1050.00,
  "progress_pct": 100,
  "weeks_remaining": 0,
  "status": "ready",
  "price_history": [
    { "date": "2026-07-01", "price": 1200.00 },
    { "date": "2026-09-15", "price": 1149.00 },
    { "date": "2026-11-04", "price": 1070.00 }
  ],
  "financing_options": [
    {
      "type": "pay_in_4",
      "label": "Pay in 4",
      "installments": 4,
      "installment_amount": 262.50,
      "frequency": "every 2 weeks",
      "interest": 0
    },
    {
      "type": "pay_monthly_6",
      "label": "Pay Monthly",
      "installments": 6,
      "installment_amount": 175.00,
      "frequency": "monthly",
      "interest": 0
    }
  ],
  "credit_card_offer": {
    "label": "PayPal credit card",
    "cashback_pct": 3,
    "estimated_cashback": 31.50,
    "note": "Cashback rate to be verified against current card terms"
  },
  "agent_message": "Goal hit! Your laptop is $1,050 today with code TECH20: $150 under your target. Buy now?"
}
```

- `final_price` = `current_price − best_coupon.discount`. `best_coupon` is `null` if none applies. Coupons come from `coupons.json` ("Honey-style", simulated).
- `savings_vs_target` = `target_price − final_price` (counts as `save_for_it` savings after purchase).
- `progress_pct` = `saved_so_far / final_price × 100`, capped at 100.
- `price_history` drives the sparkline.
- Pay Later and the credit card are **simulated** in Sandbox: we calculate the plan and tag the order.

### `GET /api/save-for-it/goals/{buyer_id}`

```json
{ "goals": [ { "...": "same shape as status" } ] }
```

### `POST /api/save-for-it/purchase/{goal_id}`

Request:

```json
{ "payment_option": "pay_in_4", "confirmed": true }
```

`payment_option`: `pay_now | pay_in_4 | pay_monthly_6`. Save For It purchases always need confirmation ("Buy now?" → you tap), so the first call without `confirmed: true` returns `409 NEEDS_CONFIRMATION`.
Response: same as `POST /api/orders`. The goal becomes `purchased` after capture.

### `POST /api/save-for-it/simulate-week/{goal_id}` — demo helper

Moves one `weekly_amount` into the goal and re-checks price + coupons (what the daily job does), so the demo doesn't need to wait real weeks.

Request (optional): `{ "weeks": 1 }`. Response: the updated goal (same shape as status).

---

## 4. Agent Pass (spending rules)

Every order and every claim goes through Agent Pass first. The agent never spends without your rules or approval.

### `GET /api/agent-pass/{buyer_id}`

```json
{
  "buyer_id": "B001",
  "autonomous_enabled": true,
  "autonomous_claims": true,
  "auto_approve_limit": 50.00,
  "max_unplanned_purchase": 150.00,
  "max_daily_spend": 300.00,
  "monthly_limit": 2000.00,
  "blocked_categories": ["gambling"],
  "approved_merchants": [],
  "spent_today": 18.00,
  "spent_this_month": 412.50
}
```

`approved_merchants: []` means any low-dispute merchant is fine.

### `PUT /api/agent-pass/{buyer_id}`

Request: any subset of the editable fields (`autonomous_enabled`, `autonomous_claims`, `auto_approve_limit` 0–200, `max_unplanned_purchase`, `max_daily_spend`, `monthly_limit`, `blocked_categories`, `approved_merchants`).
Response: full rules object.

### `POST /api/agent-pass/check`

Request:

```json
{
  "buyer_id": "B001",
  "amount": 200.00,
  "category": "electronics",
  "merchant_id": "M019",
  "action": "purchase",
  "planned": false
}
```

- `action`: `purchase | claim`.
- `planned`: `true` for Save For It purchases (the user set this goal), `false` otherwise.

Response (always **200**, it's a preview):

```json
{
  "decision": "BLOCK",
  "reason": "$200.00 unplanned purchase is over your $150.00 limit",
  "remaining_today": 282.00,
  "remaining_this_month": 1587.50
}
```

**Purchase rules (checked in order):**

1. Category in `blocked_categories` → `BLOCK`
2. Not planned and `amount > max_unplanned_purchase` → `BLOCK`
3. Would go over `monthly_limit` → `BLOCK`
4. Not planned and would go over `max_daily_spend` → `BLOCK`
5. Planned (Save For It) → `NEEDS_CONFIRMATION` ("Buy now?")
6. `autonomous_enabled` off, or `amount > auto_approve_limit`, or merchant not in a non-empty `approved_merchants` → `NEEDS_CONFIRMATION`
7. Otherwise → `APPROVE`

**Claim rules** (money coming back to you): `autonomous_claims` on → `APPROVE`, off → `NEEDS_CONFIRMATION`.

Demo story: insoles $18 → APPROVE · laptop $1,050 (planned) → NEEDS_CONFIRMATION · random $200 → BLOCK.

### `GET /api/agent-pass/{buyer_id}/actions`

Recent agent decisions, for the settings screen log.

```json
{
  "actions": [
    {
      "action_id": "AP_55",
      "action": "purchase",
      "amount": 200.00,
      "category": "electronics",
      "merchant_name": "GadgetGrove",
      "decision": "BLOCK",
      "reason": "$200.00 unplanned purchase is over your $150.00 limit",
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
  "product_name": "Running Insoles",
  "merchant_id": "M007",
  "category": "sports",
  "amount": 18.00,
  "original_price": 24.00,
  "payment_option": "pay_now",
  "source": "better_deal",
  "goal_id": null,
  "confirmed": false
}
```

- `payment_option`: `pay_now | pay_in_4 | pay_monthly_6`
- `source`: `better_deal | save_for_it | agent | direct`. `save_for_it` counts as planned for Agent Pass.
- `original_price` optional; `original_price − amount` counts as a `better_deal` saving after capture.
- `confirmed`: `true` after the user taps "Confirm" on a `NEEDS_CONFIRMATION`.

Response `201`:

```json
{
  "order_id": "5O190127TN364715T",
  "status": "CREATED",
  "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=5O190127TN364715T",
  "amount": 18.00,
  "payment_option": "pay_now",
  "installment_plan": null,
  "agent_pass": { "decision": "APPROVE", "reason": "$18.00 is under your $50.00 auto-approve limit" }
}
```

For `pay_in_4` / `pay_monthly_6`, `installment_plan` is filled (simulated):

```json
"installment_plan": {
  "installments": 4,
  "installment_amount": 262.50,
  "frequency": "every 2 weeks",
  "schedule": ["2026-11-09", "2026-11-23", "2026-12-07", "2026-12-21"]
}
```

Errors: `403 AGENT_PASS_BLOCKED`, `409 NEEDS_CONFIRMATION`, `502 PAYPAL_ERROR`.

**Frontend flow:** open `approve_url` (popup / new tab) → user logs in with the **sandbox buyer** account and approves → call capture.

### `POST /api/orders/{order_id}/capture`

No body. Response:

```json
{
  "order_id": "5O190127TN364715T",
  "status": "COMPLETED",
  "capture_id": "3C679366HH908993F",
  "amount": 18.00,
  "saved": 6.00,
  "message": "+$6.00 saved!"
}
```

`saved` drives the "+$X saved!" animation (0 if none). `409 NOT_APPROVED` if the buyer hasn't approved yet.

### `GET /api/orders/{order_id}`

```json
{ "order_id": "5O190127TN364715T", "status": "APPROVED", "amount": 18.00, "payment_option": "pay_now" }
```

`status`: `CREATED | APPROVED | COMPLETED`.

---

## 6. Flow C — Post-Purchase Guardian (4 autonomous actions)

"PayPal never stops working." All four checks are **rules on the data**, not ML:

| `type` | Rule | Agent action | `recoverable_amount` |
|---|---|---|---|
| `price_drop` | Merchant price fell within 7 days of purchase | Auto price-match (refund the difference) | paid − new price |
| `overcharge` | Charged > order total by more than 5% (tax buffer) | Flag + auto-dispute | charged − order total |
| `delivery_delay` | No delivery by the promised date | Auto-contact merchant | 0 (time, not money) |
| `late_refund` | Refund not received after the merchant's promised window | Auto-escalate | refund amount |

Alert `status`: `detected → resolved (action taken) → recovered (money back)`. `delivery_delay` ends at `resolved` (or `recovered` if it gets delivered).

**Autonomous:** after detection, each alert goes through Agent Pass (`action: "claim"`). If `APPROVE`, the agent acts right away (status `resolved`, `action_taken` filled). If `NEEDS_CONFIRMATION`, it stays `detected` and the user taps Claim.

**Recovery:** purchases made through our app have a real Sandbox capture, so price-drop/overcharge recoveries are **real Sandbox refunds**. Historical (generated) purchases have no capture, so their recovery is simulated (`recovery_method: "simulated"`).

### `POST /api/post-purchase/scan/{buyer_id}`

Starts the scan in the background. Response `202`:

```json
{ "scan_id": "S_1a2b", "status": "running" }
```

### `GET /api/post-purchase/results/{buyer_id}`

Poll every 3 seconds until `scan_status` is `complete`. Alerts appear as each check finishes, and statuses move forward as actions/recoveries happen, so the counter can tick up live.

```json
{
  "scan_status": "complete",
  "checks": {
    "price_drop": "complete",
    "overcharge": "complete",
    "delivery_delay": "complete",
    "late_refund": "complete"
  },
  "alerts": [
    {
      "alert_id": "AL_301",
      "type": "price_drop",
      "title": "Price drop on your headphones",
      "details": "You paid $89.00 on Tuesday. SoundLab dropped it to $71.00 on Thursday.",
      "transaction_id": "T_08812",
      "merchant_name": "SoundLab",
      "product_name": "Wireless Headphones",
      "purchase_date": "2026-10-27",
      "amount_paid": 89.00,
      "reference_price": 71.00,
      "recoverable_amount": 18.00,
      "status": "recovered",
      "action_taken": "Auto price-match requested. You did nothing.",
      "recovery_method": "paypal_refund",
      "paypal_reference": "8MC585209K746392H",
      "detected_at": "2026-11-09T10:15:00Z"
    },
    {
      "alert_id": "AL_302",
      "type": "overcharge",
      "title": "Overcharged by ShopRight",
      "details": "Order total $45.00, you were charged $54.00. $9.00 gap.",
      "transaction_id": "T_09107",
      "merchant_name": "ShopRight",
      "product_name": "Online order",
      "purchase_date": "2026-11-02",
      "amount_paid": 54.00,
      "reference_price": 45.00,
      "recoverable_amount": 9.00,
      "status": "resolved",
      "action_taken": "Flagged and auto-disputed.",
      "recovery_method": "simulated",
      "paypal_reference": null,
      "detected_at": "2026-11-09T10:15:01Z"
    },
    {
      "alert_id": "AL_303",
      "type": "delivery_delay",
      "title": "Your order is late",
      "details": "Promised 3-day shipping. Day 5, nothing arrived.",
      "transaction_id": "T_09230",
      "merchant_name": "HomeNest",
      "product_name": "Desk Lamp",
      "purchase_date": "2026-11-04",
      "promised_date": "2026-11-07",
      "days_late": 2,
      "recoverable_amount": 0,
      "status": "resolved",
      "action_taken": "Auto-contacted merchant.",
      "recovery_method": null,
      "paypal_reference": null,
      "detected_at": "2026-11-09T10:15:02Z"
    },
    {
      "alert_id": "AL_304",
      "type": "late_refund",
      "title": "Refund overdue from StyleLoop",
      "details": "Merchant said 5–7 days. Day 10, no refund.",
      "transaction_id": "T_08744",
      "merchant_name": "StyleLoop",
      "product_name": "Denim Jacket (returned)",
      "purchase_date": "2026-10-20",
      "refund_requested_date": "2026-10-30",
      "days_overdue": 3,
      "recoverable_amount": 39.99,
      "status": "resolved",
      "action_taken": "Agent auto-escalated.",
      "recovery_method": "simulated",
      "paypal_reference": null,
      "detected_at": "2026-11-09T10:15:03Z"
    }
  ],
  "total_recoverable": 66.99,
  "total_recovered": 18.00,
  "message": null
}
```

`scan_status`: `idle | running | complete`. No issues found: `"alerts": []` with a `message`.

### `POST /api/post-purchase/claim/{alert_id}`

For alerts left at `detected` (autonomous claims off). Request:

```json
{ "confirmed": true }
```

Runs Agent Pass (`action: "claim"`), then takes the action. Response:

```json
{
  "alert_id": "AL_301",
  "status": "resolved",
  "action_taken": "Auto price-match requested.",
  "paypal_reference": "8MC585209K746392H",
  "recoverable_amount": 18.00,
  "message": "Price-match request for $18.00 filed with SoundLab. We'll track it until it lands."
}
```

When money comes back, the alert becomes `recovered` and the amount is added to `/api/savings`.

---

## 7. Merchant Side ("For Your Business")

"PayPal knows your customer better than you do." Every buyer transaction + outcome feeds merchant intelligence.

### `GET /api/merchant/dashboard/{merchant_id}`

```json
{
  "merchant_id": "M007",
  "merchant_name": "TechHaven",
  "summary": {
    "at_risk_customers": 340,
    "recoverable_revenue": 48210.00,
    "offers_sent": 5,
    "offers_redeemed": 2,
    "win_back_rate_pct": 40,
    "revenue_won_back": 342.00
  },
  "churn_risk": [
    {
      "customer_id": "B214",
      "customer_name": "Sarah Kim",
      "churn_probability": 0.87,
      "risk_tier": "high",
      "days_since_purchase": 74,
      "total_spend": 1240.50,
      "order_count": 9,
      "last_category": "electronics",
      "offer_status": null
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

- `churn_risk`: sorted by `churn_probability` desc. `risk_tier`: `high (>= 0.7) | medium (0.4–0.7) | low (< 0.4)`.
- `offer_status`: `null | sent | redeemed | ignored`.
- `recoverable_revenue`: yearly spend of at-risk customers.
- `cross_sell` is a stretch goal and may be `[]`.

### `POST /api/merchant/send-offer`

Request:

```json
{ "merchant_id": "M007", "customer_id": "B214", "discount_pct": 15 }
```

`discount_pct` optional (backend picks from risk tier).

Response:

```json
{
  "offer_id": "O_9001",
  "customer_id": "B214",
  "customer_name": "Sarah Kim",
  "discount_pct": 15,
  "message": "15% off your next order, Sarah! We miss you at TechHaven. Valid for 14 days.",
  "message_source": "gemini",
  "invoice_id": "INV2-ABCD-1234-EFGH-5678",
  "invoice_status": "SENT",
  "sent_at": "2026-11-09T11:00:00Z"
}
```

- `message_source`: `gemini | template`.
- `invoice_id` / `invoice_status` from PayPal Sandbox Invoicing. If invoicing fails: `invoice_status: "FAILED"`, offer still recorded.

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

For the demo this can be a "Simulate customer response" button. Retraining is an offline script (Amrutha).

---

## 8. AI Agent (Gemini picks the tools)

One chat endpoint where Gemini decides which tools to call: the same logic as the endpoints above, wrapped as agent tools. This is what makes the AI "the agent," not just a text writer.

Tools the agent can call: `find_better_deal`, `check_agent_pass`, `create_order`, `create_goal`, `get_goal_status`, `scan_purchases`, `get_savings`.

### `POST /api/agent/chat`

Request:

```json
{
  "buyer_id": "B001",
  "message": "I'm about to buy running insoles for $24 at FootFirst",
  "session_id": null
}
```

Response:

```json
{
  "session_id": "CH_51c2",
  "reply": "Found the same insoles for $18 at StrideShop (rated 9.1/10, 2-day delivery). That's under your $50 auto-approve limit, so I've created the order: approve it in PayPal and you'll save $6.",
  "reply_source": "gemini",
  "tool_calls": [
    { "tool": "find_better_deal", "summary": "Best option $18.00 at StrideShop (save $6.00)" },
    { "tool": "check_agent_pass", "summary": "APPROVE: under $50.00 auto-approve limit" },
    { "tool": "create_order", "summary": "Sandbox order 5O190127TN364715T created" }
  ],
  "cards": [
    { "type": "better_deal", "data": { "...": "same shape as find-better-deal response" } },
    { "type": "order", "data": { "...": "same shape as POST /api/orders response" } }
  ],
  "pending_confirmation": null
}
```

- `tool_calls`: what the agent did, in order (show as "agent steps" in the UI).
- `cards`: structured results the frontend can render with the existing components. `type`: `better_deal | order | goal | agent_pass | savings | scan`.
- `pending_confirmation`: when Agent Pass says `NEEDS_CONFIRMATION`, this holds what's waiting, e.g. `{ "action": "create_order", "amount": 1050.00, "reason": "Save For It purchase: Buy now?" }`. The user confirms by replying "yes" (same `session_id`) or with the normal endpoint.
- `reply_source`: `gemini | template`. If Gemini is down, the backend runs the obvious tool for the message and answers with a template.

---

## 9. Demo helpers

### `POST /api/demo/reset`

Resets goals, alerts, savings, orders log, and Agent Pass rules for the demo users back to the seeded starting state. No body. Response:

```json
{ "status": "reset", "buyer_id": "B001", "merchant_id": "M007" }
```

---

## Endpoint summary

| Method | Path | Screen |
|---|---|---|
| GET | `/health` | — |
| GET | `/api/savings/{buyer_id}` | Savings report |
| POST | `/api/find-better-deal` | Flow A |
| POST | `/api/save-for-it/create` | Flow B |
| GET | `/api/save-for-it/status/{goal_id}` | Flow B |
| GET | `/api/save-for-it/goals/{buyer_id}` | Flow B |
| POST | `/api/save-for-it/purchase/{goal_id}` | Flow B |
| POST | `/api/save-for-it/simulate-week/{goal_id}` | Flow B (demo) |
| GET | `/api/agent-pass/{buyer_id}` | Agent Pass settings |
| PUT | `/api/agent-pass/{buyer_id}` | Agent Pass settings |
| POST | `/api/agent-pass/check` | Agent Pass indicator (A / B / C) |
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
| POST | `/api/agent/chat` | Agent chat |
| POST | `/api/demo/reset` | Demo |

## Open questions for review

1. **Hetav:** does every screen have what it needs? Anything missing or named awkwardly?
2. **Hetav:** OK opening `approve_url` in a popup / new tab, then calling capture?
3. **Hetav:** savings cards: show `latest.amount` (like the diagram: "$18, Headphones, Oct 29") or `total`? Note the diagram's numbers don't add up ("This month: $54" but the Nov cards sum to $165). The app will show real computed values, so the video must match the app, not the diagram.
4. **Hetav:** want an agent chat box (section 8) in the UI? It's the strongest "meaningful AI" proof for judges.
5. **Amrutha:** data columns needed by the rules:
   - transactions: `transaction_id, buyer_id, merchant_id, product_name, category, purchase_date, order_total, amount_charged, promised_delivery_date, delivered_date, refund_requested_date, refund_promised_days, refund_received_date, refund_amount`
   - price_changes: `merchant_id, product_name, change_date, old_price, new_price`
   - products: `product_id, product_name, category, price, merchant_id, rating (0–10), delivery_days`
   - coupons: `code, description, discount (or pct), category / merchant_id, expires`
   - churn output: `customer_id, customer_name, merchant_id, churn_probability, days_since_purchase, total_spend, order_count, last_category`
6. **Team:** confirm the PayPal credit card cashback % before it goes in the demo.
7. **Team, "Built with" footer:** only list what we actually use. Coupons are "Honey-style (simulated)", not the Honey API. Channel3 only if it works. LangChain + Agent Toolkit only if the agent endpoint ends up using them (backend will try them for section 8 and report back).
