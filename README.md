# Nexus by PayPal

An AI agent that saves you money before, during, and after every purchase, and gives merchants the intelligence to keep customers coming back. Only PayPal sees both sides of the transaction. We built on that.

**Live app:** https://paypal-shopping-agent-web.onrender.com
**API docs:** https://paypal-shopping-agent-api.onrender.com/docs

Built for the PayPal AI Hackathon — November 2026.

## The problem

PayPal processes $1.79 trillion a year but the product experience ends the moment money moves. Users open PayPal at checkout and close it. There is no reason to come back. Meanwhile, overcharges show up on roughly 8% of transactions, price drops within a week hit about 15%, and about 5% of requested refunds never actually arrive. PayPal has the data to catch all of these. Nobody is using it.

## What it does

**Buyer side**

- **Better Deal Before You Pay** — finds the same product cheaper at a better-rated merchant before you checkout
- **Save For It** — auto-saves weekly toward a goal, watches the price, surfaces Pay in 4 and coupons when the price drops
- **Post-Purchase Guardian** — catches price drops ($18 Instant Pot recovery), flags overcharges ($12.40 Denim Jacket), predicts delivery delays (87% risk), tracks overdue refunds
- **Savings Dashboard** — running total of everything recovered, computed from real model output

**Merchant side**

- **Churn Risk Dashboard** — ranks at-risk customers by probability in a sortable, filterable AG Grid table
- **One-click Win-back** — AI writes personalized offers, PayPal sends them as invoices
- **Cross-sell Intelligence** — surfaces products bought together with suggested bundle discounts

## How PayPal and AI are used

**PayPal Sandbox** runs through every flow. Orders v2 creates and captures payments in Better Deal. The Disputes API files claims for overcharges and escalates overdue refunds. Invoicing v2 sends AI-generated win-back offers to at-risk customers. Agent Pass enforces user spending rules before any transaction executes.

**Gemini Flash Lite** powers the AI agent through direct function calling via the google-genai SDK. Two **GradientBoosting models** (scikit-learn) predict delivery delays (AUC 0.80) and customer churn (AUC 0.76). Four rule-based detectors handle price drops, overcharges, overpayment comparison, and refund tracking.

## Tech stack

- **AI agent:** Gemini Flash Lite, direct function calling (no LangChain)
- **ML models:** scikit-learn GradientBoostingClassifier, pandas, NumPy
- **Backend:** FastAPI, Python
- **Payments:** PayPal Sandbox (Orders v2, Disputes, Invoicing v2)
- **Frontend:** React (Vite) + TypeScript + Tailwind + AG Grid + Recharts
- **Deploy:** Render (frontend static site + backend web service)

## Repo structure

## Running locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add PayPal + Gemini keys
cd ../models
python generate_data.py --out ../data
python train.py --data-dir ../data
cd ../backend
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To run with sample data (no backend needed), set `VITE_USE_MOCKS=true`.

### Demo reset

To reset demo state between walkthroughs: `POST /api/demo/reset` at the API docs URL.

## Team

| Name | Area | GitHub |
| --- | --- | --- |
| Amrutha Ravikumar | Data + AI models | [@Amy-way05](https://github.com/Amy-way05) |
| Hetav Raval | Frontend + deployment | [@rhetav](https://github.com/rhetav) |
| Sri Krishna Koushik | Backend + API | [@skkoushik453](https://github.com/skkoushik453) |

## Sponsor tools

- **AG Grid** — merchant churn table with custom cell renderers, probability bars, tier badges, row grouping, filtering, pinned summary row, CSV export
- **Render** — deployment (frontend static site, backend web service)

## License

MIT — see [LICENSE](LICENSE)
