"""Run the SQL data-quality checks in sql/data_checks.sql and print the results.

Usage:
    python -m src.check_data
"""

import pandas as pd

from src import db
from src.config import ROOT

CHECKS_FILE = ROOT / "sql" / "data_checks.sql"


def parse_queries(text: str) -> list[tuple[str, str]]:
    """Split the .sql file into (name, query) pairs on '-- name:' markers."""
    queries = []
    for block in text.split("-- name:")[1:]:
        name, _, sql = block.partition("\n")
        queries.append((name.strip(), sql.strip()))
    return queries


def main() -> None:
    conn = db.connect()
    pd.set_option("display.width", 140)
    for name, sql in parse_queries(CHECKS_FILE.read_text()):
        print(f"\n=== {name} ===")
        df = pd.read_sql_query(sql, conn)
        print(df.to_string(index=False) if not df.empty else "(no rows)")
    conn.close()


if __name__ == "__main__":
    main()
