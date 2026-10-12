"""Master Agent API.

Run from the repository root:
    uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload

Interactive API docs: http://localhost:8000/docs
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dap import __version__
from dap.master.api import agents, health, projects
from dap.master.config import get_settings

API_PREFIX = "/api/v1"

settings = get_settings()

app = FastAPI(title="Distributed Agents Platform - Master", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix=API_PREFIX)
api.include_router(health.router)
api.include_router(agents.router)
api.include_router(projects.router)
app.include_router(api)
