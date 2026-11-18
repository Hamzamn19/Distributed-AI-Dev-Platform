"""Ready SQLite helpers of the generated application. Not written by the agents.

    from backend.db import connect, execute, fetch_all, fetch_one

    fetch_all(sql, params) -> list[dict]     every row as a dict
    fetch_one(sql, params) -> dict | None    the first row, or None
    execute(sql, params) -> int              INSERT: the new id; UPDATE/DELETE: changed rows
    connect()                                a connection (foreign keys on), for several
                                             statements in one transaction (init_db)

The tests point DB_PATH at a file of their own before the app starts.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute(sql, params)]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with connect() as connection:
        row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> int:
    with connect() as connection:
        cursor = connection.execute(sql, params)
        return cursor.lastrowid if sql.lstrip().upper().startswith("INSERT") else cursor.rowcount
