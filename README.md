# Macro Regimes & US Sector Rotation

**Question:** How do US equity sectors perform under different macroeconomic regimes —
rising vs. falling rates, high vs. low inflation, inverted vs. normal yield curve —
and can a simple regime-based sector rotation beat buy-and-hold?

## Data

| Source | Content | Frequency | Since |
|---|---|---|---|
| Yahoo Finance | 11 SPDR sector ETFs (XLK, XLF, XLE, ...) + SPY benchmark, dividend-adjusted | Daily | 1999 (XLRE 2015, XLC 2018) |
| FRED (St. Louis Fed) | Fed funds rate, CPI, core PCE, unemployment, industrial production, 10Y-2Y spread, NBER recessions | Monthly / daily | 1999 |

All data is stored in a local **SQLite** database (`data/market.db`) with a normalised schema
(`assets`, `prices`, `series_meta`, `macro`, `ingest_log`). Ingestion is idempotent, so it can be re-run safely to refresh data.

## Roadmap

- [x] **1. Data layer** — ingestion pipeline, SQLite schema, SQL data-quality checks
- [x] **2. Analysis layer** — look-ahead-safe macro regimes; sector excess returns, volatility, hit rates and t-stats per regime
- [x] **3. Strategy layer** — walk-forward regime rotation backtest vs. SPY, equal-weight and an in-sample (look-ahead) control
- [x] **4. Presentation** — interactive Streamlit dashboard
- [ ] Written report

## Key findings (2000-2026)

| Strategy (Mar 2005 – Sep 2026) | CAGR | Sharpe | Max drawdown | $1 grows to |
|---|---|---|---|---|
| SPY buy & hold | 10.9% | 0.65 | −50.8% | $9.39 |
| Equal-weight sectors | 10.0% | 0.60 | −49.1% | $7.76 |
| **Regime rotation (walk-forward)** | **8.9%** | **0.49** | −48.2% | **$6.25** |
| Regime rotation (in-sample, look-ahead) | 12.7% | 0.70 | −46.9% | $13.18 |

1. **An honest regime rotation does not beat SPY.** It trails by ~2 points a year, mainly by over-weighting energy, which trailed SPY by ~17% a year in 2014-2020.
2. **Look-ahead bias is worth ~3.8 points a year.** The identical strategy "beats" SPY once it may use future data.
3. **Few regime effects survive scrutiny.** Only 1 of 77 sector-regime tests reaches |t| ≥ 2, roughly what chance alone would produce.
4. **Apparent patterns trace back to single episodes.** Tech's strength in high inflation comes from the 2023-26 AI rally (64 of 70 high-inflation months are after 2021); financials' strength with an inverted curve comes from the 2000 dot-com rotation.
5. **Reverse causality:** SPY does worst while the Fed is cutting, because the Fed cuts in crises (2001, 2008, 2020).

## Data-quality notes

- XLRE and XLC launched in 2015 and 2018; cross-sector comparisons must account for shorter histories.
- CPI and unemployment have no October 2025 observation in FRED (not published during the US government shutdown); the analysis layer must handle this gap explicitly.
- Daily moves above 15% were reviewed and correspond to real market events (2008 GFC, March 2020), not data errors.

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
echo "YOUR_FRED_API_KEY" > fred_api_key.txt   # free key: https://fred.stlouisfed.org/docs/api/api_key.html
./venv/bin/python -m src.ingest       # download data into data/market.db
./venv/bin/python -m src.check_data   # run SQL data-quality checks
./venv/bin/python -m src.analysis     # regime statistics
./venv/bin/python -m src.backtest     # backtest summary
./venv/bin/streamlit run app.py       # interactive dashboard (or double-click run_app.command)
```

## Project structure

```
src/config.py       tickers, FRED series, paths
src/db.py           SQLite schema and upsert helpers
src/ingest.py       Yahoo Finance + FRED ingestion
src/check_data.py   runs the checks in sql/data_checks.sql
src/regimes.py      macro indicators and look-ahead-safe regime labels
src/analysis.py     sector statistics by regime
src/backtest.py     walk-forward rotation backtest and performance metrics
app.py              Streamlit dashboard
sql/                SQL queries (monthly returns, data checks)
```
