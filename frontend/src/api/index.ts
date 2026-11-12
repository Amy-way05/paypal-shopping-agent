// One function per endpoint in API.md. Screens only ever import from here.
import { request } from './http'
import type {
  AgentChatResponse,
  AgentPassCheckRequest,
  AgentPassCheckResult,
  AgentPassLogEntry,
  AgentPassRules,
  AgentPassUpdate,
  BetterDealResponse,
  CaptureResult,
  ClaimResult,
  CreateGoalRequest,
  CreateOrderRequest,
  FindBetterDealRequest,
  Goal,
  Health,
  MerchantDashboard,
  OfferOutcomeResult,
  OfferSent,
  OrderCreated,
  OrderStatus,
  PaymentOption,
  Savings,
  ScanResults,
  ScanStarted,
  SendOfferRequest,
} from '../types/api'

export const api = {
  health: () => request<Health>('GET', '/health'),

  getSavings: (buyerId: string) => request<Savings>('GET', `/api/savings/${buyerId}`),

  findBetterDeal: (body: FindBetterDealRequest) =>
    request<BetterDealResponse>('POST', '/api/find-better-deal', body),

  createGoal: (body: CreateGoalRequest) => request<Goal>('POST', '/api/save-for-it/create', body),
  getGoal: (goalId: string) => request<Goal>('GET', `/api/save-for-it/status/${goalId}`),
  listGoals: (buyerId: string) =>
    request<{ goals: Goal[]; message?: string | null }>('GET', `/api/save-for-it/goals/${buyerId}`),
  purchaseGoal: (goalId: string, body: { payment_option: PaymentOption; confirmed: boolean }) =>
    request<OrderCreated>('POST', `/api/save-for-it/purchase/${goalId}`, body),
  simulateWeek: (goalId: string, weeks = 1) =>
    request<Goal>('POST', `/api/save-for-it/simulate-week/${goalId}`, { weeks }),

  getAgentPass: (buyerId: string) => request<AgentPassRules>('GET', `/api/agent-pass/${buyerId}`),
  updateAgentPass: (buyerId: string, body: AgentPassUpdate) =>
    request<AgentPassRules>('PUT', `/api/agent-pass/${buyerId}`, body),
  checkAgentPass: (body: AgentPassCheckRequest) =>
    request<AgentPassCheckResult>('POST', '/api/agent-pass/check', body),
  getAgentPassActions: (buyerId: string) =>
    request<{ actions: AgentPassLogEntry[]; message?: string | null }>('GET', `/api/agent-pass/${buyerId}/actions`),

  createOrder: (body: CreateOrderRequest) => request<OrderCreated>('POST', '/api/orders', body),
  captureOrder: (orderId: string) => request<CaptureResult>('POST', `/api/orders/${orderId}/capture`),
  getOrder: (orderId: string) => request<OrderStatus>('GET', `/api/orders/${orderId}`),

  startScan: (buyerId: string) => request<ScanStarted>('POST', `/api/post-purchase/scan/${buyerId}`),
  getScanResults: (buyerId: string) => request<ScanResults>('GET', `/api/post-purchase/results/${buyerId}`),
  claimAlert: (alertId: string) =>
    request<ClaimResult>('POST', `/api/post-purchase/claim/${alertId}`, { confirmed: true }),

  getMerchantDashboard: (merchantId: string) =>
    request<MerchantDashboard>('GET', `/api/merchant/dashboard/${merchantId}`),
  sendOffer: (body: SendOfferRequest) => request<OfferSent>('POST', '/api/merchant/send-offer', body),
  logOfferOutcome: (offerId: string, body: { outcome: 'redeemed' | 'opened' | 'ignored'; order_amount?: number }) =>
    request<OfferOutcomeResult>('POST', `/api/merchant/offer-outcome/${offerId}`, body),

  agentChat: (body: { buyer_id: string; message: string; session_id: string | null }) =>
    request<AgentChatResponse>('POST', '/api/agent/chat', body),

  resetDemo: () => request<{ status: string; buyer_id: string; merchant_id: string }>('POST', '/api/demo/reset'),
}
