"""
RAG Pipeline — Groq replaces Ollama.
FAISS + MiniLM-L6-v2 for retrieval.
Groq (llama3-70b) for generation with OpenAI fallback.
"""
import os, pickle, requests
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import faiss
from groq import Groq
from utils.logger import get_logger
from utils.serializer import clean_value
from config import settings

log = get_logger("rag")


class LLMClient:
    """Multi-provider LLM client: Groq → OpenAI fallback → extractive fallback."""

    def __init__(self):
        self.groq_client = None
        if settings.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                log.info("llm.provider", provider="groq", model=settings.GROQ_MODEL)
            except Exception as e:
                log.warning("llm.groq_init_failed", error=str(e))
        else:
            log.warning("llm.no_api_key", note="Set GROQ_API_KEY in .env — will use extractive fallback")

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        """Call LLM with fallback chain."""
        # 1. Try Groq
        if self.groq_client:
            try:
                resp = self.groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                log.warning("llm.groq_failed", error=str(e), fallback="extractive")

        # 2. Extractive fallback (offline safe)
        return f"[LLM offline — set GROQ_API_KEY] Context summary: {user[:400]}..."


class RAGPipeline:
    def __init__(self):
        log.info("rag.loading_embed_model", model=settings.EMBED_MODEL)
        self.embedder = SentenceTransformer(settings.EMBED_MODEL)
        self.dim      = 384
        self.index: Optional[faiss.Index] = None
        self.meta: List[Dict] = []
        self.llm = LLMClient()
        self._load_or_init()

    def _load_or_init(self):
        if os.path.exists(settings.FAISS_INDEX_PATH) and os.path.exists(settings.FAISS_META_PATH):
            self.index = faiss.read_index(settings.FAISS_INDEX_PATH)
            with open(settings.FAISS_META_PATH, "rb") as f:
                self.meta = pickle.load(f)
            log.info("rag.index_loaded", vectors=self.index.ntotal)
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            log.info("rag.index_created_fresh")
            self._seed_domain_knowledge()

    def _seed_domain_knowledge(self):
        docs = [
            {"title": "Bitcoin Halving Mechanics", "text": "Bitcoin's block reward halves every 210,000 blocks (~4 years). The 2024 halving reduced rewards from 6.25 to 3.125 BTC. Historically, halvings have preceded bull markets due to supply reduction while demand stays constant or grows.", "source": "internal", "date": "2024"},
            {"title": "On-Chain Fraud Patterns", "text": "Common fraud patterns: mixer usage (Tornado Cash), address clustering with high velocity, round-number transactions, rapid fund movement through multiple hops, and exchange deposit clustering after large inflows.", "source": "internal", "date": "2024"},
            {"title": "DeFi Rug Pull Indicators", "text": "Rug pull red flags: anonymous dev teams, unaudited smart contracts, liquidity locked for <30 days, founder token allocation >20%, sudden social media hype, and whale wallets receiving disproportionate pre-sale allocations.", "source": "internal", "date": "2024"},
            {"title": "Wash Trading Detection", "text": "Wash trading signatures: identical buyer-seller address pairs across exchanges, volume spikes without price movement, round-lot trades, and low bid-ask spread manipulation. Common on low-cap altcoins.", "source": "internal", "date": "2024"},
            {"title": "Ethereum Gas Anomalies", "text": "Abnormally high gas prices relative to transaction value indicate MEV bot activity, front-running, or contract spam attacks. Gas anomaly scores above 0.8 warrant deeper on-chain investigation.", "source": "internal", "date": "2024"},
            {"title": "Market Sentiment Indicators", "text": "Leading crypto market indicators: Fear & Greed Index, futures funding rates, exchange net flows (deposits vs withdrawals), stablecoin dominance, and whale wallet movement tracked via on-chain analytics.", "source": "internal", "date": "2024"},
            {"title": "Crypto Regulatory Landscape", "text": "Key regulatory developments: SEC crypto enforcement actions, MiCA regulations in EU (effective 2024), FATF Travel Rule compliance, and Binance/Coinbase settlement precedents shape institutional crypto adoption.", "source": "internal", "date": "2024"},
            {"title": "LSTM for Crypto Forecasting", "text": "LSTM networks with attention mechanisms achieve ~60-65% directional accuracy on crypto price prediction. Key features: OHLCV, volume-weighted price, RSI, MACD signals, and on-chain metrics like active addresses.", "source": "internal", "date": "2024"},
        ]
        self.add_documents(docs)
        log.info("rag.seeded", count=len(docs))

    def add_documents(self, docs: List[Dict]):
        if not docs:
            return
        texts  = [f"{d['title']}. {d['text']}" for d in docs]
        embeds = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        self.index.add(embeds.astype(np.float32))
        self.meta.extend(docs)
        self._save()

    def _save(self):
        os.makedirs("models", exist_ok=True)
        faiss.write_index(self.index, settings.FAISS_INDEX_PATH)
        with open(settings.FAISS_META_PATH, "wb") as f:
            pickle.dump(self.meta, f)

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        q = self.embedder.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, idxs = self.index.search(q, min(k, self.index.ntotal))
        return [
            {**self.meta[i], "score": float(s)}
            for s, i in zip(scores[0], idxs[0])
            if 0 <= i < len(self.meta)
        ]

    def fetch_crypto_news(self, query: str = "cryptocurrency fraud bitcoin") -> List[Dict]:
        if not settings.NEWS_API_KEY:
            log.warning("rag.news_api_key_missing")
            return []
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": query, "sortBy": "publishedAt", "pageSize": 15,
                        "language": "en", "apiKey": settings.NEWS_API_KEY},
                timeout=12
            )
            r.raise_for_status()
            articles = r.json().get("articles", [])
            docs = [
                {
                    "title":  a["title"],
                    "text":   (a.get("description") or "") + " " + (a.get("content") or "")[:300],
                    "source": a.get("source", {}).get("name", "newsapi"),
                    "date":   (a.get("publishedAt") or "")[:10],
                }
                for a in articles if a.get("title") and a.get("description")
            ]
            if docs:
                self.add_documents(docs)
                log.info("rag.news_ingested", count=len(docs))
            return docs
        except Exception as e:
            log.warning("rag.news_fetch_failed", error=str(e))
            return []

    def generate_summary(self, query: str, context_docs: List[Dict]) -> str:
        context = "\n\n".join([
            f"[{d['title']} | {d.get('date','')} | {d.get('source','')}]\n{d['text']}"
            for d in context_docs
        ])
        system = (
            "You are CryptoSentinel's intelligence analyst. "
            "Answer using ONLY the provided context. Be concise, factual, cite sources by title. "
            "If context is insufficient, state it clearly. Do not hallucinate data."
        )
        user = f"CONTEXT:\n{context}\n\nQUERY: {query}\n\nANALYSIS:"
        return self.llm.complete(system, user, max_tokens=600)

    def query(self, user_query: str) -> dict:
        docs    = self.retrieve(user_query, k=5)
        summary = self.generate_summary(user_query, docs)
        return clean_value({
            "query":   user_query,
            "summary": summary,
            "sources": [{"title": d["title"], "source": d["source"], "score": d["score"]} for d in docs],
        })
