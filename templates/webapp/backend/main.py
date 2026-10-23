"""HTTP API of the generated application (FastAPI). Run from the application folder:

    uvicorn backend.main:app

Filled by: the BACKEND task.
Relies on: backend/database.py (its init_db() and list_/get_/add_/update_/delete_ functions).
Relied on by: frontend/app.js calls these routes; tests/test_app.py tests them.

Rules every agent follows:
- Every route starts with /api and uses the plural record name:
      GET    /api/books            list
      GET    /api/books/{id}       one record, 404 when missing
      POST   /api/books            create, status 201, answers the new record
      PUT    /api/books/{id}       update
      DELETE /api/books/{id}       delete
  plus routes for the actions of the requirement, for example POST /api/loans.
- Request bodies are pydantic models; answers are JSON (dicts or lists of dicts).
- A ValueError from database.py becomes HTTP 400 with {"detail": "<message>"}.
- The frontend/ folder is served at / and must stay the LAST line of this file,
  after every /api route.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import database

app = FastAPI(title="Generated application")
database.init_db()


# pydantic models for the request bodies, then the /api routes


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
