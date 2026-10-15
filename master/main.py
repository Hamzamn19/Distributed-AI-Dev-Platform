"""Master Agent REST API (CM6453 Distributed AI Software Development Platform), Sprint 1.

Run:
    python main.py                # serves on http://0.0.0.0:8000
Settings (DAP_TOKEN, OLLAMA_*) are read from master/.env; see .env.example.
Every request must carry the header  X-DAP-Token: <DAP_TOKEN>.
"""
import asyncio
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from typing import List, Optional

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
from config import (CONTRACT_VERSION, DAP_TOKEN, HEARTBEAT_INTERVAL_SECONDS,
                    HEARTBEAT_TIMEOUT_SECONDS, HOST, OLLAMA_MODEL, PORT, TASK_TYPES)
from decomposer import decompose_requirement
from ollama_client import OllamaClient, OllamaError, resolve_model
from router import assign_tasks

logger = logging.getLogger("master")

# Routing reads queue lengths and writes assignments; keep that atomic across requests.
_routing_lock = threading.Lock()


# --- Schemas -----------------------------------------------------------------

class AgentRegistration(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    model: str
    coding: float = Field(ge=0, le=100, description="C: coding capability, 0-100")
    reasoning: float = Field(ge=0, le=100, description="R: reasoning capability, 0-100")
    context: float = Field(ge=0, le=100, description="X: context capacity, 0-100")
    context_window: int = Field(0, ge=0, description="Optional context window in tokens")
    specialties: List[str] = Field(default_factory=list,
                                   description=f"Subset of {', '.join(TASK_TYPES)}")
    endpoint: Optional[str] = Field(None, description="Where the agent can be reached")


class ProjectRequest(BaseModel):
    requirement: str = Field(min_length=20, description="Software requirement document")
    allow_fallback: bool = True
    model: Optional[str] = Field(None, description=f"Ollama model, default {OLLAMA_MODEL}")


# --- Auth --------------------------------------------------------------------

def verify_token(x_dap_token: Optional[str] = Header(None, alias="X-DAP-Token")) -> None:
    if not x_dap_token or not secrets.compare_digest(x_dap_token, DAP_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-DAP-Token")


# --- Heartbeat monitor -------------------------------------------------------

def sweep_offline_agents() -> List[str]:
    with db.connect() as conn:
        stale = db.mark_stale_agents_offline(conn, HEARTBEAT_TIMEOUT_SECONDS)
    for agent_id in stale:
        logger.warning("[OFFLINE] %s %s sn'dir heartbeat göndermedi, offline yapıldı",
                       agent_id, HEARTBEAT_TIMEOUT_SECONDS)
    return stale


async def _heartbeat_monitor() -> None:
    while True:
        await asyncio.sleep(5)
        try:
            await asyncio.to_thread(sweep_offline_agents)
        except Exception:  # keep the monitor alive
            logger.exception("Heartbeat sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DAP_TOKEN:
        raise RuntimeError("DAP_TOKEN environment variable is not set")
    db.init_db()
    monitor = asyncio.create_task(_heartbeat_monitor())
    yield
    monitor.cancel()


APP_VERSION = "0.1.0"

app = FastAPI(title="DAP Master Agent", version=APP_VERSION, lifespan=lifespan)
# Every endpoint except /health requires the X-DAP-Token header.
api = APIRouter(dependencies=[Depends(verify_token)])


# --- Endpoints ---------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Public liveness check (no token): is the Master up and can it reach Ollama."""
    try:
        OllamaClient().installed_models()
        ollama = True
    except OllamaError:
        ollama = False
    return {"status": "ok", "version": APP_VERSION, "ollama": ollama}


@api.post("/agents/register", status_code=201)
def register_agent(body: AgentRegistration) -> dict:
    unknown = sorted({s.lower() for s in body.specialties} - set(TASK_TYPES))
    if unknown:
        raise HTTPException(422, f"Unknown specialties: {', '.join(unknown)}")
    with db.connect() as conn:
        agent = db.upsert_agent(conn, body.model_dump())
    logger.info("[REGISTER] Ajan kaydedildi: %s (model=%s, C=%g R=%g X=%g, uzmanlık=%s)",
                agent["agent_id"], agent["model"], agent["coding"], agent["reasoning"],
                agent["context"], ", ".join(agent["specialties"]) or "-")
    return {"agent": agent, "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS}


@api.get("/agents")
def list_agents() -> dict:
    with db.connect() as conn:
        agents = db.list_agents(conn)
        queues = db.queue_lengths(conn)
    for a in agents:
        a["queue_length"] = queues.get(a["agent_id"], 0)
    return {"agents": agents}


@api.post("/agents/{agent_id}/heartbeat")
def heartbeat(agent_id: str) -> dict:
    with db.connect() as conn:
        before = db.get_agent(conn, agent_id)
        if before is None or not db.touch_heartbeat(conn, agent_id):
            logger.warning("[HEARTBEAT] Kayıtlı olmayan ajan: %s", agent_id)
            raise HTTPException(404, f"Agent {agent_id!r} is not registered")
    if before["status"] == "offline":
        logger.info("[HEARTBEAT] %s canlı (offline -> online)", agent_id)
    else:
        logger.info("[HEARTBEAT] %s canlı", agent_id)
    return {"agent_id": agent_id, "status": "online",
            "next_heartbeat_in": HEARTBEAT_INTERVAL_SECONDS}


@api.get("/models")
def list_models() -> dict:
    """Models pulled into Ollama, so the dashboard can show what is selectable."""
    try:
        installed = OllamaClient().installed_models()
    except OllamaError:
        return {"default": OLLAMA_MODEL, "ollama_online": False, "installed": []}
    return {"default": OLLAMA_MODEL, "ollama_online": True, "installed": installed}


@api.get("/projects")
def list_projects() -> dict:
    with db.connect() as conn:
        return {"projects": db.list_projects(conn)}


def _decompose(body: ProjectRequest) -> dict:
    """Pick the Ollama model and split the requirement into subtasks (shared by
    /decompose and /projects)."""
    requested = (body.model or OLLAMA_MODEL).strip()
    client = OllamaClient(model=requested)
    try:
        installed = client.installed_models()
    except OllamaError:
        installed = None  # Ollama offline: the decomposer falls back if allowed
    if installed is not None:
        resolved = resolve_model(requested, installed)
        if resolved is None:
            raise HTTPException(422, f"Model '{requested}' Ollama'da yüklü değil. "
                                     f"Kurmak için: ollama pull {requested}. "
                                     f"Yüklü modeller: {', '.join(installed) or 'yok'}")
        client.model = resolved

    logger.info("[PROJECT] Gereksinim dokümanı alındı (%d karakter, model: %s)",
                len(body.requirement), client.model)
    try:
        decomposition = decompose_requirement(
            body.requirement, client=client, allow_fallback=body.allow_fallback)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, f"Decomposition failed: {exc}") from exc
    decomposition["model"] = client.model if decomposition["source"] == "ollama" else None
    return decomposition


@api.post("/decompose")
def decompose(body: ProjectRequest) -> dict:
    """Split a requirement into subtasks only: nothing is saved and nothing is assigned."""
    return {"contract_version": CONTRACT_VERSION, **_decompose(body)}


@api.post("/projects", status_code=201)
def create_project(body: ProjectRequest) -> dict:
    decomposition = _decompose(body)
    with _routing_lock, db.connect() as conn:
        project_id, ids = db.new_project_ids(conn, [t["id"] for t in decomposition["subtasks"]])
        for t in decomposition["subtasks"]:
            t["local_id"], t["id"] = t["id"], ids[t["id"]]
            t["depends_on"] = [ids[d] for d in t["depends_on"]]
        for t in decomposition["subtasks"]:
            logger.info("[TASK] %s %-13s %s%s", t["id"], t["task_type"], t["title"],
                        f"  (bağımlı: {', '.join(t['depends_on'])})" if t["depends_on"] else "")
        agents = db.list_agents(conn, online_only=True)
        if agents:
            logger.info("[ROUTE] %d online ajan arasında S skoru hesaplanıyor: %s",
                        len(agents), ", ".join(a["agent_id"] for a in agents))
        else:
            logger.warning("[ROUTE] Online ajan yok, görevler pending bırakılıyor")
        # Score every subtask against the online agents; with none online, tasks stay pending.
        assignments = (assign_tasks(decomposition["subtasks"], agents, db.queue_lengths(conn))
                       if agents else [])
        db.create_project(conn, project_id, decomposition, assignments)
        project = db.get_project(conn, project_id)
    logger.info("[PROJECT] %s kaydedildi: %d görev, %d atandı (kaynak: %s)", project_id,
                len(project["tasks"]), len(assignments), decomposition["source"])
    return {"contract_version": CONTRACT_VERSION, **project}


@api.post("/projects/{project_id}/assign-pending")
def assign_pending(project_id: str) -> dict:
    """Route a project's still-pending tasks, e.g. after agents came online."""
    with _routing_lock, db.connect() as conn:
        if db.get_project(conn, project_id) is None:
            raise HTTPException(404, f"Project {project_id!r} not found")
        tasks = db.pending_tasks(conn, project_id)
        agents = db.list_agents(conn, online_only=True)
        assignments = assign_tasks(tasks, agents, db.queue_lengths(conn)) if tasks and agents else []
        db.apply_assignments(conn, assignments)
        project = db.get_project(conn, project_id)
    logger.info("[PROJECT] %s: %d bekleyen görev atandı", project_id, len(assignments))
    return {"assigned": len(assignments), **project}


@api.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    with db.connect() as conn:
        project = db.get_project(conn, project_id)
    if project is None:
        raise HTTPException(404, f"Project {project_id!r} not found")
    return project


app.include_router(api)


# --- Frontend compatibility (/api/v1, no token) ------------------------------
# Contract (docs/contracts/PROJECT_CONTRACT.md): paths start with /api/v1 and
# frontend-called endpoints need no token (browsers cannot keep secrets).
# Baran's own paths above stay untouched (Streamlit dashboard + CLI use them).
# Fatma reads these field names: agents have agent_id/model/status,
# projects have project_id/tasks[{task_id,task_type,title,assigned_agent,score,depends_on}].

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

v1 = APIRouter(prefix="/api/v1")


@v1.get("/agents")
def v1_list_agents() -> list:
    """Token-free agent list for the web UI (same data as GET /agents)."""
    return list_agents()["agents"]


@v1.post("/projects", status_code=201)
def v1_create_project(body: ProjectRequest) -> dict:
    """Token-free project create+decompose for the web UI.

    Body is Baran's shape: {"requirement": "<20+ chars>"}.
    """
    return create_project(body)


@v1.get("/projects/{project_id}")
def v1_get_project(project_id: str) -> dict:
    """Token-free project read for the web UI (same data as GET /projects/{id})."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(404, f"Project {project_id!r} not found")
    return project


app.include_router(v1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
