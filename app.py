"""Interactive dashboard for the macro-regime sector rotation study.

Usage:
    ./venv/bin/streamlit run app.py
"""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src import db
from src.analysis import REGIME_DIMENSIONS, load_monthly_returns, regime_stats
from src.backtest import run_backtest
from src.config import BENCHMARK, SECTOR_ETFS
from src.regimes import INFLATION_THRESHOLD, RATE_LOOKBACK_MONTHS, RATE_STEP, build_indicators, label_regimes

st.set_page_config(page_title="Macro Regimes & Sector Rotation", layout="wide")

# ---------------------------------------------------------------------------
# Palette (validated reference palette; light and dark steps chosen separately)
# ---------------------------------------------------------------------------
PALETTES = {
    "light": {
        "surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7", "mid": "#f0efec",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
        "pos": "#256abf", "neg": "#e34948",
    },
    "dark": {
        "surface": "#1a1a19", "text": "#ffffff", "text2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835", "mid": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500"],
        "pos": "#3987e5", "neg": "#e66767",
    },
}

# colour follows the entity: each strategy keeps its slot whichever chart it appears in
STRATEGIES = {
    "Rotation (walk-forward)": "Rotation",
    "SPY buy & hold": "SPY",
    "Equal-weight sectors": "Equal-weight",
    "Rotation (in-sample, cheating)": "In-sample (cheating)",
}
REGIME_ORDER = {
    "rate_regime": ["cutting", "hold", "hiking"],
    "inflation_regime": ["low", "high"],
    "curve_regime": ["normal", "inverted"],
}
DIMENSION_NAMES = {
    "rate_regime": "Fed policy (6-month change in Fed funds)",
    "inflation_regime": f"Inflation (core PCE YoY vs {INFLATION_THRESHOLD}%)",
    "curve_regime": "Yield curve (10Y-2Y spread)",
}


def theme_palette() -> dict:
    try:
        return PALETTES["dark" if st.context.theme.type == "dark" else "light"]
    except Exception:
        return PALETTES["light"]


PAL = theme_palette()


def style(chart: alt.Chart, height: int = 360, width=None) -> alt.Chart:
    """Recessive axes and grid, system sans, chart surface from the palette."""
    size = {"height": height, **({"width": width} if width else {})}
    return (
        chart.properties(**size, background=PAL["surface"])
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=PAL["muted"], titleColor=PAL["text2"], gridColor=PAL["grid"],
            domainColor=PAL["axis"], tickColor=PAL["axis"], labelFontSize=12, titleFontSize=12,
            titleFontWeight="normal", labelFont="system-ui", titleFont="system-ui",
        )
        .configure_legend(labelColor=PAL["text2"], titleColor=PAL["text2"], labelFontSize=12,
                          labelFont="system-ui", orient="top", title=None, symbolStrokeWidth=3)
    )


# ---------------------------------------------------------------------------
# Data (cached: everything is derived from the local SQLite database)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    conn = db.connect()
    returns = load_monthly_returns(conn)
    regimes = label_regimes(build_indicators(conn))
    strategies, picks, perf = run_backtest(conn)
    conn.close()
    regimes = regimes.loc[regimes.index.intersection(returns.index)].dropna(subset=REGIME_DIMENSIONS)
    stats = {dim: regime_stats(returns, regimes[dim]) for dim in REGIME_DIMENSIONS}
    return returns, regimes, strategies, picks, perf, stats


returns, regimes, strategies, picks, perf, stats = load_data()
excess = returns[list(SECTOR_ETFS)].sub(returns[BENCHMARK], axis=0)


