# Frontend

React + TypeScript + Vite + Tailwind CSS web interface for the master API.

## Pages

| Path | Page |
| --- | --- |
| `/` | New project form and list of existing projects |
| `/projects/:id` | Project status, Decompose / Assign agents / Run on agents buttons, task board with agent and model |
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

Sprint 3: every page uses the real API; the UI is served by the master at `/`.
"Run on agents" sends the tasks to the workers; the task board shows each task's live
status and the agent with its model, and the Agents page shows a working agent as busy.
The project page lists every result (summary or error, time, tokens) and the generated
files with a viewer; the Agents page shows each A2A address and whether the master
reaches it (checked every 10 s).

Plain design with a light and a dark theme (no new package; Tailwind and CSS only).
The colours are named tokens in `src/index.css` (page, card, ink, muted, accent, ok,
warn, bad, ...), defined once per theme; `src/lib/theme.ts` follows the computer's
setting or the choice in the header (remembered in this browser). Every status is
shown as a plain word with its meaning on hover (`components/ui.tsx`). System fonts
only, so the UI needs no internet.

- `/` Overview (`OverviewPage.tsx`): how the platform works in three steps, the
  numbers, the new-project form, the projects, the agents and an activity list made
  from status changes between polls (`hooks/useEventLog.ts`).
- `/projects/:id`: a "next step" box that says what to press and what happens, the
  numbered steps database → backend → frontend → testing → master check with the
  agent, model, time and tokens of each (`Pipeline.tsx`), the master's acceptance
  check from `acceptance.json` (`AcceptanceMatrix.tsx`), a timeline (`Timeline.tsx`),
  task reports, activity and the files with line numbers (`FileExplorer.tsx`).
- `/agents`: one card per agent: model, preferred task, last heartbeat, current
  task, skills as bars, and whether the master reaches its A2A server.
- "▶ Open the app" (`components/OpenAppButton.tsx`) on a project page once its backend
  task is done, and "Open latest app" on the overview: the master runs the generated
  application (`POST /projects/{id}/preview`) and a new tab opens it at
  `http://<master>:<port>/`.
