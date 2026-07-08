"""
CryptoSentinel Dashboard v2 — Phase 3
Full trading UI with auth, portfolio, buy/sell, charts.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests, time, json

API = os.getenv("API_BASE", "http://localhost:8000")

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CryptoSentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif!important}
.stApp{background:#02040A;color:#EDE9E0}
section[data-testid="stSidebar"]{background:#060B14;border-right:1px solid rgba(0,229,255,0.1)}
.block-container{padding-top:1.5rem}
[data-testid="metric-container"]{
  background:rgba(255,255,255,0.03);border:1px solid rgba(0,229,255,0.12);
  border-radius:12px;padding:16px 20px!important}
[data-testid="metric-container"] label{
  font-family:'JetBrains Mono',monospace!important;font-size:11px!important;
  color:#8892A4!important;text-transform:uppercase;letter-spacing:0.08em}
[data-testid="metric-container"] [data-testid="stMetricValue"]{
  font-size:24px!important;font-weight:700!important;color:#00E5FF!important}
.stTextInput input,.stSelectbox select{
  background:#060B14!important;border:1px solid rgba(0,229,255,0.2)!important;
  border-radius:8px!important;color:#EDE9E0!important;
  font-family:'JetBrains Mono',monospace!important}
.stButton button{
  background:#00E5FF!important;color:#02040A!important;
  font-family:'JetBrains Mono',monospace!important;font-weight:600!important;
  border:none!important;border-radius:8px!important;
  box-shadow:0 0 20px rgba(0,229,255,0.3)!important}
.stButton button:hover{background:#00FDD0!important}
.stNumberInput input{
  background:#060B14!important;border:1px solid rgba(0,229,255,0.2)!important;
  border-radius:8px!important;color:#EDE9E0!important}
div[data-testid="stForm"]{
  background:rgba(255,255,255,0.03);border:1px solid rgba(0,229,255,0.1);
  border-radius:12px;padding:20px}
.trade-card{
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
  border-radius:12px;padding:20px;margin-bottom:12px}
.badge-buy{color:#22C55E;background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);
  padding:3px 10px;border-radius:999px;font-size:11px;font-family:'JetBrains Mono',monospace}
.badge-sell{color:#EF4444;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);
  padding:3px 10px;border-radius:999px;font-size:11px;font-family:'JetBrains Mono',monospace}
.pnl-pos{color:#22C55E;font-weight:600}
.pnl-neg{color:#EF4444;font-weight:600}
hr{border-color:rgba(255,255,255,0.06)!important}
</style>
""", unsafe_allow_html=True)

PLOT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Space Grotesk", color="#8892A4"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", showline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", showline=False),
    margin=dict(l=0, r=0, t=30, b=0),
)

COINS = {
    "Bitcoin (BTC)":   "bitcoin",
    "Ethereum (ETH)":  "ethereum",
    "Solana (SOL)":    "solana",
    "BNB":             "binancecoin",
    "XRP":             "ripple",
    "Dogecoin (DOGE)": "dogecoin",
    "Cardano (ADA)":   "cardano",
    "Polkadot (DOT)":  "polkadot",
    "Avalanche (AVAX)":"avalanche-2",
    "Chainlink (LINK)":"chainlink",
}

# ── SESSION STATE ──────────────────────────────────────────────────────────────
if "token"     not in st.session_state: st.session_state.token     = None
if "user"      not in st.session_state: st.session_state.user      = None
if "page"      not in st.session_state: st.session_state.page      = "dashboard"

# ── API HELPERS ────────────────────────────────────────────────────────────────
def headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def api_get(path, auth=True):
    try:
        h = headers() if auth else {}
        r = requests.get(f"{API}{path}", headers=h, timeout=15)
        return r.json() if r.ok else None
    except: return None

def api_post(path, data, auth=True):
    try:
        h = {"Content-Type": "application/json"}
        if auth: h.update(headers())
        r = requests.post(f"{API}{path}", headers=h, json=data, timeout=20)
        return r.json(), r.ok
    except Exception as e:
        return {"detail": str(e)}, False

