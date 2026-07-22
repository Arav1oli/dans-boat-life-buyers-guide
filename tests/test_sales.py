import sqlite3
from pathlib import Path

import pytest

from etl.sales import model_summary, readonly_connection


SALES_DB = Path("/Users/adrianstock/Documents/Codex/2026-07-16/running-on-this-device-claude-is/outputs/soldboats_full_pass/soldboats_full_structured.sqlite")


def test_sales_database_is_opened_query_only():
    if not SALES_DB.exists():
        pytest.skip("read-only sold-boats database is not mounted")
    with readonly_connection(SALES_DB) as conn:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE must_not_exist(id integer)")


def test_sales_summary_distinguishes_sold_from_listed_price():
    if not SALES_DB.exists():
        pytest.skip("read-only sold-boats database is not mounted")
    with readonly_connection(SALES_DB) as conn:
        row = model_summary(conn, "Sargo", "28", 120)
    assert len(row) == 4
    sold_count, median_sold_price_aud, _average_days, paired_price_count = row
    assert sold_count >= paired_price_count >= 0
    if median_sold_price_aud is not None:
        assert median_sold_price_aud > 0
