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
    # One execute("CREATE TABLE IF NOT EXISTS <things> (...)") per table, then for example:
    #     if not fetch_one("SELECT id FROM <things> LIMIT 1"):
    #         execute("INSERT INTO <things> (<field>, ...) VALUES (?, ...)", (<value>, ...))
    # execute(sql, params) and fetch_*(sql, params) open their own connection: never pass one.


# list_<things>, get_<thing>, add_<thing>, update_<thing>, delete_<thing> for every table,
# then the functions of the business rules and actions. A list with its search, for
# example (in SQL, WHERE comes before ORDER BY):
#     def list_<things>(search: str | None = None) -> list[dict]:
#         sql, params = "SELECT * FROM <things>", ()
#         if search:
#             sql += " WHERE <text column> LIKE ? OR <other text column> LIKE ?"
#             params = (f"%{search}%", f"%{search}%")
#         return fetch_all(sql + " ORDER BY id DESC", params)
