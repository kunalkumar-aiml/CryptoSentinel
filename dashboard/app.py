import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests,time
API=os.getenv("API_BASE","http://localhost:8000")
st.set_page_config(page_title="CryptoSentinel",page_icon="🛡️",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif!important}
.stApp{background:#02040A;color:#EDE9E0}
section[data-testid="stSidebar"]{background:#060B14;border-right:1px solid rgba(0,229,255,0.1)}
.block-container{padding-top:1.5rem}
[data-testid="metric-container"]{background:rgba(255,255,255,0.03);border:1px solid rgba(0,229,255,0.12);border-radius:12px;padding:16px 20px!important}
[data-testid="metric-container"] label{font-family:'JetBrains Mono',monospace!important;font-size:11px!important;color:#8892A4!important;text-transform:uppercase;letter-spacing:0.08em}
[data-testid="metric-container"] [data-testid="stMetricValue"]{font-size:24px!important;font-weight:700!important;color:#00E5FF!important}
.stTextInput input{background:#060B14!important;border:1px solid rgba(0,229,255,0.2)!important;border-radius:8px!important;color:#EDE9E0!important}
.stButton button{background:#00E5FF!important;color:#02040A!important;font-family:'JetBrains Mono',monospace!important;font-weight:600!important;border:none!important;border-radius:8px!important}
.stNumberInput input{background:#060B14!important;border:1px solid rgba(0,229,255,0.2)!important;border-radius:8px!important;color:#EDE9E0!important}
div[data-testid="stForm"]{background:rgba(255,255,255,0.03);border:1px solid rgba(0,229,255,0.1);border-radius:12px;padding:20px}
.tcard{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:20px;margin-bottom:12px}
hr{border-color:rgba(255,255,255,0.06)!important}
</style>""",unsafe_allow_html=True)
PLOT=dict(plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",font=dict(family="Space Grotesk",color="#8892A4"),xaxis=dict(gridcolor="rgba(255,255,255,0.04)",showline=False),yaxis=dict(gridcolor="rgba(255,255,255,0.04)",showline=False),margin=dict(l=0,r=0,t=30,b=0))
COINS={"Bitcoin (BTC)":"bitcoin","Ethereum (ETH)":"ethereum","Solana (SOL)":"solana","BNB":"binancecoin","XRP":"ripple","Dogecoin (DOGE)":"dogecoin","Cardano (ADA)":"cardano","Polkadot (DOT)":"polkadot","Avalanche (AVAX)":"avalanche-2","Chainlink (LINK)":"chainlink"}
for k,v in [("token",None),("user",None),("page","dashboard")]:
    if k not in st.session_state: st.session_state[k]=v
def hdr(): return {"Authorization":f"Bearer {st.session_state.token}"}
def aget(p,auth=True):
    try:
        r=requests.get(f"{API}{p}",headers=hdr() if auth else {},timeout=15)
        return r.json() if r.ok else None
    except: return None
def apost(p,d,auth=True):
    try:
        h={"Content-Type":"application/json"}
        if auth: h.update(hdr())
        r=requests.post(f"{API}{p}",headers=h,json=d,timeout=20)
        return r.json(),r.ok
    except Exception as e: return {"detail":str(e)},False
def show_auth():
    _,c,__=st.columns([1,2,1])
    with c:
        st.markdown("<div style='text-align:center;padding:40px 0 20px'><div style='font-size:48px'>🛡️</div><div style='font-family:JetBrains Mono,monospace;font-size:28px;color:#00E5FF;font-weight:700'>CryptoSentinel</div><div style='color:#8892A4;font-size:14px'>AI-Powered Crypto Intelligence</div></div>",unsafe_allow_html=True)
        t1,t2=st.tabs(["Login","Register"])
        with t1:
            with st.form("lf"):
                ph=st.text_input("Phone",placeholder="9999999999")
                pw=st.text_input("Password",type="password")
                s=st.form_submit_button("Login →",use_container_width=True)
            if s:
                r,ok=apost("/auth/login",{"phone":ph,"password":pw},auth=False)
                if ok: st.session_state.token=r["access_token"]; st.session_state.user=r["user"]; st.rerun()
                else: st.error(r.get("detail","Login failed"))
        with t2:
            with st.form("rf"):
                nm=st.text_input("Full Name"); ph2=st.text_input("Phone"); pw2=st.text_input("Password",type="password")
                s2=st.form_submit_button("Create Account →",use_container_width=True)
            if s2:
                r,ok=apost("/auth/register",{"phone":ph2,"name":nm,"password":pw2},auth=False)
                if ok: st.session_state.token=r["access_token"]; st.session_state.user=r["user"]; st.success(f"Welcome {nm}!"); time.sleep(0.5); st.rerun()
                else: st.error(r.get("detail","Failed"))
def show_sidebar():
    with st.sidebar:
        st.markdown(f"<div style='padding:16px 0 8px'><div style='font-family:JetBrains Mono,monospace;font-size:16px;color:#00E5FF;font-weight:700'>🛡️ CryptoSentinel</div><div style='font-size:12px;color:#505869'>{st.session_state.user['name']}</div></div>",unsafe_allow_html=True)
        st.markdown("---")
        for lbl,key in [("📊 Dashboard","dashboard"),("💼 Portfolio","portfolio"),("📈 Trade","trade"),("📰 Market","market"),("⚡ Automation","automation"),("🧠 AI Research","ai")]:
            if st.button(lbl,use_container_width=True,type="primary" if st.session_state.page==key else "secondary"):
                st.session_state.page=key; st.rerun()
        st.markdown("---")
        sm=aget("/portfolio/summary")
        if sm:
            st.metric("Virtual INR",f"₹{sm['virtual_inr']:,.0f}")
            pnl=sm.get("total_pnl",0); c="#22C55E" if pnl>=0 else "#EF4444"
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:11px;color:#8892A4;text-transform:uppercase;margin-top:8px'>Total PnL</div><div style='font-size:20px;font-weight:700;color:{c}'>{'+'if pnl>=0 else''}₹{pnl:,.0f}</div>",unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🚪 Logout",use_container_width=True): st.session_state.token=None; st.session_state.user=None; st.rerun()
def show_dashboard():
    st.markdown("## Market Overview")
    top=aget("/top-coins?n=8",auth=False) or []
    if top:
        cols=st.columns(4)
        for i,coin in enumerate(top[:8]):
            chg=coin.get("price_change_percentage_24h") or 0
            with cols[i%4]: st.metric(coin.get("symbol","").upper(),f"${coin.get('current_price',0):,.2f}",f"{chg:+.2f}%")
    st.markdown("---")
    c1,c2=st.columns([2,1])
    with c1:
        cl=st.selectbox("Coin",list(COINS.keys()),key="dc"); cid=COINS[cl]
        data=aget(f"/ohlcv/{cid}?days=30",auth=False) or []
        if data:
            df=pd.DataFrame(data)
            if "close" in df.columns:
                color="#22C55E" if df["close"].iloc[-1]>=df["close"].iloc[0] else "#EF4444"
                fig=go.Figure(); fig.add_trace(go.Scatter(x=list(range(len(df))),y=df["close"],mode="lines",line=dict(color=color,width=2),fill="tozeroy",fillcolor="rgba(0,229,255,0.06)",name="Price"))
                fig.update_layout(**PLOT,height=320,title=dict(text=f"{cl} — 30 Day",font=dict(color="#EDE9E0",size=14)))
                st.plotly_chart(fig,use_container_width=True)
    with c2:
        info=aget(f"/market/{cid}",auth=False) or {}
        st.markdown("### Stats")
        pusd=info.get("price_usd") or 0; c24=info.get("price_change_24h") or 0; c7=info.get("price_change_7d") or 0
        def row(l,v): st.markdown(f"<div style='display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05)'><span style='color:#8892A4;font-size:13px'>{l}</span><span style='font-weight:600;font-size:13px'>{v}</span></div>",unsafe_allow_html=True)
        row("USD",f"${pusd:,.2f}"); row("INR",f"₹{pusd*83.5:,.0f}"); row("24h",f"{'🟢'if c24>=0 else'🔴'} {c24:+.2f}%"); row("7d",f"{'🟢'if c7>=0 else'🔴'} {c7:+.2f}%")
def show_portfolio():
    st.markdown("## My Portfolio")
    p=aget("/portfolio/")
    if not p: st.error("Could not load"); return
    bal=p["balance"]; c1,c2,c3,c4=st.columns(4)
    c1.metric("Cash",f"₹{bal['virtual_inr']:,.0f}"); c2.metric("Invested",f"₹{bal['total_invested_inr']:,.0f}")
    c3.metric("Value",f"₹{bal['current_value_inr']:,.0f}"); pnl=bal["total_pnl_inr"]; c4.metric("PnL",f"₹{pnl:+,.0f}",f"{bal['total_pnl_pct']:+.2f}%")
    st.markdown("---")
    hs=p.get("holdings",[])
    if not hs: st.info("No holdings. Buy crypto from Trade page!"); return
    st.markdown("### Holdings")
    for h in hs:
        clr="#22C55E" if h["pnl_inr"]>=0 else "#EF4444"; ico="▲" if h["pnl_inr"]>=0 else "▼"
        st.markdown(f"<div class='tcard'><div style='display:flex;justify-content:space-between'><div><b style='font-size:18px'>{h['symbol']}</b> <span style='color:#8892A4;font-size:13px'>{h['coin_id']}</span></div><div style='text-align:right'><b style='font-size:18px'>₹{h['current_value']:,.0f}</b><div style='color:{clr}'>{ico} ₹{abs(h['pnl_inr']):,.0f} ({h['pnl_pct']:+.2f}%)</div></div></div><div style='display:flex;gap:24px;margin-top:10px;color:#8892A4;font-size:13px'><span>Qty: <b style='color:#EDE9E0'>{h['quantity']:.6f}</b></span><span>Avg: <b style='color:#EDE9E0'>₹{h['avg_buy_price']:,.0f}</b></span><span>CMP: <b style='color:#00E5FF'>₹{h['current_price']:,.0f}</b></span></div></div>",unsafe_allow_html=True)
    st.markdown("---"); st.markdown("### Trades")
    tr=aget("/portfolio/trades"); trades=tr.get("trades",[]) if tr else []
    for t in trades[:15]:
        bc="#22C55E" if t["side"]=="BUY" else "#EF4444"; ts=t["timestamp"][:16].replace("T"," ")
        st.markdown(f"<div style='display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.04)'><div><span style='color:{bc};font-family:JetBrains Mono,monospace;font-size:11px;border:1px solid {bc};padding:2px 8px;border-radius:999px'>{t['side']}</span> <b style='margin-left:8px'>{t['symbol']}</b> <span style='color:#8892A4;font-size:13px'>{t['quantity']:.6f} @ ₹{t['price_inr']:,.0f}</span></div><div style='text-align:right'><b>₹{t['total_inr']:,.0f}</b><div style='color:#505869;font-size:11px;font-family:JetBrains Mono,monospace'>{ts}</div></div></div>",unsafe_allow_html=True)
def show_trade():
    st.markdown("## Paper Trading")
    pr=aget("/trade/prices"); prices={p["coin_id"]:p for p in (pr.get("prices") or [])} if pr else {}
    c1,c2=st.columns(2)
    with c1:
        st.markdown("### 🟢 Buy")
        with st.form("bf"):
            cl=st.selectbox("Coin",list(COINS.keys()),key="bc"); cid=COINS[cl]
            amt=st.number_input("Amount (₹)",min_value=10.0,value=5000.0,step=100.0)
            if cid in prices:
                p=prices[cid]; q=amt/p["price_inr"]; clr="#22C55E" if p["change_24h_pct"]>=0 else "#EF4444"
                st.markdown(f"<div style='background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.2);border-radius:8px;padding:12px;margin:8px 0;font-size:13px'><div style='color:#8892A4'>Price</div><div style='font-size:18px;font-weight:700;color:#00E5FF'>₹{p['price_inr']:,.2f}</div><div style='color:#8892A4'>You get ≈ <b style='color:#EDE9E0'>{q:.6f} {p['symbol']}</b></div><div style='color:{clr};font-size:12px'>24h: {p['change_24h_pct']:+.2f}%</div></div>",unsafe_allow_html=True)
            s=st.form_submit_button("Buy Now →",use_container_width=True)
        if s:
            r,ok=apost("/trade/buy",{"coin_id":cid,"amount_inr":amt})
            if ok: st.success(f"✅ {r['message']}"); st.info(f"Balance: ₹{r['balance_remaining_inr']:,.2f}")
            else: st.error(r.get("detail","Failed"))
    with c2:
        st.markdown("### 🔴 Sell")
        pf=aget("/portfolio/"); hs=pf.get("holdings",[]) if pf else []
        if not hs: st.info("No holdings to sell.")
        else:
            with st.form("sf"):
                opts={f"{h['symbol']} ({h['quantity']:.4f})":h["coin_id"] for h in hs}
                sel=st.selectbox("Holding",list(opts.keys())); scid=opts[sel]
                mode=st.radio("Mode",["Percentage","Quantity"],horizontal=True)
                if mode=="Percentage":
                    pct=st.slider("Sell %",1,100,50); sd={"coin_id":scid,"sell_pct":pct}
                else:
                    hh=next(x for x in hs if x["coin_id"]==scid)
                    qty=st.number_input("Qty",min_value=0.000001,max_value=hh["quantity"],value=hh["quantity"]); sd={"coin_id":scid,"quantity":qty}
                s2=st.form_submit_button("Sell Now →",use_container_width=True)
            if s2:
                r,ok=apost("/trade/sell",sd)
                if ok: pnl=r.get("pnl_inr",0); st.success(f"{'📈'if pnl>=0 else'📉'} {r['message']}"); st.info(f"Balance: ₹{r['balance_inr']:,.2f}")
                else: st.error(r.get("detail","Failed"))
def show_market():
    st.markdown("## Market Data")
    cl=st.selectbox("Coin",list(COINS.keys())); cid=COINS[cl]
    days=st.select_slider("Period",[7,14,30,60,90],value=30)
    data=aget(f"/ohlcv/{cid}?days={days}",auth=False) or []
    if data:
        df=pd.DataFrame(data)
        if all(c in df.columns for c in ["open","high","low","close"]):
            fig=go.Figure(go.Candlestick(x=list(range(len(df))),open=df["open"],high=df["high"],low=df["low"],close=df["close"],increasing=dict(line=dict(color="#22C55E"),fillcolor="rgba(34,197,94,0.3)"),decreasing=dict(line=dict(color="#EF4444"),fillcolor="rgba(239,68,68,0.3)")))
            fig.update_layout(**PLOT,height=420,title=dict(text=f"{cl} — {days}d",font=dict(color="#EDE9E0")),xaxis_rangeslider_visible=False)
            st.plotly_chart(fig,use_container_width=True)
def show_automation():
    st.markdown("## ⚡ Automation Rules")
    st.markdown("<div style='color:#8892A4;font-size:14px;margin-bottom:20px'>Rules auto-execute trades when conditions are met. Checked every 60 seconds.</div>",unsafe_allow_html=True)
    PRESETS={"Buy BTC dip":{"coin_id":"bitcoin","rule_type":"price_below","action":"buy","trigger_value":5000000,"amount_inr":5000,"interval":None},"Sell ETH high":{"coin_id":"ethereum","rule_type":"price_above","action":"sell","trigger_value":300000,"amount_inr":5000,"interval":None},"Take profit 20%":{"coin_id":"bitcoin","rule_type":"profit_pct","action":"sell","trigger_value":20,"amount_inr":5000,"interval":None},"Stop loss 10%":{"coin_id":"ethereum","rule_type":"loss_pct","action":"sell","trigger_value":10,"amount_inr":5000,"interval":None},"Weekly DCA BTC":{"coin_id":"bitcoin","rule_type":"recurring","action":"buy","trigger_value":0,"amount_inr":1000,"interval":"weekly"}}
    c1,c2=st.columns([1.2,0.8])
    with c1:
        st.markdown("### Create Rule")
        pre_name=st.selectbox("Preset",["Custom"]+list(PRESETS.keys())); pre=PRESETS.get(pre_name,{})
        with st.form("rul"):
            cl=st.selectbox("Coin",list(COINS.keys()),index=list(COINS.values()).index(pre.get("coin_id","bitcoin")) if pre else 0); cid=COINS[cl]
            rt_opts=["price_below","price_above","profit_pct","loss_pct","recurring"]
            rt=st.selectbox("Rule Type",rt_opts,index=rt_opts.index(pre.get("rule_type","price_below")) if pre else 0)
            act=st.radio("Action",["buy","sell"],horizontal=True,index=["buy","sell"].index(pre.get("action","buy")) if pre else 0)
            lbl={"price_below":"Trigger Price (₹)","price_above":"Trigger Price (₹)","profit_pct":"Profit % trigger","loss_pct":"Loss % trigger","recurring":"Not used (0)"}[rt]
            tv=st.number_input(lbl,min_value=0.0,value=float(pre.get("trigger_value",5000000)))
            ai=st.number_input("Amount (₹)",min_value=10.0,value=float(pre.get("amount_inr",5000)))
            inv=None
            if rt=="recurring": inv=st.selectbox("Frequency",["daily","weekly","monthly"],index=["daily","weekly","monthly"].index(pre.get("interval","weekly")) if pre.get("interval") else 1)
            nt=st.text_input("Note",placeholder="My strategy")
            sub=st.form_submit_button("Create Rule →",use_container_width=True)
        if sub:
            pl={"coin_id":cid,"rule_type":rt,"action":act,"trigger_value":tv,"amount_inr":ai,"note":nt or None}
            if rt=="recurring": pl["interval"]=inv
            r,ok=apost("/automation/rules",pl)
            if ok: st.success(f"✅ {r.get('description','')}"); st.rerun()
            else: st.error(r.get("detail","Failed"))
    with c2:
        st.markdown("### Guide")
        st.markdown("<div style='background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.1);border-radius:10px;padding:16px;font-size:13px;line-height:1.9'><b style='color:#00E5FF'>price_below</b> — Buy/sell when price drops under ₹X<br><b style='color:#00E5FF'>price_above</b> — Buy/sell when price rises above ₹X<br><b style='color:#7C3AED'>profit_pct</b> — Sell at X% profit (take profit)<br><b style='color:#EF4444'>loss_pct</b> — Sell at X% loss (stop loss)<br><b style='color:#22C55E'>recurring</b> — Auto-buy daily/weekly/monthly (DCA)</div>",unsafe_allow_html=True)
    st.markdown("---"); st.markdown("### Active Rules")
    rr=aget("/automation/rules"); rules=rr.get("rules",[]) if rr else []
    if not rules: st.info("No rules yet.")
    for r in rules:
        sc="#22C55E" if r["is_active"] else "#505869"; ac="#22C55E" if r["action"]=="buy" else "#EF4444"
        st.markdown(f"<div class='tcard'><div style='display:flex;justify-content:space-between'><div><b style='font-size:15px'>{r['note'] or r['rule_type']}</b> <span style='color:#8892A4;font-size:12px'>#{r['id']}</span></div><span style='color:{sc};font-size:12px;font-family:JetBrains Mono,monospace'>{'🟢 Active'if r['is_active']else'⏸ Paused'}</span></div><div style='display:flex;gap:20px;margin-top:10px;color:#8892A4;font-size:12px'><span>Coin: <b style='color:#EDE9E0'>{r['coin_id']}</b></span><span>Type: <b style='color:#00E5FF'>{r['rule_type']}</b></span><span>Action: <b style='color:{ac}'>{r['action'].upper()}</b></span><span>Amount: <b style='color:#EDE9E0'>₹{r['amount_inr']:,.0f}</b></span><span>Triggered: <b style='color:#EDE9E0'>{r['times_triggered']}x</b></span></div></div>",unsafe_allow_html=True)
        b1,b2=st.columns(2)
        with b1:
            if st.button(f"{'Pause'if r['is_active']else'Resume'}",key=f"t{r['id']}"): apost(f"/automation/rules/{r['id']}/toggle",{}); st.rerun()
        with b2:
            if st.button("🗑 Delete",key=f"d{r['id']}"): requests.delete(f"{API}/automation/rules/{r['id']}",headers=hdr()); st.rerun()
    st.markdown("---"); st.markdown("### Execution Log")
    lr=aget("/automation/logs"); logs=lr.get("logs",[]) if lr else []
    if logs:
        for l in logs[:10]:
            c="#22C55E" if l["status"]=="success" else "#EF4444"
            st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:13px'><div><span style='color:{c};font-family:JetBrains Mono,monospace;font-size:11px'>{l['status'].upper()}</span> <b style='margin-left:8px'>{l['action'].upper()} {l['coin_id']}</b> <span style='color:#8892A4;margin-left:8px'>{l['message']}</span></div><span style='color:#505869;font-size:11px;font-family:JetBrains Mono,monospace'>{l['executed_at'][:16].replace('T',' ')}</span></div>",unsafe_allow_html=True)
    else: st.info("No executions yet.")
def show_ai():
    st.markdown("## 🧠 AI Research")
    for i,q in enumerate(["Signs of rug pull?","Hold Bitcoin long term?","What happens after halving?","How to detect wash trading?"]):
        if st.columns(2)[i%2].button(q,use_container_width=True): st.session_state["aiq"]=q
    query=st.text_input("Ask anything",value=st.session_state.get("aiq",""),placeholder="Ask about crypto...")
    if st.button("Ask AI →",type="primary") and query:
        with st.spinner("Thinking..."):
            r,ok=apost("/rag/query",{"query":query})
        if ok:
            st.markdown(f"<div style='background:rgba(0,229,255,0.04);border:1px solid rgba(0,229,255,0.15);border-radius:12px;padding:20px;margin-top:16px'><div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#00E5FF;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px'>AI Analysis</div><div style='font-size:15px;line-height:1.75'>{r.get('summary','')}</div></div>",unsafe_allow_html=True)
            for s in r.get("sources",[]): st.markdown(f"- {s['title']} `{s.get('score',0):.2f}`")
    if "aiq" in st.session_state: del st.session_state["aiq"]
if not st.session_state.token:
    show_auth()
else:
    show_sidebar()
    pg=st.session_state.page
    if   pg=="dashboard":  show_dashboard()
    elif pg=="portfolio":  show_portfolio()
    elif pg=="trade":      show_trade()
    elif pg=="market":     show_market()
    elif pg=="automation": show_automation()
    elif pg=="ai":         show_ai()
    st.markdown("---")
    st.markdown("<div style='text-align:center;font-family:JetBrains Mono,monospace;font-size:11px;color:#505869;padding:8px'>CryptoSentinel · Paper Trading Only · Not Financial Advice</div>",unsafe_allow_html=True)
