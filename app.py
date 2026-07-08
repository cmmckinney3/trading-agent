import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
import os
import json
import markdown as md_lib

from utils.config import load_config, save_config, load_portfolio, save_portfolio, PROVIDER_PRESETS, DEFAULT_WATCHLIST
from utils.market_data import get_quote, get_portfolio_value, get_price_history, get_technicals, screen_momentum_tickers, get_news, get_earnings_date
from utils.agent import chat_with_agent, chat_with_agent_tools, get_trade_recommendation, run_daily_screener, SYSTEM_PROMPT
from utils.code_agent import run_code_agent
from utils.llm import chat_completions_create
from utils.journal import load_journal, log_trade, close_trade, check_alerts
from utils.weather import get_weather
from utils.email import (
    fetch_unread_emails, get_auth_url, authenticate_gmail, get_gmail_service, mark_as_read,
    CREDENTIALS_FILE, TOKEN_FILE as GMAIL_TOKEN_FILE,
)
from utils.calendar import (
    fetch_todays_events, fetch_upcoming_events, get_calendar_service, authenticate_calendar,
    TOKEN_FILE as CALENDAR_TOKEN_FILE,
)

@st.cache_data(ttl=3600, show_spinner=False)
def _get_portfolio_value_cached(positions_json: str) -> dict:
    return get_portfolio_value(json.loads(positions_json))


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TradeDesk AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

:root {
    --bg: #020617;
    --surface: #070d1a;
    --panel: rgba(7, 13, 26, 0.72);
    --panel-hover: rgba(12, 20, 38, 0.82);
    --border: rgba(148, 163, 184, 0.10);
    --border-strong: rgba(99, 102, 241, 0.30);
    --border-accent: rgba(16, 185, 129, 0.22);
    --text: #EEF2FF;
    --text-sec: rgba(199, 210, 254, 0.80);
    --muted: rgba(148, 163, 184, 0.72);
    --faint: rgba(100, 116, 139, 0.60);
    --green: #10B981;
    --green-dim: rgba(16, 185, 129, 0.12);
    --red: #F43F5E;
    --red-dim: rgba(244, 63, 94, 0.12);
    --blue: #6366F1;
    --blue-dim: rgba(99, 102, 241, 0.12);
    --cyan: #22D3EE;
    --gold: #F59E0B;
    --shadow: 0 24px 64px rgba(0,0,0,.50), 0 0 0 1px rgba(255,255,255,.03);
    --shadow-sm: 0 4px 16px rgba(0,0,0,.30);
    --glow-green: 0 0 24px rgba(16,185,129,.18);
    --radius: 14px;
    --radius-sm: 9px;
    --radius-lg: 22px;
}

html, body, [class*="css"] {
    font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse 1100px 650px at 6% 5%, rgba(16,185,129,.09), transparent 55%),
        radial-gradient(ellipse 900px 700px at 95% 12%, rgba(99,102,241,.09), transparent 50%),
        radial-gradient(ellipse 700px 500px at 52% 100%, rgba(16,185,129,.06), transparent 55%),
        var(--bg);
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: rgba(2, 5, 16, 0.82);
    border-right: 1px solid var(--border);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
}

@keyframes pulse-live {
    0%, 100% { opacity: 1; box-shadow: 0 0 6px #10B981; }
    50% { opacity: 0.45; box-shadow: 0 0 2px #10B981; }
}

.metric-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: var(--shadow);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    position: relative;
    overflow: hidden;
    transition: border-color .2s ease;
}
.metric-card::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: linear-gradient(180deg, var(--green) 0%, transparent 100%);
    border-radius: 14px 0 0 14px;
}
.metric-card:hover { border-color: var(--border-accent); }

.metric-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--faint);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 6px;
}

.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
}

.metric-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    margin-top: 6px;
    color: var(--muted);
}

.positive { color: var(--green); }
.negative { color: var(--red); }
.neutral  { color: var(--cyan); }

.position-row {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--shadow-sm);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    transition: all .2s ease;
    cursor: pointer;
}
.position-row:hover {
    border-color: var(--border-accent);
    background: var(--panel-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow);
}

.chat-user {
    background: rgba(99,102,241,.08);
    border: 1px solid rgba(99,102,241,.18);
    border-radius: var(--radius) var(--radius) var(--radius-sm) var(--radius);
    padding: 12px 16px;
    margin: 8px 0 8px 15%;
    font-size: 14px;
    box-shadow: var(--shadow-sm);
    line-height: 1.6;
}

.chat-agent {
    background: rgba(16,185,129,.06);
    border: 1px solid rgba(16,185,129,.16);
    border-radius: var(--radius) var(--radius) var(--radius) var(--radius-sm);
    padding: 12px 16px;
    margin: 8px 15% 8px 0;
    font-size: 14px;
    font-family: 'Space Grotesk', system-ui, sans-serif;
    box-shadow: var(--shadow-sm);
    line-height: 1.6;
}

.chat-agent p { margin: 0 0 8px 0; }
.chat-agent p:last-child { margin-bottom: 0; }
.chat-agent ul, .chat-agent ol { margin: 4px 0 8px 0; padding-left: 20px; }
.chat-agent li { margin: 2px 0; }
.chat-agent h1, .chat-agent h2, .chat-agent h3 { margin: 10px 0 4px 0; font-size: 1em; font-weight: 600; }
.chat-agent strong { font-weight: 600; }
.chat-agent code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: rgba(0,0,0,.15); padding: 1px 4px; border-radius: 3px; }

.rec-card {
    background: var(--panel);
    border: 1px solid var(--border-accent);
    border-top: 2px solid var(--green);
    border-radius: var(--radius);
    padding: 20px;
    margin: 12px 0;
    box-shadow: var(--shadow);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    font-size: 14px;
    line-height: 1.7;
}

.rec-card p { margin: 0 0 10px 0; }
.rec-card p:last-child { margin-bottom: 0; }
.rec-card ul, .rec-card ol { margin: 4px 0 10px 0; padding-left: 20px; }
.rec-card li { margin: 3px 0; }
.rec-card h1, .rec-card h2, .rec-card h3 { margin: 12px 0 4px 0; font-weight: 600; }
.rec-card h1 { font-size: 1.1em; }
.rec-card h2 { font-size: 1em; }
.rec-card h3 { font-size: 0.95em; }
.rec-card strong { font-weight: 600; }
.rec-card code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: rgba(0,0,0,.15); padding: 1px 4px; border-radius: 3px; }

.page-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--faint);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    margin-bottom: 4px;
}

.page-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 34px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.03em;
    margin-bottom: 24px;
    line-height: 1.1;
}

.accent {
    background: linear-gradient(90deg, var(--green) 0%, var(--cyan) 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.stButton > button {
    background: rgba(7,13,26,.55);
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 10px 14px;
    transition: all .18s ease;
    cursor: pointer;
}
.stButton > button:hover {
    background: rgba(16,185,129,.08);
    border-color: rgba(16,185,129,.28);
    box-shadow: 0 0 0 1px rgba(16,185,129,.12), 0 8px 24px rgba(16,185,129,.08);
    transform: translateY(-1px);
    color: var(--green);
}
.stButton > button:active { transform: translateY(0); }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(7,13,26,.55);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    transition: border-color .18s ease, box-shadow .18s ease;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(99,102,241,.40);
    box-shadow: 0 0 0 3px rgba(99,102,241,.08);
    outline: none;
}

.stTabs [data-baseweb="tab-list"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 4px;
    gap: 2px;
    backdrop-filter: blur(16px);
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 8px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    transition: all .18s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-sec);
    background: rgba(255,255,255,.03);
}
.stTabs [aria-selected="true"] {
    color: var(--text) !important;
    background: rgba(99,102,241,.14) !important;
    border-color: rgba(99,102,241,.22) !important;
}

