from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def readonly_connection(path: str | Path) -> sqlite3.Connection:
    uri = f"file:{Path(path).resolve()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def model_summary(conn: sqlite3.Connection, make: str, model: str, months: int, country: str | None = None):
    country_filter = "AND location_country_code = ?" if country else ""
    params = [f"-{months} months", make, f"%{model}%"] + ([country] if country else [])
    return conn.execute(
        f"""
        WITH matched AS (
          SELECT sold_price_aud, listed_price_aud, days_on_market, location_country_code
          FROM sold_boats
          WHERE sold_date >= date((SELECT MAX(sold_date) FROM sold_boats), ?)
            AND lower(make) = lower(?)
            AND lower(model) LIKE lower(?)
            {country_filter}
        ), ranked_price AS (
          SELECT sold_price_aud,
                 ROW_NUMBER() OVER (ORDER BY sold_price_aud) AS row_number,
                 COUNT(*) OVER () AS row_count
          FROM matched
          WHERE sold_price_aud IS NOT NULL
        )
        SELECT
          (SELECT COUNT(*) FROM matched) AS sold_count,
          (SELECT AVG(sold_price_aud) FROM ranked_price WHERE row_number IN ((row_count + 1) / 2, (row_count + 2) / 2)) AS median_sold_price_aud,
          (SELECT AVG(days_on_market) FROM matched WHERE days_on_market IS NOT NULL) AS average_days_on_market,
          (SELECT COUNT(*) FROM matched WHERE sold_price_aud IS NOT NULL AND listed_price_aud IS NOT NULL) AS paired_price_count
        """,
        params,
    ).fetchone()


def main():
    parser = argparse.ArgumentParser(description="Read-only YachtWorld market sense-check")
    parser.add_argument("--sales-db", required=True)
    parser.add_argument("--make", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--country")
    args = parser.parse_args()
    with readonly_connection(args.sales_db) as conn:
        print(model_summary(conn, args.make, args.model, args.months, args.country))


if __name__ == "__main__":
    main()
