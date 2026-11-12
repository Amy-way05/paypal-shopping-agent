"""AI agent chat (API.md section 8).

Gemini function calling over the same tools the app uses (better deal, Agent
Pass, PayPal orders, savings, Guardian, Save For It). Every purchase still
goes through Agent Pass. If Gemini is down, a simple intent router runs the
same tools and answers with a template, so the demo never breaks.
"""
import re

from fastapi import APIRouter, HTTPException

import state as m
from errors import api_error
from routers import buyer
from routers.agent_pass import run_check
from routers.orders import create_order_internal
from schemas import AgentChat, OrderCreate
from services import llm
from services import models_adapter as data

router = APIRouter(prefix="/api/agent", tags=["Agent"])

SYSTEM = """You are Nexus, PayPal's shopping agent, working for buyer {buyer_id}. You save the buyer money.
Rules:
- Use the tools for every fact and number. Never invent prices, merchants or amounts.
- When the user mentions something they want to buy with a price, call find_better_deal first.
- To buy, call buy_item. It runs Agent Pass. If it says needs_confirmation, ask the user to confirm;
  if blocked, explain the reason. Never claim an order exists unless buy_item returned an order_id.
- A created order must be approved by the buyer in PayPal (approve_url) before it's paid.
- Keep replies to 2-3 short sentences, plain text, dollar amounts with 2 decimals."""


class Toolbox:
    """Tools bound to one buyer + one request. Records calls and UI cards."""

    def __init__(self, buyer_id):
        self.buyer_id = buyer_id
        self.calls, self.cards, self.pending, self._memo = [], [], None, {}

    def _once(self, key, fn):
        # Gemini may retry on another model; never run a side effect twice per request.
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    def find_better_deal(self, product_name: str, price: float, category: str = "", merchant_name: str = "") -> dict:
        """Find the same product cheaper at a trusted merchant. category: electronics, home, apparel,
        beauty, sporting_goods, books, toys, grocery, furniture or pet_supplies (empty if unsure)."""
        def run():
            from schemas import BetterDealRequest
            cat = category or self._guess_category(product_name)
            r = buyer.find_better_deal(BetterDealRequest(
                buyer_id=self.buyer_id, product_name=product_name, price=price, category=cat,
                merchant_name=merchant_name or None))
            if r["alternatives"]:
                b = r["alternatives"][0]
                self.cards.append({"type": "better_deal", "data": {
                    "your_pick": r["your_pick"], "best_option": b, "potential_savings": r["potential_savings"]}})
                self._log("find_better_deal",
                          f"Best option ${b['price']:,.2f} at {b['merchant_name']} (save ${b['savings']:,.2f})")
            else:
                self._log("find_better_deal", r["agent_message"])
            return {"best": r["alternatives"][0] if r["alternatives"] else None,
                    "category": data.normalize_category(cat), "network": r["network"],
                    "agent_pass": r["agent_pass"], "note": r["agent_message"]}
        return self._once(("deal", product_name, price), run)

    def check_agent_pass(self, amount: float, category: str, planned: bool = False) -> dict:
        """Check the buyer's spending rules for an amount before buying."""
        c = run_check(self.buyer_id, amount, data.normalize_category(category), planned=planned)
        self._log("check_agent_pass", f"{c['decision']}: {c['reason']}")
        return c

    def buy_item(self, product_name: str, price: float, category: str, merchant_id: str = "",
                 merchant_name: str = "", original_price: float = 0.0) -> dict:
        """Create a PayPal order for the buyer (runs Agent Pass first). original_price is what the
        buyer was going to pay before the agent found the deal (0 if none)."""
        def run():
            body = OrderCreate(buyer_id=self.buyer_id, product_name=product_name, merchant_id=merchant_id or None,
                               category=data.normalize_category(category), amount=price,
                               original_price=original_price or None, source="agent")
            try:
                o = create_order_internal(body, merchant_name=merchant_name or None)
            except HTTPException as e:
                d = e.detail
                self._log("check_agent_pass", f"{d.get('decision', d['code'])}: {d.get('reason', d['message'])}")
                if d["code"] == "NEEDS_CONFIRMATION":
                    self.pending = {"tool": "create_order", "reason": d["reason"],
                                    "args": {**body.model_dump(), "confirmed": True}}
                    return {"needs_confirmation": d["reason"]}
                if d["code"] == "AGENT_PASS_BLOCKED":
                    return {"blocked": d["reason"]}
                return {"error": d["message"]}
            self._log("check_agent_pass", f"{o['agent_pass']['decision']}: {o['agent_pass']['reason']}")
            self._log("create_order", f"{o['paypal_mode'].title()} order {o['order_id']} created")
            self.cards.append({"type": "order", "data": {k: o[k] for k in (
                "order_id", "status", "approve_url", "amount", "payment_option", "paypal_mode")}})
            return {"order_id": o["order_id"], "status": o["status"], "amount": o["amount"],
                    "approve_url": o["approve_url"]}
        # at most one order per message, even if Gemini retries or the template fallback runs after it
        return self._once(("buy",), run)

    def get_savings(self) -> dict:
        """The buyer's savings report: total saved, this month, breakdown by type."""
        s = buyer.get_savings(self.buyer_id)
        self._log("get_savings", f"${s['total_saved']:,.2f} saved in total")
        self.cards.append({"type": "savings", "data": {k: s[k] for k in ("total_saved", "this_month", "breakdown")}})
        return {k: s[k] for k in ("total_saved", "this_month", "breakdown")}

    def check_my_purchases(self) -> dict:
        """Post-purchase Guardian: price drops, overcharges, late deliveries, overdue refunds."""
        alerts = data.active_alerts(self.buyer_id)
        total = round(sum(a["recoverable_amount"] for a in alerts), 2)
        self._log("check_my_purchases", f"{len(alerts)} issues, ${total:,.2f} recoverable")
        self.cards.append({"type": "guardian", "data": {"alerts": alerts, "total_recoverable": total}})
        return {"issues": [{k: a.get(k) for k in ("type", "title", "details", "recoverable_amount")}
                           for a in alerts], "total_recoverable": total}

    def list_goals(self) -> dict:
        """The buyer's Save For It goals with progress and status."""
        goals = buyer.list_goals(self.buyer_id)["goals"]
        self._log("list_goals", f"{len(goals)} goals")
        for g in goals:
            self.cards.append({"type": "goal", "data": g})
        return {"goals": [{k: g[k] for k in ("goal_id", "product_name", "final_price", "saved_so_far",
                                             "status", "agent_message")} for g in goals]}

    def create_savings_goal(self, product_name: str, target_price: float, weekly_amount: float,
                            category: str = "") -> dict:
        """Start a Save For It goal: auto-save weekly_amount and watch the price and coupons."""
        def run():
            g = buyer.create_goal_internal(self.buyer_id, product_name,
                                           category or self._guess_category(product_name), target_price, weekly_amount)
            self._log("create_savings_goal", f"Goal {g['goal_id']}: {g['weeks_remaining']} weeks to go")
            self.cards.append({"type": "goal", "data": g})
            return {k: g[k] for k in ("goal_id", "final_price", "weeks_remaining", "status", "agent_message")}
        # at most one new goal per message (same reason as buy_item)
        return self._once(("goal",), run)

    # ---- helpers
    def tools(self):
        return [self.find_better_deal, self.check_agent_pass, self.buy_item, self.get_savings,
                self.check_my_purchases, self.list_goals, self.create_savings_goal]

    def _log(self, tool, summary):
        self.calls.append({"tool": tool, "summary": summary})

    @staticmethod
    def _guess_category(product_name):
        name = data.resolve_product(product_name)
        if name:
            return next(p["category"] for p in data._products() if p["product_name"] == name)
        return "general"