# ── AUTH SCREEN ────────────────────────────────────────────────────────────────
def show_auth():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align:center;padding:40px 0 20px'>
          <div style='font-size:48px'>🛡️</div>
          <div style='font-family:JetBrains Mono,monospace;font-size:28px;
                      color:#00E5FF;font-weight:700;margin:8px 0'>CryptoSentinel</div>
          <div style='color:#8892A4;font-size:14px'>AI-Powered Crypto Intelligence Platform</div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            with st.form("login_form"):
                phone    = st.text_input("Phone Number", placeholder="9999999999")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login →", use_container_width=True)
            if submitted:
                resp, ok = api_post("/auth/login", {"phone": phone, "password": password}, auth=False)
                if ok:
                    st.session_state.token = resp["access_token"]
                    st.session_state.user  = resp["user"]
                    st.success("Login successful!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Login failed"))

        with tab2:
            with st.form("register_form"):
                name     = st.text_input("Full Name", placeholder="Kunal Kumar")
                phone2   = st.text_input("Phone Number", placeholder="9999999999")
                password2= st.text_input("Password", type="password", placeholder="min 6 chars")
                submitted2 = st.form_submit_button("Create Account →", use_container_width=True)
            if submitted2:
                resp, ok = api_post("/auth/register",
                    {"phone": phone2, "name": name, "password": password2}, auth=False)
                if ok:
                    st.session_state.token = resp["access_token"]
                    st.session_state.user  = resp["user"]
                    st.success(f"Welcome {name}! ₹1,00,000 virtual balance added.")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Registration failed"))

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style='padding:16px 0 8px'>
          <div style='font-family:JetBrains Mono,monospace;font-size:16px;color:#00E5FF;font-weight:700'>
            🛡️ CryptoSentinel
          </div>
          <div style='font-size:12px;color:#505869;margin-top:4px'>
            {st.session_state.user["name"]}
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        pages = {
            "📊 Dashboard":   "dashboard",
            "💼 Portfolio":   "portfolio",
            "📈 Trade":       "trade",
            "📰 Market":      "market",
            "🧠 AI Research": "ai",
        }
        for label, key in pages.items():
            active = st.session_state.page == key
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        summary = api_get("/portfolio/summary")
        if summary:
            st.metric("Virtual INR", f"₹{summary['virtual_inr']:,.0f}")
            pnl = summary.get("total_pnl", 0)
            pnl_color = "#22C55E" if pnl >= 0 else "#EF4444"
            st.markdown(f"""
            <div style='font-family:JetBrains Mono,monospace;font-size:11px;color:#8892A4;
                        text-transform:uppercase;letter-spacing:0.08em;margin-top:8px'>
              Total PnL
            </div>
            <div style='font-size:20px;font-weight:700;color:{pnl_color}'>
              {"+" if pnl>=0 else ""}₹{pnl:,.0f}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user  = None
            st.rerun()

# ── DASHBOARD ──────────────────────────────────────────────────────────────────
def show_dashboard():
    st.markdown("## Market Overview")

    top = api_get("/top-coins?n=8", auth=False) or []
    if top:
        cols = st.columns(4)
        for i, coin in enumerate(top[:8]):
            chg = coin.get("price_change_percentage_24h") or 0
            with cols[i % 4]:
                st.metric(
                    coin.get("symbol","").upper(),
                    f"${coin.get('current_price',0):,.2f}",
                    f"{chg:+.2f}%",
                )

    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        coin_label = st.selectbox("Select Coin", list(COINS.keys()), key="dash_coin")
        coin_id    = COINS[coin_label]
        ohlcv      = api_get(f"/ohlcv/{coin_id}?days=30", auth=False) or []
        if ohlcv:
            df = pd.DataFrame(ohlcv)
            fig = go.Figure()
            if "close" in df.columns:
                color = "#22C55E" if df["close"].iloc[-1] >= df["close"].iloc[0] else "#EF4444"
                fig.add_trace(go.Scatter(
                    x=list(range(len(df))), y=df["close"],
                    mode="lines", line=dict(color=color, width=2),
                    fill="tozeroy", fillcolor=f"rgba({','.join(str(int(color[i:i+2],16)) for i in (1,3,5))},0.08)",
                    name="Price",
                ))
            fig.update_layout(**PLOT, height=320,
                title=dict(text=f"{coin_label} — 30 Day Price", font=dict(color="#EDE9E0", size=14)))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        info = api_get(f"/market/{coin_id}", auth=False) or {}
        st.markdown("### Market Stats")
        price_usd = info.get("price_usd") or 0
        price_inr = price_usd * 83.5
        chg_24h   = info.get("price_change_24h") or 0
        chg_7d    = info.get("price_change_7d")  or 0
        mc        = info.get("market_cap")       or 0
        vol       = info.get("volume_24h")       or 0

        def row(label, value):
            st.markdown(f"""
            <div style='display:flex;justify-content:space-between;
                        padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05)'>
              <span style='color:#8892A4;font-size:13px'>{label}</span>
              <span style='font-weight:600;font-size:13px'>{value}</span>
            </div>""", unsafe_allow_html=True)

        row("Price (USD)",  f"${price_usd:,.2f}")
        row("Price (INR)",  f"₹{price_inr:,.0f}")
        row("24h Change",   f"{'🟢' if chg_24h>=0 else '🔴'} {chg_24h:+.2f}%")
        row("7d Change",    f"{'🟢' if chg_7d>=0 else '🔴'} {chg_7d:+.2f}%")
        row("Market Cap",   f"${mc/1e9:.2f}B")
        row("Volume 24h",   f"${vol/1e6:.1f}M")

# ── PORTFOLIO ──────────────────────────────────────────────────────────────────
def show_portfolio():
    st.markdown("## My Portfolio")
    portfolio = api_get("/portfolio/")
    if not portfolio:
        st.error("Could not load portfolio")
        return

    bal = portfolio["balance"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Balance",    f"₹{bal['virtual_inr']:,.0f}")
    c2.metric("Invested",        f"₹{bal['total_invested_inr']:,.0f}")
    c3.metric("Current Value",   f"₹{bal['current_value_inr']:,.0f}")
    pnl = bal["total_pnl_inr"]
    c4.metric("Total PnL",       f"₹{pnl:+,.0f}", f"{bal['total_pnl_pct']:+.2f}%")

    st.markdown("---")
    holdings = portfolio.get("holdings", [])
    if not holdings:
        st.info("No holdings yet. Go to **Trade** to buy your first crypto!")
        return

    st.markdown("### Holdings")
    for h in holdings:
        pnl_cls = "pnl-pos" if h["pnl_inr"] >= 0 else "pnl-neg"
        pnl_icon = "▲" if h["pnl_inr"] >= 0 else "▼"
        st.markdown(f"""
        <div class='trade-card'>
          <div style='display:flex;justify-content:space-between;align-items:center'>
            <div>
              <span style='font-size:18px;font-weight:700'>{h['symbol']}</span>
              <span style='color:#8892A4;font-size:13px;margin-left:8px'>{h['coin_id']}</span>
            </div>
            <div style='text-align:right'>
              <div style='font-size:18px;font-weight:700'>₹{h['current_value']:,.0f}</div>
              <div class='{pnl_cls}'>{pnl_icon} ₹{abs(h['pnl_inr']):,.0f} ({h['pnl_pct']:+.2f}%)</div>
            </div>
          </div>
          <div style='display:flex;gap:32px;margin-top:12px;color:#8892A4;font-size:13px'>
            <span>Qty: <b style='color:#EDE9E0'>{h['quantity']:.6f}</b></span>
            <span>Avg: <b style='color:#EDE9E0'>₹{h['avg_buy_price']:,.0f}</b></span>
            <span>CMP: <b style='color:#00E5FF'>₹{h['current_price']:,.0f}</b></span>
            <span>Invested: <b style='color:#EDE9E0'>₹{h['invested_inr']:,.0f}</b></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Allocation pie chart
    if len(holdings) > 1:
        st.markdown("### Allocation")
        fig = go.Figure(go.Pie(
            labels=[h["symbol"] for h in holdings],
            values=[h["current_value"] for h in holdings],
            hole=0.6,
            marker=dict(colors=["#00E5FF","#7C3AED","#22C55E","#F59E0B","#EF4444",
                                 "#8B5CF6","#06B6D4","#10B981","#F97316","#EC4899"]),
        ))
        fig.update_layout(**PLOT, height=300, showlegend=True,
            legend=dict(font=dict(color="#8892A4")))
        st.plotly_chart(fig, use_container_width=True)

    # Trade history
    st.markdown("---")
    st.markdown("### Trade History")
    trades_resp = api_get("/portfolio/trades")
    trades = trades_resp.get("trades", []) if trades_resp else []
    if trades:
        for t in trades[:10]:
            badge_cls  = "badge-buy" if t["side"] == "BUY" else "badge-sell"
            ts = t["timestamp"][:16].replace("T"," ")
            st.markdown(f"""
            <div style='display:flex;justify-content:space-between;align-items:center;
                        padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04)'>
              <div style='display:flex;align-items:center;gap:12px'>
                <span class='{badge_cls}'>{t['side']}</span>
                <span style='font-weight:600'>{t['symbol']}</span>
                <span style='color:#8892A4;font-size:13px'>{t['quantity']:.6f} @ ₹{t['price_inr']:,.0f}</span>
              </div>
              <div style='text-align:right'>
                <div style='font-weight:600'>₹{t['total_inr']:,.0f}</div>
                <div style='color:#505869;font-size:11px;font-family:JetBrains Mono,monospace'>{ts}</div>
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No trades yet.")

# ── TRADE ──────────────────────────────────────────────────────────────────────
def show_trade():
    st.markdown("## Paper Trading")
    st.markdown("<div style='color:#8892A4;font-size:14px;margin-bottom:24px'>All trades use virtual money — no real funds involved.</div>",
                unsafe_allow_html=True)

    # Live prices
    prices_resp = api_get("/trade/prices")
    prices = {p["coin_id"]: p for p in (prices_resp.get("prices") or [])} if prices_resp else {}

    col1, col2 = st.columns(2)

    # BUY
    with col1:
        st.markdown("### 🟢 Buy")
        with st.form("buy_form"):
            coin_label = st.selectbox("Select Coin", list(COINS.keys()), key="buy_coin")
            coin_id    = COINS[coin_label]
            amount     = st.number_input("Amount (₹)", min_value=10.0, value=5000.0, step=100.0)

            if coin_id in prices:
                p = prices[coin_id]
                qty_est = amount / p["price_inr"]
                st.markdown(f"""
                <div style='background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.2);
                            border-radius:8px;padding:12px;margin:8px 0;font-size:13px'>
                  <div style='color:#8892A4'>Current Price</div>
                  <div style='font-size:18px;font-weight:700;color:#00E5FF'>₹{p['price_inr']:,.2f}</div>
                  <div style='color:#8892A4;margin-top:4px'>You get ≈ <b style='color:#EDE9E0'>{qty_est:.6f} {p['symbol']}</b></div>
                  <div style='color:{"#22C55E" if p["change_24h_pct"]>=0 else "#EF4444"};font-size:12px'>
                    24h: {p["change_24h_pct"]:+.2f}%
                  </div>
                </div>
                """, unsafe_allow_html=True)

            submitted = st.form_submit_button("Buy Now →", use_container_width=True)

        if submitted:
            resp, ok = api_post("/trade/buy", {"coin_id": coin_id, "amount_inr": amount})
            if ok:
                st.success(f"✅ {resp['message']}")
                st.info(f"Balance remaining: ₹{resp['balance_remaining_inr']:,.2f}")
            else:
                st.error(resp.get("detail", "Trade failed"))

    # SELL
    with col2:
        st.markdown("### 🔴 Sell")
        portfolio = api_get("/portfolio/")
        holdings  = portfolio.get("holdings", []) if portfolio else []

        if not holdings:
            st.info("No holdings to sell. Buy some crypto first!")
        else:
            with st.form("sell_form"):
                hold_options = {f"{h['symbol']} ({h['quantity']:.4f})": h["coin_id"] for h in holdings}
                selected     = st.selectbox("Select Holding", list(hold_options.keys()))
                sell_coin    = hold_options[selected]
                sell_mode    = st.radio("Sell Mode", ["Percentage", "Quantity"], horizontal=True)

                if sell_mode == "Percentage":
                    pct = st.slider("Sell %", 1, 100, 50)
                    sell_data = {"coin_id": sell_coin, "sell_pct": pct}
                else:
                    holding = next(h for h in holdings if h["coin_id"] == sell_coin)
                    qty = st.number_input("Quantity", min_value=0.000001,
                                          max_value=holding["quantity"], value=holding["quantity"])
                    sell_data = {"coin_id": sell_coin, "quantity": qty}

                if sell_coin in prices:
                    p = prices[sell_coin]
                    st.markdown(f"""
                    <div style='background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);
                                border-radius:8px;padding:12px;margin:8px 0;font-size:13px'>
                      <div style='color:#8892A4'>Current Price</div>
                      <div style='font-size:18px;font-weight:700;color:#00E5FF'>₹{p['price_inr']:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)

                submitted2 = st.form_submit_button("Sell Now →", use_container_width=True)

            if submitted2:
                resp, ok = api_post("/trade/sell", sell_data)
                if ok:
                    pnl = resp.get("pnl_inr", 0)
                    emoji = "📈" if pnl >= 0 else "📉"
                    st.success(f"{emoji} {resp['message']}")
                    st.info(f"Balance: ₹{resp['balance_inr']:,.2f}")
                else:
                    st.error(resp.get("detail", "Sell failed"))

# ── MARKET ─────────────────────────────────────────────────────────────────────
def show_market():
    st.markdown("## Market Data")
    coin_label = st.selectbox("Select Coin", list(COINS.keys()))
    coin_id    = COINS[coin_label]
    days       = st.select_slider("Period", [7, 14, 30, 60, 90], value=30)

    ohlcv = api_get(f"/ohlcv/{coin_id}?days={days}", auth=False) or []
    if ohlcv:
        df = pd.DataFrame(ohlcv)
        if all(c in df.columns for c in ["open","high","low","close"]):
            fig = go.Figure(go.Candlestick(
                x=list(range(len(df))),
                open=df["open"], high=df["high"],
                low=df["low"],   close=df["close"],
                increasing=dict(line=dict(color="#22C55E"), fillcolor="rgba(34,197,94,0.3)"),
                decreasing=dict(line=dict(color="#EF4444"), fillcolor="rgba(239,68,68,0.3)"),
            ))
            fig.update_layout(**PLOT, height=420, title=dict(
                text=f"{coin_label} — {days} Day Candlestick",
                font=dict(color="#EDE9E0")),
                xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            if "volume" in df.columns:
                fig2 = go.Figure(go.Bar(
                    x=list(range(len(df))), y=df["volume"],
                    marker_color="rgba(0,229,255,0.3)",
                ))
                fig2.update_layout(**PLOT, height=160,
                    title=dict(text="Volume", font=dict(color="#EDE9E0",size=12)))
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Chart data loading...")

# ── AI RESEARCH ────────────────────────────────────────────────────────────────
def show_ai():
    st.markdown("## 🧠 AI Research")
    st.markdown("<div style='color:#8892A4;margin-bottom:20px'>Ask anything about crypto markets, on-chain data, or your portfolio.</div>",
                unsafe_allow_html=True)

    examples = [
        "What are signs of a rug pull?",
        "Should I hold Bitcoin long term?",
        "What happens after a halving?",
        "How to detect wash trading?",
    ]
    st.markdown("**Quick questions:**")
    cols = st.columns(2)
    for i, q in enumerate(examples):
        if cols[i%2].button(q, use_container_width=True):
            st.session_state["ai_query"] = q

    query = st.text_input("Your question", value=st.session_state.get("ai_query",""),
                          placeholder="Ask anything about crypto...")

    if st.button("Ask AI →", type="primary") and query:
        with st.spinner("Retrieving intelligence..."):
            resp, ok = api_post("/rag/query", {"query": query})
        if ok:
            st.markdown(f"""
            <div style='background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.15);
                        border-radius:12px;padding:20px;margin-top:16px'>
              <div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#00E5FF;
                          letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px'>AI Analysis</div>
              <div style='font-size:15px;line-height:1.75;color:#EDE9E0'>{resp.get("summary","")}</div>
            </div>""", unsafe_allow_html=True)
            sources = resp.get("sources", [])
            if sources:
                st.markdown("**Sources:**")
                for s in sources:
                    st.markdown(f"- {s['title']} `{s.get('score',0):.2f}`")
        else:
            st.error("AI query failed")

    if "ai_query" in st.session_state:
        del st.session_state["ai_query"]

# ── MAIN ───────────────────────────────────────────────────────────────────────
if not st.session_state.token:
    show_auth()
else:
    show_sidebar()
    page = st.session_state.page
    if   page == "dashboard": show_dashboard()
    elif page == "portfolio": show_portfolio()
    elif page == "trade":     show_trade()
    elif page == "market":    show_market()
    elif page == "ai":        show_ai()

    st.markdown("---")
    st.markdown("""
    <div style='text-align:center;font-family:JetBrains Mono,monospace;
        font-size:11px;color:#505869;padding:8px'>
        CryptoSentinel · Paper Trading Only · Not Financial Advice
    </div>""", unsafe_allow_html=True)
