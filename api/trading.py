"""
Paper Trading Engine — Buy/Sell crypto with virtual INR.
Uses live CoinGecko prices. No real money involved.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional
from database.session import get_db
from database.models import User, Portfolio, Holding, Trade
from auth.deps import get_current_user
from data.coingecko import get_coin_info
from utils.logger import get_logger

log    = get_logger("trading")
router = APIRouter(prefix="/trade", tags=["Paper Trading"])

USD_TO_INR = 83.5  # Approximate rate

SUPPORTED_COINS = {
    "bitcoin":     "BTC",
    "ethereum":    "ETH",
    "solana":      "SOL",
    "binancecoin": "BNB",
    "ripple":      "XRP",
    "dogecoin":    "DOGE",
    "cardano":     "ADA",
    "polkadot":    "DOT",
    "avalanche-2": "AVAX",
    "chainlink":   "LINK",
}


class BuyRequest(BaseModel):
    coin_id:    str = Field(..., example="bitcoin")
    amount_inr: float = Field(..., gt=10, description="Amount in INR to invest")

class SellRequest(BaseModel):
    coin_id:  str   = Field(..., example="bitcoin")
    quantity: Optional[float] = Field(None, gt=0, description="Quantity to sell (None = sell all)")
    sell_pct: Optional[float] = Field(None, gt=0, le=100, description="Percentage to sell (e.g. 50 = sell half)")


@router.post("/buy")
async def buy(
    req: BuyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Buy crypto using virtual INR.
    Uses live CoinGecko price.
    Minimum order: ₹10
    """
    if req.coin_id not in SUPPORTED_COINS:
        raise HTTPException(400, f"Unsupported coin. Supported: {list(SUPPORTED_COINS.keys())}")

    # Get live price
    info = get_coin_info(req.coin_id)
    price_usd = info.get("price_usd")
    if not price_usd:
        raise HTTPException(503, "Could not fetch live price. Try again.")
    price_inr = price_usd * USD_TO_INR

    # Get portfolio
    port_result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Check balance
    if portfolio.virtual_inr < req.amount_inr:
        raise HTTPException(400, f"Insufficient balance. Available: ₹{portfolio.virtual_inr:,.2f}")

    # Calculate quantity
    quantity = req.amount_inr / price_inr

    # Deduct INR from portfolio
    portfolio.virtual_inr    -= req.amount_inr
    portfolio.total_invested += req.amount_inr

    # Update or create holding
    h_result = await db.execute(
        select(Holding).where(
            Holding.portfolio_id == portfolio.id,
            Holding.coin_id == req.coin_id
        )
    )
    holding = h_result.scalar_one_or_none()

    if holding:
        # Weighted average buy price
        total_qty   = holding.quantity + quantity
        total_cost  = holding.total_invested + req.amount_inr
        holding.avg_buy_price  = total_cost / total_qty
        holding.quantity       = total_qty
        holding.total_invested = total_cost
    else:
        holding = Holding(
            portfolio_id  = portfolio.id,
            coin_id       = req.coin_id,
            symbol        = SUPPORTED_COINS[req.coin_id],
            quantity      = quantity,
            avg_buy_price = price_inr,
            total_invested= req.amount_inr,
        )
        db.add(holding)

    # Record trade
    trade = Trade(
        portfolio_id = portfolio.id,
        coin_id      = req.coin_id,
        symbol       = SUPPORTED_COINS[req.coin_id],
        side         = "BUY",
        quantity     = quantity,
        price_inr    = price_inr,
        total_inr    = req.amount_inr,
        order_type   = "MARKET",
        status       = "FILLED",
        note         = f"Paper trade — bought at ₹{price_inr:,.2f}",
    )
    db.add(trade)
    await db.commit()

    log.info("trade.buy", user_id=current_user.id, coin=req.coin_id,
             qty=round(quantity, 8), price_inr=round(price_inr, 2), amount=req.amount_inr)

    return {
        "status":     "FILLED",
        "side":       "BUY",
        "coin_id":    req.coin_id,
        "symbol":     SUPPORTED_COINS[req.coin_id],
        "quantity":   round(quantity, 8),
        "price_inr":  round(price_inr, 2),
        "total_inr":  round(req.amount_inr, 2),
        "balance_remaining_inr": round(portfolio.virtual_inr, 2),
        "message":    f"Bought {round(quantity, 6)} {SUPPORTED_COINS[req.coin_id]} at ₹{price_inr:,.2f}",
    }


