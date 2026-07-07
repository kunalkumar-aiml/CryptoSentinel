"""
CryptoSentinel Dashboard
Run: streamlit run dashboard/app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import requests, time

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CryptoSentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS (Cyberpunk Dark) ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif !important;
}
.stApp {
    background: #02040A;
    color: #EDE9E0;
}
section[data-testid="stSidebar"] {
    background: #060B14;
    border-right: 1px solid rgba(0,229,255,0.1);
}
.block-container { padding-top: 1.5rem; }

/* Metric cards */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(0,229,255,0.12);
    border-radius: 12px;
    padding: 16px 20px !important;
}
[data-testid="metric-container"] label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    color: #8892A4 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #00E5FF !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 13px !important;
}

/* Inputs */
.stTextInput input, .stSelectbox select {
    background: #060B14 !important;
    border: 1px solid rgba(0,229,255,0.2) !important;
    border-radius: 8px !important;
    color: #EDE9E0 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.stTextInput input:focus {
    border-color: #00E5FF !important;
    box-shadow: 0 0 0 2px rgba(0,229,255,0.15) !important;
}

/* Buttons */
.stButton button {
    background: #00E5FF !important;
    color: #02040A !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    box-shadow: 0 0 20px rgba(0,229,255,0.3) !important;
    transition: all 0.2s !important;
}
.stButton button:hover {
    background: #00FDD0 !important;
    box-shadow: 0 0 32px rgba(0,229,255,0.5) !important;
    transform: translateY(-1px) !important;
}

/* Risk badges */
.badge { display:inline-block; padding:5px 14px; border-radius:999px; font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:600; letter-spacing:0.06em; }
.badge-low      { background:rgba(34,197,94,0.15);  color:#22C55E; border:1px solid rgba(34,197,94,0.4);  }
.badge-medium   { background:rgba(251,176,66,0.12); color:#FBB042; border:1px solid rgba(251,176,66,0.4); }
.badge-high     { background:rgba(239,68,68,0.12);  color:#EF4444; border:1px solid rgba(239,68,68,0.4);  }
.badge-critical { background:rgba(244,63,94,0.18);  color:#F43F5E; border:1px solid rgba(244,63,94,0.6);  animation: blink-border 1s ease-in-out infinite; }
@keyframes blink-border { 0%,100%{border-color:rgba(244,63,94,0.6)} 50%{border-color:rgba(244,63,94,1)} }

/* Panel cards */
.panel {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.panel-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: #00E5FF;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 12px;
}

/* Divider */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* Sidebar title */
.sidebar-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px; color: #00E5FF; font-weight: 500;
    margin-bottom: 4px;
}
.sidebar-sub { font-size: 12px; color: #505869; margin-bottom: 24px; }

/* Plotly background match */
.js-plotly-plot .plotly { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

PLOTLY_THEME = dict(
    plot_bgcolor  = "rgba(0,0,0,0)",
    paper_bgcolor = "rgba(0,0,0,0)",
    font          = dict(family="Space Grotesk", color="#8892A4"),
    xaxis         = dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    yaxis         = dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    margin        = dict(l=0, r=0, t=30, b=0),
)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def risk_badge(level: str) -> str:
    cls = {"LOW":"low","MEDIUM":"medium","HIGH":"high","CRITICAL":"critical"}.get(level,"medium")
    return f'<span class="badge badge-{cls}">{level}</span>'

def risk_color(level: str) -> str:
    return {"LOW":"#22C55E","MEDIUM":"#FBB042","HIGH":"#EF4444","CRITICAL":"#F43F5E"}.get(level,"#8892A4")

def api_get(path: str):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=15)
        return r.json() if r.ok else None
    except:
        return None

def api_post(path: str, payload: dict):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=90)
        return r.json() if r.ok else None
    except:
        return None

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🛡️ CryptoSentinel</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">AI Risk Intelligence</div>', unsafe_allow_html=True)
    st.markdown("---")

    page = st.radio("Navigation", ["📊 Dashboard", "🔍 Wallet Analyzer", "💬 Intelligence Query", "📈 Market Data"], label_visibility="collapsed")
    st.markdown("---")

    coin_options = {"Bitcoin (BTC)":"bitcoin","Ethereum (ETH)":"ethereum","Solana (SOL)":"solana","BNB":"binancecoin","XRP":"ripple"}
    selected_coin_label = st.selectbox("Coin", list(coin_options.keys()))
    selected_coin = coin_options[selected_coin_label]

    st.markdown("---")
    health = api_get("/health")
    if health and health.get("agent_ready"):
        st.success("🟢 Agent Online")
    else:
        st.error("🔴 Agent Offline — start main.py")

# ─── Page: Dashboard ──────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.markdown("## Market Overview")
    top = api_get("/top-coins?n=8") or []

    if top:
        cols = st.columns(4)
        for i, coin in enumerate(top[:4]):
            chg = coin.get("price_change_percentage_24h", 0) or 0
            with cols[i]:
                st.metric(
                    label=f"{coin.get('symbol','').upper()}",
                    value=f"${coin.get('current_price', 0):,.2f}",
                    delta=f"{chg:+.2f}%",
                    delta_color="normal"
                )

    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        ohlcv_data = api_get(f"/ohlcv/{selected_coin}?days=30") or []
        if ohlcv_data:
            df_chart = pd.DataFrame(ohlcv_data)
            fig = go.Figure()
            if "close" in df_chart.columns:
                # Price line with gradient fill
                fig.add_trace(go.Scatter(
                    x=list(range(len(df_chart))),
                    y=df_chart["close"],
                    mode="lines",
                    line=dict(color="#00E5FF", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(0,229,255,0.06)",
                    name="Price",
                ))
            fig.update_layout(title=f"{selected_coin_label} — 30 Day Price", **PLOTLY_THEME,
                              height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Price chart — connect API to load live data")

    with col2:
        coin_info = api_get(f"/market/{selected_coin}") or {}
        chg_24h = coin_info.get("price_change_24h", 0) or 0
        chg_7d  = coin_info.get("price_change_7d", 0) or 0
        st.markdown('<div class="panel"><div class="panel-title">Market Stats</div>', unsafe_allow_html=True)
        st.markdown(f"**Price:** ${coin_info.get('price_usd', 0):,.2f}")
        st.markdown(f"**24h Change:** {'🟢' if chg_24h>0 else '🔴'} {chg_24h:+.2f}%")
        st.markdown(f"**7d Change:** {'🟢' if chg_7d>0 else '🔴'} {chg_7d:+.2f}%")
        st.markdown(f"**Market Cap:** ${coin_info.get('market_cap',0)/1e9:.2f}B")
        st.markdown(f"**Vol 24h:** ${coin_info.get('volume_24h',0)/1e6:.1f}M")
        st.markdown("</div>", unsafe_allow_html=True)

# ─── Page: Wallet Analyzer ────────────────────────────────────────────────────
elif page == "🔍 Wallet Analyzer":
    st.markdown("## Wallet Risk Analyzer")
    st.markdown("Paste any Ethereum wallet address to run the full agentic analysis pipeline.")

    col1, col2 = st.columns([3, 1])
    with col1:
        wallet = st.text_input("Ethereum Wallet Address", placeholder="0xAbc123...", label_visibility="collapsed")
    with col2:
        analyze_btn = st.button("🔍 Analyze Wallet", use_container_width=True)

    if analyze_btn and wallet:
        with st.spinner("🤖 Agent running — fetching on-chain data, scoring fraud, forecasting prices, retrieving intelligence..."):
            t0 = time.time()
            result = api_post("/analyze", {"wallet_address": wallet, "coin_id": selected_coin})
            elapsed = round(time.time() - t0, 1)

        if not result:
            st.error("Analysis failed — is the API running? `python main.py`")
        else:
            # Overall risk banner
            risk = result.get("overall_risk", "UNKNOWN")
            score = result.get("overall_score", 0)
            color = risk_color(risk.split()[0])
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border:1px solid {color}40;border-left:4px solid {color};
                        border-radius:12px;padding:20px 24px;margin:16px 0">
                <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#8892A4;margin-bottom:6px">OVERALL RISK ASSESSMENT</div>
                <div style="font-size:28px;font-weight:700;color:{color}">{risk}</div>
                <div style="font-size:13px;color:#8892A4;margin-top:4px">Risk score: {score:.3f} · Analyzed in {elapsed}s</div>
            </div>
            """, unsafe_allow_html=True)

            # Three column results
            c1, c2, c3 = st.columns(3)

            with c1:
                fraud = result.get("fraud_analysis", {})
                st.markdown('<div class="panel"><div class="panel-title">🔴 Fraud Analysis</div>', unsafe_allow_html=True)
                fraud_prob = fraud.get("fraud_probability", 0)
                # Gauge
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=fraud_prob * 100,
                    title={"text": "Fraud Score", "font": {"color": "#8892A4", "size": 12}},
                    number={"suffix": "%", "font": {"color": "#EDE9E0"}},
                    gauge={
                        "axis": {"range": [0, 100], "tickcolor": "#505869"},
                        "bar": {"color": risk_color(fraud.get("risk_level",""))},
                        "bgcolor": "rgba(0,0,0,0)",
                        "bordercolor": "rgba(0,0,0,0)",
                        "steps": [
                            {"range": [0,30], "color": "rgba(34,197,94,0.1)"},
                            {"range": [30,60],"color": "rgba(251,176,66,0.1)"},
                            {"range": [60,80],"color": "rgba(239,68,68,0.1)"},
                            {"range": [80,100],"color": "rgba(244,63,94,0.15)"},
                        ],
                    }
                ))
                fig_gauge.update_layout(**PLOTLY_THEME, height=180)
                st.plotly_chart(fig_gauge, use_container_width=True)
                st.markdown(f"Risk Level: {risk_badge(fraud.get('risk_level',''))}", unsafe_allow_html=True)
                if fraud.get("top_features"):
                    st.markdown("**Top SHAP features:**")
                    for f in fraud["top_features"][:3]:
                        bar_w = min(abs(f["shap_value"]) * 80, 100)
                        clr = "#EF4444" if f["shap_value"] > 0 else "#22C55E"
                        st.markdown(f"""<div style="margin:4px 0">
                            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#8892A4">{f['feature']}</span>
                            <div style="background:{clr}40;width:{bar_w}%;height:4px;border-radius:2px;margin-top:3px"></div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                forecast = result.get("price_forecast", {})
                st.markdown('<div class="panel"><div class="panel-title">📈 Price Forecast</div>', unsafe_allow_html=True)
                prices = forecast.get("predicted_prices", [])
                if prices:
                    fig_fc = go.Figure()
                    x = [f"+{(i+1)*4}h" for i in range(len(prices))]
                    color_fc = "#22C55E" if forecast.get("direction") == "UP" else "#EF4444"
                    fig_fc.add_trace(go.Scatter(
                        x=x, y=prices,
                        mode="lines+markers",
                        line=dict(color=color_fc, width=2.5),
                        marker=dict(color=color_fc, size=6),
                        fill="tozeroy", fillcolor=f"{color_fc}15",
                    ))
                    fig_fc.update_layout(**PLOTLY_THEME, height=180, showlegend=False)
                    st.plotly_chart(fig_fc, use_container_width=True)
                direction = forecast.get("direction", "")
                chg = forecast.get("change_pct", 0)
                arrow = "🟢 ▲" if direction == "UP" else "🔴 ▼"
                st.markdown(f"**Direction:** {arrow} {abs(chg):.2f}%")
                st.markdown(f"**Current:** ${forecast.get('current_price', 0):,.2f}")
                st.markdown(f"**Horizon:** {forecast.get('horizon_hours', 0)} hours")
                st.markdown("</div>", unsafe_allow_html=True)

            with c3:
                rag = result.get("market_intelligence", {})
                st.markdown('<div class="panel"><div class="panel-title">🧠 Intelligence Report</div>', unsafe_allow_html=True)
                summary = rag.get("summary", "No summary available")
                st.markdown(f'<div style="font-size:13px;color:#8892A4;line-height:1.6">{summary[:400]}...</div>', unsafe_allow_html=True)
                st.markdown("**Sources:**")
                for src in rag.get("sources", [])[:3]:
                    score_bar = int(src.get("score", 0) * 100)
                    st.markdown(f"""<div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#505869;
                                              margin:4px 0">{src['title'][:40]}...
                        <span style="color:#00E5FF;float:right">{src.get('score',0):.2f}</span></div>""",
                        unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # Recommendations
            st.markdown("### Recommendations")
            recs = result.get("recommendations", [])
            for rec in recs:
                st.markdown(f"""<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                                           border-radius:8px;padding:12px 16px;margin:6px 0;font-size:14px">{rec}</div>""",
                    unsafe_allow_html=True)

            # Agent trace
            with st.expander("🤖 Agent Reasoning Trace"):
                for i, msg in enumerate(result.get("agent_trace", [])):
                    st.markdown(f"""<div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                                               color:#505869;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
                        <span style="color:#00E5FF">[{i+1}]</span> {msg}</div>""", unsafe_allow_html=True)

