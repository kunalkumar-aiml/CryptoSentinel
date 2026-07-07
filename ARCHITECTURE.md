# CryptoSentinel — Technical Architecture Blueprint
## From Portfolio Project → Production SaaS

---

## Phase 1 (NOW — 4 weeks): Fix & Harden Core
**Goal: Stable, deployed, demo-able to investors**

### What's fixed in v2.0:
- ✅ CoinGecko 429 → Retry + Cache + CoinCap fallback
- ✅ Etherscan V1 → V2 migration
- ✅ NaN/Inf JSON bug → orjson + clean_value()
- ✅ fillcolor hex bug → rgba() everywhere
- ✅ Ollama → Groq (llama3-70b-8192)
- ✅ Production logging (structlog JSON)
- ✅ Redis cache (in-memory fallback for local dev)
- ✅ Pydantic v2 settings management

### Deployment (Phase 1):
```
Railway.app (free tier)
├── FastAPI (main.py) — $5/mo
├── Redis — Railway plugin free
└── PostgreSQL — Railway plugin free

Frontend: Streamlit (temporary, lives at localhost:8501)
```

---

## Phase 2 (Weeks 5-10): Multi-User SaaS
**Goal: Real users, auth, paper trading**

### New Components:
```
auth/
├── models.py       — User, Session, ApiKey (SQLAlchemy)
├── router.py       — /auth/register, /auth/login, /auth/refresh
├── jwt.py          — Access + refresh token logic
└── oauth.py        — Google + GitHub OAuth (via Authlib)

portfolio/
├── models.py       — Portfolio, Position, Trade, PnL
├── router.py       — /portfolio/*, /paper-trade/*
├── engine.py       — Paper trading engine (fills at market price)
└── pnl.py          — Real-time PnL calculation

database/
├── session.py      — Async SQLAlchemy session
└── migrations/     — Alembic migrations
```

### Database Schema (PostgreSQL):
```sql
users           (id, email, username, password_hash, created_at, plan)
portfolios      (id, user_id, name, cash_balance, created_at)
positions       (id, portfolio_id, coin_id, quantity, avg_cost, opened_at)
trades          (id, portfolio_id, coin_id, side, quantity, price, fee, timestamp)
alerts          (id, user_id, coin_id, condition, threshold, channel, is_active)
agent_reports   (id, user_id, wallet, coin, report_json, created_at)
```

### Tech Stack additions:
- **Auth**: python-jose (JWT) + passlib (bcrypt) + Authlib (OAuth)
- **DB**: SQLAlchemy 2.0 async + Alembic
- **Queue**: Celery + Redis (background agent jobs)
- **WebSocket**: FastAPI WebSocket for live price streaming

---

## Phase 3 (Weeks 11-18): Multi-Agent Company
**Goal: 10+ specialized agents running autonomously**

### Agent Architecture (Celery tasks):
```
agents/
├── orchestrator.py     — LangGraph CEO agent (already built)
├── market_agent.py     — Live price + volume + orderbook
├── tech_analysis.py    — RSI, MACD, EMA, VWAP, Bollinger
├── news_agent.py       — CoinDesk, CoinTelegraph, Bloomberg RSS
├── sentiment_agent.py  — Twitter/X + Reddit sentiment (VADER + BERT)
├── whale_agent.py      — Large wallet tracking, exchange flows
├── risk_agent.py       — Position sizing, stop-loss, drawdown
├── execution_agent.py  — Paper trade execution
├── notification_agent.py — Email + Telegram + Discord alerts
└── scheduler.py        — Celery beat periodic tasks
```

### Message Flow:
```
User Input / Schedule
        ↓
[Redis Queue]
        ↓
[Celery Worker] picks up task
        ↓
[Orchestrator Agent] — LangGraph
        ↓
[Specialized Agents] run in parallel
        ↓
[Results stored in PostgreSQL]
        ↓
[WebSocket] pushes to frontend
        ↓
[Notification Agent] sends alerts
```

