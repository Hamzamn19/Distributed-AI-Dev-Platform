# Project Plan: Distributed Multi-Agent Software Development Platform

CM6453 Software Processes term project. Scrum, 5 sprints of 2 weeks, 7 people.
This is a living document: change it at any Retrospective. Last updated: Oct 2, 2026.

## 1. Product Goal
A web app where a user enters a software requirement and a master agent splits it into tasks, assigns them to LLM agents (different models, different machines) based on their measured strengths, and merges the results into a working web app.

**MVP scope (Product Owner confirms):** one user, no login, generated app from a fixed template, 3+ agent nodes on at least 2 machines. Out of scope: accounts, billing, production hardening, in-browser code editing.

## 2. Architecture in one picture
```
Browser UI (React)  ->  FastAPI API  ->  Master Orchestrator
                                          analyze -> decompose -> classify -> select agent -> dispatch -> integrate
                                                |                         |
                                          Database (tasks, agents,   Agent Nodes (one per machine)
                                          profiles, metrics)         each runs one model via Ollama
LLM Gateway (LiteLLM): one API for local and cloud models, captures tokens and latency
Git: each agent pushes a branch agent/<agent>/<task-id>; the Master merges in dependency order
```
Contracts frozen in Sprint 1: Task schema, AgentProfile, TaskResult, event list, task state machine.

## 3. Technology plan: learn, but never block the project
We want job-market technologies, so we use the full stack from the shared plan. To keep every sprint shippable, each technology has a tier and a fallback.

| Tier | Meaning |
|---|---|
| Core | Must work in every sprint. No fallback needed. |
| Learn | Time-boxed spike. If it is not working by the Sprint Review, we switch to the fallback and write down what we learned. |
| Stretch | Only if the Must cards are done. |

| Technology | Tier | Fallback |
|---|---|---|
| Python, FastAPI, Pydantic | Core | none |
| Ollama + LiteLLM (local and cloud models) | Core | call Ollama HTTP directly |
| SQLAlchemy | Core | none |
| React + Vite + Tailwind | Core | Streamlit page |
| Git, pull requests, GitHub Actions CI | Learn | run tests locally before merge |
| Docker Compose | Learn | run services locally |
| PostgreSQL + Alembic | Learn | SQLite |
| Redis + Celery (queue per agent) | Learn | FastAPI background tasks + HTTP calls |
| Socket.io live updates | Learn | UI polls the API every 2 seconds |
| LangGraph (agent logic) | Learn | plain Python function chain |
| Multi-machine network (VPN or LAN) | Learn | all nodes on one machine, different ports |
| Docker sandbox runner | Stretch | subprocess with timeout in a temp folder |
| PyGithub service | Stretch | local git only |
| Monaco, React Flow, Recharts extras | Stretch | plain tables |

