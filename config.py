from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # App
    APP_NAME: str = "CryptoSentinel"
    APP_VERSION: str = "2.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-in-production-min-32-chars"
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:8501"]

    # LLM — Groq primary, OpenAI fallback
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-70b-8192"
    GROQ_FALLBACK_MODEL: str = "mixtral-8x7b-32768"
    OPENAI_API_KEY: str = ""

    # Data APIs
    ETHERSCAN_API_KEY: str = "demo"
    NEWS_API_KEY: str = ""
    COINGECKO_API_KEY: str = ""  # Pro key optional

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cryptosentinel"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/cryptosentinel"

    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_PRICE: int = 30          # 30s for live prices
    CACHE_TTL_OHLCV: int = 300         # 5min for OHLCV
    CACHE_TTL_NEWS: int = 600          # 10min for news
    CACHE_TTL_ONCHAIN: int = 120       # 2min for on-chain

    # ML Models
    FRAUD_MODEL_PATH: str = "models/fraud_model.pkl"
    FORECAST_MODEL_PATH: str = "models/forecast_model.pt"

    # Fraud thresholds
    FRAUD_THRESHOLD: float = 0.65
    EMBED_MODEL: str = "all-MiniLM-L6-v2"
    FAISS_INDEX_PATH: str = "models/faiss_news.index"
    FAISS_META_PATH: str = "models/faiss_meta.pkl"

    # Monitoring
    SENTRY_DSN: str = ""

    # External endpoints
    COINGECKO_BASE: str = "https://api.coingecko.com/api/v3"
    COINCAP_BASE: str = "https://api.coincap.io/v2"
    ETHERSCAN_BASE: str = "https://api.etherscan.io/v2/api"  # V2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
