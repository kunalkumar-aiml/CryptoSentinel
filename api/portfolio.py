"""
Portfolio API — GET holdings, PnL, balance, trade history.
All endpoints are protected (JWT required).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.session import get_db
from database.models import User, Portfolio, Holding, Trade
from auth.deps import get_current_user
from data.coingecko import get_coin_info
from utils.logger import get_logger

log    = get_logger("portfolio")
router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("/")
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full portfolio — balance + holdings + PnL."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Get all holdings
    h_result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio.id)
    )
    holdings = h_result.scalars().all()

    # Enrich with live prices
    holdings_data = []
    total_current_value = 0.0
    total_invested = 0.0

    for h in holdings:
        if h.quantity <= 0:
            continue
        info = get_coin_info(h.coin_id)
        price_inr = (info.get("price_usd") or 0) * 83.5  # USD to INR
        current_value = h.quantity * price_inr
        invested      = h.total_invested
        pnl           = current_value - invested
        pnl_pct       = (pnl / invested * 100) if invested > 0 else 0

        total_current_value += current_value
        total_invested      += invested

        holdings_data.append({
            "coin_id":      h.coin_id,
            "symbol":       h.symbol,
            "quantity":     round(h.quantity, 8),
            "avg_buy_price":round(h.avg_buy_price, 2),
            "current_price":round(price_inr, 2),
            "invested_inr": round(invested, 2),
            "current_value":round(current_value, 2),
            "pnl_inr":      round(pnl, 2),
            "pnl_pct":      round(pnl_pct, 2),
        })

    total_pnl     = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    net_worth     = portfolio.virtual_inr + total_current_value

    return {
        "user":      {"id": current_user.id, "name": current_user.name},
        "balance": {
            "virtual_inr":       round(portfolio.virtual_inr, 2),
            "total_invested_inr":round(total_invested, 2),
            "current_value_inr": round(total_current_value, 2),
            "net_worth_inr":     round(net_worth, 2),
            "total_pnl_inr":     round(total_pnl, 2),
            "total_pnl_pct":     round(total_pnl_pct, 2),
        },
        "holdings": sorted(holdings_data, key=lambda x: x["current_value"], reverse=True),
    }


@router.get("/trades")
async def get_trades(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get trade history — latest 50 trades."""
    port_result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    t_result = await db.execute(
        select(Trade)
        .where(Trade.portfolio_id == portfolio.id)
        .order_by(Trade.created_at.desc())
        .limit(limit)
    )
    trades = t_result.scalars().all()

    return {
        "trades": [
            {
                "id":         t.id,
                "coin_id":    t.coin_id,
                "symbol":     t.symbol,
                "side":       t.side,
                "quantity":   round(t.quantity, 8),
                "price_inr":  round(t.price_inr, 2),
                "total_inr":  round(t.total_inr, 2),
                "order_type": t.order_type,
                "status":     t.status,
                "timestamp":  t.created_at.isoformat(),
            }
            for t in trades
        ],
        "total": len(trades),
    }


@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick summary — balance + trade count."""
    port_result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    trade_count = await db.execute(
        select(Trade).where(Trade.portfolio_id == portfolio.id)
    )
    trades = trade_count.scalars().all()

    return {
        "virtual_inr":   round(portfolio.virtual_inr, 2),
        "total_trades":  len(trades),
        "total_invested":round(portfolio.total_invested, 2),
        "total_pnl":     round(portfolio.total_pnl, 2),
    }
