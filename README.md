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
- [ ] **2. Analysis layer** — define macro regimes; sector returns, volatility and hit rates per regime; significance tests
- [ ] **3. Strategy layer** — regime-based rotation backtest vs. SPY (CAGR, Sharpe, max drawdown)
- [ ] **4. Presentation** — Streamlit dashboard + written report

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
```

## Project structure

```
src/config.py       tickers, FRED series, paths
src/db.py           SQLite schema and upsert helpers
src/ingest.py       Yahoo Finance + FRED ingestion
src/check_data.py   runs the checks in sql/data_checks.sql
sql/                SQL queries
```
