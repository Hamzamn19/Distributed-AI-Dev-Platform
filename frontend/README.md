# Frontend

React + TypeScript + Vite + Tailwind CSS web interface for the master API.

## Pages

| Path | Page |
| --- | --- |
| `/` | New project form and list of existing projects |
| `/projects/:id` | Project status, Decompose / Assign agents buttons, task board |
| `/agents` | Registered agents: name, owner, model, role hint, scores, status |

The project and agents pages refresh every 3 seconds. All API calls live in `src/api/client.ts`;
pages never call `fetch` directly. The API base is relative (`/api/v1`), so the same build
works from any PC that opens the master's address.

## Run

Normal use: build once, the master serves the UI on its own address.

```bash
cd frontend
npm install
npm run build          # type check (tsc) + build into frontend/dist
cd ..
python -m dap.master   # then open http://localhost:8000
```

From another PC open `http://<master Tailscale IP>:8000`.

Development with hot reload: start the master, then

```bash
cd frontend
npm run dev            # http://localhost:5173, /api is forwarded to the master on :8000
```

`frontend/.env` is not needed. Set `VITE_API_BASE_URL` only for unusual setups
(see `.env.example`).

## Status

Sprint 3 (phase 1): every page uses the real API; the sample data is gone. The UI is
served by the master at `/`.
