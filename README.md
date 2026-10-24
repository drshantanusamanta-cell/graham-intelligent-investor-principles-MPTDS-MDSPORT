# 📈 Wealthcon Investment Scorer

**Designed & developed by Dr. Shantanu Samanta** — Physician · Quantitative Market Analyst & Trading-Systems Developer · Kolkata, India

A Streamlit app that screens NSE/BSE companies with two complementary frameworks, using fundamentals from Screener.in and prices from Yahoo Finance. The layout adapts to desktop, tablet/iPad and phone screens.

| Framework | Question it answers | Output |
|---|---|---|
| **MDSPORT** | Is this a high-quality, growing, low-debt business? | Score /100 → VALID · WATCHLIST · REJECTED |
| **MPTDS** | Are price, tax, dividend and sales in a sustained uptrend? | VALID · INVALID |
| **Graham** | Does it pass Benjamin Graham's defensive / enterprising screens, and is it cheap on his formulas? | NET-NET · DEFENSIVE PASS · ENTERPRISING PASS · FAILS GRAHAM |

## Finding a company
Type either a ticker (`TCS`, `SHRIRAMFIN`, a BSE code) **or just the company's name** (`Shriram Finance`, `asian paints`, `sbi`). Names are converted to the NSE symbol automatically:

1. a built-in list of common short-forms (SBI, L&T, HUL, RIL, M&M…),
2. Screener.in's company search,
3. Yahoo Finance search as a fallback.

The best match is used straight away and shown above the results; when several companies match, a *"Not the right company?"* picker lets you switch.

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

### Graham (*The Intelligent Investor*)
- **Defensive (Ch. 14), all 7 must pass:** size; current ratio ≥ 2 and long-term debt ≤ net current assets; positive earnings for 10 years; 20 years of unbroken dividends; EPS up ≥ ⅓ over 10 years (3-year averages); P/E ≤ 15 on 3-year average EPS; P/B ≤ 1.5 or P/E × P/B ≤ 22.5.
- **Enterprising (Ch. 15):** current ratio ≥ 1.5 and debt ≤ 110% of net current assets; no loss in 5 years; some current dividend; EPS above 5 years ago; price < 120% of net tangible assets.
- **Valuation:** Graham Number √(22.5 × EPS × BVPS); growth formula EPS × (8.5 + 2g) × 4.4 ÷ Y (g capped at 15%, Y = 10Y G-Sec + optional AAA spread); net-net = price ≤ ⅔ of NCAV per share; earnings yield vs Y; optional 25–75% stock/bond band from the NIFTY P/E.
- Tests with too little history show **NO DATA** and never count as a pass. Current-ratio and NCAV tests are **N/A** for banks/NBFCs.
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