hr { border-color: var(--border); margin: 20px 0; }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,.22); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,.38); }

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    letter-spacing: -0.02em;
}

[data-testid="stExpander"] details {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: blur(16px);
}
[data-testid="stExpander"] summary {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 13px;
    font-weight: 500;
}

[data-baseweb="select"] > div:first-child {
    background: rgba(7,13,26,.55) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text) !important;
}

[data-testid="stNumberInput"] input {
    background: rgba(7,13,26,.55) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}

[data-testid="stCode"] pre {
    background: rgba(7,13,26,.80) !important;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-family: 'JetBrains Mono', monospace !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
if "config" not in st.session_state:
    st.session_state.config = load_config()

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

if "conversation" not in st.session_state:
    st.session_state.conversation = []

if "screener_results" not in st.session_state:
    st.session_state.screener_results = None

if "last_screener_run" not in st.session_state:
    st.session_state.last_screener_run = None

if "gmail_service" not in st.session_state:
    if os.path.exists(GMAIL_TOKEN_FILE) and os.path.exists(CREDENTIALS_FILE):
        try:
            st.session_state.gmail_service = get_gmail_service()
        except Exception:
            st.session_state.gmail_service = None
    else:
        st.session_state.gmail_service = None

if "gmail_emails" not in st.session_state:
    st.session_state.gmail_emails = None

if "gmail_summary" not in st.session_state:
    st.session_state.gmail_summary = None

if "morning_briefing" not in st.session_state:
    st.session_state.morning_briefing = None

if "calendar_service" not in st.session_state:
    if os.path.exists(CALENDAR_TOKEN_FILE) and os.path.exists(CREDENTIALS_FILE):
        try:
            st.session_state.calendar_service = get_calendar_service()
        except Exception:
            st.session_state.calendar_service = None
    else:
        st.session_state.calendar_service = None

if "calendar_events" not in st.session_state:
    st.session_state.calendar_events = None

# Derived on every render from current config
ai_config = {
    "model": st.session_state.config.get("model", "gpt-4o-mini"),
    "api_key": st.session_state.config.get("api_key", "") or None,
    "base_url": st.session_state.config.get("base_url", "") or None,
}

city = st.session_state.config.get("city", "").strip() or "New York,NY"

# ── API key warning ───────────────────────────────────────────────────────────
if not st.session_state.config.get("api_key"):
    st.warning("No API key configured — go to the ⚙️ Settings tab to get started.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding-bottom:18px;border-bottom:1px solid rgba(148,163,184,.10);margin-bottom:18px">
        <div style="display:flex;align-items:center;gap:10px">
            <div style="width:34px;height:34px;background:linear-gradient(135deg,#10B981 0%,#059669 100%);border-radius:10px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 18px rgba(16,185,129,.22);flex-shrink:0">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
            </div>
            <div>
                <div style="font-family:'Space Grotesk',sans-serif;font-size:17px;font-weight:700;color:#EEF2FF;letter-spacing:-.025em;line-height:1.2">TradeDesk</div>
                <div style="display:flex;align-items:center;gap:6px;margin-top:2px">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(100,116,139,.65);text-transform:uppercase;letter-spacing:.14em">AI Terminal</span>
                    <span style="width:6px;height:6px;background:#10B981;border-radius:50%;display:inline-block;box-shadow:0 0 6px #10B981;animation:pulse-live 2s ease-in-out infinite"></span>
                </div>
            </div>
        </div>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(100,116,139,.60);text-transform:uppercase;letter-spacing:.14em;margin-bottom:14px">Portfolio</div>
    """, unsafe_allow_html=True)

    positions_json = json.dumps(st.session_state.portfolio["positions"], sort_keys=True)
    col_ref, col_time = st.columns([1, 2])
    with col_ref:
        if st.button("↺ Refresh", key="sb_refresh", width='stretch'):
            _get_portfolio_value_cached.clear()
            st.rerun()

    with st.spinner("Loading prices..."):
        pf = _get_portfolio_value_cached(positions_json)

    with col_time:
        st.caption(f"{len(pf['positions'])} holdings")

    total_invested = pf["total_value"]
    total_with_cash = total_invested + st.session_state.portfolio["cash"]

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Value</div>
        <div class="metric-value">${total_with_cash:,.2f}</div>
        <div class="metric-sub neutral">Cash: ${st.session_state.portfolio['cash']:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    _SCROLL_THRESHOLD = 8

    if pf["positions"]:
        st.markdown("**Positions**")
        rows_html = ""
        for pos in pf["positions"]:
            val = pos.get("value", 0)
            chg = pos.get("change_pct", 0)
            chg_class = "positive" if chg >= 0 else "negative"
            chg_sym = "▲" if chg >= 0 else "▼"
            rows_html += f"""
            <div class="position-row">
                <div>
                    <div style="font-family:'JetBrains Mono',monospace;font-weight:600;color:#EEF2FF">{pos['ticker']}</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(100,116,139,.65)">{pos['shares']} shares</div>
                </div>
                <div style="text-align:right">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:#EEF2FF">${val:,.2f}</div>
                    <div class="{chg_class}" style="font-family:'JetBrains Mono',monospace;font-size:11px">{chg_sym} {abs(chg):.2f}%</div>
                </div>
            </div>"""

        if len(pf["positions"]) > _SCROLL_THRESHOLD:
            st.markdown(
                f'<div style="max-height:420px;overflow-y:auto;padding-right:2px">{rows_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(rows_html, unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("⚙ Manage Positions"):
        st.markdown("**Add Position**")
        col1, col2 = st.columns(2)
        with col1:
            new_ticker = st.text_input("Ticker", key="new_ticker", placeholder="AAPL")
        with col2:
            new_shares = st.number_input("Shares", min_value=0.0, step=0.001, key="new_shares")
        new_cost = st.number_input("Cost Basis (optional)", min_value=0.0, step=0.01, key="new_cost")
        if st.button("Add"):
            if new_ticker and new_shares > 0:
                st.session_state.portfolio["positions"].append({
                    "ticker": new_ticker.upper(),
                    "shares": new_shares,
                    "cost_basis": new_cost if new_cost > 0 else None,
                })
                save_portfolio(st.session_state.portfolio)
                _get_portfolio_value_cached.clear()
                st.rerun()

        st.markdown("**Update Cash**")
        new_cash = st.number_input("Cash Balance", value=st.session_state.portfolio["cash"], step=0.01)
        if st.button("Update Cash"):
            st.session_state.portfolio["cash"] = new_cash
            save_portfolio(st.session_state.portfolio)
            st.rerun()

        st.markdown("**Remove Position**")
        tickers = [p["ticker"] for p in st.session_state.portfolio["positions"]]
        if tickers:
            remove_ticker = st.selectbox("Select", tickers, key="remove_sel")
            if st.button("Remove"):
                st.session_state.portfolio["positions"] = [
                    p for p in st.session_state.portfolio["positions"] if p["ticker"] != remove_ticker
                ]
                save_portfolio(st.session_state.portfolio)
                _get_portfolio_value_cached.clear()
                st.rerun()


# ── Main content ──────────────────────────────────────────────────────────────
st.markdown('<div class="page-header">AI Swing Trading Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="page-title">TradeDesk <span class="accent">AI</span></div>', unsafe_allow_html=True)

# ── Position alerts (piggybacking on already-fetched pf prices) ───────────────
for _p in pf["positions"]:
    _price = _p.get("current_price")
    if _price is None:
        continue
    if _p.get("target") and _price >= _p["target"]:
        st.success(f"🎯 **{_p['ticker']} TARGET HIT** — current ${_price:.2f} ≥ target ${_p['target']:.2f}")
    if _p.get("stop") and _price <= _p["stop"]:
        st.error(f"🛑 **{_p['ticker']} STOP TRIGGERED** — current ${_price:.2f} ≤ stop ${_p['stop']:.2f}")

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Morning Briefing", "Analyst Chat", "Screener",
    "Ticker Analysis", "Positions", "Settings", "Journal", "Code Agent",
])


# ── Tab 0: Morning Briefing ───────────────────────────────────────────────────
with tab0:
    st.markdown("**Good morning! Here's your daily overview.**")

    weather_col, market_col = st.columns(2)

    with weather_col:
        st.markdown(f"### Weather — {city}")
        with st.spinner("Fetching weather..."):
            weather = get_weather(city)

        if weather:
            # Pre-compute next 2 hourly slots
            _cur_hr = datetime.now().hour
            _all_hourly = list(weather["forecast"][0].get("hourly", [])) if weather.get("forecast") else []
            if len([s for s in _all_hourly if int(s["time"]) // 100 > _cur_hr]) < 2 and len(weather.get("forecast", [])) > 1:
                _all_hourly = _all_hourly + list(weather["forecast"][1].get("hourly", []))
            _next_slots = [s for s in _all_hourly if int(s["time"]) // 100 > _cur_hr][:2]

            def _fmt_hr(t):
                h = int(t) // 100
                return ("12am" if h == 0 else f"{h}am") if h < 12 else ("12pm" if h == 12 else f"{h - 12}pm")

            # Weather icon
            _desc = weather["description"]
            _icon = ("☀️" if any(w in _desc for w in ("Sunny", "Clear")) else
                     "⛅" if any(w in _desc for w in ("Cloud", "Partly")) else
                     "🌧️" if any(w in _desc for w in ("Rain", "Drizzle")) else
                     "⛈️" if "Thunder" in _desc else
                     "🌨️" if "Snow" in _desc else "🌤️")

            st.markdown(f"""
            <div class="metric-card">
                <div style="display:flex;align-items:center;gap:16px">
                    <div style="font-size:42px">{_icon}</div>
                    <div>
                        <div class="metric-value">{weather['temp_f']}°F</div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:rgba(148,163,184,.72)">
                            Feels like {weather['feels_like_f']}°F &middot; {weather['description']}
                        </div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:14px">
                    <div><span style="color:rgba(100,116,139,.60);font-size:10px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.12em">Humidity</span><br>
                        <span style="color:#EEF2FF;font-family:'JetBrains Mono',monospace">{weather['humidity']}%</span></div>
                    <div><span style="color:rgba(100,116,139,.60);font-size:10px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.12em">Wind</span><br>
                        <span style="color:#EEF2FF;font-family:'JetBrains Mono',monospace">{weather['wind_mph']} mph {weather['wind_dir']}</span></div>
                    <div><span style="color:rgba(100,116,139,.60);font-size:10px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.12em">UV Index</span><br>
                        <span style="color:#EEF2FF;font-family:'JetBrains Mono',monospace">{weather['uv_index']}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Hourly strip — separate call to avoid f-string nesting issues
            if _next_slots:
                _now_cell = (
                    '<div style="flex:1;text-align:center;padding:10px 8px;background:rgba(16,185,129,.08);'
                    'border-radius:9px;border:1px solid rgba(16,185,129,.22)">'
                    '<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:rgba(100,116,139,.60);'
                    'text-transform:uppercase;letter-spacing:.12em">Now</div>'
                    '<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;'
                    'color:#10B981;margin:4px 0">' + str(weather['temp_f']) + '&deg;</div>'
                    '<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:rgba(148,163,184,.70)">'
                    + weather['description'][:18] + '</div></div>'
                )
                _future_cells = ""
                for _s in _next_slots:
                    _label = _fmt_hr(_s["time"])
                    _temp  = _s.get("tempF", "—")
                    _sdesc = _s.get("weatherDesc", [{}])[0].get("value", "")[:18]
                    _future_cells += (
                        '<div style="flex:1;text-align:center;padding:10px 8px;background:rgba(255,255,255,.03);'
                        'border-radius:9px;border:1px solid rgba(148,163,184,.10)">'
                        '<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:rgba(100,116,139,.60);'
                        'text-transform:uppercase;letter-spacing:.12em">' + _label + '</div>'
                        '<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;'
                        'color:#EEF2FF;margin:4px 0">' + str(_temp) + '&deg;</div>'
                        '<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:rgba(148,163,184,.70)">'
                        + _sdesc + '</div></div>'
                    )
                st.markdown(
                    '<div style="display:flex;gap:8px;margin-bottom:12px">'
                    + _now_cell + _future_cells +
                    '</div>',
                    unsafe_allow_html=True,
                )

            if weather.get("forecast"):
                st.markdown("**3-Day Forecast**")
                fc_cols = st.columns(3)
                for i, (col, day) in enumerate(zip(fc_cols, weather["forecast"][:3])):
                    with col:
                        day_date = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a %m/%d") if "date" in day else f"Day {i+1}"
                        max_t = day.get("maxtempF", "")
                        min_t = day.get("mintempF", "")
                        day_desc = day.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value", "")
                        st.markdown(f"""
                        <div class="metric-card" style="text-align:center;padding:14px">
                            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--faint)">{day_date}</div>
                            <div style="font-size:24px;margin:6px 0">
                                {"☀️" if "Sunny" in day_desc or "Clear" in day_desc else
                                 ("⛅" if "Cloud" in day_desc or "Partly" in day_desc else
                                 ("🌧️" if "Rain" in day_desc else "🌤️"))}
                            </div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:var(--text)">
                                <span style="color:var(--green)">{max_t}°F</span> /
                                <span style="color:var(--blue)">{min_t}°F</span>
                            </div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted)">{day_desc[:30]}</div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.warning("Unable to fetch weather data.")

    with market_col:
        st.markdown("### Market Overview")
        with st.spinner("Fetching market data..."):
            indices = [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^DJI", "DOW")]
            index_data = []
            for ticker, name in indices:
                try:
                    t = yf.Ticker(ticker)
                    hist = t.history(period="2d")
                    if not hist.empty:
                        close = hist["Close"].iloc[-1]
                        prev = hist["Close"].iloc[-2] if len(hist) > 1 else close
                        chg = close - prev
                        chg_pct = (chg / prev) * 100
                        index_data.append({
                            "name": name,
                            "value": round(close, 2),
                            "change": round(chg, 2),
                            "change_pct": round(chg_pct, 2),
                        })
                except Exception:
                    pass

            for idx in index_data:
                chg_color = "var(--green)" if idx["change"] >= 0 else "var(--red)"
                chg_sym = "▲" if idx["change"] >= 0 else "▼"
                st.markdown(f"""
                <div class="metric-card" style="padding:12px 14px">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <div class="metric-label">{idx['name']}</div>
                            <div class="metric-value" style="font-size:20px">{idx['value']:,.2f}</div>
                        </div>
                        <div style="text-align:right">
                            <div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:600;color:{chg_color}">
                                {chg_sym} {abs(idx['change_pct']):.2f}%
                            </div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted)">
                                {chg_sym} {abs(idx['change']):.2f}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Your Portfolio")
        st.markdown(f"""
        <div class="metric-card" style="padding:12px 14px">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <div class="metric-label">Total Value</div>
                    <div class="metric-value" style="font-size:20px;color:var(--green)">${total_with_cash:,.2f}</div>
                </div>
                <div style="text-align:right">
                    <div class="metric-label">Positions</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:16px;color:var(--text)">
                        {len(pf["positions"])} holdings
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Gmail Digest ──────────────────────────────────────────────────────────
    st.markdown("### Email Digest")

    if not st.session_state.gmail_service:
        if os.path.exists(CREDENTIALS_FILE):
            if st.button("🔐 Start Gmail Auth", width='stretch'):
                try:
                    with st.spinner("Opening browser for Google auth..."):
                        authenticate_gmail()
                        st.session_state.gmail_service = get_gmail_service()
                    st.success("Authenticated! Loading emails...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Auth failed: {e}")
        else:
            st.warning("Gmail setup required.")
            st.markdown(f"""
            <div class="metric-card" style="padding:16px">
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text)">
                    <b>Step 1:</b> Set up Gmail API access<br><br>
                    {get_auth_url().replace(chr(10), "<br>")}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        col_refresh, col_summarize, col_clear = st.columns(3)
        with col_refresh:
            refresh_emails = st.button("🔄 Refresh Emails", width='stretch')
        with col_summarize:
            summarize = st.button("🤖 Summarize with AI", width='stretch')
        with col_clear:
            mark_all_read = st.button("✅ Mark All Read", width='stretch')

        if refresh_emails:
            with st.spinner("Fetching emails..."):
                st.session_state.gmail_emails = fetch_unread_emails(st.session_state.gmail_service)
                st.session_state.gmail_summary = None
            st.rerun()

        if st.session_state.gmail_emails is None:
            with st.spinner("Fetching emails..."):
                try:
                    st.session_state.gmail_emails = fetch_unread_emails(st.session_state.gmail_service)
                except Exception as e:
                    st.error(f"Email error: {e}")

        if mark_all_read and st.session_state.gmail_emails:
            for em in st.session_state.gmail_emails:
                try:
                    mark_as_read(st.session_state.gmail_service, em["id"])
                except Exception:
                    pass
            st.session_state.gmail_emails = []
            st.session_state.gmail_summary = None
            st.rerun()

        if summarize and st.session_state.gmail_emails:
            with st.spinner("AI is summarizing your emails..."):
                email_context = "\n".join([
                    f"- From: {e['from']} | Subject: {e['subject']} | {e['snippet'][:100]}"
                    for e in st.session_state.gmail_emails[:10]
                ])
                messages = [
                    {"role": "system", "content": "You are a concise email summarizer. Given a list of emails, provide a brief morning digest: group by priority, highlight action items, and note anything urgent. Be direct and actionable."},
                    {"role": "user", "content": f"Summarize these emails for my morning digest:\n\n{email_context}"},
                ]
                response = chat_completions_create(messages=messages, temperature=0.5, **ai_config)
                st.session_state.gmail_summary = response["content"]

        if st.session_state.gmail_emails:
            st.markdown(f"**{len(st.session_state.gmail_emails)} unread email(s)**")
            for em in st.session_state.gmail_emails[:10]:
                sender = em["from"].split("<")[0].strip() if "<" in em["from"] else em["from"]
                with st.expander(f"**{sender}** — {em['subject']}"):
                    st.caption(em["date"])
                    st.write(em["snippet"])
                    if st.button(f"Mark '{em['subject']}' as read", key=f"read_{em['id']}"):
                        try:
                            mark_as_read(st.session_state.gmail_service, em["id"])
                            st.session_state.gmail_emails = [e for e in st.session_state.gmail_emails if e["id"] != em["id"]]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
        else:
            st.info("No unread emails!")

        if st.session_state.gmail_summary:
            st.markdown("---")
            st.markdown("**AI Email Summary**")
            _html = md_lib.markdown(st.session_state.gmail_summary, extensions=["nl2br"])
            st.markdown(f'<div class="chat-agent">🤖 {_html}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Google Calendar ───────────────────────────────────────────────────────
    st.markdown("### Upcoming Schedule (5 Days)")

    if not st.session_state.calendar_service:
        if os.path.exists(CREDENTIALS_FILE):
            if st.button("📅 Connect Google Calendar", width='stretch'):
                try:
                    with st.spinner("Opening browser for Google Calendar auth..."):
                        authenticate_calendar()
                        st.session_state.calendar_service = get_calendar_service()
                        st.session_state.calendar_events = fetch_todays_events(st.session_state.calendar_service)
                    st.success("Calendar connected!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Calendar auth failed: {e}")
        else:
            st.info("Add credentials.json to enable Google Calendar.")
    else:
        cal_refresh, cal_upcoming = st.columns(2)
        with cal_refresh:
            if st.button("🔄 Refresh Calendar", width='stretch'):
                with st.spinner("Fetching calendar..."):
                    st.session_state.calendar_events = fetch_todays_events(st.session_state.calendar_service)
                st.rerun()
        with cal_upcoming:
            if st.button("📆 Show Next 5 Days", width='stretch'):
                with st.spinner("Fetching upcoming events..."):
                    st.session_state.calendar_events = fetch_upcoming_events(st.session_state.calendar_service, days=5)
                st.rerun()

        if st.session_state.calendar_events is None:
            with st.spinner("Loading upcoming events..."):
                try:
                    st.session_state.calendar_events = fetch_upcoming_events(st.session_state.calendar_service, days=5)
                except Exception as e:
                    st.error(f"Calendar error: {e}")

        if st.session_state.calendar_events is not None:
            if not st.session_state.calendar_events:
                st.info("Nothing on the calendar today.")
            else:
                for ev in st.session_state.calendar_events:
                    time_label = "All day" if ev["all_day"] else f"{ev['start_display']} – {ev['end_display']}"
                    loc_html = f'<span style="color:var(--faint);font-size:11px"> · 📍 {ev["location"]}</span>' if ev["location"] else ""
                    st.markdown(f"""
                    <div class="metric-card" style="padding:12px 14px;margin-bottom:8px">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start">
                            <div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:var(--text)">{ev['title']}</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--blue);margin-top:3px">{time_label}{loc_html}</div>
                            </div>
                        </div>
                        {f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:var(--muted);margin-top:6px">{ev["description"]}</div>' if ev.get("description") else ""}
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── AI Morning Briefing ───────────────────────────────────────────────────
    st.markdown("### AI Morning Briefing")
    st.caption("Combines weather, market, portfolio, and email context into a daily briefing")

    if st.button("📊 Generate Briefing", width='stretch'):
        with st.spinner("Generating your morning briefing..."):
            weather_ctx = ""
            if weather:
                weather_ctx = f"Weather in {city}: {weather['temp_f']}°F, {weather['description']}, wind {weather['wind_mph']}mph {weather['wind_dir']}, humidity {weather['humidity']}%."

            market_ctx = ""
            if index_data:
                idx_strs = [f"{i['name']}: {i['value']:,.2f} ({'+' if i['change'] >= 0 else ''}{i['change_pct']}%)" for i in index_data]
                market_ctx = f"Market indices: {', '.join(idx_strs)}."

            portfolio_ctx = (
                f"Portfolio value: ${total_with_cash:,.2f}. "
                f"Holdings: {', '.join([p['ticker'] for p in pf['positions']]) or 'none'}. "
                f"Cash: ${st.session_state.portfolio['cash']:.2f}."
            )

            email_ctx = ""
            if st.session_state.gmail_emails:
                email_ctx = f"You have {len(st.session_state.gmail_emails)} unread emails. Top subjects: {', '.join([e['subject'] for e in st.session_state.gmail_emails[:5]])}."

            calendar_ctx = ""
            if st.session_state.calendar_events:
                ev_strs = [
                    f"{e['title']} at {e['start_display']}" if not e["all_day"] else f"{e['title']} (all day)"
                    for e in st.session_state.calendar_events[:5]
                ]
                calendar_ctx = f"Today's calendar: {', '.join(ev_strs)}."

            try:
                momentum = screen_momentum_tickers()
                momentum_ctx = f"Top momentum tickers: {', '.join([m['ticker'] for m in momentum[:5]])}." if momentum else ""
            except Exception:
                momentum_ctx = ""

            briefing_prompt = f"""You are a morning briefing assistant. Generate a concise, actionable morning briefing for a swing trader.

Context:
{weather_ctx}
{market_ctx}
{portfolio_ctx}
{email_ctx}
{calendar_ctx}
{momentum_ctx}

Structure your briefing as:
1. **Good Morning** — brief greeting with weather/market flavor
2. **Market Snapshot** — what's happening in the market
3. **Portfolio Check** — quick assessment of current holdings
4. **Email Priorities** — any action items from unread emails
5. **Schedule** — key meetings or events today (if any)
6. **Today's Focus** — what to watch, any momentum plays
7. **Action Items** — bullet list of concrete actions

Be concise, direct, and actionable. No fluff."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": briefing_prompt},
            ]
            response = chat_completions_create(messages=messages, temperature=0.5, **ai_config)
            st.session_state.morning_briefing = response["content"]

    if st.session_state.morning_briefing:
        _html = md_lib.markdown(st.session_state.morning_briefing, extensions=["nl2br"])
        st.markdown(f'<div class="rec-card">{_html}</div>', unsafe_allow_html=True)


# ── Tab 1: Chat ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown("**Ask your AI trading analyst anything**")
    st.caption("Examples: 'What are today's top picks?' · 'Best momentum plays under $20?' · 'Give me a full trade on NVDA'")

    if not st.session_state.conversation:
        st.markdown("""
        <div style="text-align:center;padding:48px 40px 24px;color:rgba(100,116,139,.45);font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.06em">
            ▸ Start by asking for today's top picks, or type a ticker to analyze
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.conversation:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user">🧑 {msg["content"].split("USER QUESTION:")[-1].strip()}</div>', unsafe_allow_html=True)
            else:
                html_content = md_lib.markdown(msg["content"], extensions=["nl2br"])
                st.markdown(f'<div class="chat-agent">🤖 {html_content}</div>', unsafe_allow_html=True)

    st.markdown("---")

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Message",
            placeholder="Type your question...",
            label_visibility="collapsed",
            key="chat_input",
        )
    with col_btn:
        send = st.button("SEND", width='stretch')

    quick_cols = st.columns(4)
    quick_prompts = [
        "What are today's top 3 picks?",
        "Best momentum plays under $20?",
        "Review my current positions",
        "What sectors are leading today?",
    ]
    for i, (col, prompt) in enumerate(zip(quick_cols, quick_prompts)):
        with col:
            if st.button(prompt, key=f"quick_{i}", width='stretch'):
                user_input = prompt
                send = True

    if send and user_input:
        with st.spinner("Analyzing..."):
            portfolio_context = {**st.session_state.portfolio, "total_value": total_with_cash}
            watchlist = st.session_state.config.get("watchlist", DEFAULT_WATCHLIST)
            response = chat_with_agent_tools(
                user_input,
                st.session_state.conversation,
                portfolio_context,
                ai_config,
                watchlist=watchlist,
            )
            st.session_state.conversation.append({"role": "user", "content": user_input})
            st.session_state.conversation.append({"role": "assistant", "content": response})
        st.rerun()

    if st.session_state.conversation:
        if st.button("🗑 Clear Chat", key="clear_chat"):
            st.session_state.conversation = []
            st.rerun()


# ── Tab 2: Screener ───────────────────────────────────────────────────────────
with tab2:
    st.markdown("**Daily Momentum Screener**")
    st.caption("Scans high-momentum tickers and surfaces the AI's top swing trade candidates")

    col_run, col_time = st.columns([2, 3])
    with col_run:
        run_screener = st.button("🔍 RUN SCREENER", width='stretch')
    with col_time:
        if st.session_state.last_screener_run:
            st.caption(f"Last run: {st.session_state.last_screener_run}")

    if run_screener:
        with st.spinner("Scanning market... this takes ~30 seconds"):
            portfolio_context = {**st.session_state.portfolio, "total_value": total_with_cash}
            watchlist = st.session_state.config.get("watchlist", DEFAULT_WATCHLIST)
            result = run_daily_screener(portfolio_context, ai_config, watchlist=watchlist)
            st.session_state.screener_results = result
            st.session_state.last_screener_run = datetime.now().strftime("%b %d, %Y %I:%M %p")

    if st.session_state.screener_results:
        _html = md_lib.markdown(st.session_state.screener_results, extensions=["nl2br"])
        st.markdown(f'<div class="rec-card">{_html}</div>', unsafe_allow_html=True)


# ── Tab 3: Ticker Analysis ────────────────────────────────────────────────────
with tab3:
    st.markdown("**Analyze Any Ticker**")

    col_ticker, col_btn3 = st.columns([3, 1])
    with col_ticker:
        analyze_ticker = st.text_input("Enter ticker symbol", placeholder="e.g. NVDA", label_visibility="collapsed", key="analyze_input")
    with col_btn3:
        analyze_btn = st.button("ANALYZE", width='stretch')

    if analyze_btn and analyze_ticker:
        ticker = analyze_ticker.upper().strip()

        with st.spinner(f"Pulling data for {ticker}..."):
            quote = get_quote(ticker)
            tech = get_technicals(ticker)
            hist = get_price_history(ticker)
            news = get_news(ticker, limit=5)
            earnings = get_earnings_date(ticker)

        if not quote:
            st.error(f"Could not fetch data for {ticker}. Check the symbol.")
        else:
            chg_color = "#10B981" if quote["change"] >= 0 else "#F43F5E"
            st.markdown(f"""
            <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:24px;flex-wrap:wrap">
                <span style="font-family:'Space Grotesk',sans-serif;font-size:32px;font-weight:700;color:#EEF2FF;letter-spacing:-.03em">{ticker}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:600;color:#EEF2FF">${quote['price']:,.2f}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:15px;color:{chg_color};background:{'rgba(16,185,129,.10)' if quote['change'] >= 0 else 'rgba(244,63,94,.10)'};padding:4px 10px;border-radius:6px;border:1px solid {'rgba(16,185,129,.20)' if quote['change'] >= 0 else 'rgba(244,63,94,.20)'}">
                    {'▲' if quote['change'] >= 0 else '▼'} {abs(quote['change']):.2f} ({abs(quote['change_pct']):.2f}%)
                </span>
            </div>
            """, unsafe_allow_html=True)

            if not hist.empty:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist["Open"],
                    high=hist["High"],
                    low=hist["Low"],
                    close=hist["Close"],
                    name=ticker,
                    increasing_fillcolor="#10B981",
                    decreasing_fillcolor="#F43F5E",
                    increasing_line_color="#10B981",
                    decreasing_line_color="#F43F5E",
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(7,13,26,0)",
                    plot_bgcolor="rgba(7,13,26,0.60)",
                    font=dict(family="JetBrains Mono", color="#64748b", size=11),
                    xaxis=dict(gridcolor="rgba(148,163,184,.08)", showgrid=True, rangeslider_visible=False, linecolor="rgba(148,163,184,.10)"),
                    yaxis=dict(gridcolor="rgba(148,163,184,.08)", showgrid=True, linecolor="rgba(148,163,184,.10)"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=320,
                )
                st.plotly_chart(fig, width='stretch')

            if tech:
                t_cols = st.columns(6)
                indicators = [
                    ("RSI", tech.get("rsi"), ""),
                    ("SMA 20", tech.get("sma20"), "$"),
                    ("SMA 50", tech.get("sma50"), "$"),
                    ("ATR", tech.get("atr"), "$"),
                    ("Vol Ratio", tech.get("vol_ratio"), "x"),
                    ("EMA 9", tech.get("ema9"), "$"),
                ]
                for col, (label, val, prefix) in zip(t_cols, indicators):
                    with col:
                        if val is not None:
                            rsi_color = "#F59E0B" if label == "RSI" and val > 70 else ("#F43F5E" if label == "RSI" and val < 30 else "#EEF2FF")
                            st.markdown(f"""
                            <div class="metric-card" style="padding:12px">
                                <div class="metric-label">{label}</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:600;color:{rsi_color}">
                                    {prefix}{val}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

            st.markdown("---")

            # Earnings + News
            if earnings:
                st.info(f"📅 Next earnings: **{earnings}**")

            if news:
                st.markdown("**Recent News**")
                news_html = ""
                for item in news:
                    news_html += (
                        f'<div style="padding:8px 12px;margin-bottom:6px;background:rgba(7,13,26,.55);'
                        f'border:1px solid rgba(148,163,184,.10);border-radius:9px;'
                        f'font-family:Space Grotesk,sans-serif;font-size:13px">'
                        f'<span style="color:#EEF2FF">{item["title"]}</span>'
                        f'<span style="color:rgba(100,116,139,.60);font-size:11px;margin-left:10px">'
                        f'{item["publisher"]} · {item["date"]}</span></div>'
                    )
                st.markdown(news_html, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**AI Trade Recommendation**")
            with st.spinner("AI is analyzing..."):
                portfolio_context = {**st.session_state.portfolio, "total_value": total_with_cash}
                rec = get_trade_recommendation(ticker, portfolio_context, ai_config)
            _html = md_lib.markdown(rec, extensions=["nl2br"])
            st.markdown(f'<div class="rec-card">{_html}</div>', unsafe_allow_html=True)


# ── Tab 4: Positions ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("**Current Holdings**")

    if not pf["positions"]:
        st.info("No positions yet. Add some in the sidebar.")
    else:
        sort_opt = st.selectbox(
            "Sort by",
            ["Value (High → Low)", "Value (Low → High)", "Alphabetical", "P&L (High → Low)", "P&L (Low → High)"],
            index=0,
            label_visibility="collapsed",
        )
        sorted_positions = list(pf["positions"])
        if sort_opt == "Value (High → Low)":
            sorted_positions.sort(key=lambda p: p.get("value", 0), reverse=True)
        elif sort_opt == "Value (Low → High)":
            sorted_positions.sort(key=lambda p: p.get("value", 0))
        elif sort_opt == "Alphabetical":
            sorted_positions.sort(key=lambda p: p["ticker"])
        elif sort_opt == "P&L (High → Low)":
            sorted_positions.sort(key=lambda p: p.get("gain_loss") or 0, reverse=True)
        elif sort_opt == "P&L (Low → High)":
            sorted_positions.sort(key=lambda p: p.get("gain_loss") or 0)

        for pos in sorted_positions:
            price = pos.get("current_price", 0)
            val = pos.get("value", 0)
            chg = pos.get("change_pct", 0)

            with st.expander(f"{pos['ticker']}  —  ${val:,.2f}  ({'+' if chg >= 0 else ''}{chg:.2f}%)"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Shares", f"{pos['shares']}")
                    st.metric("Current Price", f"${price:,.2f}")
                with c2:
                    st.metric("Position Value", f"${val:,.2f}")
                    pct_of_port = (val / total_with_cash * 100) if total_with_cash > 0 else 0
                    st.metric("% of Portfolio", f"{pct_of_port:.1f}%")
                with c3:
                    if pos.get("gain_loss") is not None:
                        gl = pos["gain_loss"]
                        st.metric("Unrealized P&L", f"${gl:,.2f}", delta=f"{gl:+.2f}")

                hist = get_price_history(pos["ticker"], period="1mo")
                if not hist.empty:
                    color = "#10B981" if hist["Close"].iloc[-1] >= hist["Close"].iloc[0] else "#F43F5E"
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(
                        x=hist.index, y=hist["Close"],
                        fill="tozeroy", line=dict(color=color, width=2),
                        fillcolor=f"rgba({'16,185,129' if color == '#10B981' else '244,63,94'},0.1)",
                    ))
                    fig2.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(7,13,26,0.50)",
                        margin=dict(l=0, r=0, t=0, b=0), height=120,
                        xaxis=dict(visible=False), yaxis=dict(visible=False),
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, width='stretch')

                st.markdown("**Price Alerts**")
                al_c1, al_c2 = st.columns(2)
                with al_c1:
                    new_target = st.number_input(
                        "Target $", min_value=0.0, step=0.01,
                        value=float(pos.get("target") or 0),
                        key=f"target_{pos['ticker']}",
                    )
                with al_c2:
                    new_stop = st.number_input(
                        "Stop $", min_value=0.0, step=0.01,
                        value=float(pos.get("stop") or 0),
                        key=f"stop_{pos['ticker']}",
                    )
                if st.button("Set Alerts", key=f"set_alerts_{pos['ticker']}"):
                    for _p in st.session_state.portfolio["positions"]:
                        if _p["ticker"] == pos["ticker"]:
                            _p["target"] = new_target if new_target > 0 else None
                            _p["stop"] = new_stop if new_stop > 0 else None
                    save_portfolio(st.session_state.portfolio)
                    _get_portfolio_value_cached.clear()
                    st.success("Alert levels saved!")
                    st.rerun()

    st.markdown("---")
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:rgba(100,116,139,.65);padding:16px 20px;background:rgba(7,13,26,.72);border:1px solid rgba(148,163,184,.10);border-radius:9px;display:flex;gap:24px;flex-wrap:wrap">
        <span>Invested <span style="color:#EEF2FF;font-weight:600">${total_invested:,.2f}</span></span>
        <span>Cash <span style="color:#EEF2FF;font-weight:600">${st.session_state.portfolio['cash']:.2f}</span></span>
        <span>Total <span style="color:#10B981;font-weight:700">${total_with_cash:,.2f}</span></span>
    </div>
    """, unsafe_allow_html=True)


# ── Tab 5: Settings ───────────────────────────────────────────────────────────
with tab5:
    st.markdown("**AI & App Configuration**")
    st.caption("Settings are saved to `config.json` in the app folder and persist across restarts.")

    saved_provider = st.session_state.config.get("provider", "OpenAI")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### AI Provider")

        provider = st.selectbox(
            "Provider",
            list(PROVIDER_PRESETS.keys()),
            index=list(PROVIDER_PRESETS.keys()).index(saved_provider) if saved_provider in PROVIDER_PRESETS else 0,
        )
        preset = PROVIDER_PRESETS[provider]

        api_key = st.text_input(
            "API Key",
            value=st.session_state.config.get("api_key", ""),
            type="password",
            placeholder=preset["placeholder"],
        )

        # Auto-fill model when provider changes, otherwise keep saved value
        model_default = (
            st.session_state.config.get("model", preset["default_model"])
            if provider == saved_provider
            else preset["default_model"]
        )
        model = st.text_input(
            "Model Name",
            value=model_default,
            placeholder=preset["default_model"] or "model-name",
        )

        if provider == "Custom (OpenAI-compatible)":
            base_url_default = (
                st.session_state.config.get("base_url", "")
                if provider == saved_provider
                else ""
            )
            base_url = st.text_input(
                "Base URL",
                value=base_url_default,
                placeholder="https://your-provider.com/v1",
            )
        else:
            base_url = preset["base_url"]
            st.caption(f"Endpoint: `{base_url}`")

    with col_right:
        st.markdown("### App Settings")
        city_input = st.text_input(
            "Your City (for weather)",
            value=st.session_state.config.get("city", ""),
            placeholder="e.g. New York,NY or London",
        )

        st.markdown("### Screener Watchlist")
        st.caption("Tickers the screener checks for momentum setups. Comma-separated.")
        current_watchlist = st.session_state.config.get("watchlist", DEFAULT_WATCHLIST)
        watchlist_input = st.text_area(
            "Watchlist tickers",
            value=", ".join(current_watchlist),
            height=110,
            key="watchlist_input",
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### About this provider")
        st.info(preset["info"])

        st.markdown("### Current config")
        st.code(
            f"Provider : {st.session_state.config.get('provider', '—')}\n"
            f"Model    : {st.session_state.config.get('model', '—')}\n"
            f"API key  : {'set ✓' if st.session_state.config.get('api_key') else 'not set'}\n"
            f"City     : {st.session_state.config.get('city') or '—'}\n"
            f"Watchlist: {len(current_watchlist)} tickers",
            language=None,
        )

    st.markdown("---")

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 Save Settings", width='stretch'):
            parsed_watchlist = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
            new_config = {
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "city": city_input,
                "watchlist": parsed_watchlist if parsed_watchlist else DEFAULT_WATCHLIST,
            }
            save_config(new_config)
            st.session_state.config = new_config
            st.success("Settings saved!")
            st.rerun()

    with col_test:
        if st.button("🧪 Test Connection", width='stretch'):
            if not api_key:
                st.error("Enter an API key first.")
            else:
                with st.spinner("Testing connection..."):
                    try:
                        result = chat_completions_create(
                            model=model,
                            messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
                            temperature=0,
                            api_key=api_key,
                            base_url=base_url or None,
                        )
                        st.success(f"Connected! Model replied: {result['content'][:80]}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")


# ── Tab 6: Journal ────────────────────────────────────────────────────────────
with tab6:
    st.markdown("**Trade Journal**")
    st.caption("Log and track trade recommendations, set targets and stops, and review your track record.")

    journal = load_journal()
    open_trades = [t for t in journal if t["status"] == "open"]
    closed_trades = [t for t in journal if t["status"] == "closed"]

    # ── Alert check ───────────────────────────────────────────────────────────
    j_col1, j_col2 = st.columns([1, 4])
    with j_col1:
        check_j_alerts = st.button("🔔 Check Alerts", key="j_check_alerts", width='stretch')
    if check_j_alerts and open_trades:
        with st.spinner("Checking prices against open trades..."):
            j_alerts = check_alerts(journal)
        if j_alerts:
            for ja in j_alerts:
                tr = ja["trade"]
                if ja["type"] == "TARGET_HIT":
                    st.success(f"🎯 **{tr['ticker']} TARGET HIT** — current ${ja['current_price']:.2f} ≥ target ${tr['target']:.2f}")
                else:
                    st.error(f"🛑 **{tr['ticker']} STOP TRIGGERED** — current ${ja['current_price']:.2f} ≤ stop ${tr['stop']:.2f}")
        else:
            st.info("No alerts — all open trades within range.")

    st.markdown("---")

    # ── Log new trade ─────────────────────────────────────────────────────────
    with st.expander("➕ Log New Trade"):
        lc1, lc2 = st.columns(2)
        with lc1:
            j_ticker = st.text_input("Ticker", key="j_ticker", placeholder="NVDA")
            j_action = st.selectbox("Action", ["BUY", "SELL", "SHORT"], key="j_action")
            j_entry = st.number_input("Entry Price $", min_value=0.0, step=0.01, key="j_entry")
        with lc2:
            j_target = st.number_input("Target Price $", min_value=0.0, step=0.01, key="j_target")
            j_stop = st.number_input("Stop Loss $", min_value=0.0, step=0.01, key="j_stop")
            j_notes = st.text_area("Notes / Thesis", key="j_notes", height=80, placeholder="Why this trade?")
        if st.button("Log Trade", key="j_log_btn"):
            if j_ticker and j_entry > 0:
                log_trade(
                    j_ticker, j_action, j_entry,
                    j_target if j_target > 0 else None,
                    j_stop if j_stop > 0 else None,
                    j_notes,
                )
                st.success(f"Logged {j_action} {j_ticker.upper()} @ ${j_entry:.2f}")
                st.rerun()
            else:
                st.warning("Enter a ticker and entry price.")

    st.markdown("---")

    # ── Open trades ───────────────────────────────────────────────────────────
    if open_trades:
        st.markdown(f"### Open Trades ({len(open_trades)})")
        for trade in reversed(open_trades):
            label = f"{trade['action']} {trade['ticker']} @ ${trade['entry_price']:.2f} — {trade['logged_at'][:10]}"
            with st.expander(label):
                oc1, oc2, oc3 = st.columns(3)
                with oc1:
                    st.metric("Entry", f"${trade['entry_price']:.2f}")
                with oc2:
                    st.metric("Target", f"${trade['target']:.2f}" if trade.get("target") else "—")
                with oc3:
                    st.metric("Stop", f"${trade['stop']:.2f}" if trade.get("stop") else "—")
                if trade.get("notes"):
                    st.caption(trade["notes"])
                ec1, ec2 = st.columns([2, 1])
                with ec1:
                    exit_price = st.number_input("Exit Price $", min_value=0.0, step=0.01, key=f"exit_{trade['id']}")
                with ec2:
                    if st.button("Close Trade", key=f"close_{trade['id']}", width='stretch'):
                        if exit_price > 0:
                            close_trade(trade["id"], exit_price)
                            st.success("Trade closed and P&L recorded!")
                            st.rerun()
                        else:
                            st.warning("Enter an exit price.")
    else:
        st.info("No open trades. Log one above.")

    # ── Closed trades / track record ─────────────────────────────────────────
    if closed_trades:
        st.markdown("---")
        st.markdown("### Track Record")
        wins = [t for t in closed_trades if (t.get("pnl_pct") or 0) > 0]
        losses = [t for t in closed_trades if (t.get("pnl_pct") or 0) <= 0]
        avg_pnl = sum(t["pnl_pct"] for t in closed_trades if t.get("pnl_pct") is not None) / len(closed_trades) if closed_trades else 0

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Total Trades", len(closed_trades))
        sc2.metric("Winners", len(wins))
        sc3.metric("Win Rate", f"{len(wins) / len(closed_trades) * 100:.0f}%" if closed_trades else "—")
        sc4.metric("Avg P&L", f"{avg_pnl:+.1f}%")

        st.markdown("**History**")
        for trade in reversed(closed_trades):
            pnl = trade.get("pnl_pct")
            pnl_color = "var(--green)" if pnl and pnl > 0 else "var(--red)"
            pnl_str = f"{pnl:+.1f}%" if pnl is not None else "—"
            exit_str = f"${trade['exit_price']:.2f}" if trade.get("exit_price") else "—"
            notes_html = f' <span style="color:var(--faint)">| {trade["notes"][:60]}</span>' if trade.get("notes") else ""
            st.markdown(f"""
            <div class="metric-card" style="padding:10px 14px;margin-bottom:6px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="font-family:'JetBrains Mono',monospace;font-weight:600;color:#EEF2FF">{trade['action']} {trade['ticker']}</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);margin-left:10px">{trade['logged_at'][:10]}</span>
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace;font-weight:700;color:{pnl_color}">{pnl_str}</div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted);margin-top:4px">
                    Entry ${trade['entry_price']:.2f} → Exit {exit_str}{notes_html}
                </div>
            </div>
            """, unsafe_allow_html=True)


# ── Tab 7: Code Agent ─────────────────────────────────────────────────────────
with tab7:
    st.markdown("### Code Agent")
    st.caption("Point the agent at any codebase and give it a task. It will read, edit, and create files autonomously.")

    st.markdown("---")

    # ── Config row ────────────────────────────────────────────────────────────
    path_col, rounds_col = st.columns([4, 1])
    with path_col:
        ca_path = st.text_input(
            "Codebase path",
            value=os.getcwd(),
            placeholder="/path/to/your/project",
            key="ca_path",
        )
    with rounds_col:
        ca_max_rounds = st.number_input(
            "Max rounds",
            min_value=1,
            max_value=50,
            value=20,
            key="ca_max_rounds",
            help="Hard ceiling on LLM iterations. The agent calls mark_complete when it decides it's done.",
        )

    # ── Task selection ────────────────────────────────────────────────────────
    TASK_PRESETS = {
        "Custom task": "",
        "Improve code quality and readability": "Review the codebase and improve code quality and readability. Look for duplicated logic, unclear naming, dead code, and inconsistent patterns. Fix what you find.",
        "Add error handling": "Review the codebase and add robust error handling and input validation where it is missing or insufficient.",
        "Refactor to reduce duplication": "Find duplicated code and logic across the codebase and refactor it into shared helpers or utilities.",
        "Add type hints": "Add Python type hints to all functions and methods that are missing them, following the existing style.",
        "Write a README": "Create a comprehensive README.md for this project — overview, setup instructions, usage, and architecture.",
        "Add logging": "Add structured logging throughout the codebase using Python's logging module, replacing any bare print statements.",
    }

    preset_choice = st.selectbox(
        "Quick task preset",
        list(TASK_PRESETS.keys()),
        key="ca_preset",
    )

    ca_task = st.text_area(
        "Task description",
        value=TASK_PRESETS[preset_choice],
        height=110,
        placeholder="Describe exactly what you want the agent to do...",
        key="ca_task",
    )

    # ── Run button ────────────────────────────────────────────────────────────
    if st.button("Run Agent", key="ca_run", type="primary", width="stretch"):
        if not ca_task.strip():
            st.warning("Enter a task description.")
        elif not ca_path.strip():
            st.warning("Enter a codebase path.")
        else:
            with st.status("Agent running...", expanded=True) as ca_status:
                for event in run_code_agent(ca_task, ca_path, ai_config, max_rounds=ca_max_rounds):
                    etype = event["type"]

                    if etype == "round":
                        st.markdown(f"**Round {event['round']} / {event['max']}**")

                    elif etype == "thought":
                        st.markdown(event["content"])

                    elif etype == "tool_call":
                        name = event["name"]
                        args = event["args"]
                        if name == "list_files":
                            label = args.get("pattern", "**/*")
                            st.write(f"📁 `list_files` — `{args.get('directory', '.')}` / `{label}`")
                        elif name == "read_file":
                            st.write(f"📄 `read_file` — `{args.get('path')}`")
                        elif name == "write_file":
                            st.write(f"✏️ `write_file` — `{args.get('path')}`")
                        elif name == "mark_complete":
                            st.write("✅ `mark_complete`")
                        else:
                            st.write(f"🔧 `{name}`")

                    elif etype == "tool_result":
                        result = event["result"]
                        if result.get("error"):
                            st.error(f"Tool error: {result['error']}")

                    elif etype in ("done", "max_rounds"):
                        st.markdown("---")
                        changed = event.get("changed_files", [])
                        if changed:
                            st.markdown(f"**Files changed ({len(changed)}):**")
                            for f in changed:
                                st.write(f"• `{f}`")
                        summary = event.get("summary") or event.get("message", "")
                        if summary:
                            st.markdown("**Summary**")
                            st.markdown(summary)
                        if etype == "done":
                            ca_status.update(label="Agent complete", state="complete")
                        else:
                            ca_status.update(label=f"Stopped — {event['message']}", state="error")

                    elif etype == "error":
                        st.error(event["message"])
                        ca_status.update(label="Agent error", state="error")
