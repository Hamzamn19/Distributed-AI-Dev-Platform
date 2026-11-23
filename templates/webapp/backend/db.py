"""READY HELPERS - no agent writes this file.

SQLite access for backend/database.py. Three functions, nothing else:

    fetch_all(sql, params=())  -> list[dict]   all rows
    fetch_one(sql, params=())  -> dict | None  first row or None
    execute(sql, params=())    -> int          last inserted id (or 0)

The database file is app.db in the project folder; the environment variable
APP_DB overrides it (the tests use this).
"""

import os
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "app.db"


def db_path() -> str:
    return os.environ.get("APP_DB") or str(DEFAULT_PATH)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    conn = _connect()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    conn = _connect()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid or 0
    finally:
        conn.close()
