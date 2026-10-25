"""
Wealthcon Investment Scorer — MDSPORT & MPTDS
Designed & developed by Dr. Shantanu Samanta (Kolkata).

UI layer only. Scoring rules live in engine.py, data fetching in data_sources.py.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from html import escape

from data_sources import (
    DataError, NotFoundError, alias_symbol, fetch_company, fetch_fy_prices, fetch_yahoo_extras, load_nse_equities,
    looks_like_symbol, resolve_company, suggest_symbols,
)
from engine import (
    DE_LIMIT, MDSPORT_YEARS, MPTDS_MCAP_MIN, MPTDS_PARAMS, SENSITIVITY, SPORT_LABELS,
    VALID_ABOVE, WATCHLIST_FROM, evaluate_mdsport, evaluate_mptds, period_end,
)
from graham import (
    AMFI_MIDCAP_FLOOR, FAIL, NA, NO_DATA, PARTIAL, PASS, GrahamInputs, allocation_band, balance_from_sources,
    detect_financial, evaluate_graham,
)

IIV_NAME = "Indian Intelligent Investor"   # Graham's screens adapted for NSE large and midcaps

DEFAULT_GSEC = 7.20  # % — India 10Y G-Sec, late Sep 2026. Update it in Advanced options.

# ----------------------------------------------------------------------------
# Identity
# ----------------------------------------------------------------------------
APP_NAME = "Wealthcon Investment Scorer"
AUTHOR = "Dr. Shantanu Samanta"
AUTHOR_TITLE = "Physician · Quantitative Market Analyst & Trading-Systems Developer"
AUTHOR_PLACE = "Kolkata, India"
YEAR = date.today().year

st.set_page_config(
    page_title=f"{APP_NAME} · {AUTHOR}",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",  # open on desktop, collapsed on phones
    menu_items={"About": f"**{APP_NAME}**\n\nDesigned & developed by **{AUTHOR}**, {AUTHOR_PLACE}."},
)

# ----------------------------------------------------------------------------
# Palette & styles (responsive: fluid grids + clamp() type + breakpoints)
# ----------------------------------------------------------------------------
C = {
    "indigo": "#4338CA", "violet": "#7C3AED", "pink": "#DB2777", "teal": "#0D9488",
    "sky": "#0284C7", "amber": "#F59E0B", "green": "#16A34A", "red": "#DC2626",
}
VERDICT_STYLE = {
    "VALID": ("linear-gradient(135deg,#059669,#22C55E)", "✅"),
    "WATCHLIST": ("linear-gradient(135deg,#D97706,#FBBF24)", "👀"),
    "REJECTED": ("linear-gradient(135deg,#B91C1C,#F43F5E)", "⛔"),
    "INVALID": ("linear-gradient(135deg,#B91C1C,#F43F5E)", "⛔"),
}
SERIES_COLORS = {"Price": C["violet"], "Tax": C["teal"], "Dividend": C["amber"], "Sales": C["sky"]}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {font-family:'Inter',system-ui,sans-serif;}
.block-container {padding-top:3.4rem; padding-bottom:2rem; max-width:1320px;}

/* ---------- hero ---------- */
.hero {background:linear-gradient(120deg,#312E81 0%,#6D28D9 45%,#DB2777 100%);
  color:#fff; border-radius:22px; padding:clamp(18px,3.2vw,34px) clamp(18px,3.5vw,40px);
  box-shadow:0 14px 40px -18px rgba(109,40,217,.65); position:relative; overflow:hidden;}
.hero:after {content:""; position:absolute; right:-60px; top:-60px; width:240px; height:240px;
  border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%);}
.hero h1 {font-family:'Poppins',sans-serif; font-size:clamp(1.45rem,3.6vw,2.45rem);
  margin:0 0 .25rem 0; color:#fff; line-height:1.15; padding:0;}
.hero p {margin:.15rem 0 0 0; opacity:.93; font-size:clamp(.88rem,1.6vw,1.02rem);}
.byline {display:inline-flex; align-items:center; gap:.55rem; flex-wrap:wrap; margin-top:.9rem;
  background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28); border-radius:999px;
  padding:.38rem .9rem .38rem .38rem; backdrop-filter:blur(4px); font-size:clamp(.78rem,1.4vw,.92rem);}
.avatar {width:30px; height:30px; border-radius:50%; display:grid; place-items:center;
  background:linear-gradient(135deg,#FBBF24,#F97316); color:#3B0764; font-weight:700; font-size:.8rem;}
.byline b {font-weight:600;}

/* ---------- grids ---------- */
.grid {display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr)); margin:14px 0;}
.grid-2 {display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr)); margin:14px 0;}

/* ---------- cards ---------- */
.stat {border-radius:16px; padding:14px 16px; color:#fff; min-height:92px;
  box-shadow:0 8px 22px -14px rgba(0,0,0,.55);}
.stat .k {font-size:.74rem; text-transform:uppercase; letter-spacing:.07em; opacity:.88;}
.stat .v {font-family:'Poppins',sans-serif; font-size:clamp(1.15rem,2.3vw,1.55rem); font-weight:600; margin-top:2px;}
.stat .s {font-size:.8rem; opacity:.9;}
.verdict {border-radius:20px; padding:clamp(16px,2.4vw,24px); color:#fff;
  box-shadow:0 14px 34px -18px rgba(0,0,0,.6);}
.verdict .t {font-size:.8rem; letter-spacing:.09em; text-transform:uppercase; opacity:.9;}
.verdict .big {font-family:'Poppins',sans-serif; font-size:clamp(1.7rem,4.4vw,2.6rem); font-weight:700; line-height:1.1; margin:.2rem 0;}
.verdict .r {font-size:.92rem; opacity:.95;}
.pill {display:inline-block; padding:.18rem .62rem; border-radius:999px; font-size:.76rem; font-weight:600;
  margin:.4rem .3rem 0 0; background:rgba(255,255,255,.2); border:1px solid rgba(255,255,255,.35);}
.gate {border-radius:16px; padding:14px 16px; border:1px solid rgba(127,127,127,.22);
  background:rgba(127,127,127,.06); border-top:5px solid var(--c);}
.gate h4 {margin:0 0 .25rem 0; font-family:'Poppins',sans-serif; font-size:1.02rem; padding:0;}
.gate .row {display:flex; justify-content:space-between; gap:8px; font-size:.86rem; padding:2px 0;}
.gate .muted {opacity:.7; font-size:.78rem; margin-top:4px;}
.legend {display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 10px;}
.legend span {padding:.22rem .6rem; border-radius:8px; color:#fff; font-size:.78rem; font-weight:600;}
.note {border-left:4px solid #F59E0B; background:rgba(245,158,11,.10); border-radius:10px;
  padding:.55rem .8rem; font-size:.86rem; margin:.35rem 0;}
.match {border-radius:12px; padding:.55rem .85rem; margin:.4rem 0 .2rem; font-size:.92rem;
  background:linear-gradient(120deg,rgba(124,58,237,.12),rgba(13,148,136,.12));
  border:1px solid rgba(124,58,237,.25);}
.match .sym {display:inline-block; margin-left:.35rem; padding:.05rem .5rem; border-radius:999px;
  background:#7C3AED; color:#fff; font-size:.78rem; font-weight:600; letter-spacing:.03em;}
.section-title {font-family:'Poppins',sans-serif; font-size:clamp(1.05rem,2vw,1.3rem); font-weight:600; margin:.6rem 0 .2rem;}

/* ---------- Graham checklist ---------- */
.gwrap {overflow-x:auto; margin:6px 0 12px;}
.gtable {width:100%; border-collapse:separate; border-spacing:0; font-size:.86rem; min-width:560px;}
.gtable th {text-align:left; font-weight:600; padding:8px 10px; border-bottom:2px solid rgba(127,127,127,.25);
  font-size:.74rem; text-transform:uppercase; letter-spacing:.06em; opacity:.8;}
.gtable td {padding:8px 10px; border-bottom:1px solid rgba(127,127,127,.15); vertical-align:top;}
.gtable td.n {font-weight:600; white-space:nowrap;}
.gtable .sub {opacity:.68; font-size:.76rem; margin-top:2px;}
.badge {display:inline-block; min-width:64px; text-align:center; padding:.16rem .5rem; border-radius:999px;
  color:#fff; font-size:.72rem; font-weight:700; letter-spacing:.04em;}
.badge.mb {display:none; min-width:0; margin-left:4px;}

/* ---------- author card ---------- */
.author {border-radius:18px; padding:16px; color:#fff;
  background:linear-gradient(150deg,#0F766E 0%,#0369A1 55%,#4338CA 100%);
  box-shadow:0 12px 30px -18px rgba(3,105,161,.8);}
.author .name {font-family:'Poppins',sans-serif; font-size:1.08rem; font-weight:600; margin-top:.5rem;}
.author .role {font-size:.82rem; opacity:.95; margin-top:.15rem; line-height:1.4;}
.author .tags {margin-top:.55rem;}
.author .tags span {display:inline-block; font-size:.7rem; padding:.15rem .5rem; margin:.2rem .2rem 0 0;
  border-radius:999px; background:rgba(255,255,255,.18);}
.author .big-avatar {width:46px; height:46px; border-radius:14px; display:grid; place-items:center;
  background:linear-gradient(135deg,#FBBF24,#F97316); color:#3B0764; font-weight:700; font-family:'Poppins',sans-serif;}

/* ---------- footer ---------- */
.footer {margin-top:2rem; border-radius:20px; padding:clamp(16px,2.6vw,26px);
  background:linear-gradient(120deg,rgba(67,56,202,.10),rgba(219,39,119,.10));
  border:1px solid rgba(127,127,127,.2); font-size:.84rem;}
.footer .who {font-family:'Poppins',sans-serif; font-size:1rem; font-weight:600;}
.footer .disc {opacity:.78; margin-top:.6rem; line-height:1.5;}

/* ---------- widgets ---------- */
div.stButton > button[kind="primary"], div.stFormSubmitButton > button {
  background:linear-gradient(120deg,#6D28D9,#DB2777); border:0; color:#fff; font-weight:600;
  border-radius:12px; min-height:2.75rem;}
div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button:hover {filter:brightness(1.08); color:#fff;}
[data-testid="stForm"] {border-radius:18px; border:1px solid rgba(127,127,127,.22);
  background:rgba(127,127,127,.04);}
.stTabs [data-baseweb="tab-list"] {gap:6px; flex-wrap:wrap;}
.stTabs [data-baseweb="tab"] {border-radius:10px 10px 0 0; padding:8px 14px;}

/* ---------- tablet ---------- */
@media (max-width: 1024px) {
  .block-container {padding-left:1.2rem; padding-right:1.2rem;}
}
/* ---------- phone ---------- */
@media (max-width: 640px) {
  .block-container {padding:3.2rem 0.7rem 1.5rem;}
  .byline {border-radius:16px;}
  .hero {border-radius:16px;}
  .hero:after {display:none;}
  .stat {min-height:auto; padding:12px 14px;}
  .verdict {border-radius:16px;}
  .stTabs [data-baseweb="tab"] {padding:6px 10px; font-size:.85rem;}
  .footer {border-radius:16px;}
  .gtable {min-width:0;}
  .gtable th:nth-child(3), .gtable td:nth-child(3) {display:none;}
  .gtable td.n {white-space:normal;}
  .badge.mb {display:inline-block;}
}
</style>
"""


