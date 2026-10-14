# Distributed Multi-Agent Software Development Platform

CM6453 Software Processes term project (Team 2). We build a web platform where a user enters a software requirement and a master agent splits it into tasks, assigns them to LLM agents running on different machines according to their measured strengths, and merges the results into a working web app.

## Where things are
| Folder / file | Purpose |
|---|---|
| `docs/PROJECT_PLAN.md` | Goal, architecture, technology plan, roadmap, risks |
| `docs/sprints/` | One file per sprint: goal, planning notes, review, retrospective, report |
| `docs/adr/` | Short decision records (what we tried, result, decision) |
| `docs/hardware.md` | Everyone's machine specs and installed models |
| `backend/` | FastAPI app, orchestration, database |
| `frontend/` | React + Vite + Tailwind web UI |
| `agents/` | Agent Node (worker) code and the benchmark harness |
| `tests/` | Cross-component and end-to-end tests |
| `CONTRIBUTING.md` | Branches, commits, pull requests, Definition of Done |

## Team workflow
Scrum, 5 sprints of 2 weeks. Planning board: Trello (link: TODO). Every change goes through a pull request reviewed by a teammate.

## Getting started
TODO: filled in by card S1-06 (clone, install, run, test).

## Status
Sprint 1 (Oct 5 - Oct 18, tentative): foundation and first end-to-end slice.