def crosshair_lines(wide: pd.DataFrame, y_title: str, y_format: str, log: bool = False,
                    end_labels: bool = True) -> alt.Chart:
    """Multi-series line chart with a hover crosshair that lists every series at that month."""
    names = [n for n in STRATEGIES if n in wide.columns]
    keys = {n: f"s{i}" for i, n in enumerate(names)}            # plain field names for Vega
    data = wide[names].rename(columns=keys)
    data.index = data.index.to_timestamp()
    data = data.rename_axis("month").reset_index()
    long = data.melt("month", var_name="key", value_name="value")
    long["series"] = long["key"].map({v: STRATEGIES[k] for k, v in keys.items()})

    domain = list(STRATEGIES.values())
    color = alt.Color("series:N", scale=alt.Scale(domain=domain, range=PAL["series"]),
                      legend=alt.Legend(values=[STRATEGIES[n] for n in names]))
    lo, hi = long["value"].min(), long["value"].max()
    # tight domain so the gaps between lines are visible
    y_scale = alt.Scale(type="log", domain=[lo * 0.9, hi * 1.1], nice=False) if log else alt.Scale(zero=False)
    y_axis = alt.Axis(format=y_format, values=[0.5, 1, 2, 3, 5, 10, 15, 20]) if log else alt.Axis(format=y_format)
    x = alt.X("month:T", title=None,
              axis=alt.Axis(format="%Y", grid=False, tickCount={"interval": "year", "step": 2}))

    hover = alt.selection_point(nearest=True, on="pointerover", fields=["month"], empty=False, clear="pointerout")
    lines = alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=x, y=alt.Y("value:Q", title=y_title, scale=y_scale, axis=y_axis), color=color)
    dots = lines.mark_point(filled=True, size=70, stroke=PAL["surface"], strokeWidth=2).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)))
    rule = alt.Chart(data).mark_rule(color=PAL["axis"], strokeWidth=1).encode(
        x="month:T",
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y")]
        + [alt.Tooltip(f"{keys[n]}:Q", title=STRATEGIES[n], format=y_format) for n in names],
    ).add_params(hover)

    last = long[long["month"] == long["month"].max()]
    labels = alt.Chart(last).mark_text(align="left", dx=8, fontSize=12, color=PAL["text2"]).encode(
        x="month:T", y="value:Q",
        text=alt.Text("label:N"),
    ).transform_calculate(label=f"datum.series + '  ' + format(datum.value, '{y_format}')")
    layers = lines + rule + dots + labels if end_labels else lines + rule + dots
    return layers.properties(padding={"right": 170 if end_labels else 10, "left": 5, "top": 5, "bottom": 5})


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Macro Regimes & US Sector Rotation")
st.markdown(
    "**Question:** do US equity sectors behave predictably across macro regimes "
    "(Fed policy, inflation, yield curve), and can a regime-based sector rotation beat buying SPY?"
)
st.info(
    "**Answer: not reliably.** An honest walk-forward rotation trails SPY by about 2 points a year. "
    "The same strategy only 'wins' when it is allowed to peek at future data, "
    "and most apparent regime patterns trace back to one or two historical episodes."
)

