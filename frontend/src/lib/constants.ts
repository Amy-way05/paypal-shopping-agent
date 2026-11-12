// App name is a placeholder until the team picks one (task: Branding + polish).
export const APP_NAME = 'PayPal Shopping Agent'

// Demo users from the API contract (no login).
export const DEMO_BUYER_ID = 'B001'
export const DEMO_MERCHANT_ID = 'M007' // TechHaven in data/merchants.csv (API.md v0.3)

// The backend's real catalog categories (API.md v0.3), plus 'gambling' so the default Agent Pass block is visible.
export const CATEGORIES = [
  'electronics',
  'home',
  'apparel',
  'beauty',
  'sporting_goods',
  'books',
  'toys',
  'grocery',
  'furniture',
  'pet_supplies',
  'gambling',
] as const

// Fallbacks for empty states. Prefer the API's own `message` when it sends one.
export const EMPTY = {
  savings: 'No savings yet. Compare a price or run a scan and your first win lands here.',
  recent: 'Nothing to show yet. Actions the agent takes for you will appear here.',
  alternatives: 'You already have the best price. No cheaper option from trusted merchants.',
  goals: 'No goals yet. Add something you want and PayPal saves toward it and watches the price.',
  guardianIdle:
    'Scan your recent purchases. PayPal checks for price drops, overcharges, late deliveries and overdue refunds.',
  guardianClean: 'All clear. No price drops, overcharges, late orders or overdue refunds found.',
  agentLog: 'No agent decisions yet. Try a purchase in the tester above.',
  churn: 'No at-risk customers right now.',
  crossSell: 'Not enough purchase history yet for bundle suggestions.',
} as const
