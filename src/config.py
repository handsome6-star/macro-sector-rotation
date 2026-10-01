"""Project-wide settings: which assets and macro series to track, and where data lives."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "market.db"
FRED_KEY_PATH = ROOT / "fred_api_key.txt"

# Most SPDR sector ETFs launched in Dec 1998, so 1999 gives ~25 years of history.
START_DATE = "1999-01-01"

BENCHMARK = "SPY"

# The 11 GICS sectors, tracked via SPDR Select Sector ETFs.
# XLRE (2015) and XLC (2018) have shorter histories - analysis must handle that.
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

# FRED series used to describe the macro regime.
# series_id: (name, frequency, units)
MACRO_SERIES = {
    "FEDFUNDS": ("Effective Federal Funds Rate", "monthly", "percent"),
    "CPIAUCSL": ("CPI, All Urban Consumers", "monthly", "index"),
    "PCEPILFE": ("Core PCE Price Index", "monthly", "index"),
    "UNRATE": ("Unemployment Rate", "monthly", "percent"),
    "INDPRO": ("Industrial Production Index", "monthly", "index"),
    "T10Y2Y": ("10Y minus 2Y Treasury Spread", "daily", "percent"),
    "USREC": ("NBER Recession Indicator", "monthly", "binary"),
}
