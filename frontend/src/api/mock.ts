// In-memory stand-in for the backend, used when VITE_USE_MOCKS=true.
// It follows API.md closely (paths, shapes, error codes, Agent Pass rule order) so the
// screens behave the same against the real backend. All numbers are examples.
/* eslint-disable @typescript-eslint/no-explicit-any */
import { ApiError } from './errors'
import type { Method } from './http'
import type {
  AgentCard,
  AgentChatResponse,
  AgentPassCheckResult,
  AgentPassLogEntry,
  AgentPassRules,
  Alternative,
  AlertType,
  BetterDealResponse,
  CaptureResult,
  ChurnRow,
  CreateOrderRequest,
  Decision,
  FindBetterDealRequest,
  GuardianAlert,
  Goal,
  InstallmentPlan,
  MerchantDashboard,
  OfferSent,
  OrderCreated,
  PaymentOption,
  Savings,
  SavingsKind,
  ScanResults,
} from '../types/api'

// ---------- tiny helpers ----------
const r2 = (n: number) => Math.round(n * 100) / 100
const usd = (n: number) => `$${n.toFixed(2)}`
let counter = 1000
const uid = () => (counter++).toString(36).toUpperCase()
const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms))

function isoDay(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

const MERCHANTS: Record<string, string> = {
  M001: 'TechHaven',
  M003: 'SoundLab',
  M007: 'StrideShop',
  M011: 'SoleMate',
  M019: 'GadgetGrove',
  M023: 'ValueMart',
  M031: 'BrightBuy',
}

// ---------- state ----------
interface MockOrder {
  id: string
  approved: boolean
  status: 'CREATED' | 'APPROVED' | 'COMPLETED'
  amount: number
  option: PaymentOption
  original?: number
  goalId: string | null
  item: string
  merchantName: string
  saving: number
}

interface MockGoal {
  id: string
  buyer_id: string
  product_name: string
  category: string
  target: number
  weekly: number
  weeks: number
  merchant: string
  purchased: boolean
  purchasedSaving: number
}

function seedSavings(): Savings {
  return {
    buyer_id: 'B001',
    total_saved: 847.0,
    this_month: 165.0,
    breakdown: {
      price_drop: {
        label: 'Price drop recovered',
        total: 312.4,
        count: 11,
        latest: { item: 'Headphones', merchant_name: 'SoundLab', amount: 18.0, date: '2026-10-29' },
      },
      overcharge: {
        label: 'Overcharge caught',
        total: 188.6,
        count: 9,
        latest: { item: 'Online order', merchant_name: 'ShopRight', amount: 9.0, date: '2026-11-02' },
      },
      better_deal: {
        label: 'Better deal found',
        total: 196.0,
        count: 23,
        latest: { item: 'Insoles', merchant_name: 'StrideShop', amount: 6.0, date: '2026-11-05' },
      },
      save_for_it: {
        label: 'Save For It discount',
        total: 150.0,
        count: 1,
        latest: { item: 'Laptop', merchant_name: 'TechHaven', amount: 150.0, date: '2026-11-04' },
      },
    },
    trend: [
      { month: '2026-06', amount: 92.1 },
      { month: '2026-07', amount: 140.55 },
      { month: '2026-08', amount: 201.3 },
      { month: '2026-09', amount: 118.05 },
      { month: '2026-10', amount: 130.0 },
      { month: '2026-11', amount: 165.0 },
    ],
    recent_actions: [
      {
        action_id: 'A_102',
        type: 'price_drop',
        title: 'Auto price-match from SoundLab',
        amount: 18.0,
        status: 'recovered',
        timestamp: '2026-10-29T16:02:00Z',
      },
      {
        action_id: 'A_101',
        type: 'overcharge',
        title: 'Overcharge caught at ShopRight',
        amount: 9.0,
        status: 'recovered',
        timestamp: '2026-11-02T09:41:00Z',
      },
      {
        action_id: 'A_100',
        type: 'better_deal',
        title: 'Cheaper insoles at StrideShop',
        amount: 6.0,
        status: 'recovered',
        timestamp: '2026-11-05T13:20:00Z',
      },
    ],
    analytics: {
      spend_this_month: 1240.75,
      spend_by_category: [
        { category: 'electronics', amount: 612.4, saved: 58.99 },
        { category: 'home', amount: 310.15, saved: 18.0 },
        { category: 'sporting_goods', amount: 188.2, saved: 6.0 },
        { category: 'fashion', amount: 130.0, saved: 0 },
      ],
      purchases_watched: 42,
      active_alerts: 2,
      top_merchant: { merchant_name: 'TechHaven', amount: 409.0 },
      savings_rate_pct: 13.3,
    },
  }
}

function seedRules(): AgentPassRules {
  return {
    buyer_id: 'B001',
    autonomous_enabled: true,
    autonomous_claims: true,
    auto_approve_limit: 50,
    max_unplanned_purchase: 150,
    max_daily_spend: 300,
    monthly_limit: 2000,
    blocked_categories: ['gambling'],
    approved_merchants: [],
    spent_today: 18,
    spent_this_month: 412.5,
  }
}

function seedGoals(): MockGoal[] {
  return [
    {
      id: 'G_7f3a',
      buyer_id: 'B001',
      product_name: 'Dell XPS 14 Laptop',
      category: 'electronics',
      target: 1200,
      weekly: 100,
      weeks: 7,
      merchant: 'TechHaven',
      purchased: false,
      purchasedSaving: 0,
    },
  ]
}

const CHURN_SEED: ChurnRow[] = [
  { customer_id: 'B214', customer_name: 'Sarah Kim', churn_probability: 0.87, risk_tier: 'high', days_since_purchase: 74, total_spend: 1240.5, order_count: 9, last_category: 'electronics', offer_status: null },
  { customer_id: 'B087', customer_name: 'Marcus Hill', churn_probability: 0.82, risk_tier: 'high', days_since_purchase: 91, total_spend: 980.0, order_count: 7, last_category: 'electronics', offer_status: null },
  { customer_id: 'B342', customer_name: 'Priya Nair', churn_probability: 0.79, risk_tier: 'high', days_since_purchase: 66, total_spend: 2105.25, order_count: 14, last_category: 'home', offer_status: null },
  { customer_id: 'B119', customer_name: 'Diego Alvarez', churn_probability: 0.74, risk_tier: 'high', days_since_purchase: 58, total_spend: 640.0, order_count: 5, last_category: 'electronics', offer_status: null },
  { customer_id: 'B455', customer_name: 'Hannah Lee', churn_probability: 0.71, risk_tier: 'high', days_since_purchase: 83, total_spend: 455.8, order_count: 4, last_category: 'sports', offer_status: null },
  { customer_id: 'B203', customer_name: 'Tom Becker', churn_probability: 0.63, risk_tier: 'medium', days_since_purchase: 49, total_spend: 880.0, order_count: 8, last_category: 'electronics', offer_status: null },
  { customer_id: 'B391', customer_name: 'Aisha Khan', churn_probability: 0.58, risk_tier: 'medium', days_since_purchase: 41, total_spend: 1320.4, order_count: 11, last_category: 'home', offer_status: null },
  { customer_id: 'B066', customer_name: 'Lucas Meyer', churn_probability: 0.52, risk_tier: 'medium', days_since_purchase: 38, total_spend: 310.0, order_count: 3, last_category: 'sports', offer_status: null },
  { customer_id: 'B278', customer_name: 'Emma Rossi', churn_probability: 0.47, risk_tier: 'medium', days_since_purchase: 35, total_spend: 760.9, order_count: 6, last_category: 'electronics', offer_status: null },
  { customer_id: 'B150', customer_name: 'Noah Park', churn_probability: 0.33, risk_tier: 'low', days_since_purchase: 22, total_spend: 540.0, order_count: 5, last_category: 'home', offer_status: null },
  { customer_id: 'B410', customer_name: 'Olivia Brown', churn_probability: 0.27, risk_tier: 'low', days_since_purchase: 19, total_spend: 1980.0, order_count: 16, last_category: 'electronics', offer_status: null },
  { customer_id: 'B032', customer_name: 'Ethan Wright', churn_probability: 0.18, risk_tier: 'low', days_since_purchase: 12, total_spend: 215.5, order_count: 2, last_category: 'sports', offer_status: null },
]

function seed() {
  return {
    savings: seedSavings(),
    rules: seedRules(),
    log: [
      {
        action_id: 'AP_55',
        action: 'purchase',
        amount: 200,
        category: 'electronics',
        merchant_name: 'GadgetGrove',
        decision: 'BLOCK',
        reason: '$200.00 unplanned purchase is over your $150.00 limit',
        timestamp: new Date(Date.now() - 86400000).toISOString(),
      },
    ] as AgentPassLogEntry[],
    goals: seedGoals(),
    orders: {} as Record<string, MockOrder>,
    scan: null as null | { id: string; startedAt: number; claimedAt: Record<string, number> },
    appliedAlerts: new Set<string>(),
    churn: CHURN_SEED.map((c) => ({ ...c, offer_id: null as string | null })),
    merchant: { offersSent: 5, offersRedeemed: 2, revenueWonBack: 342 },
    offers: {} as Record<string, string>, // offer_id -> customer_id
    sessions: {} as Record<string, { pending: null | { productId: string; name: string; merchantId: string; merchantName: string; category: string; amount: number; original: number } }>,
  }
}

let S = seed()

export function mockApproveOrder(orderId: string): void {
  const o = S.orders[orderId]
  if (o) {
    o.approved = true
    o.status = 'APPROVED'
  }
}

// ---------- Agent Pass ----------
function checkRules(a: {
  amount: number
  category: string
  merchantId?: string
  action: 'purchase' | 'claim'
  planned: boolean
}): AgentPassCheckResult {
  const r = S.rules
  const remainingToday = r2(r.max_daily_spend - r.spent_today)
  const remainingMonth = r2(r.monthly_limit - r.spent_this_month)
  const out = (decision: Decision, reason: string): AgentPassCheckResult => ({
    decision,
    reason,
    remaining_today: remainingToday,
    remaining_this_month: remainingMonth,
  })

  if (a.action === 'claim') {
    return r.autonomous_claims
      ? out('APPROVE', 'Automatic claims are on')
      : out('NEEDS_CONFIRMATION', 'Automatic claims are off. Confirm to file this claim.')
  }
  if (r.blocked_categories.includes(a.category)) return out('BLOCK', `${a.category} is on your blocked list`)
  if (!a.planned && a.amount > r.max_unplanned_purchase)
    return out('BLOCK', `${usd(a.amount)} unplanned purchase is over your ${usd(r.max_unplanned_purchase)} limit`)
  if (r.spent_this_month + a.amount > r.monthly_limit)
    return out('BLOCK', `${usd(a.amount)} would go over your ${usd(r.monthly_limit)} monthly limit`)
  if (!a.planned && r.spent_today + a.amount > r.max_daily_spend)
    return out('BLOCK', `${usd(a.amount)} would go over your ${usd(r.max_daily_spend)} daily limit`)
  if (a.planned) return out('NEEDS_CONFIRMATION', 'Save For It purchase: Buy now?')
  if (!r.autonomous_enabled) return out('NEEDS_CONFIRMATION', 'Autonomous purchases are off. Confirm to buy.')
  if (a.amount > r.auto_approve_limit)
    return out('NEEDS_CONFIRMATION', `${usd(a.amount)} is over your ${usd(r.auto_approve_limit)} auto-approve limit`)
  if (r.approved_merchants.length > 0 && a.merchantId && !r.approved_merchants.includes(a.merchantId))
    return out('NEEDS_CONFIRMATION', 'This merchant is not on your approved list')
  return out('APPROVE', `${usd(a.amount)} is under your ${usd(r.auto_approve_limit)} auto-approve limit`)
}

function logDecision(a: { action: 'purchase' | 'claim'; amount: number; category: string; merchantName: string }, res: AgentPassCheckResult) {
  S.log.unshift({
    action_id: `AP_${uid()}`,
    action: a.action,
    amount: a.amount,
    category: a.category,
    merchant_name: a.merchantName,
    decision: res.decision,
    reason: res.reason,
    timestamp: new Date().toISOString(),
  })
  S.log = S.log.slice(0, 20)
}

// ---------- Savings ----------
function addSaving(kind: SavingsKind, amount: number, item: string, merchant: string, title: string) {
  const s = S.savings
  const card = s.breakdown[kind]
  card.total = r2(card.total + amount)
  card.count += 1
  card.latest = { item, merchant_name: merchant, amount: r2(amount), date: isoDay(0) }
  s.total_saved = r2(s.total_saved + amount)
  s.this_month = r2(s.this_month + amount)
  s.trend[s.trend.length - 1].amount = r2(s.trend[s.trend.length - 1].amount + amount)
  s.analytics.savings_rate_pct = Math.round((s.this_month / s.analytics.spend_this_month) * 1000) / 10
  s.recent_actions.unshift({
    action_id: `A_${uid()}`,
    type: kind,
    title,
    amount: r2(amount),
    status: 'recovered',
    timestamp: new Date().toISOString(),
  })
  s.recent_actions = s.recent_actions.slice(0, 8)
}

// ---------- Flow A ----------
interface CatalogItem {
  name: string
  match: RegExp
  median: number
  alts: { id: string; mid: string; price: number; rating: number; days: number; dispute: number; ontime: number }[]
}

const CATALOG: CatalogItem[] = [
  {
    name: 'Running Insoles',
    match: /insole/i,
    median: 19.5,
    alts: [
      { id: 'P_0231', mid: 'M007', price: 18, rating: 9.1, days: 2, dispute: 0.012, ontime: 0.96 },
      { id: 'P_0232', mid: 'M011', price: 19, rating: 8.6, days: 3, dispute: 0.018, ontime: 0.93 },
    ],
  },
  {
    name: 'Wireless Headphones',
    match: /headphone/i,
    median: 74,
    alts: [
      { id: 'P_0310', mid: 'M003', price: 71, rating: 9.0, days: 2, dispute: 0.011, ontime: 0.97 },
      { id: 'P_0311', mid: 'M031', price: 69.5, rating: 8.4, days: 4, dispute: 0.02, ontime: 0.91 },
      { id: 'P_0312', mid: 'M023', price: 73, rating: 8.8, days: 3, dispute: 0.015, ontime: 0.94 },
    ],
  },
  {
    name: 'Dell XPS 14 Laptop',
    match: /laptop|xps|macbook/i,
    median: 1090,
    alts: [
      { id: 'P_0410', mid: 'M001', price: 1050, rating: 9.2, days: 3, dispute: 0.009, ontime: 0.97 },
      { id: 'P_0411', mid: 'M019', price: 1079, rating: 8.5, days: 5, dispute: 0.02, ontime: 0.9 },
    ],
  },
]

function findDeal(req: FindBetterDealRequest): BetterDealResponse {
  const item = CATALOG.find((c) => c.match.test(req.product_name))
  const median = item ? item.median : r2(req.price * 0.85)
  const percentile = Math.max(1, Math.min(99, Math.round(50 + ((req.price - median) / median) * 165)))
  const overpaying = percentile > 65

  // Like the real backend: only products in the catalog get alternatives.
  const rawAlts = item ? item.alts : []

  const alternatives: Alternative[] = rawAlts
    .filter((a) => a.price < req.price)
    .sort((a, b) => a.price - b.price)
    .slice(0, 3)
    .map((a) => ({
      product_id: a.id,
      product_name: req.product_name,
      price: a.price,
      merchant_id: a.mid,
      merchant_name: MERCHANTS[a.mid] ?? a.mid,
      rating: a.rating,
      delivery_days: a.days,
      dispute_rate: a.dispute,
      on_time_rate: a.ontime,
      savings: r2(req.price - a.price),
    }))

  const best = alternatives[0] ?? null
  let agent_pass = null as BetterDealResponse['agent_pass']
  if (best) {
    const res = checkRules({ amount: best.price, category: req.category, merchantId: best.merchant_id, action: 'purchase', planned: false })
    agent_pass = { decision: res.decision, reason: res.reason }
    logDecision({ action: 'purchase', amount: best.price, category: req.category, merchantName: best.merchant_name }, res)
  }

  return {
    your_pick: { product_name: req.product_name, price: req.price, merchant_name: req.merchant_name },
    network: { median_price: median, percentile, overpaying },
    alternatives,
    best_option: best ? best.product_id : null,
    potential_savings: best ? best.savings : 0,
    source: 'local_catalog',
    matched_product: item ? item.name : null,
    agent_pass,
    agent_message: best
      ? `Same ${req.product_name.toLowerCase()} for ${usd(best.price)} at ${best.merchant_name}: rated ${best.rating}/10 with ${best.delivery_days}-day delivery. That's ${usd(best.savings)} less${req.merchant_name ? ` than ${req.merchant_name}` : ''}.`
      : item
        ? 'You already have the best price we can find.'
        : `I couldn't find "${req.product_name}" at other stores in the catalog.`,
    message: best ? null : item ? 'You already have the best price we can find.' : `I couldn't find "${req.product_name}" at other stores in the catalog.`,
  }
}

// ---------- Orders ----------
function installmentPlan(option: PaymentOption, amount: number): InstallmentPlan | null {
  if (option === 'pay_now') return null
  const n = option === 'pay_in_4' ? 4 : 6
  const gap = option === 'pay_in_4' ? 14 : 30
  return {
    installments: n,
    installment_amount: r2(amount / n),
    frequency: option === 'pay_in_4' ? 'every 2 weeks' : 'monthly',
    schedule: Array.from({ length: n }, (_, i) => isoDay(i * gap)),
  }
}

function createOrder(body: CreateOrderRequest): OrderCreated {
  const planned = body.source === 'save_for_it'
  const res = checkRules({ amount: body.amount, category: body.category, merchantId: body.merchant_id, action: 'purchase', planned })
  const merchantName = MERCHANTS[body.merchant_id] ?? body.merchant_id
  logDecision({ action: 'purchase', amount: body.amount, category: body.category, merchantName }, res)
  if (res.decision === 'BLOCK') {
    throw new ApiError(403, { code: 'AGENT_PASS_BLOCKED', decision: 'BLOCK', reason: res.reason })
  }
  if (res.decision === 'NEEDS_CONFIRMATION' && !body.confirmed) {
    throw new ApiError(409, { code: 'NEEDS_CONFIRMATION', decision: 'NEEDS_CONFIRMATION', reason: res.reason, message: res.reason })
  }
  const id = `5O${uid()}TN${Math.floor(Math.random() * 90000 + 10000)}`
  S.orders[id] = {
    id,
    approved: false,
    status: 'CREATED',
    amount: body.amount,
    option: body.payment_option,
    original: body.original_price,
    goalId: body.goal_id,
    item: body.product_name,
    merchantName,
    saving: body.original_price ? Math.max(0, r2(body.original_price - body.amount)) : 0,
  }
  return {
    order_id: id,
    status: 'CREATED',
    approve_url: `mock://paypal/checkoutnow?token=${id}`,
    amount: body.amount,
    payment_option: body.payment_option,
    installment_plan: installmentPlan(body.payment_option, body.amount),
    agent_pass: { decision: res.decision, reason: res.reason },
    paypal_mode: 'sandbox',
  }
}

function capture(orderId: string): CaptureResult {
  const o = S.orders[orderId]
  if (!o) throw new ApiError(404, { code: 'NOT_FOUND', message: `Order ${orderId} not found` })
  if (!o.approved) throw new ApiError(409, { code: 'NOT_APPROVED', message: 'The buyer has not approved this order in PayPal yet.' })
  if (o.status !== 'COMPLETED') {
    o.status = 'COMPLETED'
    S.rules.spent_today = r2(S.rules.spent_today + o.amount)
    S.rules.spent_this_month = r2(S.rules.spent_this_month + o.amount)
    if (o.goalId) {
      const g = S.goals.find((x) => x.id === o.goalId)
      if (g) {
        g.purchased = true
        g.purchasedSaving = goalView(g, true).savings_vs_target
        o.saving = Math.max(0, g.purchasedSaving)
        if (o.saving > 0) addSaving('save_for_it', o.saving, g.product_name, g.merchant, `Save For It: ${g.product_name}`)
      }
    } else if (o.saving > 0) {
      addSaving('better_deal', o.saving, o.item, o.merchantName, `Cheaper ${o.item.toLowerCase()} at ${o.merchantName}`)
    }
  }
  return {
    order_id: o.id,
    status: 'COMPLETED',
    capture_id: `3C${uid()}HH${Math.floor(Math.random() * 900000 + 100000)}`,
    amount: o.amount,
    saved: o.saving,
    message: o.saving > 0 ? `+${usd(o.saving)} saved!` : 'Payment complete.',
  }
}

// ---------- Flow B ----------
function goalView(g: MockGoal, ignorePurchased = false): Goal {
  const price = (w: number) => r2(Math.max(g.target * 0.86, g.target * (1 - 0.035 * w)))
  const current = price(g.weeks)
  const discount = g.weeks >= 2 ? Math.round(current * 0.02) : 0
  const coupon = discount > 0 ? { code: `SAVE${discount}`, description: `$${discount} off ${g.category}`, discount } : null
  const final = r2(current - discount)
  const saved = r2(g.weekly * g.weeks)

  const raw = [
    { date: isoDay(-(7 * g.weeks + 84)), price: r2(g.target * 1.04) },
    { date: isoDay(-(7 * g.weeks + 49)), price: r2(g.target * 1.02) },
    ...Array.from({ length: g.weeks + 1 }, (_, i) => ({ date: isoDay(-(7 * (g.weeks - i))), price: price(i) })),
  ]
  const history = raw.filter((p, i) => i === 0 || i === raw.length - 1 || p.price !== raw[i - 1].price)
  const low = Math.min(...history.map((p) => p.price), final)

  const purchased = g.purchased && !ignorePurchased
  const status: Goal['status'] = purchased ? 'purchased' : saved >= final ? 'ready' : g.weeks >= 2 ? 'deal_found' : 'saving'
  const fmt = (n: number) => usd(n).replace('.00', '')
  const message =
    status === 'purchased'
      ? `Bought. You paid ${fmt(final)} instead of ${fmt(g.target)}.`
      : status === 'ready'
        ? `Goal hit! Your ${g.product_name.toLowerCase()} is ${fmt(final)} today${coupon ? ` with code ${coupon.code}` : ''}: ${fmt(g.target - final)} under your target. Buy now?`
        : status === 'deal_found'
          ? `The price dropped to ${fmt(final)}${coupon ? ` with code ${coupon.code}` : ''}. You've saved ${fmt(saved)} so far. Can't wait? Pay Later is below.`
          : `Saving ${fmt(g.weekly)} a week. I'm watching the price and coupons for you.`

  return {
    goal_id: g.id,
    buyer_id: g.buyer_id,
    product_name: g.product_name,
    category: g.category,
    merchant_name: g.merchant,
    target_price: g.target,
    current_price: current,
    best_coupon: coupon,
    final_price: final,
    savings_vs_target: r2(g.target - final),
    all_time_low: low,
    weekly_amount: g.weekly,
    saved_so_far: saved,
    progress_pct: Math.min(100, Math.round((saved / final) * 100)),
    weeks_remaining: Math.max(0, Math.ceil((final - saved) / g.weekly)),
    status,
    price_history: history,
    financing_options: [
      { type: 'pay_in_4', label: 'Pay in 4', installments: 4, installment_amount: r2(final / 4), frequency: 'every 2 weeks', interest: 0 },
      { type: 'pay_monthly_6', label: 'Pay Monthly', installments: 6, installment_amount: r2(final / 6), frequency: 'monthly', interest: 0 },
    ],
    credit_card_offer: {
      label: 'PayPal credit card',
      cashback_pct: 3,
      estimated_cashback: r2(final * 0.03),
      note: 'Cashback rate to be verified against current card terms',
    },
    agent_message: message,
  }
}

function findGoal(id: string): MockGoal {
  const g = S.goals.find((x) => x.id === id)
  if (!g) throw new ApiError(404, { code: 'NOT_FOUND', message: `Goal ${id} not found` })
  return g
}

// ---------- Flow C ----------
const SCAN_STEPS: { type: AlertType; at: number }[] = [
  { type: 'price_drop', at: 1200 },
  { type: 'overcharge', at: 2400 },
  { type: 'delivery_delay', at: 3600 },
  { type: 'late_refund', at: 4800 },
]

function alertTemplates(): Record<AlertType, Omit<GuardianAlert, 'status' | 'action_taken' | 'detected_at'>> {
  return {
    price_drop: {
      alert_id: 'AL_301',
      type: 'price_drop',
      title: 'Price drop on your headphones',
      details: 'You paid $89.00 on Tuesday. SoundLab dropped it to $71.00 on Thursday.',
      transaction_id: 'T_08812',
      merchant_name: 'SoundLab',
      product_name: 'Wireless Headphones',
      purchase_date: isoDay(-13),
      amount_paid: 89,
      reference_price: 71,
      recoverable_amount: 18,
      recovery_method: 'paypal_refund',
      paypal_reference: '8MC585209K746392H',
    },
    overcharge: {
      alert_id: 'AL_302',
      type: 'overcharge',
      title: 'Overcharged by ShopRight',
      details: 'Order total $45.00, you were charged $54.00. $9.00 gap.',
      transaction_id: 'T_09107',
      merchant_name: 'ShopRight',
      product_name: 'Online order',
      purchase_date: isoDay(-8),
      amount_paid: 54,
      reference_price: 45,
      recoverable_amount: 9,
      recovery_method: 'simulated',
      paypal_reference: null,
    },
    delivery_delay: {
      alert_id: 'AL_303',
      type: 'delivery_delay',
      title: 'Your order is late',
      details: 'Promised 3-day shipping. Day 5, nothing arrived.',
      transaction_id: 'T_09230',
      merchant_name: 'HomeNest',
      product_name: 'Desk Lamp',
      purchase_date: isoDay(-6),
      promised_date: isoDay(-3),
      days_late: 2,
      recoverable_amount: 0,
      recovery_method: null,
      paypal_reference: null,
    },
    late_refund: {
      alert_id: 'AL_304',
      type: 'late_refund',
      title: 'Refund overdue from StyleLoop',
      details: 'Merchant said 5–7 days. Day 10, no refund.',
      transaction_id: 'T_08744',
      merchant_name: 'StyleLoop',
      product_name: 'Denim Jacket (returned)',
      purchase_date: isoDay(-20),
      refund_requested_date: isoDay(-10),
      days_overdue: 3,
      recoverable_amount: 39.99,
      recovery_method: 'simulated',
      paypal_reference: null,
    },
  }
}

const ACTION_TEXT: Record<AlertType, string> = {
  price_drop: 'Auto price-match requested. You did nothing.',
  overcharge: 'Flagged and auto-disputed.',
  delivery_delay: 'Auto-contacted merchant.',
  late_refund: 'Agent auto-escalated.',
}

function scanResults(): ScanResults {
  const scan = S.scan
  if (!scan) {
    return {
      scan_status: 'idle',
      checks: { price_drop: 'pending', overcharge: 'pending', delivery_delay: 'pending', late_refund: 'pending' },
      alerts: [],
      total_recoverable: 0,
      total_recovered: 0,
      message: 'Run a scan to check your recent purchases.',
    }
  }
  const t = Date.now() - scan.startedAt
  const templates = alertTemplates()
  const checks = {} as ScanResults['checks']
  const alerts: GuardianAlert[] = []

  for (const step of SCAN_STEPS) {
    if (t < step.at) {
      checks[step.type] = 'running'
      continue
    }
    checks[step.type] = 'complete'
    const tpl = templates[step.type]
    const since = t - step.at
    const auto = S.rules.autonomous_claims
    const claimedAt = scan.claimedAt[tpl.alert_id]
    let status: GuardianAlert['status'] = 'detected'
    let actionTaken: string | null = null

    if (auto || claimedAt !== undefined) {
      const sinceAction = auto ? since : Date.now() - (claimedAt as number)
      const resolvedAfter = auto ? 1500 : 0
      if (sinceAction >= resolvedAfter) {
        status = 'resolved'
        actionTaken = ACTION_TEXT[step.type]
        if (step.type === 'price_drop' && sinceAction >= resolvedAfter + 2000) status = 'recovered'
      }
    }
    if (status === 'recovered' && !S.appliedAlerts.has(tpl.alert_id)) {
      S.appliedAlerts.add(tpl.alert_id)
      addSaving('price_drop', tpl.recoverable_amount, tpl.product_name, tpl.merchant_name, `Auto price-match from ${tpl.merchant_name}`)
    }
    alerts.push({ ...tpl, status, action_taken: actionTaken, detected_at: new Date(scan.startedAt + step.at).toISOString() })
  }

  const done = SCAN_STEPS.every((s) => t >= s.at)
  return {
    scan_status: done ? 'complete' : 'running',
    checks,
    alerts,
    total_recoverable: r2(alerts.reduce((n, a) => n + a.recoverable_amount, 0)),
    total_recovered: r2(alerts.filter((a) => a.status === 'recovered').reduce((n, a) => n + a.recoverable_amount, 0)),
    message: done && alerts.length === 0 ? 'All clear.' : null,
  }
}

// ---------- Merchant ----------
function dashboard(): MerchantDashboard {
  const m = S.merchant
  return {
    merchant_id: 'M007',
    merchant_name: 'TechHaven',
    summary: {
      at_risk_customers: 340,
      recoverable_revenue: 48210,
      offers_sent: m.offersSent,
      offers_redeemed: m.offersRedeemed,
      win_back_rate_pct: m.offersSent ? Math.round((m.offersRedeemed / m.offersSent) * 100) : 0,
      revenue_won_back: m.revenueWonBack,
    },
    churn_risk: S.churn.map((c) => ({ ...c })).sort((a, b) => b.churn_probability - a.churn_probability),
    cross_sell: [
      { product_a: 'Laptops', product_b: 'Laptop Bags', co_purchase_rate: 0.34, suggested_bundle_discount_pct: 10 },
      { product_a: 'Headphones', product_b: 'Phone Cases', co_purchase_rate: 0.27, suggested_bundle_discount_pct: 8 },
      { product_a: 'Monitors', product_b: 'HDMI Cables', co_purchase_rate: 0.41, suggested_bundle_discount_pct: 12 },
      { product_a: 'Keyboards', product_b: 'Mouse Pads', co_purchase_rate: 0.22, suggested_bundle_discount_pct: 6 },
    ],
    model_info: { churn_model: 'GradientBoostingClassifier', auc: 0.74, precision: 0.68, recall: 0.71, note: 'Metrics on synthetic data' },
    message: null,
  }
}

function sendOffer(body: { merchant_id: string; customer_id: string; discount_pct?: number }): OfferSent {
  const c = S.churn.find((x) => x.customer_id === body.customer_id)
  if (!c) throw new ApiError(404, { code: 'NOT_FOUND', message: `Customer ${body.customer_id} not found` })
  const discount = body.discount_pct ?? (c.risk_tier === 'high' ? 15 : c.risk_tier === 'medium' ? 10 : 5)
  const offerId = `O_${uid()}`
  c.offer_status = 'sent'
  c.offer_id = offerId
  S.offers[offerId] = c.customer_id
  S.merchant.offersSent += 1
  return {
    offer_id: offerId,
    customer_id: c.customer_id,
    customer_name: c.customer_name,
    discount_pct: discount,
    message: `${discount}% off your next order, ${c.customer_name.split(' ')[0]}! We miss you at TechHaven. Valid for 14 days.`,
    message_source: 'template',
    invoice_id: null,
    invoice_status: 'SIMULATED',
    invoice_error: null,
    sent_at: new Date().toISOString(),
  }
}

// ---------- Agent chat ----------
function guessCategory(name: string): string {
  if (/insole|shoe|run/i.test(name)) return 'sporting_goods'
  if (/headphone|laptop|phone|monitor|keyboard/i.test(name)) return 'electronics'
  return 'home'
}

function chat(body: { buyer_id: string; message: string; session_id: string | null }): AgentChatResponse {
  const sid = body.session_id ?? `CH_${uid()}`
  const msg = body.message.trim()
  const lower = msg.toLowerCase()
  const base = { session_id: sid, reply_source: 'template' as const }

  if (/scan|guardian|my purchases/.test(lower)) {
    S.scan = { id: `S_${uid()}`, startedAt: Date.now(), claimedAt: {} }
    S.appliedAlerts.clear()
    return {
      ...base,
      reply: "I'm checking your recent purchases for price drops, overcharges, late deliveries and overdue refunds. Open Guardian to watch it work.",
      tool_calls: [{ tool: 'scan_purchases', summary: 'Scan started for 42 purchases' }],
      cards: [{ type: 'scan', data: { scan_id: S.scan.id } }],
      pending_confirmation: null,
    }
  }

  if (/how much|saved|savings/.test(lower)) {
    return {
      ...base,
      reply: `You've saved ${usd(S.savings.total_saved)} in total, ${usd(S.savings.this_month)} of it this month.`,
      tool_calls: [{ tool: 'get_savings', summary: `Total saved ${usd(S.savings.total_saved)}` }],
      cards: [{ type: 'savings', data: { total_saved: S.savings.total_saved, this_month: S.savings.this_month } }],
      pending_confirmation: null,
    }
  }

  const priceMatch = /\$\s?([\d,]+(?:\.\d+)?)/.exec(msg)
  if (priceMatch) {
    const price = Number(priceMatch[1].replace(/,/g, ''))
    const nameMatch = /(?:buy(?:ing)?|get(?:ting)?)\s+(.+?)\s+(?:for|at)\s+\$/i.exec(msg)
    const name = nameMatch ? nameMatch[1].replace(/^(some|a|an|the)\s+/i, '') : 'that item'
    const merchantMatch = /\bat\s+([A-Z][A-Za-z]+)\s*$/.exec(msg)
    const category = guessCategory(name)
    const deal = findDeal({ buyer_id: body.buyer_id, product_name: name.replace(/\b\w/g, (c) => c.toUpperCase()), price, category, merchant_name: merchantMatch?.[1] })
    const best = deal.alternatives[0]
    const calls = [{ tool: 'find_better_deal', summary: best ? `Best option ${usd(best.price)} at ${best.merchant_name} (save ${usd(best.savings)})` : 'No cheaper option found' }]
    const cards: AgentCard[] = best ? [{ type: 'better_deal', data: { your_pick: deal.your_pick, best_option: best, potential_savings: deal.potential_savings } }] : []
    if (!best || !deal.agent_pass) {
      return { ...base, reply: deal.agent_message, tool_calls: calls, cards, pending_confirmation: null }
    }
    calls.push({ tool: 'check_agent_pass', summary: `${deal.agent_pass.decision}: ${deal.agent_pass.reason}` })
    if (deal.agent_pass.decision === 'APPROVE') {
      const order = createOrder({
        buyer_id: body.buyer_id,
        product_id: best.product_id,
        product_name: best.product_name,
        merchant_id: best.merchant_id,
        category,
        amount: best.price,
        original_price: price,
        payment_option: 'pay_now',
        source: 'agent',
        goal_id: null,
        confirmed: false,
      })
      calls.push({ tool: 'create_order', summary: `Sandbox order ${order.order_id} created` })
      cards.push({ type: 'order', data: order })
      return {
        ...base,
        reply: `${deal.agent_message} That's under your auto-approve limit, so I created the order. Approve it in PayPal and you'll save ${usd(best.savings)}.`,
        tool_calls: calls,
        cards,
        pending_confirmation: null,
      }
    }
    if (deal.agent_pass.decision === 'NEEDS_CONFIRMATION') {
      // Same shape as the real backend: to confirm, the UI POSTs /api/orders with these args.
      return {
        ...base,
        reply: `${deal.agent_message} ${deal.agent_pass.reason}. Confirm below and I'll create the order.`,
        tool_calls: calls,
        cards,
        pending_confirmation: {
          tool: 'create_order',
          reason: deal.agent_pass.reason,
          args: {
            buyer_id: body.buyer_id,
            product_id: best.product_id,
            product_name: best.product_name,
            merchant_id: best.merchant_id,
            category,
            amount: best.price,
            original_price: price,
            payment_option: 'pay_now',
            source: 'agent',
            goal_id: null,
            confirmed: true,
          },
        },
      }
    }
    return { ...base, reply: `${deal.agent_message} I can't buy it for you though: ${deal.agent_pass.reason}.`, tool_calls: calls, cards, pending_confirmation: null }
  }

  return {
    ...base,
    reply: 'I can compare prices before you buy, check how much you have saved, or scan your recent purchases. Try: "I\'m about to buy running insoles for $24 at FootFirst".',
    tool_calls: [],
    cards: [],
    pending_confirmation: null,
  }
}

// ---------- routing ----------
type Handler = (m: RegExpExecArray, body: any) => unknown

const routes: [Method, RegExp, Handler][] = [
  ['GET', /^\/health$/, () => ({ status: 'ok', service: 'nexus-by-paypal', paypal_env: 'sandbox', paypal_configured: true, gemini_configured: true })],

  ['GET', /^\/api\/savings\/([^/]+)$/, () => structuredClone(S.savings)],

  ['POST', /^\/api\/find-better-deal$/, (_m, b: FindBetterDealRequest) => {
    if (!b.product_name || !(b.price > 0)) throw new ApiError(400, { code: 'BAD_REQUEST', message: 'Add a product name and a price.' })
    return findDeal(b)
  }],

  ['POST', /^\/api\/save-for-it\/create$/, (_m, b) => {
    if (!b.product_name || !(b.target_price > 0) || !(b.weekly_amount > 0))
      throw new ApiError(400, { code: 'BAD_REQUEST', message: 'Add a product, a target price and a weekly amount.' })
    const g: MockGoal = {
      id: `G_${uid().toLowerCase()}`,
      buyer_id: b.buyer_id,
      product_name: b.product_name,
      category: b.category,
      target: b.target_price,
      weekly: b.weekly_amount,
      weeks: 0,
      merchant: 'TechHaven',
      purchased: false,
      purchasedSaving: 0,
    }
    S.goals.unshift(g)
    return goalView(g)
  }],
  ['GET', /^\/api\/save-for-it\/status\/([^/]+)$/, (m) => goalView(findGoal(m[1]))],
  ['GET', /^\/api\/save-for-it\/goals\/([^/]+)$/, () => ({
    goals: S.goals.map((g) => goalView(g)),
    message: S.goals.length ? null : 'No goals yet.',
  })],
  ['POST', /^\/api\/save-for-it\/purchase\/([^/]+)$/, (m, b) => {
    const g = findGoal(m[1])
    const v = goalView(g)
    if (!b.confirmed) throw new ApiError(409, { code: 'NEEDS_CONFIRMATION', decision: 'NEEDS_CONFIRMATION', reason: 'Save For It purchase: Buy now?', message: 'Save For It purchase: Buy now?' })
    return createOrder({
      buyer_id: g.buyer_id,
      product_id: 'P_0410',
      product_name: g.product_name,
      merchant_id: 'M001',
      category: g.category,
      amount: v.final_price,
      original_price: g.target,
      payment_option: b.payment_option ?? 'pay_now',
      source: 'save_for_it',
      goal_id: g.id,
      confirmed: true,
    })
  }],
  ['POST', /^\/api\/save-for-it\/simulate-week\/([^/]+)$/, (m, b) => {
    const g = findGoal(m[1])
    g.weeks += Math.max(1, Math.min(52, Number(b?.weeks) || 1))
    return goalView(g)
  }],

  ['GET', /^\/api\/agent-pass\/([^/]+)\/actions$/, () => ({ actions: S.log.map((x) => ({ ...x })), message: S.log.length ? null : 'No agent decisions yet.' })],
  ['POST', /^\/api\/agent-pass\/check$/, (_m, b) => {
    const res = checkRules({ amount: b.amount, category: b.category, merchantId: b.merchant_id, action: b.action, planned: !!b.planned })
    logDecision({ action: b.action, amount: b.amount, category: b.category, merchantName: MERCHANTS[b.merchant_id ?? ''] ?? 'Tester' }, res)
    return res
  }],
  ['GET', /^\/api\/agent-pass\/([^/]+)$/, () => ({ ...S.rules })],
  ['PUT', /^\/api\/agent-pass\/([^/]+)$/, (_m, b) => {
    const allowed = ['autonomous_enabled', 'autonomous_claims', 'auto_approve_limit', 'max_unplanned_purchase', 'max_daily_spend', 'monthly_limit', 'blocked_categories', 'approved_merchants']
    if (b.auto_approve_limit !== undefined && (b.auto_approve_limit < 0 || b.auto_approve_limit > 200))
      throw new ApiError(400, { code: 'BAD_REQUEST', message: 'Auto-approve limit must be between $0 and $200.' })
    for (const k of allowed) if (k in b) (S.rules as any)[k] = b[k]
    return { ...S.rules }
  }],

  ['POST', /^\/api\/orders$/, (_m, b: CreateOrderRequest) => createOrder(b)],
  ['POST', /^\/api\/orders\/([^/]+)\/capture$/, (m) => capture(m[1])],
  ['GET', /^\/api\/orders\/([^/]+)$/, (m) => {
    const o = S.orders[m[1]]
    if (!o) throw new ApiError(404, { code: 'NOT_FOUND', message: `Order ${m[1]} not found` })
    return { order_id: o.id, status: o.status, amount: o.amount, payment_option: o.option }
  }],

  ['POST', /^\/api\/post-purchase\/scan\/([^/]+)$/, () => {
    S.scan = { id: `S_${uid()}`, startedAt: Date.now(), claimedAt: {} }
    S.appliedAlerts.clear()
    return { scan_id: S.scan.id, status: 'running' }
  }],
  ['GET', /^\/api\/post-purchase\/results\/([^/]+)$/, () => scanResults()],
  ['POST', /^\/api\/post-purchase\/claim\/([^/]+)$/, (m) => {
    const alertId = m[1]
    const tpl = Object.values(alertTemplates()).find((a) => a.alert_id === alertId)
    if (!tpl || !S.scan) throw new ApiError(404, { code: 'NOT_FOUND', message: `Alert ${alertId} not found` })
    const res = checkRules({ amount: tpl.recoverable_amount, category: 'claim', action: 'claim', planned: false })
    logDecision({ action: 'claim', amount: tpl.recoverable_amount, category: tpl.type, merchantName: tpl.merchant_name }, res)
    S.scan.claimedAt[alertId] = Date.now()
    return {
      alert_id: alertId,
      status: 'resolved',
      action_taken: ACTION_TEXT[tpl.type],
      paypal_reference: tpl.paypal_reference,
      recoverable_amount: tpl.recoverable_amount,
      message: `Claim for ${usd(tpl.recoverable_amount)} filed with ${tpl.merchant_name}. We'll track it until it lands.`,
    }
  }],

  ['GET', /^\/api\/merchant\/dashboard\/([^/]+)$/, () => dashboard()],
  ['POST', /^\/api\/merchant\/send-offer$/, (_m, b) => sendOffer(b)],
  ['POST', /^\/api\/merchant\/offer-outcome\/([^/]+)$/, (m, b) => {
    const offerId = m[1]
    const customerId = S.offers[offerId]
    const c = S.churn.find((x) => x.customer_id === customerId)
    if (!c) throw new ApiError(404, { code: 'NOT_FOUND', message: `Offer ${offerId} not found` })
    let won = 0
    if (b.outcome === 'redeemed') {
      won = Number(b.order_amount) || 189
      c.offer_status = 'redeemed'
      S.merchant.offersRedeemed += 1
      S.merchant.revenueWonBack = r2(S.merchant.revenueWonBack + won)
    } else if (b.outcome === 'ignored') {
      c.offer_status = 'ignored'
    }
    return {
      offer_id: offerId,
      outcome: b.outcome,
      revenue_won_back: won,
      feedback_rows_logged: 128 + Object.keys(S.offers).length,
      message: 'Outcome logged. It will be used when the churn model is retrained.',
    }
  }],

  ['POST', /^\/api\/agent\/chat$/, (_m, b) => chat(b)],

  ['POST', /^\/api\/demo\/reset$/, () => {
    S = seed()
    return { status: 'reset', buyer_id: 'B001', merchant_id: 'M007' }
  }],
]

export async function mockHandle<T>(method: Method, path: string, body?: unknown): Promise<T> {
  await sleep(220 + Math.random() * 280) // long enough for skeletons to show
  const clean = path.split('?')[0]
  for (const [m, re, handler] of routes) {
    if (m !== method) continue
    const match = re.exec(clean)
    if (match) return structuredClone(handler(match, body ?? {})) as T
  }
  throw new ApiError(404, { code: 'NOT_FOUND', message: `Mock API has no route for ${method} ${path}` })
}