def html(markup: str) -> None:
    """Render HTML. Lines are stripped so Markdown never mistakes indentation for code."""
    st.markdown("\n".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def fmt_num(v: float, digits: int = 1, suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.{digits}f}{suffix}"


def fy_short(label: str) -> str:
    """'Mar 2025' -> 'FY25'; other year-ends keep their month: 'Dec 2024' -> "Dec '24"."""
    mon, yr = label.split()
    return f"FY{yr[-2:]}" if mon == "Mar" else f"{mon} '{yr[-2:]}"


PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def style_fig(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        height=height, autosize=True, margin=dict(l=8, r=8, t=40, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="center", x=0.5),
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(127,127,127,.18)", zeroline=False)
    return fig


def show_chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG, theme="streamlit")


# ----------------------------------------------------------------------------
# Cached data access
# ----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_company(symbol: str, basis: str):
    return fetch_company(symbol, basis)


@st.cache_data(ttl=86400, show_spinner=False)
def load_matches(text: str):
    return resolve_company(text)


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(symbol: str, labels: tuple[str, ...]):
    return fetch_fy_prices(symbol, list(labels))


class _NotCached(Exception):
    """Raised inside a cached function so a failed download is retried next run, not cached for 24 h."""


@st.cache_data(ttl=86400, show_spinner=False)
def _nse_list_cached():
    try:
        df = load_nse_equities()
    except Exception:
        raise _NotCached(None)
    if df is None or df.empty:
        raise _NotCached(None)
    return df


def get_nse_list():
    """NSE equity symbols + names (Dhan's public scrip master), or None when it can't be downloaded."""
    try:
        return _nse_list_cached()
    except _NotCached:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_extras(symbol: str):
    return fetch_yahoo_extras(symbol)


# ----------------------------------------------------------------------------
# Building blocks
# ----------------------------------------------------------------------------
def initials(name: str) -> str:
    parts = [p for p in name.replace("Dr.", "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper()


def render_hero() -> None:
    html(f"""
    <div class="hero">
      <h1>📈 {APP_NAME}</h1>
      <p><b>MDSPORT</b> quality-growth scoring &nbsp;·&nbsp; <b>MPTDS</b> trend-sustainability test &nbsp;·&nbsp; <b>Graham</b> defensive / enterprising screens &nbsp;·&nbsp; NSE / BSE equities</p>
      <div class="byline"><span class="avatar">{initials(AUTHOR)}</span>
        <span>Designed &amp; developed by <b>{AUTHOR}</b> · {AUTHOR_PLACE}</span></div>
    </div>
    """)


def author_card() -> str:
    return f"""
    <div class="author">
      <div class="big-avatar">{initials(AUTHOR)}</div>
      <div class="name">{AUTHOR}</div>
      <div class="role">{AUTHOR_TITLE}<br>{AUTHOR_PLACE}</div>
      <div class="tags"><span>Clinical medicine</span><span>Quant analysis</span>
        <span>NSE · NIFTY systems</span><span>Python · Streamlit</span></div>
    </div>
    """


def render_sidebar() -> None:
    with st.sidebar:
        html(author_card())
        st.markdown("")
        st.markdown("##### How to read the verdicts")
        html(f"""
        <div class="legend">
          <span style="background:{C['green']}">VALID</span>
          <span style="background:{C['amber']}">WATCHLIST</span>
          <span style="background:{C['red']}">REJECTED / INVALID</span>
        </div>
        """)
        st.caption(
            f"**MDSPORT**: D/E < {DE_LIMIT:.1f} gate, then 5 SPORT parameters × {MDSPORT_YEARS} years × 0–4 pts. "
            f">{VALID_ABOVE} valid · {WATCHLIST_FROM}–{VALID_ABOVE} watchlist.\n\n"
            f"**MPTDS**: Market cap ≥ ₹{MPTDS_MCAP_MIN:,.0f} Cr and rising Price, Tax, Dividend and Sales trends.\n\n"
            "**Graham**: 7 defensive + 5 enterprising tests from *The Intelligent Investor*, "
            "Graham Number, growth formula and net-net (NCAV)."
        )


def render_form() -> dict | None:
    # Fixed widget key: passing value= would give the box a new identity whenever the symbol changes, and Streamlit
    # would then discard the next thing typed. A suggestion click sets _wc_input_pending, applied here before the
    # widget exists (a widget's state can't be changed after it is drawn in the same run).
    if "_wc_input_pending" in st.session_state:
        st.session_state["wc_input"] = st.session_state.pop("_wc_input_pending")
    st.session_state.setdefault("wc_input", st.session_state.get("last_symbol", "TCS"))
    with st.form("query_form"):
        c1, c2 = st.columns([1.6, 1])  # two rows of two: comfortable on tablets, stacks on phones
        c3, c4 = st.columns([1.6, 1])
        symbol = c1.text_input("Company name or NSE symbol", key="wc_input",
                               placeholder="e.g. Shriram Finance, asian paints, TCS",
                               help="An exact NSE symbol (any case, .NS allowed) or a BSE code opens straight away. "
                                    "Anything else — a company name or a typo — shows a list of likely stocks.").strip()
        basis = c2.selectbox("Statements", ["Auto", "Consolidated", "Standalone"],
                             help="Auto = consolidated, falling back to standalone when consolidated is empty.")
        sens = c3.selectbox("MPTDS sensitivity", list(SENSITIVITY),
                            format_func=lambda k: f"{k} (≥{SENSITIVITY[k]['min_growth']:.0f}%, R²≥{SENSITIVITY[k]['min_r2']})")
        years = c4.slider("MPTDS years", 5, 10, 10, help="Trend window for MPTDS (5–10 years). MDSPORT always uses 5.")

        with st.expander("Advanced options"):
            a1, a2, a3 = st.columns(3)
            use_de = a1.checkbox("Enter D/E manually", help="Use when you have the exact Non-Current Liabilities / Total Equity figure.")
            de_val = a1.number_input("D/E (NCL ÷ Equity)", min_value=0.0, max_value=20.0, value=0.0, step=0.01)
            large_min = a2.number_input("Large-cap cut-off (₹ Cr)", min_value=0.0, value=float(MPTDS_MCAP_MIN), step=500.0)
            mid_min = a3.number_input("Mid-cap cut-off (₹ Cr)", min_value=0.0, value=5000.0, step=500.0,
                                      help="The framework only fixes the ₹10,000 Cr line; set mid/small to your own convention.")

            st.markdown(f"**{IIV_NAME} inputs**")
            g1, g2, g3, g4 = st.columns(4)
            gsec = g1.number_input("10Y G-Sec yield %", min_value=0.5, max_value=20.0, value=DEFAULT_GSEC, step=0.05,
                                   help="Y for the earnings-yield comparison and the stock/bond band. "
                                        "(The growth formula is the book's E × (8.5 + 2g) and doesn't use Y.) "
                                        "Update to today's yield.")
            spread = g2.number_input("AAA spread over G-Sec (bps)", min_value=0, max_value=500, value=0, step=5,
                                     help="Graham's Y was the AAA corporate yield. 0 uses the G-Sec yield directly, "
                                          "which gives a higher value than an AAA yield would.")
            mos = g3.number_input("Required margin of safety %", min_value=0, max_value=80, value=25, step=5,
                                  help="Applied to the growth-formula value to get a buy price. Graham set no "
                                       "fixed percentage; 25% is a common choice.")
            nifty_pe = g4.number_input("NIFTY 50 P/E (for allocation)", min_value=0.0, max_value=80.0, value=0.0,
                                       step=0.1, help="Optional. Used only for Graham's 25–75% stock/bond band. "
                                                      "0 = skip.")
            h1, h2, h3 = st.columns(3)
            graham_size = h1.number_input("Size cut-off: AMFI midcap floor (₹ Cr)", min_value=0.0,
                                          value=float(AMFI_MIDCAP_FLOOR), step=500.0,
                                          help="Market cap of the company ranked 250 in AMFI's list (₹34,700 Cr in "
                                               "the Jan-2026 list). AMFI revises it every January and July.")
            infl_floor = h2.checkbox("Inflation floor on earnings growth (optional)",
                                     help="Test 5 then needs EPS growth ≥ the larger of Graham's ⅓ and the rise in "
                                          "consumer prices (RBI CPI) between the same two 3-year windows. "
                                          "Off = Graham's rule exactly.")
            force_fin = h3.checkbox("Treat as bank / NBFC / insurer",
                                    help="Use when the company is a lender or insurer that the app didn't detect. "
                                         "Its balance-sheet and net-net tests then show N/A.")
            use_bs = st.checkbox("Enter current assets / liabilities manually (₹ Cr)",
                                 help="Use when Yahoo Finance has no balance sheet for this stock, or its basis "
                                      "differs from Screener's. Blank fields keep Yahoo's value.")
            b1, b2, b3, b4 = st.columns(4)
            m_ca = b1.number_input("Current assets", min_value=0.0, value=None, step=100.0)
            m_cl = b2.number_input("Current liabilities", min_value=0.0, value=None, step=100.0)
            m_tl = b3.number_input("Total liabilities", min_value=0.0, value=None, step=100.0)
            m_ltd = b4.number_input("Long-term debt", min_value=0.0, value=None, step=100.0)

        go_btn = st.form_submit_button("🚀  Analyse", type="primary", width="stretch")

    if go_btn:
        st.session_state["last_symbol"] = symbol
        st.session_state["query"] = dict(
            symbol=symbol, basis=basis, sens=sens, years=years,
            de_override=de_val if use_de else None, large_min=large_min, mid_min=mid_min,
            gsec=gsec, spread=spread, mos=mos / 100.0, nifty_pe=nifty_pe,
            graham_size=graham_size, infl_floor=infl_floor, force_fin=force_fin,
            manual_bs=dict(current_assets=m_ca, current_liabilities=m_cl, total_liabilities=m_tl,
                           long_term_debt=m_ltd) if use_bs else None,
        )
    return st.session_state.get("query")


def stat(label: str, value: str, sub: str, grad: str) -> str:
    return f'<div class="stat" style="background:{grad}"><div class="k">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>'


def render_company_strip(data, years_used: int) -> None:
    html(f"""
    <div class="grid">
      {stat("Company", data.name[:38], f"{data.symbol} · {data.basis}", "linear-gradient(135deg,#4338CA,#7C3AED)")}
      {stat("Market cap", "₹" + fmt_num(data.market_cap, 0) + " Cr", "Screener.in", "linear-gradient(135deg,#0369A1,#0EA5E9)")}
      {stat("Current price", "₹" + fmt_num(data.current_price, 2), "Screener.in", "linear-gradient(135deg,#0F766E,#14B8A6)")}
      {stat("Annual data", f"{years_used} yrs", f"{data.pnl.index[0]} → {data.pnl.index[-1]}", "linear-gradient(135deg,#BE185D,#F472B6)")}
    </div>
    """)


def verdict_card(title: str, verdict: str, big: str, reason: str, pills: list[str]) -> str:
    grad, icon = VERDICT_STYLE[verdict]
    pills_html = "".join(f'<span class="pill">{p}</span>' for p in pills)
    return f"""<div class="verdict" style="background:{grad}">
      <div class="t">{title}</div><div class="big">{icon} {big}</div>
      <div class="r">{reason}</div><div>{pills_html}</div></div>"""


# ----------------------------------------------------------------------------
# MDSPORT tab
# ----------------------------------------------------------------------------
POINT_COLORS = ["#DC2626", "#F97316", "#FACC15", "#4ADE80", "#16A34A"]


def mdsport_gauge(score: int) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"suffix": " / 100", "font": {"size": 30}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#4338CA", "thickness": 0.28},
            "steps": [
                {"range": [0, WATCHLIST_FROM], "color": "rgba(220,38,38,.35)"},
                {"range": [WATCHLIST_FROM, VALID_ABOVE], "color": "rgba(245,158,11,.40)"},
                {"range": [VALID_ABOVE, 100], "color": "rgba(22,163,74,.40)"},
            ],
            "threshold": {"line": {"color": "#DB2777", "width": 4}, "value": score},
        },
        title={"text": "MDSPORT score"},
    ))
    fig = style_fig(fig, height=270)
    fig.update_layout(margin=dict(l=34, r=34, t=40, b=8))
    return fig