**Spike rule:** each Learn technology gets one time-boxed card (about 4-6 hours of one person's time). At the Review we decide: keep it or use the fallback. Write a short ADR (3-5 lines: what we tried, result, decision). These notes also help the Scrum assessment report.

**Network note:** we are 7 people. Check the current free-plan user limit of the VPN you pick (for example Tailscale) before Sprint 2. Only the people whose machines run agent nodes need an account.

## 4. Models and machines
Each member fills one row (card S1-10). The capability benchmark in Sprint 2 turns this into measured scores.

| Member | Machine / OS | GPU + VRAM (or unified memory) | RAM | Models installed | Speed (tokens/s) |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

Rule of thumb (approximate, check the Ollama library for current models): a 4-bit model needs about 0.6 GB per billion parameters plus 1.5-2 GB for context.
- About 6 GB VRAM: 7-8B models, short context.
- About 8 GB VRAM: 7-8B comfortably.
- About 12 GB VRAM: up to 14B.
- 16 GB or more (or Apple unified memory 24 GB+): 14B to 32B.

Examples to benchmark: a coding model (Qwen2.5-Coder 7B/14B), a reasoning model (a DeepSeek-R1 distill), a general instruct model (Llama or Qwen instruct), plus one cloud model for the demo.

**Master model tip:** reasoning models often print a thinking block before the answer, which breaks strict JSON. Strip it, or use JSON/structured output, and always validate with Pydantic and retry once with a repair prompt.

## 5. How we work (adapted for a course team with limited hours)
- **Roles:** Scrum Master: Hamzah. Product Owner: to be confirmed at Sprint 1 Planning. Everyone else is a Developer; the PO and SM also take sprint cards.
- **Events per sprint:** Planning up to 1.5 h, Review up to 45 min, Retrospective up to 45 min. Check-ins: short written updates 2-3 times a week plus one 15-20 minute call.
- **Cards:** the team picks cards at Planning (no pre-assigned owners). Each card has one owner and one buddy reviewer, so nobody is the only person who knows an area.
- **Areas (FE, BE, AI, DB, DevOps)** are interests, not silos. Every sprint produces a working end-to-end slice, not a finished layer.
- **Definition of Done (add item 5):** the card's author can explain it at the Review. This keeps AI-assisted work educational.
- **AI use:** welcome on every card. The rule is that we understand and can defend what we merge.

## 6. Capacity and estimation
- The backlog has 377 story points in total (326 are Must). Points are not hours; Sprint 1 is the calibration sprint.
- From Sprint 2 on: forecast = points actually Done in the previous sprint, plus or minus 20%.
- If velocity is lower than the plan needs, cut in this order: Could cards, then Should cards, then Learn technologies fall back. The Product Owner owns the order.
- Most cards are labelled Must, so after Sprint 1 the Product Owner will have to re-rank some Must cards too; the first velocity decides how much of the plan is realistic.
- Must points per sprint: S1: 74 | S2: 63 | S3: 56 | S4: 67 | S5: 66.

## 7. Roadmap (each sprint ends with a demoable Increment)
| Sprint | Dates (tentative) | Sprint Goal |
|---|---|---|
| 1 | Oct 5 - Oct 18 | A user submits a requirement and sees it decomposed into persisted tasks in the web UI, on a shared dev/CI foundation. |
| 2 | Oct 19 - Nov 1 | Agents register with measured capabilities; the master assigns each task to the best-fit agent, visible live. |
| 3 | Nov 2 - Nov 15 | Assigned agents write code on branches and respect task dependencies. |
| 4 | Nov 16 - Nov 29 | Generated code is integrated, tested and reviewed; failed tasks are reassigned automatically. |
| 5 | Nov 30 - Dec 13 | End-to-end autonomous run with dashboard metrics, model comparison, documentation and a live demo. |

## 8. Top risks
| Risk | Mitigation |
|---|---|
| Machines cannot reach each other (firewall, VPN limits) | Test in Sprint 1 (S1-10) and Sprint 2 (S2-15); fallback: one machine, several nodes; record a backup demo. |
| Small local models write weak code or break JSON | Pydantic validation + repair retry; strongest model for the Master; mock provider and dummy executor for CI. |
| Too much technology for our hours | Tier and fallback table above; cut order in section 6. |
| Frontend and backend agents produce incompatible code | Contract-first: the Architect step emits an OpenAPI contract and DB schema before tasks are assigned. |
| Code nobody understands (AI-generated) | DoD item 5; buddy review. |
| Exam weeks or holidays (for example Oct 29) | Check the academic calendar before confirming dates; shrink the forecast for that sprint. |

## 9. Open decisions
1. Product Owner (shared plan proposes one member; the team confirms).
2. Sprint dates, after checking exam weeks.
3. Hardware table (section 4) filled by everyone.
4. Sprint 1 forecast: the 13 proposed cards are a starting point; trim at Planning.
5. Check-in cadence (no daily meeting): confirm with the instructor that written updates plus a weekly call count as the Daily Scrum.
6. Which cloud model the demo uses (cost and free-tier limits).
