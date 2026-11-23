# Generated app

FastAPI + SQLite. Run everything from this folder.

    pip install -r requirements.txt
    uvicorn backend.main:app --reload     # http://127.0.0.1:8000/docs
    pytest

Files: `backend/db.py` (ready SQLite helpers), `backend/database.py` (tables),
`backend/main.py` (endpoints), `tests/test_app.py` (tests). The template starts
with one table, `items`, and two endpoints: `GET /api/items` and `POST /api/items`.
