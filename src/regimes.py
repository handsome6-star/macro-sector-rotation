"""Label each month with its macro regime, using only data available at the time.

Decision timing: at the end of month t-1 we decide what to hold during month t,
so the label for month t may only use data that was public by then.
- Fed funds rate and the 10Y-2Y spread are market rates, known in real time -> lag 1 month
- Core PCE for month m is published near the end of month m+1             -> lag 2 months
"""

import numpy as np
import pandas as pd

RATE_STEP = 0.25            # one standard Fed move, in percentage points
RATE_LOOKBACK_MONTHS = 6
INFLATION_THRESHOLD = 2.5   # core PCE YoY, percent


def load_series(conn, series_id: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, value FROM macro WHERE series_id = ? ORDER BY date",
        conn, params=(series_id,), parse_dates=["date"],
    )
    return df.set_index("date")["value"]


def build_indicators(conn) -> pd.DataFrame:
    """Monthly macro indicators as of each calendar month (not yet lagged)."""
    fed = load_series(conn, "FEDFUNDS").to_period("M")
    pce = load_series(conn, "PCEPILFE").to_period("M")
    spread = load_series(conn, "T10Y2Y")
    recession = load_series(conn, "USREC").to_period("M")

    ind = pd.DataFrame({
        "fed_funds": fed,
        "fed_change_6m": fed - fed.shift(RATE_LOOKBACK_MONTHS),
        "core_pce_yoy": (pce / pce.shift(12) - 1) * 100,
        # monthly average describes the month's state, unlike returns which use month-end
        "spread_10y2y": spread.resample("MS").mean().to_period("M"),
        "recession": recession,
    })
    # a continuous monthly index makes shift(n) mean "n months earlier"
    full_range = pd.period_range(ind.index.min(), ind.index.max(), freq="M")
    return ind.reindex(full_range)


def label_regimes(ind: pd.DataFrame) -> pd.DataFrame:
    """Regime labels for each month, built only from information known at decision time."""
    known = pd.DataFrame({
        "fed_change_6m": ind["fed_change_6m"].shift(1).round(2),
        "spread_10y2y": ind["spread_10y2y"].shift(1),
        "core_pce_yoy": ind["core_pce_yoy"].shift(2),
    })

    fed = known["fed_change_6m"]
    known["rate_regime"] = np.select(
        [fed >= RATE_STEP, fed <= -RATE_STEP, fed.notna()],
        ["hiking", "cutting", "hold"],
        default=None,
    )
    known["inflation_regime"] = np.select(
        [known["core_pce_yoy"] > INFLATION_THRESHOLD, known["core_pce_yoy"].notna()],
        ["high", "low"],
        default=None,
    )
    known["curve_regime"] = np.select(
        [known["spread_10y2y"] < 0, known["spread_10y2y"].notna()],
        ["inverted", "normal"],
        default=None,
    )
    return known
