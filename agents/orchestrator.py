"""
CryptoSentinel Agent — LangGraph orchestrator.
Flow: plan → fetch_data → run_ml → retrieve_context → reason → generate_report
"""
import json
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from data.coingecko  import get_ohlcv, get_coin_info
from data.etherscan  import get_wallet_transactions, extract_wallet_graph_features
from ml.fraud_detector   import FraudDetector
from ml.price_forecaster import PriceForecaster
from rag.pipeline        import RAGPipeline
from utils.logger import get_logger

log = get_logger("agent")


# ─── State ───────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    wallet_address : str
    coin_id        : str
    messages       : List[str]          # trace log
    wallet_features: dict
    fraud_result   : dict
    ohlcv_df       : object             # pd.DataFrame
    forecast_result: dict
    rag_result     : dict
    coin_info      : dict
    final_report   : dict


# ─── Nodes ───────────────────────────────────────────────────────────────────
def node_fetch_onchain(state: AgentState) -> AgentState:
    log.info(f"[agent] Fetching on-chain data for {state['wallet_address']}")
    df = get_wallet_transactions(state["wallet_address"], limit=200)
    features = extract_wallet_graph_features(state["wallet_address"], df)
    state["wallet_features"] = features
    state["messages"].append(f"Fetched {features.get('total_txns',0)} transactions, extracted {len(features)} graph features")
    return state


def node_run_fraud(state: AgentState, detector: FraudDetector) -> AgentState:
    log.info("[agent] Running fraud scoring")
    result = detector.predict(state["wallet_features"])
    state["fraud_result"] = result
    state["messages"].append(
        f"Fraud score: {result['fraud_probability']:.3f} | Risk: {result['risk_level']} | "
        f"Suspicious: {result['is_suspicious']}"
    )
    return state


def node_fetch_market(state: AgentState) -> AgentState:
    log.info(f"[agent] Fetching market data for {state['coin_id']}")
    df   = get_ohlcv(state["coin_id"], days=90)
    info = get_coin_info(state["coin_id"])
    state["ohlcv_df"]  = df
    state["coin_info"] = info
    state["messages"].append(
        f"Fetched {len(df)} OHLCV candles | Current price: ${info.get('price_usd', 0):,.2f}"
    )
    return state


def node_run_forecast(state: AgentState, forecaster: PriceForecaster) -> AgentState:
    log.info("[agent] Running price forecast")
    result = forecaster.predict(state["ohlcv_df"])
    state["forecast_result"] = result
    state["messages"].append(
        f"Forecast: {result['direction']} {abs(result['change_pct']):.2f}% over next {result['horizon_hours']}h"
    )
    return state


def node_rag_query(state: AgentState, rag: RAGPipeline) -> AgentState:
    log.info("[agent] Running RAG retrieval")
    coin   = state["coin_info"].get("name", state["coin_id"])
    risk   = state["fraud_result"].get("risk_level", "UNKNOWN")
    direct = state["forecast_result"].get("direction", "UNKNOWN")
    query  = f"What are the current risks and news for {coin}? Fraud risk: {risk}. Price trending: {direct}."
    result = rag.query(query)
    state["rag_result"] = result
    state["messages"].append(f"RAG retrieved {len(result['sources'])} context documents")
    return state


def node_generate_report(state: AgentState) -> AgentState:
    log.info("[agent] Generating final risk report")
    fraud    = state["fraud_result"]
    forecast = state["forecast_result"]
    rag      = state["rag_result"]
    coin     = state["coin_info"]

    # Risk score: weighted combo of fraud prob + directional risk
    fraud_weight    = 0.6
    market_weight   = 0.4
    direction_risk  = 0.3 if forecast.get("direction") == "DOWN" else 0.1
    overall_score   = fraud["fraud_probability"] * fraud_weight + direction_risk * market_weight
    overall_score   = min(overall_score, 1.0)

    if overall_score < 0.25:   overall = "LOW RISK"
    elif overall_score < 0.55: overall = "MEDIUM RISK"
    elif overall_score < 0.75: overall = "HIGH RISK"
    else:                      overall = "CRITICAL RISK"

    # Build recommendations
    recs = []
    if fraud["is_suspicious"]:
        recs.append("⚠️  Wallet exhibits high-fraud-probability patterns — avoid interaction.")
    if fraud["risk_level"] in ["HIGH", "CRITICAL"]:
        recs.append("🔍  On-chain graph anomalies detected (velocity, clustering, address-reuse).")
    if forecast["direction"] == "DOWN":
        recs.append(f"📉  Model projects {abs(forecast['change_pct']):.1f}% downside over next {forecast['horizon_hours']}h.")
    else:
        recs.append(f"📈  Model projects {forecast['change_pct']:.1f}% upside over next {forecast['horizon_hours']}h.")
    recs.append(f"🧠  LLM analysis: {rag['summary'][:300]}...")

    report = {
        "wallet_address"    : state["wallet_address"],
        "coin"              : coin.get("name", state["coin_id"]),
        "symbol"            : coin.get("symbol", ""),
        "current_price_usd" : coin.get("price_usd", 0),
        "overall_risk"      : overall,
        "overall_score"     : round(overall_score, 4),
        "fraud_analysis"    : fraud,
        "price_forecast"    : forecast,
        "market_intelligence": rag,
        "recommendations"   : recs,
        "agent_trace"       : state["messages"],
    }
    state["final_report"] = report
    log.info(f"[agent] Report generated — Overall: {overall}")
    return state


# ─── Graph Builder ────────────────────────────────────────────────────────────
def build_graph(detector: FraudDetector, forecaster: PriceForecaster, rag: RAGPipeline):
    g = StateGraph(AgentState)

    g.add_node("fetch_onchain",  node_fetch_onchain)
    g.add_node("run_fraud",      lambda s: node_run_fraud(s, detector))
    g.add_node("fetch_market",   node_fetch_market)
    g.add_node("run_forecast",   lambda s: node_run_forecast(s, forecaster))
    g.add_node("rag_query",      lambda s: node_rag_query(s, rag))
    g.add_node("generate_report",node_generate_report)

    g.set_entry_point("fetch_onchain")
    g.add_edge("fetch_onchain",   "run_fraud")
    g.add_edge("run_fraud",       "fetch_market")
    g.add_edge("fetch_market",    "run_forecast")
    g.add_edge("run_forecast",    "rag_query")
    g.add_edge("rag_query",       "generate_report")
    g.add_edge("generate_report", END)

    return g.compile()


# ─── Public API ───────────────────────────────────────────────────────────────
class CryptoSentinelAgent:
    def __init__(self):
        log.info("Initialising CryptoSentinel components...")
        self.detector   = FraudDetector()
        self.forecaster = PriceForecaster()
        self.rag        = RAGPipeline()
        self.graph      = build_graph(self.detector, self.forecaster, self.rag)
        log.info("CryptoSentinel ready ✓")

    def analyze(self, wallet_address: str, coin_id: str = "bitcoin") -> dict:
        init_state = AgentState(
            wallet_address  = wallet_address,
            coin_id         = coin_id,
            messages        = [],
            wallet_features = {},
            fraud_result    = {},
            ohlcv_df        = None,
            forecast_result = {},
            rag_result      = {},
            coin_info       = {},
            final_report    = {},
        )
        final = self.graph.invoke(init_state)
        return final["final_report"]
