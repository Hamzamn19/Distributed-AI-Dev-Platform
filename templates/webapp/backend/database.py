"""DATABASE TASK FILE - the database task replaces this example.

Contract 12.3, layer 1. For every table <things> (plural snake_case):
    list_<things>(search=None), get_<thing>(id), add_<thing>(...),
    update_<thing>(id, ...), delete_<thing>(id); and once init_db(), which can
    run again and again. A broken business rule raises ValueError.
Every table has  id INTEGER PRIMARY KEY AUTOINCREMENT.
Use only the helpers of backend/db.py (fetch_all, fetch_one, execute).

backend/main.py relies on these names: init_db, list_items, add_item.
This example has one table, "items", and no column besides id and name.
"""

from backend import db


def init_db() -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS items ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL)"
    )


def list_items(search: str | None = None) -> list[dict]:
    if search:
        return db.fetch_all(
            "SELECT * FROM items WHERE name LIKE ? ORDER BY id", (f"%{search}%",)
        )
    return db.fetch_all("SELECT * FROM items ORDER BY id")


def add_item(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("name must not be empty")
    new_id = db.execute("INSERT INTO items (name) VALUES (?)", (name,))
    return db.fetch_one("SELECT * FROM items WHERE id = ?", (new_id,))