wf, spy, cheat = (perf.loc[n] for n in ["Rotation (walk-forward)", "SPY buy & hold", "Rotation (in-sample, cheating)"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rotation CAGR (walk-forward)", f"{wf['CAGR %']:.1f}%", f"{wf['CAGR %'] - spy['CAGR %']:+.1f} pts vs SPY")
c2.metric("Sharpe ratio", f"{wf['Sharpe']:.2f}", f"{wf['Sharpe'] - spy['Sharpe']:+.2f} vs SPY")
c3.metric("Max drawdown", f"{wf['Max drawdown %']:.1f}%", f"SPY {spy['Max drawdown %']:.1f}%", delta_color="off")
c4.metric("Same strategy with look-ahead", f"{cheat['CAGR %']:.1f}%",
          f"{cheat['CAGR %'] - wf['CAGR %']:+.1f} pts from look-ahead bias", delta_color="inverse")

tab_bt, tab_reg, tab_drill, tab_method = st.tabs(["Backtest", "Regime analysis", "Drill-down", "Method & limitations"])

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
with tab_bt:
    start, end = strategies.index.min(), strategies.index.max()
    st.subheader(f"Growth of $1, {start.strftime('%b %Y')} to {end.strftime('%b %Y')}")
    growth = (1 + strategies).cumprod()
    growth.loc[start - 1] = 1.0
    growth = growth.sort_index()
    st.altair_chart(style(crosshair_lines(growth, "Growth of $1 (log scale)", "$.2f", log=True), 460),
                    use_container_width=True, theme=None)

    st.subheader("Drawdown from previous peak")
    dd = growth / growth.cummax() - 1
    st.altair_chart(style(crosshair_lines(dd[["Rotation (walk-forward)", "SPY buy & hold"]],
                                          "Drawdown", ".0%", end_labels=False), 280),
                    use_container_width=True, theme=None)

    st.subheader("Performance summary")
    st.dataframe(perf.round(2).astype(object).where(perf.notna(), "-"), use_container_width=True)

    latest = picks.index.max()
    lab = regimes.loc[latest]
    held = picks.loc[latest, "picks"].split(",")
    st.markdown(
        f"**Latest month ({latest.strftime('%b %Y')})** - regime: Fed *{lab['rate_regime']}*, "
        f"inflation *{lab['inflation_regime']}*, curve *{lab['curve_regime']}* → rotation held "
        + ", ".join(f"{t} ({SECTOR_ETFS.get(t, 'S&P 500')})" for t in held)
    )
    share = picks["picks"].str.split(",").explode().value_counts() / len(picks) * 100
    st.caption("Share of months each ETF was held by the walk-forward rotation: "
               + ", ".join(f"{t} {v:.0f}%" for t, v in share.items())
               + ". The heavy energy weight is why it lost: XLE trailed SPY by about 17% a year in 2014-2020.")

# ---------------------------------------------------------------------------
# Regime analysis
# ---------------------------------------------------------------------------
with tab_reg:
    dim = st.selectbox("Regime dimension", REGIME_DIMENSIONS, format_func=DIMENSION_NAMES.get)
    s = stats[dim].copy()
    s["significant"] = s["t_stat"].abs() >= 2
    m = float(np.ceil(s["avg_excess_pct"].abs().max() * 2) / 2)

    st.subheader("Average monthly excess return vs SPY, by sector and regime")
    base = alt.Chart(s).encode(
        x=alt.X("regime:N", sort=REGIME_ORDER[dim], title=None, axis=alt.Axis(orient="top", labelAngle=0)),
        y=alt.Y("sector:N", title=None, sort=sorted(SECTOR_ETFS.values())),
    )
    cells = base.mark_rect(stroke=PAL["surface"], strokeWidth=2, cornerRadius=2).encode(
        color=alt.Color("avg_excess_pct:Q", title="Excess return, % per month",
                        scale=alt.Scale(domain=[-m, 0, m], range=[PAL["neg"], PAL["mid"], PAL["pos"]], interpolate="lab"),
                        legend=alt.Legend(orient="right", format="+.1f", gradientLength=220)),
        tooltip=[
            alt.Tooltip("sector:N", title="Sector"), alt.Tooltip("regime:N", title="Regime"),
            alt.Tooltip("avg_excess_pct:Q", title="Avg excess % / month", format="+.2f"),
            alt.Tooltip("hit_rate_pct:Q", title="Months beating SPY %", format=".0f"),
            alt.Tooltip("t_stat:Q", title="t-stat", format=".2f"),
            alt.Tooltip("months:Q", title="Months of data"),
        ],
    )
    stars = base.transform_filter("datum.significant").mark_text(fontSize=16, color=PAL["text"]).encode(
        text=alt.value("*"))
    st.altair_chart(style(cells + stars, 440, width=alt.Step(170)),
                    use_container_width=False, theme=None)

    counts = regimes[dim].value_counts()
    st.caption(
        "Blue = beat SPY, red = trailed SPY. * marks |t| ≥ 2. "
        + " · ".join(f"{r}: {counts.get(r, 0)} months" for r in REGIME_ORDER[dim])
        + f". Only {int((pd.concat(stats.values())['t_stat'].abs() >= 2).sum())} of "
        f"{len(pd.concat(stats.values()))} sector-regime results reach |t| ≥ 2 - about what chance alone "
        "would produce across this many tests."
    )
    with st.expander("Table view"):
        st.dataframe(s.drop(columns="significant").round(2), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Drill-down: which years drive a sector's result in a regime?
# ---------------------------------------------------------------------------
with tab_drill:
    st.markdown("Pick a sector and a regime to see **which years** drive its excess return. "
                "Defaults show the high-inflation technology puzzle.")
    f1, f2, f3 = st.columns(3)
    sector_tickers = list(SECTOR_ETFS)
    ticker = f1.selectbox("Sector", sector_tickers, index=sector_tickers.index("XLK"),
                          format_func=lambda t: f"{t} - {SECTOR_ETFS[t]}")
    ddim = f2.selectbox("Regime dimension ", REGIME_DIMENSIONS, index=1, format_func=DIMENSION_NAMES.get)
    options = REGIME_ORDER[ddim]
    regime = f3.selectbox("Regime", options, index=len(options) - 1)

    months = regimes.index[regimes[ddim] == regime]
    ex = excess.loc[excess.index.intersection(months), ticker].dropna()
    by_year = ex.groupby(ex.index.year).agg(["sum", "mean", "count"])
    by_year.columns = ["total_pct", "avg_pct", "months"]
    by_year[["total_pct", "avg_pct"]] *= 100
    by_year = by_year.rename_axis("year").reset_index()
    by_year["direction"] = np.where(by_year["total_pct"] >= 0, "Beat SPY", "Trailed SPY")

    if by_year.empty:
        st.warning("No months of data for this combination.")
    else:
        # continuous year axis keeps the gaps visible: years with no months in this regime stay empty
        first_year, last_year = int(regimes.index.min().year), int(regimes.index.max().year)
        bars = alt.Chart(by_year).mark_bar(cornerRadiusEnd=4, size=14).encode(
            x=alt.X("year:Q", title=None, scale=alt.Scale(domain=[first_year - 0.5, last_year + 0.5], nice=False),
                    axis=alt.Axis(format="d", tickMinStep=1, grid=False)),
            y=alt.Y("total_pct:Q", title="Cumulative excess vs SPY in those months (%)"),
            color=alt.Color("direction:N", scale=alt.Scale(domain=["Beat SPY", "Trailed SPY"],
                                                           range=[PAL["pos"], PAL["neg"]])),
            tooltip=[alt.Tooltip("year:O", title="Year"), alt.Tooltip("months:Q", title="Months in regime"),
                     alt.Tooltip("total_pct:Q", title="Cumulative excess %", format="+.2f"),
                     alt.Tooltip("avg_pct:Q", title="Avg excess % / month", format="+.2f")],
        )
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=PAL["axis"]).encode(y="y:Q")
        st.altair_chart(style(zero + bars, 340), use_container_width=True, theme=None)

        best = by_year.loc[by_year["total_pct"].idxmax()]
        rest = ex[ex.index.year != best["year"]]
        st.markdown(
            f"**{ticker} in {regime} months:** {len(ex)} months, average excess "
            f"**{ex.mean() * 100:+.2f}%** per month. Excluding its best year ({int(best['year'])}), "
            f"the average is **{rest.mean() * 100:+.2f}%** over {len(rest)} months."
            if len(rest) else f"**{ticker} in {regime} months:** all {len(ex)} months fall in one year."
        )
        with st.expander("Table view"):
            st.dataframe(by_year.drop(columns="direction").round(2), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Method & limitations
# ---------------------------------------------------------------------------
with tab_method:
    st.markdown(f"""
**Data.** Daily dividend-adjusted closes for the 11 SPDR sector ETFs and SPY (Yahoo Finance, from 1999;
XLRE from 2015, XLC from 2018) and macro series from FRED, stored in SQLite. Monthly returns use
month-end prices so that they compound to the true holding-period return.

**Regimes** (one label per month, per dimension):
- *Fed policy:* Fed funds rate vs {RATE_LOOKBACK_MONTHS} months earlier: ≥ +{RATE_STEP} pts hiking,
  ≤ −{RATE_STEP} pts cutting, otherwise hold.
- *Inflation:* core PCE year-on-year above {INFLATION_THRESHOLD}% is high, otherwise low.
- *Yield curve:* monthly average 10Y−2Y spread below zero is inverted.

**No look-ahead.** Month *t* is labelled with data public by the end of month *t−1*: rates and spreads
lag one month, core PCE lags two months because of its publication delay.

**Backtest.** Each month, every sector is scored by the sum of its historical average excess return in
the current regime of each dimension, using only earlier months (walk-forward, 60-month warm-up,
≥ 12 months per regime). The top 3 are held equally weighted, with a 0.1% cost per unit of turnover.
If no sector qualifies, the strategy holds SPY. Sharpe ratios use the Fed funds rate as the risk-free rate.

**Limitations.**
- *Reverse causality:* SPY's weakest regime is "cutting" because the Fed cuts in crises (2001, 2008, 2020),
  not because cuts hurt stocks.
- *Multiple testing:* 77 sector-regime tests at 5% would produce about 4 "significant" results by chance.
- *Few episodes:* 64 of 70 high-inflation months fall after 2021, so that regime is effectively one episode
  (and it coincides with the AI rally).
- *One-off events:* financials' strength in inverted-curve months comes almost entirely from the 2000
  dot-com rotation; excluding 2000 they trailed SPY.
- No taxes or bid-ask spreads beyond the flat cost; SPDR ETFs stand in for sector exposure.
""")
