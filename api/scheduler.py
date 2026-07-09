"""
Automation Scheduler — checks rules every 60 seconds.
Runs as a background asyncio task inside FastAPI lifespan.
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from database.models import AutomationRule, AutomationLog, Portfolio, Holding, Trade
from data.coingecko import get_coin_info
from utils.logger import get_logger

log = get_logger("scheduler")

USD_TO_INR = 83.5
SYMBOLS = {
    "bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB",
    "ripple":"XRP","dogecoin":"DOGE","cardano":"ADA","polkadot":"DOT",
    "avalanche-2":"AVAX","chainlink":"LINK",
}


async def run_scheduler(session_factory: async_sessionmaker):
    """Background task — runs forever, checks rules every 60s."""
    log.info("scheduler.started")
    while True:
        try:
            await asyncio.sleep(60)
            await _check_all_rules(session_factory)
        except asyncio.CancelledError:
            log.info("scheduler.stopped")
            break
        except Exception as e:
            log.error("scheduler.error", error=str(e))


async def _check_all_rules(session_factory: async_sessionmaker):
    async with session_factory() as db:
        result = await db.execute(
            select(AutomationRule).where(AutomationRule.is_active == True)
        )
        rules = result.scalars().all()
        if not rules:
            return

        log.info("scheduler.checking", rules=len(rules))
        for rule in rules:
            try:
                await _evaluate_rule(rule, db)
            except Exception as e:
                log.error("scheduler.rule_error", rule_id=rule.id, error=str(e))
        await db.commit()


async def _evaluate_rule(rule: AutomationRule, db: AsyncSession):
    """Evaluate a single rule against live price."""
    info      = get_coin_info(rule.coin_id)
    price_usd = info.get("price_usd")
    if not price_usd:
        return
    price_inr = price_usd * USD_TO_INR
    now       = datetime.utcnow()

    triggered = False

    if rule.rule_type == "price_below" and price_inr < rule.trigger_value:
        triggered = True

    elif rule.rule_type == "price_above" and price_inr > rule.trigger_value:
        triggered = True

    elif rule.rule_type == "profit_pct":
        holding = await _get_holding(rule.user_id, rule.coin_id, db)
        if holding and holding.avg_buy_price > 0:
            pnl_pct = (price_inr - holding.avg_buy_price) / holding.avg_buy_price * 100
            if pnl_pct >= rule.trigger_value:
                triggered = True

    elif rule.rule_type == "loss_pct":
        holding = await _get_holding(rule.user_id, rule.coin_id, db)
        if holding and holding.avg_buy_price > 0:
            loss_pct = (holding.avg_buy_price - price_inr) / holding.avg_buy_price * 100
            if loss_pct >= rule.trigger_value:
                triggered = True

    elif rule.rule_type == "recurring":
        if _should_trigger_recurring(rule, now):
            triggered = True

    if not triggered:
        return

    # Execute the trade
    status, message = await _execute_rule(rule, price_inr, db)

    # Update rule
    rule.times_triggered += 1
    rule.last_triggered   = now

    # Deactivate one-time rules after trigger
    if rule.rule_type not in ("recurring",):
        rule.is_active = False

    # Log execution
    log_entry = AutomationLog(
        rule_id    = rule.id,
        user_id    = rule.user_id,
        coin_id    = rule.coin_id,
        action     = rule.action,
        amount_inr = rule.amount_inr,
        price_inr  = price_inr,
        status     = status,
        message    = message,
    )
    db.add(log_entry)
    log.info("automation.triggered", rule_id=rule.id, coin=rule.coin_id,
             action=rule.action, status=status, price_inr=round(price_inr,2))


async def _execute_rule(rule: AutomationRule, price_inr: float, db: AsyncSession):
    """Execute buy or sell for an automation rule."""
    try:
        port_result = await db.execute(
            select(Portfolio).where(Portfolio.user_id == rule.user_id)
        )
        portfolio = port_result.scalar_one_or_none()
        if not portfolio:
            return "failed", "Portfolio not found"

        symbol = SYMBOLS.get(rule.coin_id, rule.coin_id.upper())

        if rule.action == "buy":
            if portfolio.virtual_inr < rule.amount_inr:
                return "failed", f"Insufficient balance ₹{portfolio.virtual_inr:,.0f}"

            qty = rule.amount_inr / price_inr
            portfolio.virtual_inr    -= rule.amount_inr
            portfolio.total_invested += rule.amount_inr

            h_res = await db.execute(
                select(Holding).where(
                    Holding.portfolio_id == portfolio.id,
                    Holding.coin_id == rule.coin_id
                )
            )
            holding = h_res.scalar_one_or_none()
            if holding:
                total_qty  = holding.quantity + qty
                total_cost = holding.total_invested + rule.amount_inr
                holding.avg_buy_price  = total_cost / total_qty
                holding.quantity       = total_qty
                holding.total_invested = total_cost
            else:
                holding = Holding(
                    portfolio_id   = portfolio.id,
                    coin_id        = rule.coin_id,
                    symbol         = symbol,
                    quantity       = qty,
                    avg_buy_price  = price_inr,
                    total_invested = rule.amount_inr,
                )
                db.add(holding)

            trade = Trade(
                portfolio_id = portfolio.id,
                coin_id      = rule.coin_id,
                symbol       = symbol,
                side         = "BUY",
                quantity     = qty,
                price_inr    = price_inr,
                total_inr    = rule.amount_inr,
                order_type   = "AUTOMATION",
                status       = "FILLED",
                note         = f"Auto: {rule.note}",
            )
            db.add(trade)
            return "success", f"Bought {qty:.6f} {symbol} at ₹{price_inr:,.0f}"

        elif rule.action == "sell":
            h_res = await db.execute(
                select(Holding).where(
                    Holding.portfolio_id == portfolio.id,
                    Holding.coin_id == rule.coin_id
                )
            )
            holding = h_res.scalar_one_or_none()
            if not holding or holding.quantity <= 0:
                return "failed", "No holdings to sell"

            qty      = min(rule.amount_inr / price_inr, holding.quantity)
            proceeds = qty * price_inr
            pnl      = proceeds - (qty * holding.avg_buy_price)

            holding.quantity -= qty
            if holding.quantity < 0.000001:
                holding.quantity = 0
            portfolio.virtual_inr += proceeds
            portfolio.total_pnl   += pnl

            trade = Trade(
                portfolio_id = portfolio.id,
                coin_id      = rule.coin_id,
                symbol       = symbol,
                side         = "SELL",
                quantity     = qty,
                price_inr    = price_inr,
                total_inr    = proceeds,
                order_type   = "AUTOMATION",
                status       = "FILLED",
                note         = f"Auto: {rule.note} | PnL ₹{pnl:+,.0f}",
            )
            db.add(trade)
            return "success", f"Sold {qty:.6f} {symbol} at ₹{price_inr:,.0f} | PnL ₹{pnl:+,.0f}"

    except Exception as e:
        return "failed", str(e)

    return "failed", "Unknown action"


async def _get_holding(user_id: int, coin_id: str, db: AsyncSession):
    port_res = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))
    portfolio = port_res.scalar_one_or_none()
    if not portfolio:
        return None
    h_res = await db.execute(
        select(Holding).where(
            Holding.portfolio_id == portfolio.id,
            Holding.coin_id == coin_id
        )
    )
    return h_res.scalar_one_or_none()


def _should_trigger_recurring(rule: AutomationRule, now: datetime) -> bool:
    """Check if recurring rule should fire based on interval."""
    if not rule.last_triggered:
        return True  # Never triggered before — fire now
    delta = now - rule.last_triggered
    if rule.interval == "daily"   and delta >= timedelta(days=1):   return True
    if rule.interval == "weekly"  and delta >= timedelta(weeks=1):  return True
    if rule.interval == "monthly" and delta >= timedelta(days=30):  return True
    return False
