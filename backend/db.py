from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import settings


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def apply_schema() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            for sql_path in sorted((settings.project_root / "sql").glob("*.sql")):
                cur.execute(sql_path.read_text())
        conn.commit()
