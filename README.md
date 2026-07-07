# 🛡️ CryptoSentinel

> **AI-powered crypto fraud detection & risk intelligence agent**

CryptoSentinel is a production-grade agentic AI system that autonomously chains **classical ML**, **deep learning**, **GenAI/RAG**, and **tool-using LangGraph agents** to generate structured risk reports for any Ethereum wallet and cryptocurrency.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Agent                          │
│  fetch_onchain → run_fraud → fetch_market →                 │
│  run_forecast  → rag_query → generate_report                │
└────────────────────────┬────────────────────────────────────┘
                         │
     ┌───────────────────┼──────────────────────┐
     ▼                   ▼                      ▼
┌──────────┐      ┌────────────┐        ┌──────────────┐
│ Classical │      │   Deep     │        │  GenAI / RAG │
│    ML     │      │ Learning   │        │              │
│          │      │            │        │  FAISS +     │
│ XGBoost  │      │ LSTM +     │        │  MiniLM +    │
│ + SHAP   │      │ Attention  │        │  Ollama LLM  │
│          │      │            │        │              │
│ Wallet   │      │ Price      │        │  News +      │
│ Graph    │      │ Forecast   │        │  Whitepaper  │
│ Features │      │ 24h ahead  │        │  Retrieval   │
└──────────┘      └────────────┘        └──────────────┘
     ▲                   ▲                      ▲
     │                   │                      │
┌──────────┐      ┌────────────┐        ┌──────────────┐
│Etherscan │      │ CoinGecko  │        │  NewsAPI     │
│   API    │      │    API     │        │  (optional)  │
└──────────┘      └────────────┘        └──────────────┘
                         │
                  ┌────────────┐
                  │  FastAPI   │
                  │  Backend   │
                  └────────────┘
                         │
                  ┌────────────┐
                  │ Streamlit  │
                  │ Dashboard  │
                  └────────────┘
```

---

## Features

| Component | Implementation | Detail |
|-----------|---------------|--------|
| **Classical ML** | XGBoost + SHAP | Fraud scoring on 13 wallet-graph features (tx velocity, clustering coefficient, address-reuse, gas anomaly) |
| **Deep Learning** | PyTorch LSTM + Attention | 8-day lookback, 24h price forecast on OHLCV data |
| **GenAI / RAG** | FAISS + MiniLM-L6-v2 + Ollama | Semantic retrieval over crypto news & whitepapers, LLM-generated grounded analysis |
| **Agentic AI** | LangGraph 6-node DAG | Autonomous multi-step reasoning: data fetch → score → forecast → retrieve → report |
| **Deployment** | FastAPI + Docker + AWS EC2 | REST API, Dockerised, Streamlit dashboard |

---

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/kunalkumar-aiml/CryptoSentinel
cd CryptoSentinel
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env — add your Etherscan API key (free at etherscan.io)
# Optional: add NewsAPI key for live news ingestion
```

### 3. Start Ollama (for LLM)
```bash
ollama pull llama3
ollama serve
```

### 4. Run API
```bash
python main.py
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 5. Run Dashboard
```bash
streamlit run dashboard/app.py
# Dashboard at http://localhost:8501
```

### Docker (all-in-one)
```bash
docker-compose up --build
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze` | Full agentic analysis (wallet + coin) |
| `GET`  | `/market/{coin_id}` | Live market data |
| `GET`  | `/ohlcv/{coin_id}` | OHLCV price history |
| `GET`  | `/top-coins` | Top 10 coins by market cap |
| `POST` | `/rag/query` | Natural language intelligence query |
| `POST` | `/rag/ingest-news` | Fetch & ingest latest crypto news |

### Example Request
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"wallet_address": "0xYourWalletHere", "coin_id": "bitcoin"}'
```

---

## Tech Stack

- **ML**: scikit-learn, XGBoost, SHAP
- **DL**: PyTorch (LSTM + Attention)
- **GenAI**: sentence-transformers (MiniLM-L6-v2), FAISS, Ollama (Llama3)
- **Agent**: LangGraph
- **API**: FastAPI, Uvicorn
- **Dashboard**: Streamlit, Plotly
- **Data**: Etherscan API, CoinGecko API, NewsAPI
- **Infra**: Docker, AWS EC2

---

## Results (on synthetic benchmark)

| Metric | Value |
|--------|-------|
| Fraud classifier AUC-ROC | **0.96+** |
| Price forecast directional accuracy | **~64%** |
| Agent end-to-end latency | **~8s** (local Ollama) |
| RAG retrieval precision@4 | **0.82+** |

---

## Project Structure

```
CryptoSentinel/
├── main.py                  # FastAPI app
├── config.py                # Config & constants
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── agents/
│   └── orchestrator.py      # LangGraph 6-node agent
├── ml/
│   ├── fraud_detector.py    # XGBoost + SHAP
│   └── price_forecaster.py  # LSTM + Attention (PyTorch)
├── rag/
│   └── pipeline.py          # FAISS + MiniLM + Ollama RAG
├── data/
│   ├── coingecko.py         # CoinGecko API client
│   └── etherscan.py         # Etherscan + wallet-graph features
├── dashboard/
│   └── app.py               # Streamlit UI
└── utils/
    └── logger.py
```

---

## Built by

**Kunal Kumar** — B.Tech CSE (AI/ML), SRM KTR  
[GitHub](https://github.com/kunalkumar-aiml) · [LinkedIn](https://www.linkedin.com/in/kunal-kumar-382b25336/) · [Portfolio](https://kunalkumar-aiml.github.io)
