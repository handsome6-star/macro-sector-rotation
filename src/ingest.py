"""Download sector ETF prices (Yahoo Finance) and macro series (FRED) into SQLite.

Usage:
    python -m src.ingest
"""

import pandas as pd
import yfinance as yf
from fredapi import Fred

from src import db
from src.config import BENCHMARK, FRED_KEY_PATH, MACRO_SERIES, SECTOR_ETFS, START_DATE


def load_assets(conn) -> None:
    rows = [(t, name, "sector") for t, name in SECTOR_ETFS.items()]
    rows.append((BENCHMARK, "S&P 500 (SPDR)", "benchmark"))
    db.upsert(conn, "assets", rows)


def load_prices(conn) -> None:
    for ticker in [*SECTOR_ETFS, BENCHMARK]:
        try:
            # auto_adjust=True folds splits and dividends into Close,
            # so returns computed from it are total returns.
            hist = yf.Ticker(ticker).history(start=START_DATE, auto_adjust=True)
            hist = hist.dropna(subset=["Close"])
            if hist.empty:
                raise ValueError("no data returned")
            rows = [
                (idx.strftime("%Y-%m-%d"), ticker, float(r.Close), int(r.Volume))
                for idx, r in hist.iterrows()
            ]
            n = db.upsert(conn, "prices", rows)
            db.log_run(conn, "yfinance", ticker, n, "ok")
            print(f"  {ticker:<5} {n:>6} rows  {rows[0][0]} -> {rows[-1][0]}")
        except Exception as e:
            db.log_run(conn, "yfinance", ticker, 0, "error", str(e))
            print(f"  {ticker:<5} FAILED: {e}")


def load_macro(conn) -> None:
    fred = Fred(api_key=FRED_KEY_PATH.read_text().strip())
    meta = [(sid, name, freq, units) for sid, (name, freq, units) in MACRO_SERIES.items()]
    db.upsert(conn, "series_meta", meta)

    for series_id in MACRO_SERIES:
        try:
            s = fred.get_series(series_id, observation_start=START_DATE).dropna()
            rows = [(d.strftime("%Y-%m-%d"), series_id, float(v)) for d, v in s.items()]
            n = db.upsert(conn, "macro", rows)
            db.log_run(conn, "fred", series_id, n, "ok")
            print(f"  {series_id:<9} {n:>6} rows  {rows[0][0]} -> {rows[-1][0]}")
        except Exception as e:
            db.log_run(conn, "fred", series_id, 0, "error", str(e))
            print(f"  {series_id:<9} FAILED: {e}")


def main() -> None:
    if not FRED_KEY_PATH.exists():
        raise SystemExit(f"Missing FRED API key file: {FRED_KEY_PATH}")

    conn = db.connect()
    with conn:  # commits on success, rolls back on exception
        db.init_schema(conn)
        load_assets(conn)
        print("Prices (Yahoo Finance):")
        load_prices(conn)
        print("Macro series (FRED):")
        load_macro(conn)
    conn.close()


if __name__ == "__main__":
    main()
