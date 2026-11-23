"""BACKEND TASK FILE - the backend task replaces this example.

Contract 12.3, layer 1. For every table <things>: GET /api/<things>?search=,
GET /api/<things>/{id}, POST /api/<things> (201), PUT /api/<things>/{id},
DELETE /api/<things>/{id} (204), and once GET /api/stats. A ValueError from
backend/database.py becomes HTTP 400. Use only the functions of
backend/database.py; never write SQL here.

This example has the two endpoints GET and POST /api/items. Run it from the
project folder:  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend import database

app = FastAPI(title="Generated app")
database.init_db()


class ItemIn(BaseModel):
    name: str


@app.get("/api/items")
def get_items(search: str | None = None) -> list[dict]:
    return database.list_items(search)


@app.post("/api/items", status_code=201)
def create_item(body: ItemIn) -> dict:
    try:
        return database.add_item(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
