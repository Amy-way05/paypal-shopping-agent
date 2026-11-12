"""Bridge between the API and Amrutha's models/ package.

Her modules read the generated CSV/JSON in data/ and return dicts; this file
  * makes sure data + trained models exist (generates/trains on first start,
    because both are gitignored),
  * caches results (the data is static for a run),
  * reshapes outputs into the API.md field names.

Every number here comes from data/ or from her models. Nothing is hardcoded.
"""
import functools
import json
import os
import re
import statistics
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO / "models"
DATA_DIR = Path(os.getenv("DATA_DIR") or REPO / "data")
DELAY_MODEL = MODELS_DIR / "delay_model.joblib"
CHURN_MODEL = MODELS_DIR / "churn_model.joblib"

if str(MODELS_DIR) not in sys.path:
    sys.path.insert(0, str(MODELS_DIR))

# The synthetic dataset's "today" (generate_data.TODAY). Ages and windows are
# measured against it so the demo looks the same whatever day it runs.
DATA_TODAY = date(2026, 11, 9)
ACTIVE_WINDOW_DAYS = 30   # Guardian shows purchases from the last 30 days
REFUND_WINDOW_DAYS = 60   # ...and refunds requested in the last 60

CATEGORY_ALIASES = {
    "sports": "sporting_goods", "sport": "sporting_goods", "fitness": "sporting_goods",
    "fashion": "apparel", "clothing": "apparel", "clothes": "apparel", "shoes": "apparel",
    "kitchen": "home", "appliances": "home", "tech": "electronics", "audio": "electronics",
    "pets": "pet_supplies", "pet": "pet_supplies", "food": "grocery", "toy": "toys", "book": "books",
}


# ------------------------------------------------------------ bootstrap

def ensure_ready():
    """Generate the dataset and train the two ML models if they're missing."""
    if not (DATA_DIR / "transactions.csv").exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "generate_data.py", "--out", str(DATA_DIR)],
                       cwd=MODELS_DIR, check=True)
    if not DELAY_MODEL.exists():
        import delay_predictor
        delay_predictor.train(data_dir=str(DATA_DIR), model_path=str(DELAY_MODEL))
    if not CHURN_MODEL.exists():
        import churn_predictor
        churn_predictor.train(data_dir=str(DATA_DIR), model_path=str(CHURN_MODEL))


# ------------------------------------------------------------ raw data

@functools.lru_cache(maxsize=None)
def _txns():
    return pd.read_csv(DATA_DIR / "transactions.csv", parse_dates=["purchase_date"])


@functools.lru_cache(maxsize=None)
def _merchants():
    return pd.read_csv(DATA_DIR / "merchants.csv").set_index("merchant_id")


@functools.lru_cache(maxsize=None)
def _products():
    with open(DATA_DIR / "products.json") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def _coupons():
    with open(DATA_DIR / "coupons.json") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def _price_changes():
    return pd.read_csv(DATA_DIR / "price_changes.csv", parse_dates=["change_date"])


@functools.lru_cache(maxsize=None)
def metrics():
    p = MODELS_DIR / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else {}


def normalize_category(category):
    c = (category or "").strip().lower().replace(" ", "_")
    return CATEGORY_ALIASES.get(c, c)


def merchant(merchant_id):
    """Merchant profile with a 0-10 trust rating computed from on-time and dispute rates."""
    m = _merchants()
    if merchant_id not in m.index:
        return None
    r = m.loc[merchant_id]
    rating = round(10 * (0.7 * r.on_time_rate + 0.3 * max(0.0, 1 - r.dispute_rate * 10)), 1)
    return {"merchant_id": merchant_id, "merchant_name": r.merchant_name, "category": r.category,
            "rating": rating, "delivery_days": int(r.avg_delivery_days),
            "dispute_rate": float(r.dispute_rate), "on_time_rate": float(r.on_time_rate)}


