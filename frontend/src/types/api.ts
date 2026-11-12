// Types mirror API.md (draft v0.2). If the contract changes, change it here first
// and let the compiler show you every screen that needs updating.

export type Decision = 'APPROVE' | 'NEEDS_CONFIRMATION' | 'BLOCK'
export type PaymentOption = 'pay_now' | 'pay_in_4' | 'pay_monthly_6'

export interface AgentPassDecision {
  decision: Decision
  reason: string
}

// ---------- Health ----------
export interface Health {
  status: string
  service: string
  paypal_env: string
  paypal_configured: boolean
  gemini_configured: boolean
}

// ---------- Savings ----------
export type SavingsKind = 'price_drop' | 'overcharge' | 'better_deal' | 'save_for_it'

export interface SavingLatest {
  item: string
  merchant_name: string
  amount: number
  date: string
}

export interface BreakdownCard {
  label: string
  total: number
  count: number
  latest: SavingLatest | null
}

// The contract uses `delivery` / `refund` here but `delivery_delay` / `late_refund`
// on Guardian alerts. We accept both until the backend picks one.
export type ActionType = SavingsKind | 'delivery' | 'refund' | 'delivery_delay' | 'late_refund'
export type ActionStatus = 'detected' | 'resolved' | 'recovered'

export interface RecentAction {
  action_id: string
  type: ActionType
  title: string
  amount: number
  status: ActionStatus
  timestamp: string
}

export interface Savings {
  buyer_id: string
  total_saved: number
  this_month: number
  breakdown: Record<SavingsKind, BreakdownCard>
  trend: { month: string; amount: number }[]
  recent_actions: RecentAction[]
  analytics: {
    spend_this_month: number
    spend_by_category: { category: string; amount: number; saved: number }[]
    purchases_watched: number
    active_alerts: number
    top_merchant: { merchant_name: string; amount: number } | null
    savings_rate_pct: number
  }
  message?: string | null
}

// ---------- Flow A: Better deal ----------
export interface FindBetterDealRequest {
  buyer_id: string
  product_name: string
  price: number
  category: string
  merchant_name?: string
}

export interface Alternative {
  product_id: string
  product_name: string
  price: number
  merchant_id: string
  merchant_name: string
  rating: number
  delivery_days: number
  dispute_rate: number
  on_time_rate: number
  savings: number
}

export interface BetterDealResponse {
  your_pick: { product_name: string; price: number; merchant_name?: string }
  network: { median_price: number; percentile: number; overpaying: boolean }
  alternatives: Alternative[]
  best_option: string | null
  potential_savings: number
  source: 'channel3' | 'local_catalog'
  agent_pass: AgentPassDecision | null
  agent_message: string
  message?: string | null
}

// ---------- Flow B: Save for it ----------
export type GoalStatus = 'saving' | 'deal_found' | 'ready' | 'purchased'

export interface FinancingOption {
  type: Exclude<PaymentOption, 'pay_now'>
  label: string
  installments: number
  installment_amount: number
  frequency: string
  interest: number
}

export interface Goal {
  goal_id: string
  buyer_id: string
  product_name: string
  category: string
  merchant_name: string
  target_price: number
  current_price: number
  best_coupon: { code: string; description: string; discount: number } | null
  final_price: number
  savings_vs_target: number
  all_time_low: number
  weekly_amount: number
  saved_so_far: number
  progress_pct: number
  weeks_remaining: number
  status: GoalStatus
  price_history: { date: string; price: number }[]
  financing_options: FinancingOption[]
  credit_card_offer: {
    label: string
    cashback_pct: number
    estimated_cashback: number
    note: string
  } | null
  agent_message: string
}

export interface CreateGoalRequest {
  buyer_id: string
  product_name: string
  product_id?: string
  category: string
  target_price: number
  weekly_amount: number
}

// ---------- Agent Pass ----------
export interface AgentPassRules {
  buyer_id: string
  autonomous_enabled: boolean
  autonomous_claims: boolean
  auto_approve_limit: number
  max_unplanned_purchase: number
  max_daily_spend: number
  monthly_limit: number
  blocked_categories: string[]
  approved_merchants: string[]
  spent_today: number
  spent_this_month: number
}

export type AgentPassUpdate = Partial<
  Omit<AgentPassRules, 'buyer_id' | 'spent_today' | 'spent_this_month'>
>

export interface AgentPassCheckRequest {
  buyer_id: string
  amount: number
  category: string
  merchant_id?: string
  action: 'purchase' | 'claim'
  planned: boolean
}

export interface AgentPassCheckResult extends AgentPassDecision {
  remaining_today: number
  remaining_this_month: number
}

