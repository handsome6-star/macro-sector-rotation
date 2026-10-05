"""Backtest a macro-regime sector rotation against SPY and an equal-weight sector portfolio.

Each month t:
  1. read month t's regime labels (already lagged in regimes.py, so no look-ahead)
  2. score each sector = sum over the regime dimensions of its average excess return vs SPY
     in the current regime, using history before month t only (walk-forward)
  3. hold the TOP_N highest-scoring sectors, equal weight, during month t
     (if no sector has enough history in the current regimes, hold SPY instead)

The same strategy is also run "in-sample" (scores computed from the full history) to show
how much look-ahead bias inflates backtest results.

Usage:
    python -m src.backtest
"""

import numpy as np
import pandas as pd

from src import db
from src.analysis import OUTPUT_DIR, REGIME_DIMENSIONS, load_monthly_returns
from src.config import BENCHMARK, SECTOR_ETFS
from src.regimes import build_indicators, label_regimes, load_series

TOP_N = 3
MIN_HISTORY_MONTHS = 60      # history required before the strategy starts trading
MIN_REGIME_MONTHS = 12       # a sector needs this many months in a regime to be scored
COST_PER_TURNOVER = 0.001    # 0.1% cost per 100% of the portfolio traded

SECTORS = list(SECTOR_ETFS)
ASSETS = SECTORS + [BENCHMARK]


def sector_scores(excess_hist: pd.DataFrame, regimes_hist: pd.DataFrame, current: pd.Series) -> pd.Series:
    """Sum of each sector's average excess return in the current regime of every dimension."""
    score = pd.Series(0.0, index=excess_hist.columns)
    for dim in REGIME_DIMENSIONS:
        same_regime = excess_hist.loc[regimes_hist[dim] == current[dim]]
        enough = same_regime.count() >= MIN_REGIME_MONTHS
        score += same_regime.mean().where(enough)  # NaN if too little history -> sector not eligible
    return score


def run_rotation(returns: pd.DataFrame, regimes: pd.DataFrame, in_sample: bool) -> pd.DataFrame:
    excess = returns[SECTORS].sub(returns[BENCHMARK], axis=0)
    months = regimes.index
    prev_weights = pd.Series(0.0, index=ASSETS)
    rows = []

    for i in range(MIN_HISTORY_MONTHS, len(months)):
        t = months[i]
        hist = months if in_sample else months[:i]   # walk-forward: only months before t
        score = sector_scores(excess.loc[hist], regimes.loc[hist], regimes.loc[t])
        tradable = returns.loc[t, SECTORS].notna()  # the ETF existed at the start of month t
        picks = list(score[tradable].dropna().nlargest(TOP_N).index) or [BENCHMARK]

        weights = pd.Series(0.0, index=ASSETS)
        weights[picks] = 1 / len(picks)
        turnover = (weights - prev_weights).abs().sum()
        gross = (weights * returns.loc[t, ASSETS].fillna(0)).sum()
        rows.append({"month": t, "ret": gross - COST_PER_TURNOVER * turnover,
                     "turnover": turnover, "picks": ",".join(picks)})
        prev_weights = weights

    return pd.DataFrame(rows).set_index("month")


def performance(r: pd.Series, rf: pd.Series, spy: pd.Series) -> dict:
    growth = (1 + r).cumprod()
    years = len(r) / 12
    vol = r.std() * np.sqrt(12)
    drawdown = growth / growth.cummax() - 1
    return {
        "CAGR %": (growth.iloc[-1] ** (1 / years) - 1) * 100,
        "Volatility %": vol * 100,
        "Sharpe": (r - rf).mean() * 12 / vol,
        "Max drawdown %": drawdown.min() * 100,
        "Beat SPY months %": (r > spy).mean() * 100,
        "Growth of $1": growth.iloc[-1],
    }


def run_backtest(conn) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (monthly returns per strategy, walk-forward picks, performance table)."""
    returns = load_monthly_returns(conn)
    regimes = label_regimes(build_indicators(conn))
    fed_funds = load_series(conn, "FEDFUNDS").to_period("M")
    regimes = regimes.loc[regimes.index.intersection(returns.index)].dropna(subset=REGIME_DIMENSIONS)

    walk_forward = run_rotation(returns, regimes, in_sample=False)
    in_sample = run_rotation(returns, regimes, in_sample=True)
    months = walk_forward.index

    strategies = pd.DataFrame({
        "SPY buy & hold": returns.loc[months, BENCHMARK],
        "Equal-weight sectors": returns.loc[months, SECTORS].mean(axis=1),
        "Rotation (walk-forward)": walk_forward["ret"],
        "Rotation (in-sample, cheating)": in_sample["ret"],
    })
    rf = (fed_funds.reindex(months).ffill() / 100 / 12)  # risk-free rate proxy, monthly
    table = pd.DataFrame({name: performance(r, rf, strategies["SPY buy & hold"])
                          for name, r in strategies.items()}).T
    table.loc["SPY buy & hold", "Beat SPY months %"] = np.nan  # comparing SPY with itself is meaningless
    return strategies, walk_forward, table


def main() -> None:
    conn = db.connect()
    strategies, walk_forward, table = run_backtest(conn)
    conn.close()
    months = strategies.index

    print(f"Backtest window: {months.min()} -> {months.max()}  ({len(months)} months)\n")
    print(table.round(2).to_string(na_rep="-"))

    fallback = (walk_forward["picks"] == BENCHMARK).sum()
    print(f"\nWalk-forward: average monthly turnover {walk_forward['turnover'].mean() * 100:.0f}%, "
          f"held SPY (no eligible sector) in {fallback} of {len(walk_forward)} months")
    picked = walk_forward["picks"].str.split(",").explode().value_counts()
    share = (picked / len(walk_forward) * 100).round(0).astype(int).astype(str) + "%"
    print("How often each sector was held (walk-forward):")
    print("  " + ", ".join(f"{t} {s}" for t, s in share.items()))

    OUTPUT_DIR.mkdir(exist_ok=True)
    strategies.to_csv(OUTPUT_DIR / "backtest_returns.csv")
    walk_forward.to_csv(OUTPUT_DIR / "backtest_walk_forward_picks.csv")
    table.to_csv(OUTPUT_DIR / "backtest_summary.csv")
    print(f"\nSaved: {OUTPUT_DIR / 'backtest_summary.csv'} and related files")


if __name__ == "__main__":
    main()