def merchant_id_by_name(name):
    if not name:
        return None
    m = _merchants()
    hit = m[m.merchant_name.str.lower() == name.strip().lower()]
    return hit.index[0] if len(hit) else None


def buyer_exists(buyer_id):
    return bool((_txns().customer_id == buyer_id).any())


@functools.lru_cache(maxsize=None)
def customer_name(customer_id):
    """Synthetic display name, stable per customer id (the dataset has no names)."""
    from faker import Faker
    f = Faker()
    f.seed_instance(int(re.sub(r"\D", "", customer_id) or 0))
    return f.name()


# ------------------------------------------------------------ catalog

def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2}


def resolve_product(product_name, category=None):
    """Map free text ("sony headphones") to a catalog product name, or None."""
    names = sorted({p["product_name"] for p in _products()
                    if not category or p["category"] == category})
    q = product_name.strip().lower()
    for n in names:
        if n.lower() == q:
            return n
    for n in names:
        if q in n.lower() or n.lower() in q:
            return n
    qt = _tokens(product_name)
    best, best_score = None, 0
    for n in names:
        score = len(qt & _tokens(n))
        if score > best_score:
            best, best_score = n, score
    if best and (best_score >= 2 or (best_score == 1 and len(qt) == 1)):
        return best
    return None if category is None else resolve_product(product_name, None)


def catalog_listing(product_name):
    """Cheapest current listing + price history for a catalog product."""
    rows = [p for p in _products() if p["product_name"] == product_name]
    if not rows:
        return None
    cheapest = min(rows, key=lambda p: p["price"])
    ids = {p["product_id"] for p in rows}
    pc = _price_changes()
    pc = pc[pc.product_id.isin(ids)].sort_values("change_date")
    history = [{"date": r.change_date.date().isoformat(), "price": round(float(r.new_price), 2)}
               for r in pc.itertuples()]
    prices = [p["price"] for p in rows] + [h["price"] for h in history]
    m = merchant(cheapest["merchant_id"]) or {}
    return {"product_id": cheapest["product_id"], "product_name": product_name,
            "category": cheapest["category"], "price": round(cheapest["price"], 2),
            "merchant_id": cheapest["merchant_id"], "merchant_name": m.get("merchant_name"),
            "all_time_low": round(min(prices), 2), "price_history": history[-6:]}


def best_coupon(category, price, merchant_id):
    """Highest-value unexpired coupon this merchant offers for this category."""
    today = DATA_TODAY.isoformat()
    best = None
    for c in _coupons():
        if c["category"] != category or c["expires"] < today or c["merchant_id"] != merchant_id:
            continue
        discount = round(price * c["discount_pct"] / 100, 2)
        if not best or discount > best["discount"]:
            best = {"code": c["code"], "description": f"{c['discount_pct']}% off {category.replace('_', ' ')}",
                    "discount": discount, "discount_pct": c["discount_pct"], "expires": c["expires"],
                    "merchant_id": c["merchant_id"]}
    return best


# ------------------------------------------------------------ better deal

def better_deal(product_name, price, category, merchant_id=None):
    """Amrutha's overpayment comparator, limited to the SAME product at other stores."""
    import overpayment
    cat = normalize_category(category)
    resolved = resolve_product(product_name, cat)
    if resolved:
        cat = next(p["category"] for p in _products() if p["product_name"] == resolved)
    res = overpayment.run(cat, float(price), data_dir=str(DATA_DIR),
                          product_name=resolved, exclude_merchant_id=merchant_id)
    alts = []
    for a in res["alternatives"]:
        if a["product_name"] != resolved:
            continue  # her fallback returns other products in the category; not a "same item" deal
        m = merchant(a["merchant_id"]) or {}
        alts.append({**a, "price": round(a["price"], 2), "rating": m.get("rating"),
                     "delivery_days": m.get("delivery_days")})
    alts.sort(key=lambda a: a["price"])
    network = res["network"]
    if resolved:
        # "typical price" = what this same product sells for across the network, not the whole category
        prices = sorted(p["price"] for p in _products() if p["product_name"] == resolved)
        median = float(statistics.median(prices))
        network = {"median_price": round(median, 2),
                   "percentile": int(round(100 * sum(1 for x in prices if x < float(price)) / len(prices))),
                   "overpaying": bool(float(price) > median)}
    return {"network": network, "alternatives": alts[:3], "matched_product": resolved,
            "category": cat}