# ─── Page: Intelligence Query ──────────────────────────────────────────────────
elif page == "💬 Intelligence Query":
    st.markdown("## Intelligence Query")
    st.markdown("Ask anything about crypto markets, fraud patterns, or on-chain activity.")

    query = st.text_input("Your question", placeholder="What are signs of a rug pull?", label_visibility="collapsed")
    ask_btn = st.button("🧠 Ask Intelligence", use_container_width=False)

    if ask_btn and query:
        with st.spinner("Retrieving context and generating analysis..."):
            result = api_post("/rag/query", {"query": query})
        if result:
            st.markdown("### Analysis")
            st.markdown(f"""<div class="panel"><div style="font-size:15px;line-height:1.75;color:#EDE9E0">
                {result.get('summary', 'No response')}</div></div>""", unsafe_allow_html=True)
            st.markdown("### Source Documents")
            for src in result.get("sources", []):
                st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
                    background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                    border-radius:8px;padding:10px 16px;margin:6px 0">
                    <span style="font-size:13px">{src['title']}</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#00E5FF">{src.get('score',0):.3f}</span>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Sample questions:**")
    samples = ["What are indicators of wash trading?","How does Tornado Cash affect wallet risk scoring?",
               "What happens to crypto prices after Bitcoin halving?","What is DeFi rug pull risk?"]
    cols = st.columns(2)
    for i, s in enumerate(samples):
        with cols[i % 2]:
            st.markdown(f"""<div style="background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.1);
                border-radius:8px;padding:10px 14px;margin:4px 0;font-size:13px;color:#8892A4;
                font-family:'JetBrains Mono',monospace">{s}</div>""", unsafe_allow_html=True)

