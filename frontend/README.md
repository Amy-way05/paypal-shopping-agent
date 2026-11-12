# Frontend

React (Vite) + TypeScript + Tailwind + Recharts + AG Grid. Two tabs: **For You** (buyer) and **For Your Business** (merchant).

## Run it

```bash
cd frontend
npm install
cp .env.example .env.local    # already included in the zip; edit as needed
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
3. Polls `GET /api/orders/{id}` every 2s until `APPROVED`, closes the popup, calls capture.
4. If the popup is blocked, shows an "Open PayPal" link instead.

Optional: set PayPal's return/cancel URLs to `<frontend>/?paypal=return` / `?paypal=cancel`. `main.tsx` shows a "you can close this window" page.
For the demo, log in as the sandbox buyer in that browser beforehand.

## Notes

- Pay Later and the credit card are simulated in the sandbox; the UI says so.
- Alerts with `recovery_method: "simulated"` are tagged "Simulated in sandbox".
- AG Grid row grouping is an Enterprise feature; the churn table uses tier filter chips instead.
- App name is a placeholder: `APP_NAME` in `src/lib/constants.ts`.
- Demo reset: footer link "Reset demo data" (calls `POST /api/demo/reset`).
