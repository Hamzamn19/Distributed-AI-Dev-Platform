"""SQLite persistence for agents, projects and the task graph (master/data/dap.db)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    model           TEXT NOT NULL,
    coding          REAL NOT NULL,          -- C, 0-100
    reasoning       REAL NOT NULL,          -- R, 0-100
    context         REAL NOT NULL,          -- X, 0-100
    context_window  INTEGER NOT NULL DEFAULT 0,
    specialties     TEXT NOT NULL DEFAULT '[]',
    endpoint        TEXT,
    status          TEXT NOT NULL DEFAULT 'online',   -- online | offline
    registered_at   TEXT NOT NULL,
    last_heartbeat  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id   TEXT PRIMARY KEY,                    -- P-001, P-002 ...
    name         TEXT NOT NULL,
    summary      TEXT,
    requirement  TEXT NOT NULL,
    source       TEXT NOT NULL,                       -- ollama | fallback
    model        TEXT,                                -- Ollama model used for decomposition
    status       TEXT NOT NULL,                       -- planned
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id                  TEXT PRIMARY KEY,        -- T-0001, T-0002 ...
    project_id               TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    local_id                 TEXT NOT NULL,           -- T1, T2 ... from the decomposer
    task_type                TEXT NOT NULL,
    title                    TEXT NOT NULL,
    description              TEXT,
    acceptance_criteria      TEXT NOT NULL DEFAULT '[]',
    complexity               INTEGER,
    estimated_context_tokens INTEGER,
    assigned_agent           TEXT REFERENCES agents(agent_id),
    score                    REAL,
    score_breakdown          TEXT,
    status                   TEXT NOT NULL,           -- pending (no agent online) | assigned
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);

-- Edges of the task graph: task_id cannot start before depends_on is done.
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id     TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    depends_on  TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on)
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_status ON tasks(assigned_agent, status);
"""

ACTIVE_STATUSES = ("assigned",)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path = DB_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(projects)")}
        if "model" not in columns:  # databases created before model selection existed
            conn.execute("ALTER TABLE projects ADD COLUMN model TEXT")


# --- Agents ------------------------------------------------------------------

def _agent_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["specialties"] = json.loads(d["specialties"])
    return d


def upsert_agent(conn: sqlite3.Connection, agent: dict) -> dict:
    ts = now()
    conn.execute(
        """INSERT INTO agents (agent_id, model, coding, reasoning, context, context_window,
                               specialties, endpoint, status, registered_at, last_heartbeat)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'online', ?, ?)
           ON CONFLICT(agent_id) DO UPDATE SET
               model = excluded.model, coding = excluded.coding,
               reasoning = excluded.reasoning, context = excluded.context,
               context_window = excluded.context_window, specialties = excluded.specialties,
               endpoint = excluded.endpoint, status = 'online',
               last_heartbeat = excluded.last_heartbeat""",
        (agent["agent_id"], agent["model"], agent["coding"], agent["reasoning"],
         agent["context"], agent.get("context_window") or 0,
         json.dumps([s.lower() for s in agent.get("specialties", [])]),
         agent.get("endpoint"), ts, ts),
    )
    return get_agent(conn, agent["agent_id"])


