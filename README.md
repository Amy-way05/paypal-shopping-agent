# PayPal Shopping Agent — [final app name once decided]

> Apple Pay pays. PayPal shops for you.

An AI agent that works before, during, and after every purchase — finding better deals, recovering money automatically, and giving merchants intelligence only PayPal's two-sided data can provide.

Built for [Paypal Hackathon ] — [Nov 12th, 2026].

## The problem

PayPal processes $1.79 trillion a year but nobody thinks about it the moment money moves. Users only open the app at checkout. Meanwhile, everyone overpays, misses price drops, gets silently overcharged, and loses refunds nobody is tracking.

## What it does

**Buyer side**
- **Better Deal Before You Pay** — finds a cheaper option for what you're already about to buy, before checkout
- **Save For It** — auto-saves weekly toward a goal, watches the price, buys when it drops
- **Post-Purchase Guardian** — catches price drops after you buy, flags overcharges, watches delivery delays, tracks overdue refunds
- **Savings Report** — running counter of everything recovered

**Merchant side**
- **Churn risk ranking** — flags customers about to stop buying, ranked by probability
- **One-click win-back** — AI writes the offer, PayPal sends it
- **Cross-sell intelligence** — spots products bought together, suggests bundles

## Tech stack

- **LLM / Agent:** Gemini Flash (google-genai SDK) with function calling; model fallback chain + template fallback so the demo never breaks
- **Backend:** FastAPI (in-memory session state, resettable via `POST /api/demo/reset`)
- **Payments:** PayPal REST **Sandbox** only: Orders v2 (create/capture), Refunds, Invoicing
- **ML:** scikit-learn GradientBoosting for delivery-delay and churn prediction; price drop, overcharge, refund and overpayment checks are plain rules (see `models/metrics.json`)
- **Product data:** Local catalog (Channel3 if viable)
- **Frontend:** React (Vite) + Tailwind + AG Grid + Recharts
- **Deploy:** Render

## Repo structure

```
backend/     FastAPI app, models wrapped as API endpoints, DB
frontend/    React + Vite app
data/        Generated datasets (merchants.csv, transactions.csv, etc.) — gitignored, see data/README
models/      ML model code + trained artifacts (joblib)
```

## Team

| Name | Area | GitHub |
| --- | --- | --- |
| Amy | Data + AI models | [@Amy-way05](https://github.com/Amy-way05) |
| Hetav | Frontend + deployment | [@rhetav](https://github.com/rhetav) |
| Sri (Koushik) | Backend + API | [@skkoushik453](https://github.com/skkoushik453) |

## Running locally

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn main:app --reload
```
- First start generates `data/` and trains the models (~30 s); later starts reuse them.
- API docs: http://localhost:8000/docs. The contract is in [API.md](API.md).
- Tests (no PayPal/Gemini calls): `python -m pytest -q`
- PayPal check: `python scripts/paypal_smoke_test.py` (creates a $1 **sandbox** order)
- To pay an order in the demo, open its `approve_url` and log in with a **sandbox personal account** (developer.paypal.com → Testing tools → Sandbox accounts), then call capture.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Status

See the team task board for full task breakdown and status. [Link it here]

## License

MIT — see [LICENSE](LICENSE)