# ------------------------------------------------------------ fallback

def _fallback(tb, message):
    """No LLM available: route by intent, run the same tools, template the reply."""
    text = message.lower()
    price = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", message) or re.search(r"(\d+(?:\.\d{1,2})?)\s?(?:dollars|usd)", text)
    if price:
        amount = float(price.group(1))
        product = re.sub(r"\$\s?\d+(\.\d+)?|\b(for|at|is|it's|buy|i want|want|to|a|an|the|find|me|cheaper|"
                         r"deal|on|some|new|please|can you|get)\b", " ", text, flags=re.I)
        product = re.sub(r"\s+", " ", product).strip(" ?.!,") or "item"
        if re.search(r"\bsave\b|\bgoal\b|saving", text):
            g = tb.create_savings_goal(product, amount, 50.0)
            return g["agent_message"]
        d = tb.find_better_deal(product, amount)
        b = d["best"]
        if not b:
            return d["note"]
        reply = (f"Found the same {b['product_name']} for ${b['price']:,.2f} at {b['merchant_name']} "
                 f"(rated {b['rating']}/10, {b['delivery_days']}-day delivery). That's ${b['savings']:,.2f} less.")
        o = tb.buy_item(b["product_name"], b["price"], d["category"], b["merchant_id"], b["merchant_name"], amount)
        if "order_id" in o:
            return reply + " It's within your Agent Pass limits, so I've created the order: approve it in PayPal."
        if "needs_confirmation" in o:
            return reply + f" {o['needs_confirmation']}. Want me to go ahead?"
        return reply + f" I didn't buy it: {o.get('blocked') or o.get('error')}."
    if re.search(r"refund|late|overcharg|price drop|scan|purchases|guardian", text):
        r = tb.check_my_purchases()
        return (f"I found {len(r['issues'])} issues on your recent purchases, "
                f"${r['total_recoverable']:,.2f} recoverable. I'm on it.")
    if re.search(r"goal|saving for|save for", text):
        g = tb.list_goals()["goals"]
        return g[0]["agent_message"] if g else "No goals yet. Tell me what you're saving for and your weekly amount."
    if re.search(r"sav|how much", text):
        s = tb.get_savings()
        return f"I've saved you ${s['total_saved']:,.2f} so far, ${s['this_month']:,.2f} this month."
    return ("Tell me what you're buying and the price (\"insoles for $24\"), ask about your savings, "
            "or say \"check my purchases\".")


@router.post("/chat")
def chat(body: AgentChat):
    buyer._require_buyer(body.buyer_id)
    if not body.message.strip():
        raise api_error(400, "BAD_REQUEST", "message: Say something to the agent")
    session_id = body.session_id or m.new_id("CH_")
    tb = Toolbox(body.buyer_id)
    history = m.STATE["chats"].get(session_id, [])
    result = llm.run_tools(SYSTEM.format(buyer_id=body.buyer_id), history, body.message, tb.tools())
    if result:
        reply, source, new_history = result
        m.STATE["chats"][session_id] = new_history[-30:]
    else:
        reply, source = _fallback(tb, body.message), "template"
    return {
        "session_id": session_id,
        "reply": reply,
        "reply_source": source,
        "tool_calls": tb.calls,
        "cards": tb.cards,
        "pending_confirmation": tb.pending,
    }