def get_agent(conn: sqlite3.Connection, agent_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    return _agent_row(row) if row else None


def list_agents(conn: sqlite3.Connection, online_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM agents" + (" WHERE status = 'online'" if online_only else "")
    return [_agent_row(r) for r in conn.execute(sql + " ORDER BY agent_id")]


def touch_heartbeat(conn: sqlite3.Connection, agent_id: str) -> bool:
    cur = conn.execute(
        "UPDATE agents SET last_heartbeat = ?, status = 'online' WHERE agent_id = ?",
        (now(), agent_id),
    )
    return cur.rowcount > 0


def mark_stale_agents_offline(conn: sqlite3.Connection, timeout_seconds: int) -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat(
        timespec="seconds")
    stale = [r["agent_id"] for r in conn.execute(
        "SELECT agent_id FROM agents WHERE status = 'online' AND last_heartbeat < ?", (cutoff,))]
    if stale:
        conn.executemany("UPDATE agents SET status = 'offline' WHERE agent_id = ?",
                         [(a,) for a in stale])
    return stale


def queue_lengths(conn: sqlite3.Connection) -> dict[str, int]:
    """q for every agent: number of tasks currently assigned to it."""
    marks = ",".join("?" * len(ACTIVE_STATUSES))
    rows = conn.execute(
        f"SELECT assigned_agent, COUNT(*) AS n FROM tasks "
        f"WHERE assigned_agent IS NOT NULL AND status IN ({marks}) GROUP BY assigned_agent",
        ACTIVE_STATUSES,
    )
    return {r["assigned_agent"]: r["n"] for r in rows}


# --- Projects & task graph ---------------------------------------------------

def _next_id(conn: sqlite3.Connection, table: str, column: str, prefix: str) -> int:
    row = conn.execute(
        f"SELECT MAX(CAST(SUBSTR({column}, ?) AS INTEGER)) FROM {table}",
        (len(prefix) + 1,)).fetchone()
    return (row[0] or 0) + 1


def new_project_ids(conn: sqlite3.Connection, local_ids: list[str]) -> tuple[str, dict[str, str]]:
    """Allocate P-001 style project id and T-0001 style task ids (global sequence)."""
    project_id = f"P-{_next_id(conn, 'projects', 'project_id', 'P-'):03d}"
    first = _next_id(conn, "tasks", "task_id", "T-")
    return project_id, {lid: f"T-{first + i:04d}" for i, lid in enumerate(local_ids)}


def create_project(conn: sqlite3.Connection, project_id: str, decomposition: dict,
                   assignments: list[dict]) -> None:
    """Store the project, its tasks (with their routed agent, if any) and the task graph.

    decomposition["subtasks"] and assignments must already carry the global task ids.
    """
    ts = now()
    by_task = {a["task_id"]: a for a in assignments}
    conn.execute(
        """INSERT INTO projects (project_id, name, summary, requirement, source, model, status,
                                 created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'planned', ?, ?)""",
        (project_id, decomposition["project_name"], decomposition["summary"],
         decomposition["requirement"], decomposition["source"], decomposition.get("model"),
         ts, ts),
    )
    for t in decomposition["subtasks"]:
        a = by_task.get(t["id"])
        conn.execute(
            """INSERT INTO tasks (task_id, project_id, local_id, task_type, title, description,
                                  acceptance_criteria, complexity, estimated_context_tokens,
                                  assigned_agent, score, score_breakdown, status,
                                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t["id"], project_id, t["local_id"], t["task_type"], t["title"],
             t["description"], json.dumps(t["acceptance_criteria"]), t["complexity"],
             t["estimated_context_tokens"],
             a["assigned_agent"] if a else None, a["score"] if a else None,
             json.dumps(a["score_breakdown"]) if a else None,
             "assigned" if a else "pending", ts, ts),
        )
    for t in decomposition["subtasks"]:
        conn.executemany(
            "INSERT INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
            [(t["id"], d) for d in t["depends_on"]],
        )


def _task_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["score_breakdown"] = json.loads(d["score_breakdown"]) if d["score_breakdown"] else None
    d["acceptance_criteria"] = json.loads(d["acceptance_criteria"])
    d["depends_on"] = [r["depends_on"] for r in conn.execute(
        "SELECT depends_on FROM task_dependencies WHERE task_id = ?", (d["task_id"],))]
    return d


def pending_tasks(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    """Unassigned tasks of a project in the shape the router expects."""
    out = []
    for r in conn.execute("SELECT * FROM tasks WHERE project_id = ? AND status = 'pending' "
                          "ORDER BY task_id", (project_id,)):
        d = _task_row(conn, r)
        out.append({"id": d["task_id"], "task_type": d["task_type"], "title": d["title"],
                    "estimated_context_tokens": d["estimated_context_tokens"],
                    "depends_on": d["depends_on"]})
    return out


def apply_assignments(conn: sqlite3.Connection, assignments: list[dict]) -> None:
    ts = now()
    for a in assignments:
        conn.execute(
            "UPDATE tasks SET assigned_agent = ?, score = ?, score_breakdown = ?, status = 'assigned', "
            "updated_at = ? WHERE task_id = ?",
            (a["assigned_agent"], a["score"], json.dumps(a["score_breakdown"]), ts, a["task_id"]))


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    """Newest first, with task and assignment counts."""
    return [dict(r) for r in conn.execute(
        """SELECT p.project_id, p.name, p.summary, p.source, p.model, p.status, p.created_at,
                  COUNT(t.task_id) AS task_count,
                  SUM(t.status = 'assigned') AS assigned_count
           FROM projects p LEFT JOIN tasks t ON t.project_id = p.project_id
           GROUP BY p.project_id ORDER BY p.created_at DESC, p.project_id DESC""")]


def get_project(conn: sqlite3.Connection, project_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return None
    project = dict(row)
    tasks = [_task_row(conn, r) for r in conn.execute(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY rowid", (project_id,))]
    project["tasks"] = tasks
    project["task_graph"] = {
        "nodes": [t["task_id"] for t in tasks],
        "edges": [{"from": d, "to": t["task_id"]} for t in tasks for d in t["depends_on"]],
    }
    return project
