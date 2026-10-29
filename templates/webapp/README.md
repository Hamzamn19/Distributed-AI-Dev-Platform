# Generated application

Written by the agents of the Distributed AI Software Development Platform from a
requirement document. `git log` shows which agent wrote which part.

| File | Written by |
| --- | --- |
| `backend/database.py` | database task: SQLite tables and functions |
| `backend/main.py` | backend task: FastAPI routes under `/api` |
| `frontend/index.html`, `frontend/app.js` | frontend task: the page |
| `tests/test_app.py` | testing task: pytest tests of the API |
| `backend/db.py`, `frontend/lib.js`, `frontend/style.css` | ready parts of the template |

## Run

From this folder, with Python 3.11 or newer:

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app        # then open http://localhost:8000
```

Tests: `python -m pytest` (they use a database file of their own). The data is
stored in `app.db` in this folder, with some sample records; delete it to start again.
