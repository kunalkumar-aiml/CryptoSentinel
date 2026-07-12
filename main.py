from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import time
from pydantic import BaseModel
from typing import Optional

from database.session import create_tables, AsyncSessionLocal
from auth.router import router as auth_router
from api.portfolio import router as portfolio_router
from api.trading import router as trading_router
from api.automation import router as automation_router
from api.scheduler import run_scheduler
from data.coingecko import get_top_coins, get_coin_info, get_ohlcv
from utils.logger import get_logger
from utils.serializer import safe_json_response, orjson_dumps
from utils.cache import get_cache, cache_key
from config import settings

log = get_logger("api")

class ORJSONResponse(Response):
    media_type = "application/json"
    def render(self, content) -> bytes:
        return orjson_dumps(content)

_agent = None
_cache = None
_scheduler_task = None

async def _load_agent_background():
    global _agent
    try:
        from agents.orchestrator import CryptoSentinelAgent
        _agent = CryptoSentinelAgent()
        log.info("agent.ready")
    except Exception as e:
        log.error("agent.load_failed", error=str(e))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache, _scheduler_task
    log.info("startup.begin", version=settings.APP_VERSION)
    await create_tables()
    _cache = await get_cache()
    # Load agent in background so Railway doesn't timeout
    asyncio.create_task(_load_agent_background())
    _scheduler_task = asyncio.create_task(run_scheduler(AsyncSessionLocal))
    log.info("startup.complete")
    yield
    if _scheduler_task:
        _scheduler_task.cancel()
    log.info("shutdown")

app = FastAPI(
    title="CryptoSentinel API",
    version=settings.APP_VERSION,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)
app.include_router(portfolio_router)
app.include_router(trading_router)
app.include_router(automation_router)

@app.middleware("http")
async def request_logger(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    ms = round((time.monotonic() - t0) * 1000, 1)
    log.info("http", method=request.method, path=request.url.path,
             status=response.status_code, ms=ms)
    return response

class AnalyzeRequest(BaseModel):
    wallet_address: str
    coin_id: str = "bitcoin"

class RAGRequest(BaseModel):
    query: str

@app.get("/")
def root():
    return {
        "service": "CryptoSentinel",
        "version": settings.APP_VERSION,
        "status": "running",
        "agent": "ready" if _agent else "loading"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent_ready": _agent is not None,
        "version": settings.APP_VERSION,
    }

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not _agent:
        raise HTTPException(503, "Agent still loading, retry in 60 seconds")
    t0 = time.monotonic()
    try:
        report = await _run_in_thread(_agent.analyze, req.wallet_address, req.coin_id)
        report["latency_seconds"] = round(time.monotonic() - t0, 2)
        return safe_json_response(report)
    except Exception as e:
        log.error("analyze.failed", error=str(e))
        raise HTTPException(500, str(e)[:200])

@app.get("/market/{coin_id}")
async def market(coin_id: str):
    ck = cache_key("market", coin_id)
    cached = await _cache.get(ck)
    if cached: return cached
    data = get_coin_info(coin_id)
    await _cache.set(ck, data, ttl=30)
    return data

@app.get("/ohlcv/{coin_id}")
async def ohlcv(coin_id: str, days: int = 30):
    ck = cache_key("ohlcv", coin_id, days)
    cached = await _cache.get(ck)
    if cached: return cached
    df   = get_ohlcv(coin_id, days)
    data = safe_json_response(df.tail(300).to_dict(orient="records"))
    await _cache.set(ck, data, ttl=300)
    return data

@app.get("/top-coins")
async def top_coins(n: int = 10):
    ck = cache_key("top_coins", n)
    cached = await _cache.get(ck)
    if cached: return cached
    data = get_top_coins(n)
    await _cache.set(ck, data, ttl=30)
    return data

@app.post("/rag/query")
def rag_query(req: RAGRequest):
    if not _agent:
        raise HTTPException(503, "Agent still loading")
    return safe_json_response(_agent.rag.query(req.query))

async def _run_in_thread(fn, *args):
    import functools
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT, reload=False)