def mdsport_heatmap(res) -> go.Figure:
    pts = res.points
    vals = res.values
    names = {"S": "Sales", "P": "PAT", "O": "OPM", "R": "ROCE", "T": "Tax"}
    short = [f"{i[0]} · {names[i[0]]}" for i in pts.index]
    text = [[f"{fmt_num(vals.iat[r, c], 1, '%')}<br><b>{int(pts.iat[r, c])} pt</b>"
             for c in range(pts.shape[1])] for r in range(pts.shape[0])]
    scale = [[0.0, POINT_COLORS[0]], [0.25, POINT_COLORS[1]], [0.5, POINT_COLORS[2]],
             [0.75, POINT_COLORS[3]], [1.0, POINT_COLORS[4]]]
    fig = go.Figure(go.Heatmap(
        z=pts.to_numpy(), x=[fy_short(c) for c in pts.columns], y=short, zmin=0, zmax=4, colorscale=scale,
        text=text, texttemplate="%{text}", textfont={"size": 11, "color": "#111827"},
        xgap=4, ygap=4, showscale=False,
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    fig = style_fig(fig, height=360)
    fig.update_layout(title=dict(text="Year-by-year points (0–4 each)", x=0, font=dict(size=14)))
    return fig


def render_mdsport(res) -> None:
    show_chart(mdsport_gauge(res.score))
    with st.container():
        de_color = C["green"] if res.de_pass else (C["red"] if not math.isnan(res.de_ratio) else C["amber"])
        de_txt = "PASS" if res.de_pass else ("FAIL — auto reject" if not math.isnan(res.de_ratio) else "Not available")
        html(f"""
        <div class="grid-2">
        <div class="gate" style="--c:{de_color}">
          <h4>D · Debt-to-Equity gate</h4>
          <div class="row"><span>D/E ratio</span><b>{fmt_num(res.de_ratio, 2)}</b></div>
          <div class="row"><span>Limit</span><b>&lt; {DE_LIMIT:.2f}</b></div>
          <div class="row"><span>Result</span><b style="color:{de_color}">{de_txt}</b></div>
          <div class="muted">Period: {res.de_period}. Proxy = Borrowings ÷ (Equity capital + Reserves); framework definition is NCL ÷ Total equity.</div>
        </div>
        <div class="gate" style="--c:{C['sky']}">
          <h4>M · Market capitalisation</h4>
          <div class="row"><span>Market cap</span><b>₹{fmt_num(res.mcap, 0)} Cr</b></div>
          <div class="row"><span>Class</span><b>{res.mcap_class}</b></div>
          <div class="muted">Classification only — does not add points.</div>
        </div>
        </div>
        """)

    html('<div class="section-title">SPORT scorecard</div>')
    html("""<div class="legend">""" + "".join(
        f'<span style="background:{POINT_COLORS[i]};color:{"#111827" if i in (2, 3) else "#fff"}">{lab}</span>'
        for i, lab in enumerate(["&lt;5% → 0", "5–10% → 1", "10–15% → 2", "15–20% → 3", "&gt;20% → 4"])
    ) + "</div>")
    show_chart(mdsport_heatmap(res))

    totals = res.param_totals
    fig = go.Figure(go.Bar(
        x=totals.to_numpy(), y=[i.split(" · ")[1] for i in totals.index], orientation="h",
        marker=dict(color=[C["sky"], C["violet"], C["teal"], C["amber"], C["pink"]]),
        text=[f"{int(v)}/20" for v in totals], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x}/20<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 24])
    fig.update_yaxes(autorange="reversed")
    fig = style_fig(fig, height=260)
    fig.update_layout(title=dict(text="Points per parameter (max 20)", x=0, font=dict(size=14)))
    show_chart(fig)

    st.caption(f"Data coverage: {res.coverage:.0%} of the 25 scoring cells.")
    for n in res.notes:
        html(f'<div class="note">⚠️ {n}</div>')


# ----------------------------------------------------------------------------
# MPTDS tab
# ----------------------------------------------------------------------------
def render_mptds(res) -> None:
    mcol = C["green"] if res.mcap_pass else C["red"]
    cards = [f"""<div class="gate" style="--c:{mcol}">
      <h4>{'✅' if res.mcap_pass else '❌'} M · Market cap</h4>
      <div class="row"><span>Value</span><b>₹{fmt_num(res.mcap, 0)} Cr</b></div>
      <div class="row"><span>Needs</span><b>≥ ₹{MPTDS_MCAP_MIN:,.0f} Cr</b></div></div>"""]
    for p in MPTDS_PARAMS:
        m = res.metrics[p]
        col = C["green"] if m["passes"] else C["red"]
        note = f'<div class="muted">{m["note"]}</div>' if m["note"] else ""
        cards.append(f"""<div class="gate" style="--c:{col}">
          <h4>{'✅' if m['passes'] else '❌'} {p[0]} · {p}</h4>
          <div class="row"><span>Avg YoY growth</span><b>{fmt_num(m['avg_growth'], 1, '%')}</b></div>
          <div class="row"><span>R² (trend fit)</span><b>{fmt_num(m['r2'], 2)}</b></div>
          <div class="row"><span>CAGR</span><b>{fmt_num(m['cagr'], 1, '%')}</b></div>
          <div class="row"><span>Years used</span><b>{m['n_years']}</b></div>{note}</div>""")
    html('<div class="grid">' + "".join(cards) + "</div>")
    st.caption(f"Pass rule: average YoY growth ≥ {res.min_growth:.0f}%, R² ≥ {res.min_r2} and a rising regression line.")

    html('<div class="section-title">Trend lines</div>')
    units = {"Price": "₹", "Tax": "₹ Cr", "Dividend": "₹ Cr", "Sales": "₹ Cr"}
    for i in range(0, len(MPTDS_PARAMS), 2):
        cols = st.columns(2)  # side-by-side on desktop/tablet, stacked on phones
        for col, p in zip(cols, MPTDS_PARAMS[i:i + 2]):
            s = res.series[p].dropna()
            m = res.metrics[p]
            fig = go.Figure()
            xl = [fy_short(l) for l in s.index]
            fig.add_trace(go.Bar(x=xl, y=s.to_numpy(), name=p,
                                 marker=dict(color=SERIES_COLORS[p], opacity=0.85),
                                 hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
            if not math.isnan(m["slope"]) and len(s) >= 3:
                xs = np.array([period_end(l).year + period_end(l).month / 12.0 for l in s.index])
                fig.add_trace(go.Scatter(x=xl, y=m["intercept"] + m["slope"] * xs, mode="lines",
                                         name="Regression", line=dict(color="#DB2777", width=3, dash="dot")))
            badge = "✅" if m["passes"] else "❌"
            fig = style_fig(fig, height=290)
            fig.update_layout(title=dict(text=f"{badge} {p} ({units[p]}) · R² {fmt_num(m['r2'], 2)}", x=0, font=dict(size=14)),
                              showlegend=False)
            with col:
                show_chart(fig)

    norm = res.series.apply(lambda c: c / c[c > 0].dropna().iloc[0] * 100 if (c > 0).any() else c * np.nan)
    fig = go.Figure()
    for p in MPTDS_PARAMS:
        fig.add_trace(go.Scatter(x=[fy_short(l) for l in norm.index], y=norm[p], mode="lines+markers", name=p,
                                 line=dict(color=SERIES_COLORS[p], width=3), connectgaps=False))
    fig = style_fig(fig, height=340)
    fig.update_layout(title=dict(text=f"All four rebased to 100 ({len(norm)}-year window)", x=0, font=dict(size=14)),
                      hovermode="x unified")
    show_chart(fig)


# ----------------------------------------------------------------------------
# Graham tab
# ----------------------------------------------------------------------------
STATUS_COLORS = {PASS: C["green"], FAIL: C["red"], PARTIAL: C["teal"], NO_DATA: C["amber"], NA: "#6B7280"}


def checklist_html(checks) -> str:
    rows = "".join(
        f"""<tr><td class="n">{escape(c.name)} <span class="badge mb" style="background:{STATUS_COLORS[c.status]}">{c.status}</span>
        <div class="sub">{escape(c.rule)}</div></td>
        <td>{escape(c.value)}{f'<div class="sub">{escape(c.note)}</div>' if c.note else ''}</td>
        <td><span class="badge" style="background:{STATUS_COLORS[c.status]}">{c.status}</span></td></tr>"""
        for c in checks
    )
    return f"""<div class="gwrap"><table class="gtable"><thead><tr><th>Test · Graham's rule</th>
      <th>This stock</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def mos_txt(v: float) -> str:
    if v is None or math.isnan(v):
        return "—"
    return f"{abs(v):.0%} {'below' if v >= 0 else 'above'}"


def render_graham(g, price: float, q: dict) -> None:
    def_col = C["green"] if g.def_pass == g.def_applicable else C["amber"] if g.def_pass >= g.def_applicable - 2 else C["red"]
    ent_col = C["green"] if g.ent_pass == g.ent_applicable else C["amber"] if g.ent_pass >= g.ent_applicable - 1 else C["red"]
    nn = (not math.isnan(g.net_net_buy)) and price <= g.net_net_buy
    nn_col = C["green"] if nn else ("#6B7280" if math.isnan(g.ncav_ps) else C["red"])
    html(f"""
    <div class="grid">
      <div class="gate" style="--c:{def_col}"><h4>Defensive investor</h4>
        <div class="row"><span>Tests passed</span><b>{g.def_pass} / {g.def_applicable}</b></div>
        <div class="muted">Ch. 14 — all must pass.</div></div>
      <div class="gate" style="--c:{ent_col}"><h4>Enterprising investor</h4>
        <div class="row"><span>Tests passed</span><b>{g.ent_pass} / {g.ent_applicable}</b></div>
        <div class="muted">Ch. 15 — looser rules, more homework.</div></div>
      <div class="gate" style="--c:{nn_col}"><h4>Net-net (NCAV)</h4>
        <div class="row"><span>NCAV / share</span><b>₹{fmt_num(g.ncav_ps, 2)}</b></div>
        <div class="row"><span>⅔ buy line</span><b>₹{fmt_num(g.net_net_buy, 2)}</b></div>
        <div class="muted">{'Price is at or below ⅔ of NCAV.' if nn else 'Not a net-net.'}</div></div>
      <div class="gate" style="--c:{C['sky']}"><h4>Earnings yield vs bonds</h4>
        <div class="row"><span>E/P (3-yr EPS)</span><b>{fmt_num(g.earnings_yield, 2, '%')}</b></div>
        <div class="row"><span>Bond yield Y</span><b>{fmt_num(g.bond_yield, 2, '%')}</b></div>
        <div class="muted">{'—' if math.isnan(g.earnings_yield) else ('Above' if g.earnings_yield > g.bond_yield else 'Below') + ' the bond yield.'}</div></div>
    </div>
    """)

    html('<div class="section-title">Defensive investor — 7 tests (Ch. 14)</div>')
    html(checklist_html(g.defensive))
    html('<div class="section-title">Enterprising investor — 5 tests (Ch. 15)</div>')
    html(checklist_html(g.enterprising))

    html('<div class="section-title">Graham valuation vs price</div>')
    levels = [
        ("Graham Number", g.graham_number, C["sky"]),
        (f"Growth value (g {fmt_num(g.growth_g * 100 if not math.isnan(g.growth_g) else np.nan, 1)}%)", g.growth_value, C["violet"]),
        (f"Growth buy line ({q.get('mos', 0.25):.0%} MoS)", g.growth_buy, C["green"]),
        ("NCAV / share", g.ncav_ps, C["teal"]),
        ("⅔ NCAV (net-net buy)", g.net_net_buy, C["amber"]),
    ]
    levels = [(n, v, c) for n, v, c in levels if v is not None and not math.isnan(v) and v > 0]
    if levels:
        fig = go.Figure(go.Bar(
            x=[v for _, v, _ in levels], y=[n for n, _, _ in levels], orientation="h",
            marker=dict(color=[c for _, _, c in levels]),
            text=[f"₹{v:,.0f}" for _, v, _ in levels], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: ₹%{x:,.2f}<extra></extra>",
        ))
        fig.add_vline(x=price, line=dict(color=C["pink"], width=3, dash="dot"),
                      annotation_text=f"Price ₹{price:,.0f}", annotation_position="top")
        fig.update_xaxes(range=[0, max([v for _, v, _ in levels] + [price]) * 1.22])
        fig.update_yaxes(autorange="reversed")
        fig = style_fig(fig, height=80 + 46 * len(levels))
        fig.update_layout(showlegend=False, margin=dict(l=8, r=8, t=46, b=8))
        show_chart(fig)
    else:
        st.info("Not enough data to compute any Graham value for this stock.")

    html(f"""
    <div class="grid-2">
      <div class="gate" style="--c:{C['sky']}"><h4>Graham Number √(22.5 × EPS × BVPS)</h4>
        <div class="row"><span>EPS (3-yr avg) · BVPS</span><b>₹{fmt_num(g.eps_avg3, 2)} · ₹{fmt_num(g.bvps, 2)}</b></div>
        <div class="row"><span>Graham Number</span><b>₹{fmt_num(g.graham_number, 2)}</b></div>
        <div class="row"><span>Price vs Graham Number</span><b>{mos_txt(g.mos_graham_number)}</b></div>
        <div class="muted">The most a defensive investor should pay (P/E 15 × P/B 1.5).</div></div>
      <div class="gate" style="--c:{C['violet']}"><h4>Growth formula V = EPS × (8.5 + 2g)</h4>
        <div class="row"><span>EPS (latest FY) · g</span><b>₹{fmt_num(g.eps_latest, 2)} · {fmt_num(g.growth_g * 100 if not math.isnan(g.growth_g) else np.nan, 1, '%')}</b></div>
        <div class="row"><span>Value · buy line</span><b>₹{fmt_num(g.growth_value, 2)} · ₹{fmt_num(g.growth_buy, 2)}</b></div>
        <div class="row"><span>Price vs value</span><b>{mos_txt(g.mos_growth)}</b></div>
        <div class="muted">The Intelligent Investor, Ch. 11. g = CAGR of 3-yr average EPS over up to 10 yrs, capped at 15% (the cap is this app's, not Graham's). A rough heuristic, as Graham himself warned.</div></div>
    </div>
    """)

    pe = q.get("nifty_pe") or 0.0
    with st.expander("Market allocation — Graham's 25–75% stock/bond band (Ch. 4)"):
        if pe > 0:
            band, why, _ = allocation_band(pe, g.bond_yield)
            st.markdown(f"**Suggested stocks : bonds = {band}**  \n{why}")
        else:
            st.markdown("Enter the NIFTY 50 P/E under *Advanced options* to see the band.")
        st.caption("Graham's rule: never less than 25% or more than 75% in stocks; 50:50 by default. The cut-offs "
                   "used here (earnings yield ÷ bond yield below 1 → 25:75, 1–1.5 → 50:50, 1.5 or more → 75:25) "
                   "are this app's reading of his guidance, not figures from the book.")

    with st.expander(f"{IIV_NAME}: what differs from Graham's rules, and why"):
        st.markdown(iiv_adaptations_md())

    for n in g.notes:
        html(f'<div class="note">⚠️ {n}</div>')


def iiv_adaptations_md() -> str:
    """The Indian adaptations and the reason for each (shown in the tab and in the Method tab)."""
    return f"""
**Unchanged from the book.** Current ratio ≥ 2, debt ≤ net current assets, 10 years of profits, 20 years of
dividends, EPS up ≥ ⅓, P/E ≤ 15, P/B ≤ 1.5 or P/E × P/B ≤ 22.5, all five enterprising tests, the Graham Number
and net-net. Graham set his P/E 15 cap when US AAA corporate bonds yielded about 7.2% (July 1972); India's
10-year AAA corporate yield was 7.49% in July 2026, so the bond-yield environment gives no reason to move it.

| Change | Graham's rule | Here | Why |
|---|---|---|---|
| **Size** | Sales ≥ $100M (1971 dollars) | Market cap ≥ AMFI midcap floor (₹{AMFI_MIDCAP_FLOOR:,.0f} Cr, Jan-2026 list) | Graham's aim was to exclude small companies. His dollar figure doesn't translate to India, while AMFI's top-250 list is SEBI's official large/midcap definition. Difference: AMFI ranks by market value, Graham used sales. AMFI revises the floor every January and July. |
| **Debt** | Long-term debt | Long-term debt **including non-current lease liabilities**, where Yahoo reports them | Since FY2019-20 Ind AS 116 puts leases on the balance sheet as fixed obligations. Only the non-current part is added; the current part already sits in current liabilities. |
| **Banks / NBFCs / insurers** | Current ratio and debt tests | Financial-condition and net-net tests **N/A**; a pass shows as **DEFENSIVE PASS\\*** in amber | Bank (Banking Regulation Act format) and NBFC (Schedule III, Division III) balance sheets have no current/non-current split, so the ratios can't be computed. Graham gave no balance-sheet threshold for lenders, so none is invented; the \\* says financial strength was not assessed. Detected from Screener's financing labels or a Deposits row, or set manually under *Advanced options*. |
| **Growth formula** | V = E × (8.5 + 2g), Ch. 11 | Same | The × 4.4 ÷ Y bond-yield version used earlier is a later revision that is not in *The Intelligent Investor*, so it was removed. The 15% cap on g is this app's practitioner limit, not Graham's. |
| **Earnings growth (optional, off by default)** | EPS up ≥ ⅓ over 10 years | EPS up ≥ max(⅓, CPI floor) | Graham's ⅓ is nominal. The floor is the rise in consumer prices between the same two 3-year windows, so a company can't pass while its EPS shrank in real terms. CPI: RBI Handbook Table 236 (All-India Combined, financial-year averages). With this app's 12-year window, FY14–FY25 gives a floor of about +55%. FY2025-26 is approximate because RBI changed the CPI base mid-year. **This is an addition, not Graham's rule.** |

**Not changed, still a limitation:** older EPS is not restated for bonus issues or splits; compare the growth
test with the net-profit growth shown beside it.
"""


# ----------------------------------------------------------------------------
# Data & methodology tabs
# ----------------------------------------------------------------------------
def graham_frame(g) -> pd.DataFrame:
    rows = [("Defensive", c) for c in g.defensive] + [("Enterprising", c) for c in g.enterprising]
    return pd.DataFrame([{"Screen": s, "Test": c.name, "Rule": c.rule, "Value": c.value, "Result": c.status}
                         for s, c in rows])


def render_data(data, mds, mpt, gr=None) -> None:
    st.markdown("**MDSPORT inputs (%, last 5 years)**")
    st.dataframe(mds.values.style.format("{:.1f}", na_rep="—"), width="stretch")
    st.markdown("**MPTDS series**")
    st.dataframe(mpt.series.style.format("{:,.2f}", na_rep="—"), width="stretch")
    with st.expander("Full Screener P&L"):
        st.dataframe(data.pnl, width="stretch")
    with st.expander("Balance sheet & ratios"):
        st.dataframe(data.balance_sheet, width="stretch")
        st.dataframe(data.ratios, width="stretch")
    if gr is not None:
        st.markdown("**Graham checklist**")
        st.dataframe(graham_frame(gr), width="stretch", hide_index=True)
    csv = pd.concat({"MPTDS": mpt.series.T, "MDSPORT": mds.values}).to_csv()
    if gr is not None:
        csv += "\nGraham checklist\n" + graham_frame(gr).to_csv(index=False)
    csv = csv.encode()
    st.download_button("⬇️  Download inputs (CSV)", csv, file_name=f"{data.symbol}_wealthcon_scores.csv",
                       mime="text/csv", width="stretch")
    st.caption(f"Source: [{data.url}]({data.url}) and Yahoo Finance (split-adjusted financial-year-end close; "
               "latest balance sheet and dividend history for the Graham tests).")


def render_method() -> None:
    st.markdown(f"""
#### MDSPORT — quality-growth score
**Screening filters (MD)**
- **M · Market cap** — size class (Large / Mid / Small). Classification only.
- **D · Debt-to-Equity** — Non-Current Liabilities ÷ Total Equity. **D/E ≥ {DE_LIMIT:.2f} is an automatic REJECT**, whatever the score.

**Scoring parameters (SPORT)** — each graded **0–4 points for every one of the last {MDSPORT_YEARS} years**
| Parameter | Measured as |
|---|---|
| **S** Sales growth % | YoY growth in sales |
| **P** PAT growth % | YoY growth in net profit |
| **O** OPM % | Operating profit margin level |
| **R** ROCE % | Return on capital employed level |
| **T** Tax growth % | YoY growth in tax paid (PBT − PAT) |

Slabs: &lt;5% → 0 · 5–10% → 1 · 10–15% → 2 · 15–20% → 3 · &gt;20% → 4.
Maximum = 5 × 5 × 4 = **100**. **Valid > {VALID_ABOVE}**, **Watchlist {WATCHLIST_FROM}–{VALID_ABOVE}**, **Rejected < {WATCHLIST_FROM}**.

#### MPTDS — trend-sustainability test
- **M** Market cap ≥ ₹{MPTDS_MCAP_MIN:,.0f} Cr
- **P** Price — financial-year-end (March) close
- **T** Tax paid — PBT − PAT
- **D** Dividend paid — PAT × Dividend payout %
- **S** Sales — revenue from operations

Each of P, T, D, S must be in a rising trend over 5–10 years: **Moderate** = average growth ≥ 5% and R² ≥ 0.25; **Strict** = ≥ 10% and R² ≥ 0.55. **VALID** only when M and all four trends pass.

#### Implementation choices
- Growth off a zero or negative base is treated as undefined (scores 0 / skipped) instead of producing infinite values.
- A value of exactly 20% scores 3 points ("> 20%" is needed for 4).
- D/E uses Screener's Borrowings ÷ (Equity capital + Reserves) as a proxy for NCL ÷ Equity; override it under *Advanced options* when you have the exact figure.
- Prices are never back-filled: a year with no trade near its year-end is left blank.
- Banks and NBFCs don't report OPM/ROCE in the same way, so MDSPORT under-scores them by design.

#### {IIV_NAME} — Graham's *The Intelligent Investor*, adapted for NSE large and midcaps
**Defensive investor (Ch. 14)** — all seven must pass:
1. **Size** — market cap ≥ AMFI's midcap floor (₹{AMFI_MIDCAP_FLOOR:,.0f} Cr in the Jan-2026 list; Indian adaptation of Graham's 1971 dollar limit).
2. **Financial condition** — current ratio ≥ 2 and long-term debt (including non-current lease liabilities where reported) ≤ net current assets.
3. **Earnings stability** — positive earnings in each of the last 10 years.
4. **Dividend record** — uninterrupted dividends for at least 20 years.
5. **Earnings growth** — EPS up at least one-third over ~10 years, using 3-year averages at both ends. *Optional:* at least the CPI rise between the same windows, if that is larger.
6. **Moderate P/E** — price ≤ 15 × average EPS of the last 3 years.
7. **Moderate P/B** — P/B ≤ 1.5, or P/E × P/B ≤ 22.5.

**Enterprising investor (Ch. 15)** — current ratio ≥ 1.5 and debt ≤ 110% of net current assets; no loss in 5 years;
some current dividend; latest EPS above the EPS of 5 years earlier; price below 120% of net tangible assets.

**Valuation** — Graham Number √(22.5 × EPS × BVPS); growth formula V = EPS × (8.5 + 2g) (Ch. 11; g capped at
15% by this app); net-net = price ≤ ⅔ of (current assets − total liabilities) per share (not for banks/NBFCs).
Y (10Y G-Sec + optional AAA spread) is used only for the earnings-yield comparison and the stock/bond band.

**Verdict** — NET-NET BARGAIN or DEFENSIVE PASS → green; ENTERPRISING PASS → amber; otherwise FAILS GRAHAM.
Banks/NBFCs/insurers: a pass shows as DEFENSIVE PASS\\* in amber, because Graham's balance-sheet test can't be run.
**Short histories** — when a record is shorter than the test asks for, the years that exist are still analysed:
- *Earnings stability* (10 / 5 yrs): no loss in ≥ 3 years available → **PARTIAL**; any loss → FAIL.
- *Earnings growth* (10 yrs): growth over the years available (3-yr averages from 6 years, first vs last year
  with 4–5) is compared with Graham's pace of +⅓ in 10 years ≈ 2.9%/yr → on pace **PARTIAL**, below pace FAIL.
- *Dividend record* (20 yrs): paid every year of a ≥ 3-year record → **PARTIAL**; a missed year → FAIL.

PARTIAL and **NO DATA** (too few years even for that) never count as a pass; **N/A** tests (current ratio for
banks/NBFCs) are left out of the count.

**Data notes**
- EPS, profit and payout: Screener (about 12 years). Book value: Screener's top ratio.
- Current assets, current liabilities, total liabilities, long-term debt, tangible book: Yahoo Finance's latest
  balance sheet, converted to ₹ crore. A >35% gap between Yahoo's and Screener's total assets is flagged.
  Enter the figures manually under *Advanced options* when Yahoo has none.
- Dividend record: Yahoo's ex-dividend history grouped by April–March year; falls back to Screener's payout %.
- Shares = market cap ÷ price. Screener's older EPS may not be restated for bonuses or splits — compare with
  the net-profit growth shown beside the growth test.
""")
    st.markdown(f"##### {IIV_NAME}: what differs from Graham's rules, and why")
    st.markdown(iiv_adaptations_md())


def render_footer() -> None:
    html(f"""
    <div class="footer">
      <div class="who">🩺📊 {AUTHOR}</div>
      <div>{AUTHOR_TITLE} · {AUTHOR_PLACE}</div>
      <div class="disc"><b>Disclaimer:</b> This tool is for education and research only and is not investment advice
      or a recommendation to buy or sell any security. Data is pulled from third-party sources (Screener.in, Yahoo Finance)
      and may be delayed, incomplete or revised. Verify figures independently and consult a SEBI-registered investment
      adviser before investing.</div>
      <div class="disc">© {YEAR} {AUTHOR}. All rights reserved.</div>
    </div>
    """)


def resolve_symbol(text: str) -> str | None:
    """Exact NSE symbol (any case, '.NS'/'.BO' allowed), BSE code or common short-form -> symbol.
    Anything else shows the likely NSE stocks as buttons and returns None (same finder as the Forward Matrix).
    Returns "" when the NSE list can't be downloaded, so the caller falls back to the name search."""
    q = text.strip().upper()
    for suffix in (".NS", ".BO"):
        if q.endswith(suffix):
            q = q[: -len(suffix)]
    if q.isdigit():
        return q                                   # BSE code: Screener accepts it directly
    alias = alias_symbol(q)
    nse = get_nse_list()
    if nse is None:
        return ""
    symbols = set(nse["SYMBOL"])
    if q in symbols:
        return q
    if alias and alias in symbols:
        return alias
    opts = suggest_symbols(q, nse)
    if opts:
        st.warning(f"**“{text.strip()}”** is not an NSE symbol. Did you mean one of these?")
        cols = st.columns(2)
        for i, (sym_, nm_) in enumerate(opts):
            if cols[i % 2].button(f"{sym_} · {nm_.title()}" if nm_ else sym_, key=f"sugg_{sym_}", width="stretch"):
                st.session_state["query"]["symbol"] = sym_
                st.session_state["last_symbol"] = sym_
                st.session_state["_wc_input_pending"] = sym_   # show the chosen symbol in the box
                st.rerun()
    else:
        st.warning(f"**“{text.strip()}”** is not an NSE symbol and nothing similar was found. "
                   "Try the company name, e.g. *tata motors*.")
    return None


def find_company(text: str, basis: str):
    """Ticker first; if that isn't a Screener page (or the text is a name), search by name."""
    if looks_like_symbol(text):
        try:
            with st.spinner(f"Fetching filings for {text.upper()} from Screener.in…"):
                return load_company(text.upper(), basis)
        except NotFoundError:
            pass  # e.g. "Shriram" — treat as a name

    with st.spinner(f"Looking up “{text}”…"):
        matches = load_matches(text)
    if not matches:
        st.error(f"Couldn't find a listed company matching “{text}”. Try a fuller name or the NSE symbol.")
        return None

    banner = st.empty()  # filled after the picker so it always reflects the chosen match
    idx = 0
    if len(matches) > 1:
        idx = st.selectbox(
            "Not the right company? Pick another match",
            range(len(matches)), key=f"pick::{text.lower()}",
            format_func=lambda i: f"{matches[i].name}  ·  {matches[i].symbol}",
        )
    m = matches[idx]
    banner.markdown(f'<div class="match">🔎 “{escape(text)}” → <b>{escape(m.name)}</b> '
                    f'<span class="sym">{escape(m.symbol)}</span></div>', unsafe_allow_html=True)
    with st.spinner(f"Fetching filings for {m.symbol} from Screener.in…"):
        return load_company(m.symbol, basis)


# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------
def main() -> None:
    html(CSS)
    render_sidebar()
    render_hero()
    st.markdown("")
    q = render_form()

    if not q:
        html(f"""
        <div class="grid-2">
          {verdict_card("Step 1", "WATCHLIST", "Enter a company", "Type a company name (e.g. Shriram Finance) or an NSE symbol and press Analyse.", ["Screener.in", "Yahoo Finance"])}
          {verdict_card("Step 2", "VALID", "Read the verdicts", "MDSPORT scores quality growth out of 100; MPTDS checks four long-term uptrends.", ["MDSPORT", "MPTDS"])}
        </div>""")
        render_footer()
        return

    if not q["symbol"]:
        st.warning("Please enter a company name or symbol.")
        render_footer()
        return

    try:
        sym = resolve_symbol(q["symbol"])
        if sym is None:                      # suggestions are on screen; wait for a pick
            render_footer()
            return
        if sym:
            with st.spinner(f"Fetching filings for {sym} from Screener.in…"):
                data = load_company(sym, q["basis"])
        else:                                # NSE list unavailable: previous name search
            data = find_company(q["symbol"], q["basis"])
        if data is None:
            render_footer()
            return
    except DataError as e:
        st.error(str(e))
        render_footer()
        return

    pnl_m = data.pnl.tail(q["years"])
    with st.spinner("Fetching year-end prices from Yahoo Finance…"):
        prices = load_prices(data.symbol, tuple(pnl_m.index))

    cfg = SENSITIVITY[q["sens"]]
    mds = evaluate_mdsport(data.pnl, data.ratios, data.balance_sheet, data.market_cap,
                           de_override=q["de_override"], large_min=q["large_min"], mid_min=q["mid_min"])
    mpt = evaluate_mptds(data.market_cap, prices, pnl_m, cfg["min_growth"], cfg["min_r2"])

    with st.spinner("Fetching balance sheet and dividend history from Yahoo Finance…"):
        extras = load_extras(data.symbol)
    bal, bal_notes = balance_from_sources(extras.get("balance"), data.balance_sheet, q.get("manual_bs"))
    gr = evaluate_graham(GrahamInputs(
        pnl=data.pnl, balance_sheet=data.balance_sheet, price=data.current_price, market_cap=data.market_cap,
        book_value_ps=getattr(data, "book_value", np.nan), bal=bal, dividends_fy=extras.get("dividends"),
        bond_yield=q.get("gsec", DEFAULT_GSEC) + q.get("spread", 0) / 100.0,
        size_min=q.get("graham_size", AMFI_MIDCAP_FLOOR), mos_required=q.get("mos", 0.25),
        is_financial=detect_financial(data.pnl, data.balance_sheet) or bool(q.get("force_fin", False)),
        inflation_floor=bool(q.get("infl_floor", False)),
    ))
    gr.notes = bal_notes + gr.notes

    render_company_strip(data, len(data.pnl))
    passed = sum(m["passes"] for m in mpt.metrics.values()) + int(mpt.mcap_pass)
    mds_card = verdict_card(
        "MDSPORT · quality growth", mds.verdict, f"{mds.score}/100 · {mds.verdict}", mds.reason,
        [f"D/E {fmt_num(mds.de_ratio, 2)}", mds.mcap_class, f"Coverage {mds.coverage:.0%}"],
    )
    gate_pills = [("✓ " if mpt.mcap_pass else "✗ ") + "Mcap"] + [
        ("✓ " if mpt.metrics[p]["passes"] else "✗ ") + p for p in MPTDS_PARAMS
    ]
    mpt_card = verdict_card(
        "MPTDS · trend sustainability", mpt.verdict, mpt.verdict,
        f"{passed} of 5 gates passed · {q['sens']} sensitivity", gate_pills,
    )
    gr_card = verdict_card(
        f"{IIV_NAME} · Graham", gr.verdict, gr.headline, gr.reason,
        [f"Defensive {gr.def_pass}/{gr.def_applicable}", f"Enterprising {gr.ent_pass}/{gr.ent_applicable}",
         f"Graham No. ₹{fmt_num(gr.graham_number, 0)}"],
    )
    html(f'<div class="grid-2">{mds_card}{mpt_card}<div style="grid-column:1/-1">{gr_card}</div></div>')
    if prices.isna().all():
        html('<div class="note">⚠️ Yahoo Finance returned no prices for this symbol, so the MPTDS Price trend cannot pass.</div>')

    t1, t2, t5, t3, t4 = st.tabs(["🎯 MDSPORT", "📈 MPTDS", f"🧮 {IIV_NAME}", "📋 Data", "📘 Method"])
    with t1:
        render_mdsport(mds)
    with t2:
        render_mptds(mpt)
    with t5:
        render_graham(gr, data.current_price, q)
    with t3:
        render_data(data, mds, mpt, gr)
    with t4:
        render_method()

    render_footer()


main()
