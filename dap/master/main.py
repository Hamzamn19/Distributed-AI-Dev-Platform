"""Master Agent API and web interface on one address.

Run from the repository root:
    python -m dap.master
    uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload

    http://localhost:8000          web interface (frontend/dist, built with npm run build)
    http://localhost:8000/docs     interactive API docs
    http://localhost:8000/api/v1   REST API
"""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from dap import __version__
from dap.master.api import agents, health, projects
from dap.master.config import get_settings

API_PREFIX = "/api/v1"

# Built React app (cd frontend && npm run build). Tests point this at a temporary folder.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Paths the frontend fallback never answers, so a wrong API path stays a JSON 404.
NOT_FRONTEND = ("api", "docs", "redoc", "openapi.json")

NOT_BUILT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Frontend not built</title></head>
<body style="font-family: sans-serif; max-width: 40rem; margin: 3rem auto">
<h1>Frontend not built</h1>
<p>Run: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>
- or use <a href="http://localhost:5173">http://localhost:5173</a> during development.</p>
<p>The API is running: <a href="/docs">/docs</a>, <a href="/api/v1/health">/api/v1/health</a>.</p>
</body></html>"""

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


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    """Serve a file of the built frontend, or index.html for React routes."""
    if path.split("/", 1)[0] in NOT_FRONTEND:
        raise HTTPException(status_code=404, detail="Not Found")
    dist = FRONTEND_DIST.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return HTMLResponse(NOT_BUILT_PAGE)
    file = (dist / path).resolve()
    if path and file.is_file() and file.is_relative_to(dist):
        return FileResponse(file)
    return FileResponse(index)
