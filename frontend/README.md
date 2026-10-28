# Frontend

React + TypeScript + Vite + Tailwind CSS web interface for the master API.

## Pages

| Path | Page |
| --- | --- |
| `/` | New project form and list of existing projects |
| `/projects/:id` | Project status, Decompose / Assign agents buttons, task board |
| `/agents` | Registered agents: name, owner, model, role hint, scores, status |

The project and agents pages refresh every 3 seconds. All API calls live in `src/api/client.ts`;
pages never call `fetch` directly.

## Run

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_BASE_URL to the master address
npm run dev
```

Open http://localhost:5173. The master must be running at `VITE_API_BASE_URL`.

## Status

Sprint 2 (S2-06): agents page, new-project form and task board are finished and
talk to the live master API (`/api/v1`). There is no sample data left.
