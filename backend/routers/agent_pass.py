"""Agent Pass endpoints (API.md section 4) + helpers other routers use
to gate every order and claim."""
from fastapi import APIRouter

import mock_data as m
from errors import api_error
from schemas import AgentPassCheck, AgentPassUpdate
from services import agent_pass as ap

router = APIRouter(prefix="/api/agent-pass", tags=["Agent Pass"])


# ---- helpers (storage is in-memory # MOCK until Step 4) ----

def get_rules(buyer_id):
    if buyer_id not in m.STATE["rules"]:
        m.STATE["rules"][buyer_id] = m.clone(ap.DEFAULT_RULES)
    return m.STATE["rules"][buyer_id]


def get_spend(buyer_id):
    return m.STATE["spend"].setdefault(buyer_id, {"today": 0.0, "month": 0.0})


def record_spend(buyer_id, amount):
    s = get_spend(buyer_id)
    s["today"] = round(s["today"] + amount, 2)
    s["month"] = round(s["month"] + amount, 2)


def log_action(buyer_id, action, amount, category, merchant_name, decision, reason):
    m.STATE["actions"].setdefault(buyer_id, []).insert(0, {
        "action_id": m.new_id("AP_"), "action": action, "amount": round(amount, 2),
        "category": category, "merchant_name": merchant_name, "decision": decision,
        "reason": reason, "timestamp": m.now_iso(),
    })


def run_check(buyer_id, amount, category, merchant_id=None, action="purchase", planned=False):
    rules = get_rules(buyer_id)
    spend = get_spend(buyer_id)
    decision, reason = ap.decide(rules, amount, category, merchant_id, action, planned,
                                 spend["today"], spend["month"])
    return {
        "decision": decision,
        "reason": reason,
        "remaining_today": round(max(rules["max_daily_spend"] - spend["today"], 0), 2),
        "remaining_this_month": round(max(rules["monthly_limit"] - spend["month"], 0), 2),
    }


def enforce(buyer_id, amount, category, merchant_id=None, merchant_name=None,
            action="purchase", planned=False, confirmed=False):
    """Gate a real action. BLOCK -> 403, NEEDS_CONFIRMATION (unconfirmed) -> 409.
    Returns the agent_pass dict to include in the response."""
    check = run_check(buyer_id, amount, category, merchant_id, action, planned)
    decision, reason = check["decision"], check["reason"]
    log_action(buyer_id, action, amount, category, merchant_name or merchant_id, decision, reason)

    if decision == ap.BLOCK:
        raise api_error(403, "AGENT_PASS_BLOCKED", reason, decision=decision, reason=reason)
    if decision == ap.NEEDS_CONFIRMATION:
        if not confirmed:
            raise api_error(409, "NEEDS_CONFIRMATION", reason, decision=decision, reason=reason)
        return {"decision": ap.APPROVE, "reason": "User confirmed"}
    return {"decision": decision, "reason": reason}


def _rules_view(buyer_id):
    spend = get_spend(buyer_id)
    return {"buyer_id": buyer_id, **m.clone(get_rules(buyer_id)),
            "spent_today": spend["today"], "spent_this_month": spend["month"]}


# ---- endpoints ----

@router.post("/check")
def check(body: AgentPassCheck):
    return run_check(body.buyer_id, body.amount, body.category, body.merchant_id, body.action, body.planned)


@router.get("/{buyer_id}")
def get_agent_pass(buyer_id: str):
    return _rules_view(buyer_id)


@router.put("/{buyer_id}")
def update_agent_pass(buyer_id: str, body: AgentPassUpdate):
    get_rules(buyer_id).update(body.model_dump(exclude_none=True))
    return _rules_view(buyer_id)


@router.get("/{buyer_id}/actions")
def get_actions(buyer_id: str):
    actions = m.STATE["actions"].get(buyer_id, [])
    if not actions:
        return {"actions": [], "message": "No agent actions yet. Your agent will log every decision here."}
    return {"actions": actions[:50]}
