"""
Automation Engine — Phase 4
Users create rules like:
  "Buy BTC when price drops below ₹50,00,000"
  "Sell ETH if profit reaches 20%"
  "Buy ₹500 of BTC every Monday"
Rules are stored in PostgreSQL and checked by a background scheduler.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional
from database.session import get_db
from database.models import User, AutomationRule
from auth.deps import get_current_user
from utils.logger import get_logger

log    = get_logger("automation")
router = APIRouter(prefix="/automation", tags=["Automation"])

SUPPORTED_COINS = [
    "bitcoin","ethereum","solana","binancecoin","ripple",
    "dogecoin","cardano","polkadot","avalanche-2","chainlink"
]
RULE_TYPES = ["price_below","price_above","profit_pct","loss_pct","recurring"]
ACTIONS    = ["buy","sell"]
INTERVALS  = ["daily","weekly","monthly"]


class RuleRequest(BaseModel):
    coin_id:       str   = Field(..., example="bitcoin")
    rule_type:     str   = Field(..., example="price_below",
                                  description="price_below|price_above|profit_pct|loss_pct|recurring")
    action:        str   = Field(..., example="buy", description="buy|sell")
    trigger_value: float = Field(..., example=5000000.0,
                                  description="Price in INR / profit% / loss% / amount")
    amount_inr:    float = Field(..., gt=10, example=5000.0,
                                  description="INR amount to buy/sell on trigger")
    interval:      Optional[str] = Field(None, example="weekly",
                                          description="For recurring: daily|weekly|monthly")
    note:          Optional[str] = Field(None, example="Buy BTC dip strategy")


@router.post("/rules", status_code=201)
async def create_rule(
    req: RuleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    if req.coin_id not in SUPPORTED_COINS:
        raise HTTPException(400, f"Unsupported coin: {req.coin_id}")
    if req.rule_type not in RULE_TYPES:
        raise HTTPException(400, f"Invalid rule_type. Use: {RULE_TYPES}")
    if req.action not in ACTIONS:
        raise HTTPException(400, f"Invalid action. Use: {ACTIONS}")
    if req.rule_type == "recurring" and req.interval not in INTERVALS:
        raise HTTPException(400, f"Recurring rules need interval: {INTERVALS}")

    rule = AutomationRule(
        user_id       = current_user.id,
        coin_id       = req.coin_id,
        rule_type     = req.rule_type,
        action        = req.action,
        trigger_value = req.trigger_value,
        amount_inr    = req.amount_inr,
        interval      = req.interval,
        note          = req.note or _auto_description(req),
        is_active     = True,
        times_triggered = 0,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    log.info("automation.rule_created", user_id=current_user.id,
             coin=req.coin_id, type=req.rule_type)

    return {
        "id":            rule.id,
        "status":        "active",
        "description":   rule.note,
        "coin_id":       rule.coin_id,
        "rule_type":     rule.rule_type,
        "action":        rule.action,
        "trigger_value": rule.trigger_value,
        "amount_inr":    rule.amount_inr,
        "created_at":    rule.created_at.isoformat(),
    }


@router.get("/rules")
async def get_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all automation rules for the current user."""
    result = await db.execute(
        select(AutomationRule)
        .where(AutomationRule.user_id == current_user.id)
        .order_by(AutomationRule.created_at.desc())
    )
    rules = result.scalars().all()
    return {
        "rules": [_rule_dict(r) for r in rules],
        "total": len(rules),
        "active": sum(1 for r in rules if r.is_active),
    }


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an automation rule."""
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.user_id == current_user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "rule_id": rule_id}


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause or resume an automation rule."""
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.user_id == current_user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    rule.is_active = not rule.is_active
    await db.commit()
    status = "active" if rule.is_active else "paused"
    log.info("automation.rule_toggled", rule_id=rule_id, status=status)
    return {"rule_id": rule_id, "status": status}


@router.get("/logs")
async def get_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get automation execution logs."""
    from database.models import AutomationLog
    result = await db.execute(
        select(AutomationLog)
        .where(AutomationLog.user_id == current_user.id)
        .order_by(AutomationLog.executed_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id":          l.id,
                "rule_id":     l.rule_id,
                "coin_id":     l.coin_id,
                "action":      l.action,
                "amount_inr":  round(l.amount_inr, 2),
                "price_inr":   round(l.price_inr, 2),
                "status":      l.status,
                "message":     l.message,
                "executed_at": l.executed_at.isoformat(),
            }
            for l in logs
        ]
    }


def _rule_dict(r: "AutomationRule") -> dict:
    return {
        "id":              r.id,
        "coin_id":         r.coin_id,
        "rule_type":       r.rule_type,
        "action":          r.action,
        "trigger_value":   r.trigger_value,
        "amount_inr":      r.amount_inr,
        "interval":        r.interval,
        "note":            r.note,
        "is_active":       r.is_active,
        "times_triggered": r.times_triggered,
        "last_triggered":  r.last_triggered.isoformat() if r.last_triggered else None,
        "created_at":      r.created_at.isoformat(),
    }


def _auto_description(req: RuleRequest) -> str:
    coin = req.coin_id.capitalize()
    amt  = f"₹{req.amount_inr:,.0f}"
    val  = req.trigger_value
    if req.rule_type == "price_below":
        return f"{req.action.upper()} {amt} of {coin} when price drops below ₹{val:,.0f}"
    if req.rule_type == "price_above":
        return f"{req.action.upper()} {amt} of {coin} when price rises above ₹{val:,.0f}"
    if req.rule_type == "profit_pct":
        return f"SELL {amt} of {coin} when profit reaches {val:.1f}%"
    if req.rule_type == "loss_pct":
        return f"SELL {amt} of {coin} when loss exceeds {val:.1f}% (stop loss)"
    if req.rule_type == "recurring":
        return f"BUY {amt} of {coin} every {req.interval}"
    return f"{req.action.upper()} {amt} of {coin}"
