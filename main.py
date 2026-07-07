"""
CryptoSentinel FastAPI Backend — v2.0
Production: orjson responses, NaN-safe, structured logging, Prometheus metrics.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import orjson, time
from pydantic import BaseModel
from typing import Optional
from agents.orchestrator import CryptoSentinelAgent
from data.coingecko import get_top_coins, get_coin_info, get_ohlcv
from utils.logger import get_logger
from utils.serializer import safe_json_response, orjson_dumps
from utils.cache import get_cache, cache_key
from config import settings

log = get_logger("api")


class ORJSONResponse(Response):
    """NaN-safe JSON response using orjson."""
    media_type = "application/json"
    def render(self, content) -> bytes:
        return orjson_dumps(content)


app = FastAPI(
    title="CryptoSentinel API",
    description="AI-powered crypto intelligence — v2.0",
    version=settings.APP_VERSION,
    default_response_class=ORJSONResponse,
)

app.add_middleware(CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_agent: Optional[CryptoSentinelAgent] = None
_cache = None


@app.middleware("http")
async def request_logger(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    duration = round((time.monotonic() - t0) * 1000, 1)
    log.info("http.request", method=request.method, path=request.url.path,
             status=response.status_code, duration_ms=duration)
    return response


@app.on_event("startup")
async def startup():
    global _agent, _cache
    log.info("startup.begin", version=settings.APP_VERSION)
    _cache = await get_cache()
    _agent = CryptoSentinelAgent()
    log.info("startup.complete")


class AnalyzeRequest(BaseModel):
    wallet_address: str
    coin_id: str = "bitcoin"

class RAGRequest(BaseModel):
    query: str


@app.get("/")
def root():
    return {"service": "CryptoSentinel", "version": settings.APP_VERSION, "status": "running"}

@app.get("/health")
async def health():
    cache_ok = await _cache.ping() if _cache else False
    return {
        "status": "ok",
        "agent_ready": _agent is not None,
        "cache": "redis" if cache_ok else "in-memory",
        "version": settings.APP_VERSION,
    }

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not _agent:
        raise HTTPException(503, "Agent initialising, retry in 30s")
    t0 = time.monotonic()
    try:
        report = await _run_in_thread(_agent.analyze, req.wallet_address, req.coin_id)
        report["latency_seconds"] = round(time.monotonic() - t0, 2)
        return safe_json_response(report)
    except Exception as e:
        log.error("analyze.failed", error=str(e), wallet=req.wallet_address[:12])
        raise HTTPException(500, f"Analysis failed: {str(e)[:200]}")

@app.get("/market/{coin_id}")
async def market(coin_id: str):
    ck = cache_key("market", coin_id)
    cached = await _cache.get(ck)
    if cached:
        return cached
    data = get_coin_info(coin_id)
    await _cache.set(ck, data, ttl=settings.CACHE_TTL_PRICE)
    return data

@app.get("/ohlcv/{coin_id}")
async def ohlcv(coin_id: str, days: int = 30):
    ck = cache_key("ohlcv", coin_id, days)
    cached = await _cache.get(ck)
    if cached:
        return cached
    df   = get_ohlcv(coin_id, days)
    data = safe_json_response(df.tail(300).to_dict(orient="records"))
    await _cache.set(ck, data, ttl=settings.CACHE_TTL_OHLCV)
    return data

@app.get("/top-coins")
async def top_coins(n: int = 10):
    ck = cache_key("top_coins", n)
    cached = await _cache.get(ck)
    if cached:
        return cached
    data = get_top_coins(n)
    await _cache.set(ck, data, ttl=settings.CACHE_TTL_PRICE)
    return data

@app.post("/rag/query")
def rag_query(req: RAGRequest):
    if not _agent:
        raise HTTPException(503, "Agent not ready")
    return safe_json_response(_agent.rag.query(req.query))

@app.post("/rag/ingest-news")
def ingest_news(query: str = "crypto fraud bitcoin ethereum"):
    if not _agent:
        raise HTTPException(503, "Agent not ready")
    docs = _agent.rag.fetch_crypto_news(query)
    return {"ingested": len(docs), "status": "ok"}


async def _run_in_thread(fn, *args):
    import asyncio, functools
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT,
                reload=settings.DEBUG, workers=1)