@router.post("/sell")
async def sell(
    req: SellRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sell crypto holdings for virtual INR.
    Can sell by quantity or percentage.
    """
    if req.coin_id not in SUPPORTED_COINS:
        raise HTTPException(400, f"Unsupported coin: {req.coin_id}")

    # Get live price
    info = get_coin_info(req.coin_id)
    price_usd = info.get("price_usd")
    if not price_usd:
        raise HTTPException(503, "Could not fetch live price. Try again.")
    price_inr = price_usd * USD_TO_INR

    # Get portfolio + holding
    port_result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    h_result = await db.execute(
        select(Holding).where(
            Holding.portfolio_id == portfolio.id,
            Holding.coin_id == req.coin_id
        )
    )
    holding = h_result.scalar_one_or_none()
    if not holding or holding.quantity <= 0:
        raise HTTPException(400, f"No {req.coin_id} holdings to sell")

    # Determine quantity to sell
    if req.sell_pct:
        sell_qty = holding.quantity * (req.sell_pct / 100)
    elif req.quantity:
        sell_qty = req.quantity
    else:
        sell_qty = holding.quantity  # sell all

    if sell_qty > holding.quantity:
        raise HTTPException(400, f"Insufficient holdings. Available: {holding.quantity:.8f}")

    total_inr = sell_qty * price_inr

    # Calculate PnL
    cost_basis = sell_qty * holding.avg_buy_price
    pnl        = total_inr - cost_basis
    pnl_pct    = (pnl / cost_basis * 100) if cost_basis > 0 else 0

    # Update holding
    holding.quantity -= sell_qty
    portion_ratio    = sell_qty / (holding.quantity + sell_qty)
    holding.total_invested -= holding.total_invested * portion_ratio
    if holding.quantity < 0.000001:
        holding.quantity = 0
        holding.total_invested = 0

    # Add INR back to portfolio
    portfolio.virtual_inr += total_inr
    portfolio.total_pnl   += pnl

    # Record trade
    trade = Trade(
        portfolio_id = portfolio.id,
        coin_id      = req.coin_id,
        symbol       = SUPPORTED_COINS[req.coin_id],
        side         = "SELL",
        quantity     = sell_qty,
        price_inr    = price_inr,
        total_inr    = total_inr,
        order_type   = "MARKET",
        status       = "FILLED",
        note         = f"PnL: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)",
    )
    db.add(trade)
    await db.commit()

    log.info("trade.sell", user_id=current_user.id, coin=req.coin_id,
             qty=round(sell_qty, 8), price_inr=round(price_inr, 2), pnl=round(pnl, 2))

    return {
        "status":      "FILLED",
        "side":        "SELL",
        "coin_id":     req.coin_id,
        "symbol":      SUPPORTED_COINS[req.coin_id],
        "quantity":    round(sell_qty, 8),
        "price_inr":   round(price_inr, 2),
        "total_inr":   round(total_inr, 2),
        "pnl_inr":     round(pnl, 2),
        "pnl_pct":     round(pnl_pct, 2),
        "balance_inr": round(portfolio.virtual_inr, 2),
        "message":     f"Sold {round(sell_qty, 6)} {SUPPORTED_COINS[req.coin_id]} | PnL: ₹{pnl:+,.2f}",
    }


@router.get("/prices")
async def get_prices():
    """Get live prices for all supported coins in INR."""
    prices = []
    for coin_id, symbol in SUPPORTED_COINS.items():
        info = get_coin_info(coin_id)
        price_usd = info.get("price_usd") or 0
        prices.append({
            "coin_id":        coin_id,
            "symbol":         symbol,
            "price_usd":      round(price_usd, 4),
            "price_inr":      round(price_usd * USD_TO_INR, 2),
            "change_24h_pct": round(info.get("price_change_24h") or 0, 2),
        })
    return {"prices": prices, "usd_to_inr": USD_TO_INR}


@router.get("/supported-coins")
async def supported_coins():
    """List all supported coins for paper trading."""
    return {
        "coins": [
            {"coin_id": cid, "symbol": sym}
            for cid, sym in SUPPORTED_COINS.items()
        ]
    }
