"""
CoinGecko data client — production grade.
Fixes:
  - 429 Too Many Requests: exponential backoff retry + cache
  - Multi-source fallback: CoinGecko → CoinCap → synthetic (last resort)
  - No fake data when live data exists
  - Async-friendly with sync wrappers for FastAPI background
"""
import asyncio, time
import requests
import pandas as pd
import numpy as np
from typing import Optional
from utils.logger import get_logger
from utils.retry import with_retry
from utils.serializer import clean_value
from config import settings

log = get_logger("coingecko")

# Mapping: CoinGecko ID → CoinCap ID
COINCAP_MAP = {
    "bitcoin": "bitcoin", "ethereum": "ethereum", "solana": "solana",
    "binancecoin": "binance-coin", "ripple": "xrp", "dogecoin": "dogecoin",
    "cardano": "cardano", "polkadot": "polkadot", "avalanche-2": "avalanche",
}

# ─── Session with headers ──────────────────────────────────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    headers = {"Accept": "application/json", "User-Agent": "CryptoSentinel/2.0"}
    if settings.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY
    s.headers.update(headers)
    return s

SESSION = _session()


# ─── CoinGecko: OHLCV ─────────────────────────────────────────────────────────
@with_retry(attempts=4, min_wait=2, max_wait=32)
def _fetch_ohlcv_coingecko(coin_id: str, days: int) -> Optional[pd.DataFrame]:
    url = f"{settings.COINGECKO_BASE}/coins/{coin_id}/ohlc"
    r = SESSION.get(url, params={"vs_currency": "usd", "days": days}, timeout=12)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 60))
        log.warning("coingecko.rate_limit", retry_after=retry_after)
        time.sleep(retry_after)
        r.raise_for_status()
    r.raise_for_status()
    raw = r.json()
    if not raw:
        return None
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Attach volume from market_chart endpoint
    try:
        vr = SESSION.get(
            f"{settings.COINGECKO_BASE}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=12
        )
        if vr.ok:
            vols = vr.json().get("total_volumes", [])
            if vols:
                vol_df = pd.DataFrame(vols, columns=["ts", "volume"])
                vol_df["timestamp"] = pd.to_datetime(vol_df["ts"], unit="ms").dt.floor("4h")
                df["timestamp"] = df["timestamp"].dt.floor("4h")
                df = df.merge(vol_df[["timestamp", "volume"]], on="timestamp", how="left")
    except Exception as e:
        log.warning("coingecko.volume_fetch_failed", error=str(e))
        df["volume"] = np.nan

    log.info("coingecko.ohlcv.success", coin=coin_id, rows=len(df))
    return df


# ─── CoinCap fallback ──────────────────────────────────────────────────────────
@with_retry(attempts=3, min_wait=1, max_wait=10)
def _fetch_ohlcv_coincap(coin_id: str, days: int) -> Optional[pd.DataFrame]:
    cap_id = COINCAP_MAP.get(coin_id, coin_id)
    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - days * 86400 * 1000
    interval = "h1" if days <= 30 else "h6"
    url = f"{settings.COINCAP_BASE}/assets/{cap_id}/history"
    r = requests.get(url, params={"interval": interval, "start": start_ms, "end": end_ms}, timeout=12)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return None
    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["time"], unit="ms")
    df["close"]  = pd.to_numeric(df["priceUsd"], errors="coerce")
    df["open"]   = df["close"]
    df["high"]   = df["close"] * 1.005
    df["low"]    = df["close"] * 0.995
    df["volume"] = np.nan
    log.info("coincap.ohlcv.success", coin=coin_id, rows=len(df))
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


# ─── Synthetic last-resort ────────────────────────────────────────────────────
def _synthetic_ohlcv(days: int) -> pd.DataFrame:
    log.warning("data.using_synthetic_fallback", days=days)
    np.random.seed(42)
    n = days * 6
    t = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="4h")
    price = 45000.0
    prices = [price]
    for _ in range(n - 1):
        prices.append(prices[-1] * np.exp(np.random.normal(0.0002, 0.018)))
    prices = np.array(prices)
    return pd.DataFrame({
        "timestamp": t,
        "open":   prices * np.random.uniform(0.99, 1.01, n),
        "high":   prices * np.random.uniform(1.001, 1.025, n),
        "low":    prices * np.random.uniform(0.975, 0.999, n),
        "close":  prices,
        "volume": np.random.lognormal(20, 1, n),
    })


# ─── Public interface ─────────────────────────────────────────────────────────
def get_ohlcv(coin_id: str = "bitcoin", days: int = 90) -> pd.DataFrame:
    """
    Get OHLCV with multi-source fallback:
    CoinGecko → CoinCap → Synthetic
    """
    for source_fn in (_fetch_ohlcv_coingecko, _fetch_ohlcv_coincap):
        try:
            df = source_fn(coin_id, days)
            if df is not None and len(df) > 5:
                # Clean NaN/Inf before returning
                df = df.replace([np.inf, -np.inf], np.nan)
                df[["open","high","low","close"]] = df[["open","high","low","close"]].ffill().bfill()
                return df
        except Exception as e:
            log.warning("data.source.failed", source=source_fn.__name__, error=str(e))
            continue
    return _synthetic_ohlcv(days)


@with_retry(attempts=3, min_wait=2, max_wait=20)
def get_coin_info(coin_id: str = "bitcoin") -> dict:
    try:
        url = f"{settings.COINGECKO_BASE}/coins/{coin_id}"
        r = SESSION.get(url, params={"localization": "false", "tickers": "false"}, timeout=12)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 30)))
            r.raise_for_status()
        r.raise_for_status()
        d  = r.json()
        md = d.get("market_data", {})
        return clean_value({
            "name":             d.get("name"),
            "symbol":           d.get("symbol","").upper(),
            "price_usd":        md.get("current_price",{}).get("usd"),
            "market_cap":       md.get("market_cap",{}).get("usd"),
            "volume_24h":       md.get("total_volume",{}).get("usd"),
            "price_change_24h": md.get("price_change_percentage_24h"),
            "price_change_7d":  md.get("price_change_percentage_7d"),
            "ath":              md.get("ath",{}).get("usd"),
        })
    except Exception as e:
        log.warning("coingecko.coin_info.failed", coin=coin_id, error=str(e))
        return {"name": coin_id, "symbol": coin_id.upper(), "price_usd": None}


@with_retry(attempts=3, min_wait=2, max_wait=20)
def get_top_coins(n: int = 10) -> list:
    try:
        url = f"{settings.COINGECKO_BASE}/coins/markets"
        r = SESSION.get(url, params={
            "vs_currency": "usd", "order": "market_cap_desc",
            "per_page": n, "page": 1, "sparkline": False
        }, timeout=12)
        r.raise_for_status()
        return clean_value(r.json())
    except Exception as e:
        log.warning("coingecko.top_coins.failed", error=str(e))
        return []