# ------------------------------------------------------------ guardian

def _iso(d):
    return pd.Timestamp(d).date().isoformat()


def _age(d):
    return (DATA_TODAY - pd.Timestamp(d).date()).days


def _late_deliveries(buyer_id):
    """RULE: promised N days, it's now past day N and the order hasn't arrived."""
    t = _txns()
    t = t[(t.customer_id == buyer_id)]
    out = []
    for r in t.itertuples():
        age = _age(r.purchase_date)
        if age > ACTIVE_WINDOW_DAYS:
            continue
        if r.delivery_promised_days < age <= r.delivery_actual_days:
            m = merchant(r.merchant_id) or {}
            promised = pd.Timestamp(r.purchase_date).date() + timedelta(days=int(r.delivery_promised_days))
            out.append({
                "transaction_id": r.transaction_id, "type": "delivery_delay",
                "title": f"Your {r.product_name} is late",
                "details": (f"Promised {r.delivery_promised_days}-day delivery. "
                            f"Day {age}, nothing has arrived."),
                "merchant_id": r.merchant_id, "merchant_name": m.get("merchant_name"),
                "product_name": r.product_name, "purchase_date": _iso(r.purchase_date),
                "amount_paid": round(float(r.amount_charged), 2), "promised_date": promised.isoformat(),
                "days_late": age - int(r.delivery_promised_days), "recoverable_amount": 0.0,
            })
    return out


@functools.lru_cache(maxsize=None)
def _all_findings(buyer_id):
    import overcharge
    import price_drop
    import refund_tracker
    d = str(DATA_DIR)
    found = price_drop.run(buyer_id, data_dir=d) + overcharge.run(buyer_id, data_dir=d)
    found += refund_tracker.run(buyer_id, data_dir=d)
    found += _late_deliveries(buyer_id)
    return found


@functools.lru_cache(maxsize=None)
def _delay_risk(buyer_id):
    """Amrutha's ML delay model: transaction_id -> probability of a late delivery."""
    import delay_predictor
    try:
        preds = delay_predictor.run(buyer_id, data_dir=str(DATA_DIR), model_path=str(DELAY_MODEL))
    except Exception:
        return {}
    return {p["transaction_id"]: p["delay_probability"] for p in preds}


ACTIONS = {
    "price_drop": ("Auto price-match requested. You did nothing.", "Price-match request filed with {m}."),
    "overcharge": ("Flagged and auto-disputed.", "Overcharge dispute filed with {m}."),
    "delivery_delay": ("Auto-contacted merchant.", "We've contacted {m} about your order."),
    "late_refund": ("Agent auto-escalated.", "Refund escalated with {m}."),
}


def active_alerts(buyer_id):
    """Recent findings the Guardian acts on (the live scan)."""
    out = []
    risk = _delay_risk(buyer_id)
    for f in _all_findings(buyer_id):
        age = _age(f["purchase_date"])
        window = REFUND_WINDOW_DAYS if f["type"] == "late_refund" else ACTIVE_WINDOW_DAYS
        if age > window:
            continue
        if f["type"] == "late_refund" and f.get("refund_status") != "never_received":
            continue  # it arrived (late); nothing left to recover
        a = {k: v for k, v in f.items() if k != "refund_status"}
        a["alert_id"] = f"AL_{f['transaction_id'][2:]}{f['type'][0].upper()}"
        a["recoverable_amount"] = round(float(a.get("recoverable_amount") or 0), 2)
        a["action_taken"] = ACTIONS[f["type"]][0]
        a["recovery_method"] = "simulated" if a["recoverable_amount"] else None
        a["paypal_reference"] = None
        if f["type"] == "delivery_delay" and f["transaction_id"] in risk:
            a["delay_probability"] = risk[f["transaction_id"]]  # ML score, shown as context only
        out.append(a)
    order = ["price_drop", "overcharge", "delivery_delay", "late_refund"]
    out.sort(key=lambda a: (order.index(a["type"]), a["purchase_date"]), reverse=False)
    return out