### Why Celery over direct calls:
- Direct calls: if agent takes 30s, API request blocks, user times out
- Celery: user gets task_id instantly, polls for result, agents run async
- Celery scales horizontally (add workers on demand)
- Celery Beat = cron for background agent runs (every 5 min market check)

---

## Phase 4 (Weeks 19-28): Next.js Frontend
**Goal: Professional SaaS UI, TradingView-level quality**

### Frontend Architecture:
```
frontend/ (Next.js 14, App Router)
├── app/
│   ├── (auth)/          — login, register, OAuth callback
│   ├── dashboard/       — main trading dashboard
│   ├── portfolio/       — holdings, PnL, history
│   ├── agents/          — agent status, reports
│   ├── research/        — RAG chat interface
│   └── settings/        — alerts, API keys, profile
├── components/
│   ├── charts/          — Lightweight Charts (TradingView library)
│   ├── agents/          — Agent cards, status indicators
│   └── ui/              — Design system (shadcn/ui)
├── lib/
│   ├── api.ts           — API client (fetch wrapper)
│   └── websocket.ts     — Real-time price socket
└── stores/
    └── portfolio.ts     — Zustand state management
```

### Chart library: **Lightweight Charts by TradingView** (free, MIT)
- NOT Plotly — Plotly is too slow for real-time trading UI
- Lightweight Charts renders 100k candles at 60fps
- TradingView-quality out of the box

---

## Phase 5 (Weeks 29+): Scale & Monetize
**Goal: Real SaaS, paying users**

### Pricing Tiers:
| Plan | Price | Features |
|------|-------|---------|
| Free | ₹0 | 1 portfolio, 3 alerts, 5 AI queries/day |
| Pro | ₹999/mo | Unlimited portfolio, 50 alerts, 100 AI queries, paper trading |
| Institutional | ₹4999/mo | API access, unlimited agents, custom strategies, priority |

### Infrastructure at Scale:
```
Users: 1-100        → Railway (current)
Users: 100-1000     → AWS EC2 t3.medium + RDS + ElastiCache
Users: 1000-10000   → ECS Fargate (auto-scale) + Aurora + Redis Cluster
Users: 10000+       → Kubernetes + CDN + Read replicas
```

### Data at Scale (why Binance WebSocket, not CoinGecko polling):
- CoinGecko free: 30 req/min → useless for 1000 users polling simultaneously
- Binance WebSocket: one persistent connection → unlimited real-time ticks
- For Phase 3+, build a dedicated **market data service** that:
  1. Connects to Binance WS once
  2. Fans out to all users via Redis Pub/Sub
  3. Cost: 0 API calls, infinite scale

---

## Security Checklist (implement before public launch)
- [ ] Rate limiting per user (slowapi)
- [ ] Input validation (Pydantic everywhere)
- [ ] SQL injection prevention (SQLAlchemy ORM only, no raw SQL)
- [ ] API key encryption at rest (not stored in plaintext)
- [ ] HTTPS only (handled by Railway/Vercel/Nginx)
- [ ] JWT refresh token rotation
- [ ] Audit log for every trade/agent action
- [ ] Secrets in environment variables only (no .env in git)

---

## What NOT to build (mistakes to avoid)

1. **Don't build your own exchange** — paper trading uses our price engine, real trading uses CCXT library (connects to 100+ exchanges)
2. **Don't use Streamlit for production SaaS** — no auth, no real-time WebSocket, not scalable. Use it only for internal demo
3. **Don't call OpenAI/Groq directly from agents** — wrap in LLMClient with retry + fallback + rate limit tracking
4. **Don't store secrets in code** — even "demo" keys. Use .env + python-decouple
5. **Don't skip database migrations** — use Alembic from day 1, even if small

---

## Immediate Next Steps (this week)
1. Push v2.0 to GitHub (fixed bugs)
2. Deploy to Railway (free): `railway up`
3. Add Groq key to Railway env vars
4. Test `/analyze` endpoint with a real Ethereum wallet
5. Share deployed URL — this is your demo link for internship applications