export interface AgentPassLogEntry {
  action_id: string
  action: 'purchase' | 'claim'
  amount: number
  category: string
  merchant_name: string
  decision: Decision
  reason: string
  timestamp: string
}

// ---------- Orders ----------
export interface InstallmentPlan {
  installments: number
  installment_amount: number
  frequency: string
  schedule: string[]
}

export interface CreateOrderRequest {
  buyer_id: string
  product_id: string
  product_name: string
  merchant_id: string
  category: string
  amount: number
  original_price?: number
  payment_option: PaymentOption
  source: 'better_deal' | 'save_for_it' | 'agent' | 'direct'
  goal_id: string | null
  confirmed: boolean
}

export interface OrderCreated {
  order_id: string
  status: 'CREATED' | 'APPROVED' | 'COMPLETED'
  approve_url: string
  amount: number
  payment_option: PaymentOption
  installment_plan: InstallmentPlan | null
  agent_pass: AgentPassDecision
}

export interface OrderStatus {
  order_id: string
  status: 'CREATED' | 'APPROVED' | 'COMPLETED'
  amount: number
  payment_option: PaymentOption
}

export interface CaptureResult {
  order_id: string
  status: 'COMPLETED'
  capture_id: string
  amount: number
  saved: number
  message: string
}

// ---------- Flow C: Guardian ----------
export type AlertType = 'price_drop' | 'overcharge' | 'delivery_delay' | 'late_refund'
export type CheckState = 'pending' | 'running' | 'complete'

export interface GuardianAlert {
  alert_id: string
  type: AlertType
  title: string
  details: string
  transaction_id: string
  merchant_name: string
  product_name: string
  purchase_date: string
  amount_paid?: number
  reference_price?: number
  promised_date?: string
  days_late?: number
  refund_requested_date?: string
  days_overdue?: number
  recoverable_amount: number
  status: ActionStatus
  action_taken: string | null
  recovery_method: 'paypal_refund' | 'simulated' | null
  paypal_reference: string | null
  detected_at: string
}

export interface ScanStarted {
  scan_id: string
  status: 'running'
}

export interface ScanResults {
  scan_status: 'idle' | 'running' | 'complete'
  checks: Record<AlertType, CheckState>
  alerts: GuardianAlert[]
  total_recoverable: number
  total_recovered: number
  message: string | null
}

export interface ClaimResult {
  alert_id: string
  status: ActionStatus
  action_taken: string
  paypal_reference: string | null
  recoverable_amount: number
  message: string
}

// ---------- Merchant ----------
export type RiskTier = 'high' | 'medium' | 'low'
export type OfferStatus = 'sent' | 'redeemed' | 'ignored' | null

export interface ChurnRow {
  customer_id: string
  customer_name: string
  churn_probability: number
  risk_tier: RiskTier
  days_since_purchase: number
  total_spend: number
  order_count: number
  last_category: string
  offer_status: OfferStatus
  // Not in the contract yet. Needed to log an outcome after a reload.
  offer_id?: string | null
}

export interface CrossSellRow {
  product_a: string
  product_b: string
  co_purchase_rate: number
  suggested_bundle_discount_pct: number
}

export interface MerchantDashboard {
  merchant_id: string
  merchant_name: string
  summary: {
    at_risk_customers: number
    recoverable_revenue: number
    offers_sent: number
    offers_redeemed: number
    win_back_rate_pct: number
    revenue_won_back: number
  }
  churn_risk: ChurnRow[]
  cross_sell: CrossSellRow[]
  model_info: { churn_model: string; auc: number; note: string }
  message?: string | null
}

export interface SendOfferRequest {
  merchant_id: string
  customer_id: string
  discount_pct?: number
}

export interface OfferSent {
  offer_id: string
  customer_id: string
  customer_name: string
  discount_pct: number
  message: string
  message_source: 'gemini' | 'template'
  invoice_id: string | null
  invoice_status: string
  sent_at: string
}

export interface OfferOutcomeResult {
  offer_id: string
  outcome: 'redeemed' | 'opened' | 'ignored'
  revenue_won_back: number
  feedback_rows_logged: number
  message: string
}

// ---------- Agent chat ----------
export interface AgentToolCall {
  tool: string
  summary: string
}

export interface AgentCard {
  type: 'better_deal' | 'order' | 'goal' | 'agent_pass' | 'savings' | 'scan'
  data: unknown
}

export interface AgentChatResponse {
  session_id: string
  reply: string
  reply_source: 'gemini' | 'template'
  tool_calls: AgentToolCall[]
  cards: AgentCard[]
  pending_confirmation: { action: string; amount: number; reason: string } | null
}

// ---------- Errors ----------
export interface ErrorDetail {
  code?: string
  message?: string
  decision?: Decision
  reason?: string
}
