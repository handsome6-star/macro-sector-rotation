"""SQLite storage layer: schema creation and idempotent upserts."""

import sqlite3
from datetime import datetime

from src.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    ticker      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    asset_type  TEXT NOT NULL            -- 'sector' or 'benchmark'
);

CREATE TABLE IF NOT EXISTS prices (
    date        TEXT NOT NULL,           -- ISO format YYYY-MM-DD
    ticker      TEXT NOT NULL REFERENCES assets(ticker),
    adj_close   REAL NOT NULL,           -- split- and dividend-adjusted close
    volume      INTEGER,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS series_meta (
    series_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    frequency   TEXT NOT NULL,
    units       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS macro (
    date        TEXT NOT NULL,
    series_id   TEXT NOT NULL REFERENCES series_meta(series_id),
    value       REAL NOT NULL,
    PRIMARY KEY (date, series_id)
);

CREATE TABLE IF NOT EXISTS ingest_log (
    run_at      TEXT NOT NULL,
    source      TEXT NOT NULL,           -- 'yfinance' or 'fred'
    item        TEXT NOT NULL,           -- ticker or series_id
    rows        INTEGER NOT NULL,
    status      TEXT NOT NULL,           -- 'ok' or 'error'
    message     TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def upsert(conn: sqlite3.Connection, table: str, rows: list[tuple]) -> int:
    """Insert rows, replacing any existing row with the same primary key.

    Re-running ingestion is therefore safe: it refreshes data instead of duplicating it.
    """
    if not rows:
        return 0
    placeholders = ", ".join("?" * len(rows[0]))
    conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", rows)
    return len(rows)


def log_run(conn, source: str, item: str, rows: int, status: str, message: str = "") -> None:
    conn.execute(
        "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), source, item, rows, status, message),
    )
