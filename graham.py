"""
Indian Intelligent Investor layer: Benjamin Graham (The Intelligent Investor) adapted for NSE
large and midcaps, for the Wealthcon Investment Scorer.

Pure functions only (no network, no Streamlit), like engine.py.

Indian adaptations (Graham's own thresholds are unchanged; the reasons are shown in the app):
    - Size uses the AMFI midcap floor (rank <= 250) instead of Graham's 1971 dollar sales limit.
    - Long-term debt includes non-current lease liabilities (Ind AS 116) where Yahoo reports them.
    - Banks / NBFCs / insurers: financial-condition and net-net tests are N/A, and a pass is
      marked "*" and kept amber because Graham's balance-sheet test could not be run.
    - Growth formula is the book's Chapter 11 form, V = E x (8.5 + 2g).
    - Optional (off by default): test 5 requires EPS growth >= max(1/3, CPI floor), where the
      CPI floor is the rise in consumer prices between the same two 3-year windows.

Defensive investor (Ch. 14) - seven tests
    1 Size              market cap >= AMFI midcap floor (Rs 34,700 Cr, Jan-2026 list, by default)
    2 Financial cond.   current ratio >= 2  AND  long-term debt <= net current assets
    3 Earnings stab.    positive earnings in each of the last 10 years
    4 Dividend record   uninterrupted dividends for at least 20 years
    5 Earnings growth   EPS up >= one-third over ~10 years, 3-year averages at both ends
                        (optional: >= max(1/3, CPI floor))
    6 Moderate P/E      price <= 15 x average EPS of the last 3 years
    7 Moderate P/B      P/B <= 1.5, or P/E x P/B <= 22.5

Enterprising investor (Ch. 15) - five tests
    1 Financial cond.   current ratio >= 1.5  AND  debt <= 110% of net current assets
    2 Earnings stab.    no loss in the last 5 years
    3 Dividend          some current dividend
    4 Earnings growth   last year's EPS above the EPS of 5 years earlier
    5 Price             below 120% of net tangible assets per share

Valuation
    Graham Number      sqrt(22.5 x EPS(3-yr avg) x BVPS)  - the most a defensive investor pays
    Growth formula     EPS x (8.5 + 2g)                   - The Intelligent Investor, Ch. 11
    NCAV (net-net)     current assets - total liabilities; buy at <= 2/3 of NCAV per share
                       (not applicable to banks / NBFCs)
    Earnings yield     EPS(3-yr avg) / price, compared with Y

Every test reports PASS, FAIL, NO DATA (history too short or field missing) or N/A
(not applicable, e.g. current ratio for a bank). NO DATA never counts as a pass.

Developed by Dr. Shantanu Samanta.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine import pick

# ----------------------------------------------------------------------------
# Graham's thresholds
# ----------------------------------------------------------------------------
DEF_CURRENT_RATIO = 2.0
DEF_STABLE_YEARS = 10
DEF_DIVIDEND_YEARS = 20
DEF_GROWTH_MIN = 1 / 3
DEF_PE_MAX = 15.0
DEF_PB_MAX = 1.5
DEF_PE_PB_MAX = 22.5

ENT_CURRENT_RATIO = 1.5
ENT_DEBT_TO_NCA = 1.10
ENT_STABLE_YEARS = 5
ENT_GROWTH_YEARS = 5
ENT_NTA_MAX = 1.20

GROWTH_CAP = 0.15          # practitioner cap on g in the growth formula (not Graham's own rule)
NET_NET_FRACTION = 2 / 3

# ----------------------------------------------------------------------------
# Indian adaptations
# ----------------------------------------------------------------------------
# Size: AMFI's midcap floor = market cap of the company ranked 250. Jan-2026 list (valid Feb-Jul 2026).
# AMFI revises it every January and July; update it in the app's Advanced options.
AMFI_MIDCAP_FLOOR = 34_700.0     # Rs crore

# Optional inflation floor for test 5. Annual CPI inflation (%), All-India Combined, average of
# months, by financial year (label = FY end). Source: RBI Handbook of Statistics on Indian Economy,
# Table 236 (published 31 Jul 2026), from NSO/MoSPI. Base 2012=100 up to FY2024-25.
CPI_FY_PCT = {
    "Mar 2013": 9.9, "Mar 2014": 9.4, "Mar 2015": 5.9, "Mar 2016": 4.9, "Mar 2017": 4.5,
    "Mar 2018": 3.6, "Mar 2019": 3.4, "Mar 2020": 4.8, "Mar 2021": 6.2, "Mar 2022": 5.5,
    "Mar 2023": 6.7, "Mar 2024": 5.4, "Mar 2025": 4.6,
    # FY2025-26 APPROXIMATION: RBI gives 1.7% for Apr-Dec 2025 (2012 base) and 3.1% for Jan-Mar 2026
    # (new 2024 base) but no full-year figure. Time-weighted (9 x 1.7 + 3 x 3.1) / 12 = 2.05%.
    # The two bases are not chain-linked, so treat this year as approximate.
    "Mar 2026": 2.05,
}
CPI_APPROX_LABELS = {"Mar 2026"}

PASS, FAIL, NO_DATA, NA = "PASS", "FAIL", "NO DATA", "N/A"
PARTIAL = "PARTIAL"        # clean on the years available, but history shorter than Graham's rule
MIN_PARTIAL_YEARS = 3      # below this a short record says too little to show a partial result

EPS_ALIASES = ["EPS in Rs", "EPS"]


def _nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return np.nan
    return f


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
@dataclass
class BalanceItems:
    """Latest balance-sheet items in Rs crore (from Yahoo Finance or entered manually)."""
    current_assets: float = np.nan
    current_liabilities: float = np.nan
    total_liabilities: float = np.nan
    long_term_debt: float = np.nan
    tangible_book: float = np.nan      # total net tangible assets (equity - intangibles)
    total_assets: float = np.nan
    period: str = "—"
    source: str = "—"


@dataclass
class GrahamInputs:
    pnl: pd.DataFrame
    balance_sheet: pd.DataFrame
    price: float
    market_cap: float                 # Rs crore
    book_value_ps: float              # Rs per share (Screener 'Book Value')
    bal: BalanceItems
    dividends_fy: pd.Series           # FY label -> dividend per share (Yahoo), may be empty
    bond_yield: float                 # % (10Y G-Sec + spread)
    size_min: float = AMFI_MIDCAP_FLOOR   # Rs crore
    mos_required: float = 0.25        # fraction
    is_financial: bool = False
    inflation_floor: bool = False     # optional CPI floor on test 5 (off = Graham's 1/3 only)


@dataclass
class Check:
    key: str
    name: str
    rule: str
    value: str
    status: str
    note: str = ""


@dataclass
class GrahamResult:
    defensive: list[Check]
    enterprising: list[Check]
    def_pass: int
    def_applicable: int
    ent_pass: int
    ent_applicable: int
    eps_avg3: float
    eps_latest: float
    bvps: float
    shares_cr: float
    pe_avg3: float
    pb: float
    graham_number: float
    growth_g: float
    growth_value: float
    growth_buy: float
    ncav_ps: float
    net_net_buy: float
    ntav_ps: float
    earnings_yield: float
    bond_yield: float
    mos_graham_number: float
    mos_growth: float
    verdict: str                      # style key: VALID / WATCHLIST / REJECTED
    headline: str
    reason: str
    notes: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def eps_series(pnl: pd.DataFrame) -> pd.Series:
    if pnl is None or pnl.empty:
        return pd.Series(dtype=float)
    for name in EPS_ALIASES:
        if name in pnl.columns:
            return pd.to_numeric(pnl[name], errors="coerce")
    return pd.Series(np.nan, index=pnl.index, dtype=float)


def detect_financial(pnl: pd.DataFrame, bs: pd.DataFrame | None = None) -> bool:
    """Screener labels banks/NBFCs with 'Financing Profit' / 'Financing Margin %' instead of OPM.
    A 'Deposits' row in the balance sheet also marks a bank. Insurers and other financials may carry
    neither label, so the app also offers a manual 'treat as financial' switch."""
    cols = set(pnl.columns) if pnl is not None else set()
    if {"Financing Profit", "Financing Margin %"} & cols:
        return True
    bs_cols = set(bs.columns) if bs is not None and not bs.empty else set()
    return "Deposits" in bs_cols


def shares_crore(price: float, market_cap: float) -> float:
    """Shares outstanding in crore = market cap (Rs Cr) / price (Rs)."""
    if _nan(price) or _nan(market_cap) or price <= 0 or market_cap <= 0:
        return np.nan
    return market_cap / price


def book_value_per_share(bvps_screener: float, bs: pd.DataFrame, shares_cr: float) -> tuple[float, str]:
    if not _nan(bvps_screener) and bvps_screener > 0:
        return float(bvps_screener), "Screener 'Book Value'"
    if bs is not None and not bs.empty and not _nan(shares_cr) and shares_cr > 0:
        eq = (pick(bs, "equity_capital").fillna(0) + pick(bs, "reserves").fillna(0)).dropna()
        eq = eq[eq > 0]
        if len(eq):
            return float(eq.iloc[-1] / shares_cr), "(Equity capital + Reserves) ÷ shares"
    return np.nan, "—"


def dividend_streak(paid: pd.Series) -> tuple[int, int, bool]:
    """paid: chronological bool series (one entry per FY).
    Returns (unbroken years ending at the latest FY, years of history, broken-within-history)."""
    vals = [bool(v) for v in paid.tolist()]
    n = len(vals)
    streak = 0
    for v in reversed(vals):
        if not v:
            break
        streak += 1
    return streak, n, streak < n


def _status_min(value: float, limit: float) -> str:
    return NO_DATA if _nan(value) else (PASS if value >= limit else FAIL)


def _status_max(value: float, limit: float) -> str:
    return NO_DATA if _nan(value) else (PASS if value <= limit else FAIL)


def _combine(*statuses: str) -> str:
    if FAIL in statuses:
        return FAIL
    if NO_DATA in statuses:
        return NO_DATA
    if all(s == NA for s in statuses):
        return NA
    return PASS


def fmt(v: float, d: int = 2, suffix: str = "") -> str:
    return "—" if _nan(v) else f"{v:,.{d}f}{suffix}"


def _count(checks: list[Check]) -> tuple[int, int]:
    applicable = [c for c in checks if c.status != NA]
    return sum(c.status == PASS for c in applicable), len(applicable)


# ----------------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------------
def evaluate_graham(g: GrahamInputs) -> GrahamResult:
    notes: list[str] = []
    pnl = g.pnl
    eps = eps_series(pnl).dropna()
    profit = pick(pnl, "net_profit").dropna()
    payout = pick(pnl, "payout")
    price = _num(g.price)
    bal = g.bal
    fin = g.is_financial

    sh = shares_crore(price, g.market_cap)
    bvps, bv_src = book_value_per_share(g.book_value_ps, g.balance_sheet, sh)
    if eps.empty:
        notes.append("Screener did not return an 'EPS in Rs' row, so per-share tests can't be run.")
    else:
        notes.append("Graham's per-share tests use Screener's annual EPS. If the company issued bonus shares "
                     "or split its stock, older EPS may not be restated — check the 10-year growth test "
                     "against net-profit growth shown beside it.")

    eps_latest = float(eps.iloc[-1]) if len(eps) else np.nan
    eps_avg3 = float(eps.tail(3).mean()) if len(eps) >= 3 else np.nan
    pe_avg3 = price / eps_avg3 if not _nan(eps_avg3) and eps_avg3 > 0 else np.nan
    pb = price / bvps if not _nan(bvps) and bvps > 0 else np.nan

    # Balance-sheet derived (Rs crore)
    ca, cl, tl, ltd = bal.current_assets, bal.current_liabilities, bal.total_liabilities, bal.long_term_debt
    cr = ca / cl if not _nan(ca) and not _nan(cl) and cl > 0 else np.nan
    nca = ca - cl if not _nan(ca) and not _nan(cl) else np.nan
    ncav = ca - tl if not _nan(ca) and not _nan(tl) else np.nan
    if fin:
        ncav = np.nan   # lenders have no current/non-current split, so NCAV (net-net) is not applicable
    ncav_ps = ncav / sh if not _nan(ncav) and not _nan(sh) and sh > 0 else np.nan
    ntav_ps = bal.tangible_book / sh if not _nan(bal.tangible_book) and not _nan(sh) and sh > 0 else np.nan
    if _nan(ntav_ps) and not _nan(bvps):
        ntav_ps = bvps
        notes.append("Net tangible assets not available — book value per share (which includes intangibles) "
                     "is used for the enterprising 120% test, so that test is a little lenient.")

    def debt_vs_nca(limit: float) -> tuple[str, str]:
        if _nan(ltd) or _nan(nca):
            return NO_DATA, "—"
        if nca <= 0:
            return (PASS if ltd <= 0 else FAIL), f"LTD ₹{fmt(ltd, 0)} Cr vs NCA ₹{fmt(nca, 0)} Cr"
        return (PASS if ltd <= limit * nca else FAIL), f"LTD ÷ NCA = {fmt(ltd / nca, 2)}"

    # ---------------- Defensive ----------------
    d: list[Check] = []
    d.append(Check("size", "Size", f"Market cap ≥ ₹{g.size_min:,.0f} Cr", f"₹{fmt(g.market_cap, 0)} Cr",
                   _status_min(g.market_cap, g.size_min),
                   "Indian adaptation: Graham's 1971 dollar sales limit replaced by AMFI's midcap floor "
                   "(the company ranked 250 by market cap)."))

    if fin:
        d.append(Check("fin", "Financial condition", "Current ratio ≥ 2 · LT debt ≤ net current assets",
                       "—", NA, "Not meaningful for banks / NBFCs (no current/non-current split)."))
    else:
        s_cr = _status_min(cr, DEF_CURRENT_RATIO)
        s_debt, debt_txt = debt_vs_nca(1.0)
        d.append(Check("fin", "Financial condition", "Current ratio ≥ 2 · LT debt ≤ net current assets",
                       f"CR {fmt(cr, 2)} · {debt_txt}", _combine(s_cr, s_debt),
                       f"Balance sheet: {bal.source}, {bal.period}."))

    base = eps if len(eps) else profit
    s, v, note = stability_check(base, DEF_STABLE_YEARS)
    d.append(Check("stab", "Earnings stability", "Positive earnings in each of the last 10 years", v, s, note))

    d.append(_dividend_check(g.dividends_fy, payout))

    s, v, note = _ten_year_growth(eps, profit, g.inflation_floor)
    growth_rule = ("EPS up ≥ max(⅓, CPI floor) over 10 yrs (3-yr averages)" if g.inflation_floor
                   else "EPS up ≥ ⅓ over 10 yrs (3-yr averages)")
    d.append(Check("growth", "Earnings growth", growth_rule, v, s, note))

    d.append(Check("pe", "Moderate P/E", "Price ≤ 15 × avg EPS of last 3 yrs", f"P/E(3y) {fmt(pe_avg3, 1)}",
                   NO_DATA if _nan(pe_avg3) else (PASS if pe_avg3 <= DEF_PE_MAX else FAIL),
                   "Average EPS ≤ 0 makes the test fail." if not _nan(eps_avg3) and eps_avg3 <= 0 else ""))
    if not _nan(eps_avg3) and eps_avg3 <= 0:
        d[-1].status = FAIL

    pepb = pe_avg3 * pb if not _nan(pe_avg3) and not _nan(pb) else np.nan
    if _nan(pb):
        s = NO_DATA
    else:
        s = PASS if pb <= DEF_PB_MAX or (not _nan(pepb) and pepb <= DEF_PE_PB_MAX) else FAIL
    d.append(Check("pb", "Moderate P/B", "P/B ≤ 1.5, or P/E × P/B ≤ 22.5",
                   f"P/B {fmt(pb, 2)} · P/E×P/B {fmt(pepb, 1)}", s, f"Book value: {bv_src}."))

    # ---------------- Enterprising ----------------
    e: list[Check] = []
    if fin:
        e.append(Check("fin", "Financial condition", "Current ratio ≥ 1.5 · debt ≤ 110% of NCA", "—", NA,
                       "Not meaningful for banks / NBFCs."))
    else:
        s_cr = _status_min(cr, ENT_CURRENT_RATIO)
        s_debt, debt_txt = debt_vs_nca(ENT_DEBT_TO_NCA)
        e.append(Check("fin", "Financial condition", "Current ratio ≥ 1.5 · debt ≤ 110% of NCA",
                       f"CR {fmt(cr, 2)} · {debt_txt}", _combine(s_cr, s_debt)))

    s, v, note = stability_check(base, ENT_STABLE_YEARS)
    e.append(Check("stab", "Earnings stability", "No loss in the last 5 years", v, s, note))

    cur_div = _current_dividend(g.dividends_fy, payout)
    e.append(Check("div", "Dividend record", "Some current dividend",
                   "Paid" if cur_div else ("Not paid" if cur_div is False else "—"),
                   NO_DATA if cur_div is None else (PASS if cur_div else FAIL)))

    if len(eps) > ENT_GROWTH_YEARS:
        e0, e1 = float(eps.iloc[-1 - ENT_GROWTH_YEARS]), float(eps.iloc[-1])
        s = PASS if e1 > e0 else FAIL
        v = f"EPS {fmt(e1, 1)} vs {fmt(e0, 1)} ({eps.index[-1 - ENT_GROWTH_YEARS]})"
    else:
        s, v = NO_DATA, "—"
    e.append(Check("growth", "Earnings growth", "Last year's EPS > EPS 5 years earlier", v, s))

    ratio_nta = price / ntav_ps if not _nan(ntav_ps) and ntav_ps > 0 else np.nan
    if not _nan(ntav_ps) and ntav_ps <= 0:
        s = FAIL
    else:
        s = _status_max(ratio_nta, ENT_NTA_MAX)
    e.append(Check("nta", "Price vs tangible assets", "Price < 120% of net tangible assets per share",
                   f"Price ÷ NTA {fmt(ratio_nta, 2)}", s))

    # ---------------- Valuation ----------------
    gn = math.sqrt(22.5 * eps_avg3 * bvps) if not _nan(eps_avg3) and not _nan(bvps) and eps_avg3 > 0 and bvps > 0 else np.nan
    growth_g = _growth_rate(eps)
    y = _num(g.bond_yield)
    # The Intelligent Investor, Ch. 11: V = E x (8.5 + 2g), g in % a year. (The x 4.4 / Y bond-yield
    # adjustment is a later revision that is not in the book, so it is not used here.)
    if not _nan(eps_latest) and eps_latest > 0 and not _nan(growth_g):
        gv = eps_latest * (8.5 + 2 * growth_g * 100)
    else:
        gv = np.nan
    growth_buy = gv * (1 - g.mos_required) if not _nan(gv) else np.nan
    net_net_buy = ncav_ps * NET_NET_FRACTION if not _nan(ncav_ps) and ncav_ps > 0 else np.nan
    ey = eps_avg3 / price * 100 if not _nan(eps_avg3) and price > 0 else np.nan
    mos_gn = 1 - price / gn if not _nan(gn) and gn > 0 else np.nan
    mos_gv = 1 - price / gv if not _nan(gv) and gv > 0 else np.nan

    if fin:
        notes.append("Bank / NBFC detected: financial-condition tests and NCAV are not applicable; "
                     "Graham's framework was written for industrial companies.")
    if not fin and bal.source == "—":
        notes.append("No current-asset / current-liability data — Yahoo Finance had none for this symbol. "
                     "Enter them under Advanced options to complete the financial-condition and net-net tests.")

    def_pass, def_app = _count(d)
    ent_pass, ent_app = _count(e)
    def_all = def_app > 0 and def_pass == def_app
    ent_all = ent_app > 0 and ent_pass == ent_app
    is_net_net = not _nan(net_net_buy) and price <= net_net_buy

    if is_net_net:
        verdict, headline = "VALID", "NET-NET BARGAIN"
        reason = f"Price ₹{fmt(price, 2)} ≤ ⅔ of NCAV (₹{fmt(net_net_buy, 2)})"
    elif def_all and fin:
        # A lender can't be checked on Graham's balance-sheet test, so "all passed" covers only the
        # applicable tests: shown with "*" and kept amber rather than green.
        verdict, headline = "WATCHLIST", "DEFENSIVE PASS*"
        reason = (f"All {def_app} applicable defensive tests passed · *financial strength not assessed "
                  "(bank/NBFC: Graham's balance-sheet test can't be computed)")
    elif def_all:
        verdict, headline = "VALID", "DEFENSIVE PASS"
        reason = f"All {def_app} defensive tests passed"
    elif ent_all:
        verdict, headline = "WATCHLIST", "ENTERPRISING PASS" + ("*" if fin else "")
        reason = f"Defensive {def_pass}/{def_app} · all {ent_app} enterprising tests passed"
        if fin:
            reason += " · *financial strength not assessed (bank/NBFC)"
    else:
        verdict, headline = "REJECTED", "FAILS GRAHAM"
        reason = f"Defensive {def_pass}/{def_app} · Enterprising {ent_pass}/{ent_app}"
    partial = sum(c.status == PARTIAL for c in d + e)
    if partial:
        reason += f" · {partial} partial (short history)"
    no_data = sum(c.status == NO_DATA for c in d + e)
    if no_data:
        reason += f" · {no_data} test(s) lacked data"

    return GrahamResult(
        defensive=d, enterprising=e, def_pass=def_pass, def_applicable=def_app,
        ent_pass=ent_pass, ent_applicable=ent_app, eps_avg3=eps_avg3, eps_latest=eps_latest,
        bvps=bvps, shares_cr=sh, pe_avg3=pe_avg3, pb=pb, graham_number=gn, growth_g=growth_g,
        growth_value=gv, growth_buy=growth_buy, ncav_ps=ncav_ps, net_net_buy=net_net_buy,
        ntav_ps=ntav_ps, earnings_yield=ey, bond_yield=y, mos_graham_number=mos_gn,
        mos_growth=mos_gv, verdict=verdict, headline=headline, reason=reason, notes=notes,
    )


def stability_check(base: pd.Series, required: int) -> tuple[str, str, str]:
    """Earnings stability over the last `required` years, using whatever history exists.
    - any loss in the years available          -> FAIL (a loss fails however short the record)
    - full history, no loss                    -> PASS
    - shorter history (>= 3 yrs), no loss      -> PARTIAL: clean so far, but not yet Graham's full test
    - fewer than 3 years                       -> NO DATA"""
    s = pd.to_numeric(base, errors="coerce").dropna().tail(required)
    n = len(s)
    if n == 0:
        return NO_DATA, "—", "No earnings data."
    pos = int((s > 0).sum())
    span = f"{s.index[0]} – {s.index[-1]}" if n > 1 else str(s.index[0])
    losses = [str(i) for i in s.index[s <= 0]]
    value = f"{pos}/{n} yrs positive ({span})"
    if losses:
        note = "Loss / zero earnings in " + ", ".join(losses) + "."
        if n < required:
            note += f" Only {n} of the {required} years Graham asks for are available."
        return FAIL, value, note
    if n >= required:
        return PASS, value, ""
    if n < MIN_PARTIAL_YEARS:
        return NO_DATA, value, f"Only {n} year(s) of earnings — too short to judge."
    return PARTIAL, value, (f"Positive in every year available, but only {n} of the {required} years "
                            f"Graham asks for exist ({required - n} short). Not counted as a pass.")


def _dividend_check(div_fy: pd.Series, payout: pd.Series) -> Check:
    rule = "Uninterrupted dividends for ≥ 20 years"
    if div_fy is not None and len(div_fy.dropna()):
        s = div_fy.fillna(0) > 0
        streak, n, broken = dividend_streak(s)
        src = f"Yahoo dividend history ({n} FYs from {div_fy.index[0]})"
        if streak >= DEF_DIVIDEND_YEARS:
            return Check("div", "Dividend record", rule, f"{streak} yrs unbroken", PASS, src)
        if broken:
            return Check("div", "Dividend record", rule, f"{streak} yrs unbroken", FAIL,
                         src + ". A year with no dividend can also be a gap in Yahoo's data — verify.")
        return _short_dividend_record(rule, s.index, n, "Yahoo's record",
                                      "the company may have paid before Yahoo's record begins")
    p = payout.dropna() if payout is not None else pd.Series(dtype=float)
    if len(p):
        streak, n, broken = dividend_streak(p > 0)
        if not (p > 0).any():
            return Check("div", "Dividend record", rule, f"No dividend in {n} yrs (Screener payout)", FAIL,
                         f"No dividend paid in any year from {p.index[0]} to {p.index[-1]}.")
        if broken:
            return Check("div", "Dividend record", rule, f"{streak}/{n} yrs unbroken (Screener payout)", FAIL,
                         f"No dividend in {', '.join(str(i) for i in p.index[p <= 0])} (Screener payout %).")
        return _short_dividend_record(rule, p.index, n, "Screener's payout history",
                                      "Screener only shows about 12 years")
    return Check("div", "Dividend record", rule, "—", NO_DATA, "No dividend data.")


def _short_dividend_record(rule: str, idx, n: int, src: str, why_short: str) -> Check:
    """Unbroken record that is shorter than 20 years: PARTIAL from 3 years, NO DATA below that."""
    span = f"{idx[0]} – {idx[-1]}" if n > 1 else str(idx[0])
    value = f"{n}/{n} FYs paid ({span})"
    if n < MIN_PARTIAL_YEARS:
        return Check("div", "Dividend record", rule, value, NO_DATA, f"Only {n} year(s) in {src} — too short to judge.")
    return Check("div", "Dividend record", rule, value, PARTIAL,
                 f"Paid every year in {src}, but that covers only {n} of the {DEF_DIVIDEND_YEARS} years Graham "
                 f"asks for ({DEF_DIVIDEND_YEARS - n} short) — {why_short}. Not counted as a pass.")


def _current_dividend(div_fy: pd.Series, payout: pd.Series) -> bool | None:
    p = payout.dropna() if payout is not None else pd.Series(dtype=float)
    if len(p):
        return bool(p.iloc[-1] > 0)
    if div_fy is not None and len(div_fy.dropna()):
        return bool(div_fy.fillna(0).iloc[-1] > 0)
    return None


# Graham's minimum pace: +1/3 over ~10 years ~= 2.9% a year compounded
GRAHAM_GROWTH_PACE = (1 + DEF_GROWTH_MIN) ** (1 / DEF_STABLE_YEARS) - 1
MIN_GROWTH_YEARS = 4


def _short_growth(window: pd.Series, profit: pd.Series) -> tuple[str, str, str]:
    """Fewer than 10 years of EPS: measure growth over what exists and compare its yearly pace with
    Graham's (+1/3 in ten years ~= 2.9%/yr). 6-9 years -> 3-year averages at both ends; 4-5 years ->
    first vs last year. On or above pace -> PARTIAL, below pace or loss-making start -> FAIL."""
    n = len(window)
    if n < MIN_GROWTH_YEARS:
        return NO_DATA, f"{n} yrs of EPS", f"Needs at least {MIN_GROWTH_YEARS} years to measure growth."
    if n >= 6:
        start, end, gap = float(window.head(3).mean()), float(window.tail(3).mean()), n - 3
        how = f"3-yr averages {window.index[0]}–{window.index[2]} → {window.index[-3]}–{window.index[-1]}"
        pw = profit.reindex(window.index).dropna()
        p0, p1 = (pw.head(3).mean(), pw.tail(3).mean()) if len(pw) == n else (np.nan, np.nan)
    else:
        start, end, gap = float(window.iloc[0]), float(window.iloc[-1]), n - 1
        how = f"{window.index[0]} → {window.index[-1]} (too short for 3-yr averages)"
        pw = profit.reindex(window.index).dropna()
        p0, p1 = (pw.iloc[0], pw.iloc[-1]) if len(pw) == n else (np.nan, np.nan)
    np_txt = f" Net profit on the same basis: {(p1 / p0 - 1) * 100:+.0f}%." if not _nan(p0) and p0 > 0 else ""
    short = f"Only {n} of {DEF_STABLE_YEARS} years available."
    if start <= 0:
        return FAIL, f"EPS {fmt(start, 1)} → {fmt(end, 1)}", f"{short} Starting EPS ≤ 0. {how}.{np_txt}"
    total = end / start - 1
    pace = (end / start) ** (1 / gap) - 1 if end > 0 else -1.0
    value = f"{total * 100:+.0f}% over {gap} yrs ({pace * 100:+.1f}%/yr)"
    need = f"Graham's minimum pace of {GRAHAM_GROWTH_PACE * 100:.1f}%/yr (+⅓ in 10 years)"
    if pace >= GRAHAM_GROWTH_PACE:
        return PARTIAL, value, f"{short} On or above {need}. {how}.{np_txt} Not counted as a pass."
    return FAIL, value, f"{short} Below {need}. {how}.{np_txt}"


def cpi_floor(labels) -> tuple[float, str, bool]:
    """Optional inflation floor for test 5 (an Indian adaptation, not Graham's rule).

    Builds a CPI index over the same financial years as the EPS window (index = 1 at the first year,
    then compounded with each later year's annual-average CPI inflation from CPI_FY_PCT) and returns
    avg index of the last 3 years / avg index of the first 3 years, i.e. the rise in consumer prices
    between the two 3-year windows that Graham compares.
    Returns (floor ratio or NaN, explanation, uses_approximate_year)."""
    labs = [str(x) for x in labels]
    if len(labs) < 6:
        return np.nan, "window too short for two 3-year averages", False
    years = []
    for lab in labs:
        mon, _, yr = lab.partition(" ")
        if mon != "Mar" or not yr.isdigit():
            return np.nan, f"year-end {lab} is not March, so the RBI financial-year CPI series doesn't line up", False
        years.append(int(yr))
    if any(b - a != 1 for a, b in zip(years, years[1:])):
        return np.nan, "the EPS record has a gap year, so the CPI years can't be matched", False
    level, idx = 1.0, [1.0]
    for lab in labs[1:]:
        r = CPI_FY_PCT.get(lab)
        if r is None:
            return np.nan, f"no CPI figure stored for FY ending {lab}", False
        level *= 1 + r / 100
        idx.append(level)
    floor = float(np.mean(idx[-3:]) / np.mean(idx[:3]))
    approx = any(lab in CPI_APPROX_LABELS for lab in labs[1:])
    return floor, f"CPI {labs[0]}–{labs[2]} → {labs[-3]}–{labs[-1]}", approx


def _ten_year_growth(eps: pd.Series, profit: pd.Series, use_floor: bool = False) -> tuple[str, str, str]:
    """Graham: at least one-third growth in EPS over ten years, using 3-year averages at each end.
    Uses up to the last 12 FYs (so the averages are centred ~10 years apart); needs at least 10,
    otherwise the shorter record is assessed against Graham's yearly pace (PARTIAL / FAIL).
    use_floor (optional Indian adaptation): the bar becomes max(1/3, CPI floor) for the same years."""
    window = eps.tail(12)
    if len(window) < DEF_STABLE_YEARS:
        status, value, note = _short_growth(window, profit)
        if use_floor:
            note += " (Inflation floor applies only when the full 10-year record exists.)"
        return status, value, note
    start, end = float(window.head(3).mean()), float(window.tail(3).mean())
    np_txt = ""
    pw = profit.reindex(window.index).dropna()
    if len(pw) >= DEF_STABLE_YEARS:
        p0, p1 = pw.head(3).mean(), pw.tail(3).mean()
        if p0 > 0:
            np_txt = f"Net profit on the same basis: {(p1 / p0 - 1) * 100:+.0f}%."
    span = f"{window.index[0]}–{window.index[2]} → {window.index[-3]}–{window.index[-1]}"
    if start <= 0:
        return FAIL, f"EPS avg {fmt(start, 1)} → {fmt(end, 1)}", \
            f"Starting average ≤ 0, so one-third growth can't be shown. {span}. {np_txt}".strip()
    growth = end / start - 1
    need = DEF_GROWTH_MIN
    floor_txt = ""
    if use_floor:
        fl, how, approx = cpi_floor(window.index)
        if _nan(fl):
            floor_txt = f" Inflation floor not applied: {how}; Graham's ⅓ used."
        else:
            need = max(DEF_GROWTH_MIN, fl - 1)
            floor_txt = (f" Inflation floor: consumer prices rose {(fl - 1) * 100:+.0f}% ({how}, RBI CPI); "
                         f"bar = {need * 100:+.0f}%.")
            if approx:
                floor_txt += " FY2025-26 CPI is approximate (RBI base change)."
    return (PASS if growth >= need else FAIL), f"{growth * 100:+.0f}%", f"{span}. {np_txt}{floor_txt}".strip()


def _growth_rate(eps: pd.Series) -> float:
    """g for the growth formula: CAGR between the first and last 3-year EPS averages of up to
    the last 10 years, floored at 0 and capped at GROWTH_CAP. NaN when it can't be computed."""
    window = eps.dropna().tail(10)
    if len(window) < 6:
        return np.nan
    start, end = window.head(3).mean(), window.tail(3).mean()
    years = len(window) - 3
    if start <= 0 or end <= 0:
        return 0.0  # growth off a loss base is undefined: value the company as a no-growth business
    g = (end / start) ** (1 / years) - 1
    return float(min(max(g, 0.0), GROWTH_CAP))


# ----------------------------------------------------------------------------
# Market-level asset allocation (Ch. 4) - not a stock test
# ----------------------------------------------------------------------------
def allocation_band(index_pe: float, bond_yield: float) -> tuple[str, str, float]:
    """Graham's 25-75% equity band. Compares the index earnings yield with the bond yield.
    Thresholds (EY/Y < 1 -> 25:75, 1-1.5 -> 50:50, >= 1.5 -> 75:25) are this app's reading of
    Graham's guidance, not numbers from the book."""
    if _nan(index_pe) or index_pe <= 0 or _nan(bond_yield) or bond_yield <= 0:
        return "—", "Enter the index P/E and the bond yield.", np.nan
    ey = 100 / index_pe
    r = ey / bond_yield
    if r < 1.0:
        return "25 : 75", f"Index earnings yield {ey:.2f}% is below the bond yield {bond_yield:.2f}% — stocks are expensive vs bonds.", ey
    if r < 1.5:
        return "50 : 50", f"Index earnings yield {ey:.2f}% vs bond yield {bond_yield:.2f}% — Graham's neutral mix.", ey
    return "75 : 25", f"Index earnings yield {ey:.2f}% is well above the bond yield {bond_yield:.2f}% — stocks are cheap vs bonds.", ey


# ----------------------------------------------------------------------------
# Assembling the balance-sheet items (Yahoo -> manual override), with a sanity check
# ----------------------------------------------------------------------------
def balance_from_sources(yahoo: dict | None, screener_bs: pd.DataFrame | None,
                         manual: dict | None = None) -> tuple[BalanceItems, list[str]]:
    """Manual values (Rs crore) win field by field; otherwise Yahoo's latest balance sheet.
    Yahoo's total assets are compared with Screener's: a gap above 35% usually means a different
    basis (standalone vs consolidated) or a units problem, and is flagged."""
    notes: list[str] = []
    y = yahoo or {}
    b = BalanceItems()
    if y:
        b = BalanceItems(
            current_assets=_num(y.get("current_assets")),
            current_liabilities=_num(y.get("current_liabilities")),
            total_liabilities=_num(y.get("total_liabilities")),
            long_term_debt=_num(y.get("long_term_debt")),
            tangible_book=_num(y.get("tangible_book")),
            total_assets=_num(y.get("total_assets")),
            period=str(y.get("period", "—")),
            source="Yahoo Finance",
        )
        ta_s = pick(screener_bs, "Total Assets").dropna() if screener_bs is not None else pd.Series(dtype=float)
        if len(ta_s) and not _nan(b.total_assets) and ta_s.iloc[-1] > 0:
            gap = abs(b.total_assets / ta_s.iloc[-1] - 1)
            if gap > 0.35:
                notes.append(f"Yahoo's total assets (₹{fmt(b.total_assets, 0)} Cr) differ from Screener's "
                             f"(₹{fmt(float(ta_s.iloc[-1]), 0)} Cr) by {gap:.0%} — probably a different "
                             "consolidated/standalone basis. Check the current-asset figures or enter them manually.")
        if _nan(b.long_term_debt):
            notes.append("Yahoo shows no long-term debt line; Screener's total Borrowings is used instead "
                         "(it includes short-term debt, so the debt test is stricter than Graham's).")
    if _nan(b.long_term_debt) and screener_bs is not None and not screener_bs.empty:
        borr = pick(screener_bs, "borrowings").dropna()
        if len(borr):
            b.long_term_debt = float(borr.iloc[-1])
    if manual:
        used = []
        for k in ("current_assets", "current_liabilities", "total_liabilities", "long_term_debt"):
            v = _num(manual.get(k))
            if _nan(v) or v < 0 or (v == 0 and k != "long_term_debt"):
                continue  # blank = keep Yahoo's value; only debt may legitimately be 0
            setattr(b, k, v)
            used.append(k)
        if used:
            b.source = "manual" if b.source == "—" else b.source + " + manual"
            b.period = b.period if b.period != "—" else "manual"
    return b, notes
