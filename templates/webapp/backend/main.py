"""HTTP API of the generated application (FastAPI). Run from the application folder:

    uvicorn backend.main:app

Filled by: the BACKEND task.
Relies on: backend/database.py; call only functions that file really defines.
Relied on by: frontend/index.html calls these routes; tests/test_app.py tests them.

Rules every agent follows (<thing> is a record name of the requirement, <things> its plural):
- Keep everything above the line "--- write below this line ---" unchanged and keep the
  app.mount(...) line as the LAST line of this file, after every /api route.
- For every table of database.py these routes, with exactly these paths:
      GET    /api/<things>?search=...   list (calls database.list_<things>(search))
      GET    /api/<things>/{id}         one record, found(...) gives 404 when missing
      POST   /api/<things>              create, status_code=201, answers the new record
      PUT    /api/<things>/{id}         update, answers the record, 404 when missing
      DELETE /api/<things>/{id}         delete, status_code=204, 404 when missing
  plus one route per action of the requirement, for example POST /api/<things>/{id}/complete,
  and GET /api/stats answering counts for the dashboard, for example {"<things>": 12}.
- Request bodies are pydantic models with Field(...) limits (min_length, ge, le) and
  sensible defaults; one <Thing>In model per table is used for POST and PUT.
- A ValueError from database.py becomes HTTP 400 {"detail": "..."} by itself (handler
  below): do not catch it in the routes.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import database

app = FastAPI(title="Generated application")
database.init_db()


@app.exception_handler(ValueError)
def business_rule_broken(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def found(record, name: str = "Record"):
    """The record, or HTTP 404 when database.py answered None or False."""
    if not record:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return record


# --- write below this line ---
# pydantic models for the request bodies, then the /api routes


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
