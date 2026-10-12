# Frontend

Owner: Fatma.

## What it does

The web interface of the platform: a form to submit a requirement document,
a project page with the task list, and an agents page.

## First-time setup (card S1-04)

This folder already contains `src/api/types.ts` and `.env.example`. Create the
Vite project around them, from the repository root:

```bash
npm create vite@latest frontend -- --template react-ts
```

When Vite says the folder is not empty, choose **Ignore files and continue**.
Then add Tailwind CSS by following its current Vite guide, and:

```bash
cd frontend
cp .env.example .env        # Windows: copy .env.example .env
npm install
npm run dev                 # http://localhost:5173
```

## Input and output

- Input: JSON from the master API, typed in `src/api/types.ts`.
- Output: requests to the master under `VITE_API_BASE_URL + "/api/v1"`.

## Rules

- Every request goes through functions in `src/api/client.ts`
  (`getAgents`, `createProject`, `getProjects`, `getProject`,
  `decomposeProject`, `assignProject`, `getTasks`). Pages never call `fetch`
  directly.
- Field names stay snake_case, exactly as in `src/api/types.ts`.
- Live data is refreshed by asking again every 3 seconds. No WebSocket or SSE.
- All interface text is in English.

## Connections

| Talks to | How |
| --- | --- |
| Master | HTTP, endpoints listed in `docs/PROJECT_CONTRACT.md` |