def history(buyer_id):
    """Older price drops / overcharges in the synthetic history, treated as already
    recovered by the agent (they're the agent's past work in the dataset).
    Late refunds are NOT counted: that's the buyer's own money, not a saving."""
    out = []
    cats = _txns().set_index("transaction_id")["category"]
    for f in _all_findings(buyer_id):
        if f["type"] not in ("price_drop", "overcharge") or _age(f["purchase_date"]) <= ACTIVE_WINDOW_DAYS:
            continue
        out.append({"type": f["type"], "amount": round(float(f["recoverable_amount"]), 2),
                    "date": f["purchase_date"], "item": f["product_name"],
                    "merchant_name": f["merchant_name"], "title": f["title"],
                    "transaction_id": f["transaction_id"], "category": cats.get(f["transaction_id"])})
    return out


def category_of(transaction_id):
    cats = _txns().set_index("transaction_id")["category"]
    return cats.get(transaction_id)


def buyer_spend(buyer_id, days=30):
    """Spend in the last `days` of the dataset, by category and merchant."""
    t = _txns()
    t = t[(t.customer_id == buyer_id) &
          (t.purchase_date >= pd.Timestamp(DATA_TODAY - timedelta(days=days)))]
    by_cat = t.groupby("category")["amount_charged"].sum().sort_values(ascending=False)
    by_m = t.groupby("merchant_id")["amount_charged"].sum().sort_values(ascending=False)
    top = None
    if len(by_m):
        top = {"merchant_id": by_m.index[0], "merchant_name": (merchant(by_m.index[0]) or {}).get("merchant_name"),
               "amount": round(float(by_m.iloc[0]), 2)}
    month = t[t.purchase_date >= pd.Timestamp(DATA_TODAY.replace(day=1))]
    return {"total": round(float(t.amount_charged.sum()), 2),
            "this_month": round(float(month.amount_charged.sum()), 2),
            "by_category": {k: round(float(v), 2) for k, v in by_cat.items()},
            "top_merchant": top, "count": int(len(t))}


def purchases_watched(buyer_id, days=90):
    t = _txns()
    return int(((t.customer_id == buyer_id) &
                (t.purchase_date >= pd.Timestamp(DATA_TODAY - timedelta(days=days)))).sum())


# ------------------------------------------------------------ merchant

@functools.lru_cache(maxsize=None)
def churn(merchant_id):
    import churn_predictor
    rows = churn_predictor.run(merchant_id, data_dir=str(DATA_DIR), model_path=str(CHURN_MODEL),
                               min_risk="low")
    for r in rows:
        r["customer_name"] = customer_name(r["customer_id"])
        r["avg_order_value"] = round(r["total_spend"] / max(r["order_count"], 1), 2)
    return rows


@functools.lru_cache(maxsize=None)
def cross_sell(merchant_id):
    import cross_sell as xs
    rows = xs.run(merchant_id, data_dir=str(DATA_DIR))
    pretty = lambda c: c.replace("_", " ").title()  # noqa: E731
    return [{"product_a": pretty(r["category_a"]), "product_b": pretty(r["category_b"]), **r}
            for r in rows]


def warm_up():
    """Load data + run the slow models once at startup so the first request is fast."""
    from state import DEMO_BUYER, DEMO_MERCHANT
    active_alerts(DEMO_BUYER)
    churn(DEMO_MERCHANT)
    cross_sell(DEMO_MERCHANT)
