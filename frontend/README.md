# Frontend

React (Vite) + TypeScript + Tailwind + Recharts + AG Grid. Two tabs: **For You** (buyer) and **For Your Business** (merchant).

## Run it

```bash
cd frontend
npm install
cp .env.example .env.local    # talks to the real backend; set VITE_USE_MOCKS=true for sample data
npm run dev                   # http://localhost:5173
```

`.env.local`:

| Variable | Meaning |
|---|---|
| `VITE_USE_MOCKS=true` | Built-in sample data. No backend needed. Header shows "Sample data". |
| `VITE_USE_MOCKS=false` | Talks to the real backend. Header shows "Live sandbox" (or "Backend offline"). |
| `VITE_API_BASE_URL` | Backend URL. `http://localhost:8000` locally, the Render URL when deployed. |

**Before recording the demo or taking Devpost screenshots: set `VITE_USE_MOCKS=false`.**

## Structure

```
src/
  api/        index.ts = one function per endpoint in API.md; http.ts = fetch + errors;
              mock.ts = in-memory backend that follows the contract (used when mocks are on)
  types/api.ts   types mirroring API.md. Change the contract -> change this first.
  views/      Savings, BetterDeal, SaveForIt, Guardian, AgentPassSettings, MerchantDashboard
  components/ shared UI, PayPalCheckout (popup flow), AgentChat (drawer), Toast, ErrorBoundary
  lib/        constants (demo IDs, categories, empty-state text), formatters, icon/tone maps
```

Routes are hash-based: `#/savings`, `#/better-deal`, `#/save-for-it`, `#/guardian`, `#/agent-pass`, `#/business`.

## PayPal approval popup

`usePayPalCheckout()` in `components/PayPalCheckout.tsx`:

1. Opens a blank popup inside the click handler (so browsers allow it).
2. Creates the order, then points the popup at `approve_url`.
3. Retries `POST /api/orders/{id}/capture` every 2s. PayPal answers `409 NOT_APPROVED` until the buyer approves, then the capture goes through.
   It does **not** poll `GET /api/orders/{id}`: the backend returns the status stored at creation and never refreshes it from PayPal.
4. After approving, PayPal sends the popup to `<frontend>/checkout/return` (or `/checkout/cancel`). `main.tsx` shows "you can close this window", messages the main window (so capture retries immediately) and closes itself.
5. If the popup is blocked, the dialog shows an "Open PayPal" link instead. Capture still completes after approving in that tab.
6. A closed popup is not treated as a cancel (PayPal pages can make `popup.closed` unreliable). The dialog has a Cancel button; the wait ends after 10 minutes.
7. `paypal_mode: "simulated"` (PayPal switched off in the backend) captures straight away.

Requirements on the backend side: `FRONTEND_URL` must be the frontend's real URL (it builds the return/cancel URLs) and `CORS_ORIGINS` must include it.
On Render the static site needs a rewrite of `/*` to `/index.html` so `/checkout/return` loads the app (see `render.yaml`).
For the demo, log in as the sandbox buyer in that browser beforehand.

## Notes

- Pay Later and the credit card are simulated in the sandbox; the UI says so.
- Alerts with `recovery_method: "simulated"` are tagged "Simulated in sandbox".
- Demo merchant is `M007` (TechHaven), demo buyer `B001` (API.md v0.3). Categories are the backend's real ones (`sporting_goods`, `apparel`, `grocery` ...).
- Offers: the backend reports `invoice_status: "SIMULATED"` until PayPal Invoicing is enabled; the UI says so instead of claiming an invoice was sent.
- Better deal only works for products in the catalog; anything else shows "Not in our catalog yet".
- AG Grid row grouping is an Enterprise feature; the churn table uses tier filter chips instead.
- App name (Nexus by PayPal): `APP_NAME` in `src/lib/constants.ts`, plus `<title>` in `index.html`.
- Demo reset: footer link "Reset demo data" (calls `POST /api/demo/reset`).
