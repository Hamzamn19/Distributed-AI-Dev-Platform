# Frontend

React + TypeScript + Vite + Tailwind CSS web interface for the master API.

## Pages

| Path | Page |
| --- | --- |
| `/` | New project form and list of existing projects |
| `/agents` | Registered agents: name, owner, model, role hint, scores, status |

Both pages refresh every 3 seconds. All API calls live in `src/api/client.ts`;
pages never call `fetch` directly.

## Run

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_BASE_URL to the master address
npm run dev
```

Open http://localhost:5173.

## Status

Sprint 2 (S2-06): agents page and new-project form are finished and use sample
data (`src/api/mock.ts`, "Sample data" badge). The task board comes next. When
S2-01 is in main, `client.ts` switches to the real API and `mock.ts` is deleted.