# ─── Page: Market Data ────────────────────────────────────────────────────────
elif page == "📈 Market Data":
    st.markdown("## Market Data")
    ohlcv = api_get(f"/ohlcv/{selected_coin}?days=90") or []
    if ohlcv:
        df = pd.DataFrame(ohlcv)
        if "close" in df.columns and "timestamp" in df.columns:
            # Candlestick
            fig = go.Figure(go.Candlestick(
                x=df.index,
                open=df["open"], high=df["high"],
                low=df["low"],   close=df["close"],
                increasing=dict(line=dict(color="#22C55E"), fillcolor="rgba(34,197,94,0.3)"),
                decreasing=dict(line=dict(color="#EF4444"), fillcolor="rgba(239,68,68,0.3)"),
            ))
            fig.update_layout(title=f"{selected_coin_label} — 90 Day Candlestick",
                              **PLOTLY_THEME, height=420,
                              xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # Volume bar
            if "volume" in df.columns:
                fig_v = go.Figure(go.Bar(
                    x=df.index, y=df["volume"],
                    marker_color="rgba(0,229,255,0.3)",
                    marker_line=dict(color="rgba(0,229,255,0.6)", width=0.5),
                ))
                fig_v.update_layout(title="Volume", **PLOTLY_THEME, height=180)
                st.plotly_chart(fig_v, use_container_width=True)
    else:
        st.info("Connect to the API to load market data. Run `python main.py` first.")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""<div style="text-align:center;font-family:'JetBrains Mono',monospace;
    font-size:11px;color:#505869;padding:8px">
    CryptoSentinel v1.0 · Built by Kunal Kumar · SRM KTR 2026 · Not financial advice
</div>""", unsafe_allow_html=True)
