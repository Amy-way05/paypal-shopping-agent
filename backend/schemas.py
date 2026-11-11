"""Request bodies (pydantic). Field names match API.md v0.2."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PaymentOption = Literal["pay_now", "pay_in_4", "pay_monthly_6"]


class BetterDealRequest(BaseModel):
    buyer_id: str
    product_name: str = Field(min_length=1)
    price: float = Field(gt=0)
    category: str
    merchant_name: Optional[str] = None
    merchant_id: Optional[str] = None


class GoalCreate(BaseModel):
    buyer_id: str
    product_name: str = Field(min_length=1)
    product_id: Optional[str] = None
    category: str
    target_price: float = Field(gt=0)
    weekly_amount: float = Field(gt=0)


class GoalPurchase(BaseModel):
    payment_option: PaymentOption = "pay_now"
    confirmed: bool = False


class SimulateWeek(BaseModel):
    weeks: int = Field(default=1, ge=1, le=52)


class AgentPassUpdate(BaseModel):
    autonomous_enabled: Optional[bool] = None
    autonomous_claims: Optional[bool] = None
    auto_approve_limit: Optional[float] = Field(default=None, ge=0, le=200)
    max_unplanned_purchase: Optional[float] = Field(default=None, ge=0)
    max_daily_spend: Optional[float] = Field(default=None, ge=0)
    monthly_limit: Optional[float] = Field(default=None, ge=0)
    blocked_categories: Optional[List[str]] = None
    approved_merchants: Optional[List[str]] = None


class AgentPassCheck(BaseModel):
    buyer_id: str
    amount: float = Field(ge=0)
    category: str
    merchant_id: Optional[str] = None
    action: Literal["purchase", "claim"] = "purchase"
    planned: bool = False


class OrderCreate(BaseModel):
    buyer_id: str
    product_id: Optional[str] = None
    product_name: str = Field(min_length=1)
    merchant_id: Optional[str] = None
    category: str
    amount: float = Field(gt=0)
    original_price: Optional[float] = Field(default=None, gt=0)
    payment_option: PaymentOption = "pay_now"
    source: Literal["better_deal", "save_for_it", "agent", "direct"] = "direct"
    goal_id: Optional[str] = None
    confirmed: bool = False


class ClaimRequest(BaseModel):
    confirmed: bool = False


class SendOffer(BaseModel):
    merchant_id: str
    customer_id: str
    discount_pct: Optional[int] = Field(default=None, ge=1, le=90)


class OfferOutcome(BaseModel):
    outcome: Literal["redeemed", "opened", "ignored"]
    order_amount: Optional[float] = Field(default=None, ge=0)


class AgentChat(BaseModel):
    buyer_id: str
    message: str = Field(min_length=1)
    session_id: Optional[str] = None
