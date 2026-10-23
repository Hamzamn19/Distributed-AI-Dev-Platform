"""Storage of the generated application: SQLite through Python's sqlite3 module only.

Filled by: the DATABASE task.
Relied on by: backend/main.py imports this module as `from backend import database`.

Rules every agent follows:
- The database file is DB_PATH below (app.db in the application folder).
- init_db() creates every table with CREATE TABLE IF NOT EXISTS. main.py calls it once.
- For each kind of record (for example "book") write plain functions with these names:
      list_books() -> list[dict]          every record, as dicts
      get_book(book_id: int) -> dict | None
      add_book(...) -> dict               the new record, including its "id"
      update_book(book_id: int, ...) -> dict | None
      delete_book(book_id: int) -> bool
  Records are dicts whose keys are the column names; every table has an
  INTEGER PRIMARY KEY column named "id".
- Business rules of the requirement (limits, dates, checks) also go here, as
  functions that raise ValueError with a short English message when a rule is broken.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the tables of the application."""
    with connect() as connection:
        pass  # CREATE TABLE IF NOT EXISTS ... for every table


# list_..., get_..., add_..., update_..., delete_... functions for every table
