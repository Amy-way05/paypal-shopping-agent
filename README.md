# PayPal Shopping Agent — [final app name once decided]

> Apple Pay pays. PayPal shops for you.

An AI agent that works before, during, and after every purchase — finding better deals, recovering money automatically, and giving merchants intelligence only PayPal's two-sided data can provide.

Built for [Hackathon name] — [dates].

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

- **LLM / Agent:** Gemini 2.0 Flash, direct function calling
- **Backend:** FastAPI + SQLite + SQLAlchemy
- **Payments:** PayPal Sandbox + Agent Toolkit
- **ML:** scikit-learn (Isolation Forest, logistic regression, random forest)
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
| [name] | Backend + API | |
| [name] | Frontend | |

## Running locally

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn main:app --reload
```

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
