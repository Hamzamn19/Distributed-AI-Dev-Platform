"""S1-09: engine, sessions and schema initialization from master settings.

Import repositories to initialize the tables. The database address is supplied
by dap.master.config; this module never chooses its own database location.
"""

from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from dap.master.config import get_settings


class Base(DeclarativeBase):
    pass


database_url = make_url(get_settings().database_url)
if database_url.get_backend_name() == "sqlite":
    if database_url.database and database_url.database != ":memory:":
        Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(database_url)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Create missing tables and add missing nullable columns; records are retained."""
    from dap.master.db import models  # Register tables before create_all.

    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """No migration tool: a column added in a later sprint (always nullable) is
    added to an older data/dap.db with ALTER TABLE. Deleting data/dap.db also works."""
    existing = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            present = {column["name"] for column in existing.get_columns(table.name)}
            for column in table.columns:
                if column.name not in present and column.nullable:
                    kind = column.type.compile(dialect=engine.dialect)
                    connection.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {kind}')
                    )
