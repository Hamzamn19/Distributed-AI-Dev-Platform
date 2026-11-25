"""Storage of the generated application: SQLite through Python's sqlite3 module only.

Filled by: the DATABASE task.
Relied on by: backend/main.py imports this module as `from backend import database`.

Rules every agent follows (<thing> is a record name of the requirement, <things> its plural):
- Keep the import line and the signature of init_db(). Use the ready helpers of
      backend/db.py; do not write them again. Each opens its own connection:
      fetch_all(sql, params=()) -> list[dict]
      fetch_one(sql, params=()) -> dict | None
      execute(sql, params=()) -> int        INSERT: the new id; UPDATE/DELETE: changed rows
- init_db() creates every table with CREATE TABLE IF NOT EXISTS and may run any number
  of times: sample data only when the table is empty (or INSERT OR IGNORE).
  Add 3 to 5 realistic sample records per table, so the app is not empty at first start.
- Every table has an INTEGER PRIMARY KEY AUTOINCREMENT column named "id"; links between
  tables are <thing>_id INTEGER REFERENCES <things>(id); use NOT NULL, UNIQUE, CHECK
  and DEFAULT where the requirement implies them; dates as ISO text (YYYY-MM-DD).
- For EVERY table write all five functions, with exactly these names:
      list_<things>(search: str | None = None) -> list[dict]   newest first; search filters text columns
      get_<thing>(<thing>_id: int) -> dict | None
      add_<thing>(<field>, <field>, ...) -> dict                the new record, with its "id"
      update_<thing>(<thing>_id: int, <field>, ...) -> dict | None   None when missing
      delete_<thing>(<thing>_id: int) -> bool                   False when missing
  Records are dicts whose keys are the column names; a list may add the name of a linked
  record (JOIN), for example "customer_name".
- Business rules of the requirement (limits, states, dates, stock, duplicates) are checked
  here and raise ValueError("short English message"); the API turns it into HTTP 400.
  Actions of the requirement (for example complete_<thing>, assign_<thing>) are functions too.
"""

from backend.db import connect, execute, fetch_all, fetch_one


def init_db() -> None:
    """Create the tables of the application and add sample data to empty tables."""
    execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(title) <= 50),
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed'))
        )
    """)

    if not fetch_one("SELECT id FROM tasks LIMIT 1"):
        execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)", ("İlk Görev", "Bu bir açıklama örneğidir.", "active"))
        execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)", ("Tamamlanan İş", "Bu görev bitti.", "completed"))
        execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)", ("Planlanan Proje", "Gelecek ay yapılacak.", "active"))


def list_tasks(search: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM tasks", ()
    if search:
        sql += " WHERE title LIKE ? OR description LIKE ?"
        params = (f"%{search}%", f"%{search}%")
    return fetch_all(sql + " ORDER BY id DESC", params)


def get_task(task_id: int) -> dict | None:
    return fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))


def add_task(title: str, description: str) -> dict:
    if len(title) > 50:
        raise ValueError("title too long")
    new_id = execute("INSERT INTO tasks (title, description, status) VALUES (?, ?, 'active')", (title, description))
    return get_task(new_id)


def update_task(task_id: int, title: str | None = None, description: str | None = None, status: str | None = None) -> dict | None:
    if title is not None and len(title) > 50:
        raise ValueError("title too long")
    
    if title is not None:
        execute("UPDATE tasks SET title = ? WHERE id = ?", (title, task_id))
    if description is not None:
        execute("UPDATE tasks SET description = ? WHERE id = ?", (description, task_id))
    if status is not None:
        if status not in ('active', 'completed'):
            raise ValueError("invalid status")
        execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    task = get_task(task_id)
    if not task:
        return False
    if task['status'] == 'completed':
        raise ValueError("cannot delete completed task")
    
    rows = execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return rows > 0


def complete_task(task_id: int) -> dict | None:
    """Action to mark a task as completed."""
    return update_task(task_id, status='completed')
