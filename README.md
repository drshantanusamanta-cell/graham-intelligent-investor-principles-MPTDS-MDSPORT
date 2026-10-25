# 📈 Wealthcon Investment Scorer

**Designed & developed by Dr. Shantanu Samanta** — Physician · Quantitative Market Analyst & Trading-Systems Developer · Kolkata, India

A Streamlit app that screens NSE/BSE companies with two complementary frameworks, using fundamentals from Screener.in and prices from Yahoo Finance. The layout adapts to desktop, tablet/iPad and phone screens.

| Framework | Question it answers | Output |
|---|---|---|
| **MDSPORT** | Is this a high-quality, growing, low-debt business? | Score /100 → VALID · WATCHLIST · REJECTED |
| **MPTDS** | Are price, tax, dividend and sales in a sustained uptrend? | VALID · INVALID |
| **Indian Intelligent Investor** | Does it pass Benjamin Graham's defensive / enterprising screens (adapted for NSE large and midcaps), and is it cheap on his formulas? | NET-NET · DEFENSIVE PASS · ENTERPRISING PASS · FAILS GRAHAM |

## Finding a company
The search box works the same way as the Forward Matrix and Fair Value apps:

- **An exact NSE symbol** in any case, with or without `.NS` (`tcs`, `HDFCBANK.NS`, `m&m`), a **BSE code** (`532540`) or a common short-form (`SBI`, `L&T`, `HUL`, `RIL`) opens the stock straight away.
- **Anything else** (a company name like `shriram`, or a typo like `relaince`) shows up to 8 likely NSE stocks as buttons, e.g. *SHRIRAMFIN · Shriram Finance Limited*. Click one to analyse it.
- Nothing similar → a hint to try the company name.

The stock list is NSE's full equity list from Dhan's public scrip master (no login or token), cached for a day. If it can't be downloaded, the app falls back to its earlier name search (Screener.in, then Yahoo Finance).

## Methodology

### MDSPORT
- **M · Market cap** – size class (Large / Mid / Small). Classification only.
- **D · Debt-to-Equity** – Non-Current Liabilities ÷ Total Equity. **D/E ≥ 0.30 is an automatic REJECT.**
- **S · P · O · R · T** – Sales growth %, PAT growth %, OPM %, ROCE %, Tax growth %. Each is graded **0–4 points for each of the last 5 financial years**:

  | Value | < 5% | 5–10% | 10–15% | 15–20% | > 20% |
  |---|---|---|---|---|---|
  | Points | 0 | 1 | 2 | 3 | 4 |

- Maximum 5 × 5 × 4 = **100**. **> 75 VALID**, **50–75 WATCHLIST**, **< 50 REJECTED**.

### MPTDS
- **M** Market cap ≥ ₹10,000 Cr · **P** FY-end (March) close · **T** Tax = PBT − PAT · **D** Dividend = PAT × Payout % · **S** Sales.
- P, T, D and S must each show a rising trend over 5–10 years: **Moderate** = average YoY growth ≥ 5% and R² ≥ 0.25; **Strict** = ≥ 10% and R² ≥ 0.55.
- **VALID** only when M and all four trends pass.

### Indian Intelligent Investor (Graham's *The Intelligent Investor*, adapted for NSE)
- **Defensive (Ch. 14), all 7 must pass:** size (market cap ≥ AMFI midcap floor, ₹34,700 Cr in the Jan-2026 list); current ratio ≥ 2 and long-term debt (including non-current lease liabilities where Yahoo reports them) ≤ net current assets; positive earnings for 10 years; 20 years of unbroken dividends; EPS up ≥ ⅓ over 10 years (3-year averages); P/E ≤ 15 on 3-year average EPS; P/B ≤ 1.5 or P/E × P/B ≤ 22.5.
- **Optional inflation floor (off by default):** test 5 then needs EPS growth ≥ max(⅓, CPI rise between the same two 3-year windows), using RBI Handbook Table 236 CPI by financial year. An addition, not Graham's rule.
- **Enterprising (Ch. 15):** current ratio ≥ 1.5 and debt ≤ 110% of net current assets; no loss in 5 years; some current dividend; EPS above 5 years ago; price < 120% of net tangible assets.
- **Valuation:** Graham Number √(22.5 × EPS × BVPS); growth formula V = EPS × (8.5 + 2g) (Ch. 11; g capped at 15% by this app); net-net = price ≤ ⅔ of NCAV per share; earnings yield vs Y (10Y G-Sec + optional AAA spread); optional 25–75% stock/bond band from the NIFTY P/E.
- Tests with too little history show **NO DATA** and never count as a pass.
- **Banks / NBFCs / insurers:** financial-condition and net-net tests are **N/A** (no current/non-current split). A pass shows as **DEFENSIVE PASS\*** in amber because Graham's balance-sheet test couldn't be run. Detected from Screener's financing labels or a Deposits row, or set manually under *Advanced options*.
- Each change from Graham's rules, and the reason for it, is shown in the app's Indian Intelligent Investor tab and Method tab.
- Data: EPS, payout and book value from Screener; latest balance sheet (current assets/liabilities, total liabilities, long-term debt, tangible book) and dividend history from Yahoo Finance. A >35% gap between Yahoo's and Screener's total assets is flagged. Balance-sheet figures can be entered manually under *Advanced options*.

### Implementation notes
- Growth off a zero or negative base is undefined: it scores 0 (MDSPORT) or is skipped (MPTDS average) rather than producing infinite values.
- Exactly 20% scores 3 points; more than 20% is needed for 4.
- Screener's summary balance sheet doesn't separate non-current liabilities, so D/E uses **Borrowings ÷ (Equity capital + Reserves)** as a proxy. Enter the exact NCL-based figure under *Advanced options* when you have it.
- Prices are split-adjusted closes on the last trading day on or before each year-end. Missing years stay blank — they are never back- or forward-filled.
- Banks/NBFCs don't report OPM/ROCE the same way, so MDSPORT under-scores them by design.

## Project layout
```
app.py             Streamlit UI (responsive layout, charts, author credits)
engine.py          MDSPORT / MPTDS rules — pure functions, no network
graham.py          Graham defensive / enterprising screens and valuation — pure functions
data_sources.py    Screener.in parser + Yahoo Finance prices, balance sheet and dividends
tests/             Offline unit tests + headless UI smoke tests
.streamlit/        Theme
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test
```bash
pip install pytest
pytest -q
```
Tests run fully offline (network calls are mocked).

## Data sources & fair use
Fundamentals are read from public Screener.in company pages and prices from Yahoo Finance via `yfinance`. Results are cached for an hour to keep requests light. Please respect both sites' terms of use.

## Disclaimer
For education and research only — not investment advice or a recommendation to buy or sell any security. Data from third-party sources may be delayed, incomplete or revised. Verify independently and consult a SEBI-registered investment adviser before investing.

© 2026 Dr. Shantanu Samanta. All rights reserved.
