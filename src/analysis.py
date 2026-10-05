"""Sector performance by macro regime: average return, excess return vs SPY,
volatility, hit rate and t-statistic for each sector in each regime.

Usage:
    python -m src.analysis
"""

import numpy as np
import pandas as pd

from src import db
from src.config import BENCHMARK, ROOT, SECTOR_ETFS
from src.regimes import build_indicators, label_regimes

MONTHLY_RETURNS_SQL = ROOT / "sql" / "monthly_returns.sql"
OUTPUT_DIR = ROOT / "output"
REGIME_DIMENSIONS = ["rate_regime", "inflation_regime", "curve_regime"]
T_STAT_THRESHOLD = 2.0  # roughly 5% significance


def load_monthly_returns(conn) -> pd.DataFrame:
    """Wide table: one row per month, one column per ticker."""
    df = pd.read_sql_query(MONTHLY_RETURNS_SQL.read_text(), conn)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    # the current calendar month is still in progress, so its return is incomplete
    df = df[df["month"] < pd.Period.now("M")].dropna(subset=["ret"])
    return df.pivot(index="month", columns="ticker", values="ret")


def regime_stats(returns: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
    excess = returns[list(SECTOR_ETFS)].sub(returns[BENCHMARK], axis=0)
    rows = []
    for regime in labels.dropna().unique():
        months = labels.index[labels == regime]
        for ticker, sector in SECTOR_ETFS.items():
            ex = excess.loc[excess.index.intersection(months), ticker].dropna()
            n = len(ex)
            if n < 2:
                continue
            raw = returns.loc[ex.index, ticker]
            rows.append({
                "regime": regime,
                "ticker": ticker,
                "sector": sector,
                "months": n,
                "avg_return_pct": raw.mean() * 100,
                "avg_excess_pct": ex.mean() * 100,
                "ann_vol_pct": raw.std() * np.sqrt(12) * 100,
                "hit_rate_pct": (ex > 0).mean() * 100,
                "t_stat": ex.mean() / (ex.std() / np.sqrt(n)),
            })
    return pd.DataFrame(rows)


def print_summary(dimension: str, stats: pd.DataFrame, returns: pd.DataFrame, labels: pd.Series) -> None:
    """Sector x regime table of average monthly excess return; * marks |t| >= 2."""
    print(f"\n{'=' * 78}\n{dimension}: average monthly excess return vs SPY (%)   * = |t| >= {T_STAT_THRESHOLD}\n{'=' * 78}")

    cell = stats.apply(
        lambda r: f"{r.avg_excess_pct:+.2f}{'*' if abs(r.t_stat) >= T_STAT_THRESHOLD else ' '}", axis=1
    )
    table = stats.assign(cell=cell).pivot(index="sector", columns="regime", values="cell")
    print(table.to_string())

    spy = returns[BENCHMARK]
    info = []
    for regime in table.columns:
        months = labels.index[labels == regime].intersection(spy.dropna().index)
        info.append(f"{regime}: {len(months)} months, SPY avg {spy.loc[months].mean() * 100:+.2f}%/month")
    print("  " + " | ".join(info))


def save_tables(conn, returns: pd.DataFrame, regimes: pd.DataFrame) -> None:
    """Write derived tables back to SQLite so results can be explored with SQL."""
    long = returns.stack().rename("ret").reset_index()
    long["excess_ret"] = long["ret"] - long["month"].map(returns[BENCHMARK])
    long["month"] = long["month"].astype(str)
    long.to_sql("monthly_returns", conn, if_exists="replace", index=False)

    out = regimes.copy()
    out.index = out.index.astype(str)
    out.rename_axis("month").reset_index().to_sql("regimes", conn, if_exists="replace", index=False)


def main() -> None:
    conn = db.connect()
    returns = load_monthly_returns(conn)
    regimes = label_regimes(build_indicators(conn))

    # use only months where every regime label exists, so the dimensions are comparable
    regimes = regimes.loc[regimes.index.intersection(returns.index)].dropna(subset=REGIME_DIMENSIONS)
    print(f"Analysis window: {regimes.index.min()} -> {regimes.index.max()}  ({len(regimes)} months)")

    with conn:
        save_tables(conn, returns, regimes)
    conn.close()

    OUTPUT_DIR.mkdir(exist_ok=True)
    regimes.to_csv(OUTPUT_DIR / "regimes.csv")
    all_stats = []
    for dim in REGIME_DIMENSIONS:
        labels = regimes[dim]
        stats = regime_stats(returns, labels)
        print_summary(dim, stats, returns, labels)
        all_stats.append(stats.assign(dimension=dim))
    pd.concat(all_stats).to_csv(OUTPUT_DIR / "regime_stats.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'regimes.csv'}, {OUTPUT_DIR / 'regime_stats.csv'}")


if __name__ == "__main__":
    main()
