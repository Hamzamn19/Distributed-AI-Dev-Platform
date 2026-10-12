"""Database engine and session setup (SQLAlchemy 2.x, SQLite).

Owner: Can - card S1-09.

- Read the address from DATABASE_URL (dap.master.config.get_settings()).
- Create the "data/" folder and the tables when the master starts.
- Tests must be able to use a separate database (for example a temporary
  file), so do not hard-code the path.
"""
