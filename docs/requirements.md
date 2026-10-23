# Platform Requirements

The requirements of the Distributed AI Software Development Platform itself.
The applications the platform generates (for example a library system) are
its output, not its requirements.

Sources: the instructor's assignment ("CM6453 SW Processes Term Project",
updated version) and `docs/contracts/PROJECT_CONTRACT.md`. When this file and
the contract disagree, the contract wins; tell Okan.

Status as of 23 October 2026 (Sprint 3 architecture work, branch
`feature/S3-a2a-architecture`).

## 1. Purpose and scope

A user enters a long software requirement document in a web interface. A
master agent decomposes it into tasks, evaluates the capabilities of the
available agents and assigns each task to the agent that fits it best. Each
agent runs a local LLM on its own computer, carries out its tasks and sends
the result back. The master tests, reviews and integrates the parts into a
working web application. The team builds the platform with Scrum in five
two-week sprints, each ending with a working increment.

Out of scope: user accounts and login, cloud LLM APIs, generating an
application from scratch (agents fill a fixed template, contract section 12),
production hardening.

## 2. Users

| User | What they do |
| --- | --- |
| Requester | Enters a requirement document, follows the tasks, gets the generated app |
| Agent operator | A team member who runs a worker with a local model on their PC |
| Instructor | Watches the demo and checks why each task went to which agent |

## 3. Functional requirements

Status: **done** (works and is tested), **partial** (works in part, or only with
mock answers so far), **planned**.

| ID | Requirement | Sprint | Status |
| --- | --- | --- | --- |
| FR-1 | The requester submits a requirement document of 20 to 12 000 characters from the web form or the CLI; shorter or longer input is rejected with a clear message. | 1 | done |
| FR-2 | The master decomposes the requirement into tasks; each task has a title, a description, a type (contract section 9) and its dependencies. | 1 | done |
| FR-3 | A worker registers with the master, sends a heartbeat every 10 seconds and is marked `offline` after 30 seconds without one. | 1 | done |
| FR-4 | The interface lists the agents with owner, model, role, capability scores and status. | 1 | done |
| FR-5 | Projects, tasks and agents are stored in the database and survive a master restart. | 1 | done |
| FR-6 | When the LLM cannot be reached or keeps returning broken output, the master answers with a clear error and sets the project to `failed`; nothing crashes. | 1 | done |
| FR-7 | Each agent has a capability profile: coding, reasoning and context scores from 0 to 100. | 2 | done |
| FR-8 | Every model answers the same five measurement questions; the measured scores replace the estimates. | 2 | partial |
| FR-9 | Each task has one of the eight task types of contract section 9. | 2 | done |
| FR-10 | The master selects an agent with the score formula of contract section 8 and stores the reason; the interface shows the reason. | 2 | done |
| FR-11 | Assigned tasks reach the chosen agent over A2A; the interface shows each task's status and agent, refreshed every 3 seconds. | 2 | done |
| FR-12 | The master sends a task to its worker over A2A; the worker carries it out with its local LLM and returns the result (summary and files). | 3 | partial |
| FR-13 | A task is handed out only after the tasks it depends on are completed. | 3 | done |
| FR-14 | The master stores every result and writes the generated files to `workspace/<project_id>/`, versioned with git. | 3 | done |
| FR-15 | The master integrates the parts into one runnable application. | 4 | partial |
| FR-16 | The generated tests run automatically and their result is stored. | 4 | planned |
| FR-17 | A code review agent writes a short review of each generated code file. | 4 | planned |
| FR-18 | The master detects a failed or timed-out task and assigns it again, at most 3 attempts, preferably to another agent. | 4 | partial |
| FR-19 | Two tasks never write the same file; the master resolves a conflict before integration. | 4 | done |
| FR-20 | One action runs the whole flow from requirement to running application. | 5 | partial |
| FR-21 | A dashboard shows time, success rate and tokens per agent and compares the models. | 5 | planned |

## 4. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | Every model runs locally through Ollama; no cloud LLM API is used. |
| NFR-2 | All PCs are in one Tailscale network: workers call the master on port 8000 (register, heartbeat), the master calls the workers on port 9000 (tasks over A2A). |
| NFR-3 | The system keeps working with at least three workers; a missing agent's task goes to another agent. |
| NFR-4 | Settings come from `.env`; no model name, address, port or secret is written in code or committed. |
| NFR-5 | Names, fields, enum values and paths follow the contract; every error answer is `{"detail": "..."}`. |
| NFR-6 | `pytest` and `scripts/smoke_test.py` run without a real LLM (`LLM_MOCK=1`). |
| NFR-7 | The stack stays simple: no Celery, Redis, RabbitMQ, WebSocket, SSE, LangChain, LangGraph or PostgreSQL. |
| NFR-8 | The interface works on desktop and mobile widths. |
| NFR-9 | Code, comments, commit messages and interface texts are in English. |

## 5. Traceability to the assignment

Every item of the instructor's five-sprint plan and of the general
assignment text maps to at least one requirement.

| Sprint | Assignment item | Covered by | Status |
| --- | --- | --- | --- |
| 1 | Define system requirements | this file | done |
| 1 | Design overall architecture | contract sections 2 and 13, `docs/architecture.md` | done |
| 1 | Implement web interface | FR-1, FR-4, NFR-8 | done |
| 1 | Implement master-agent prototype | FR-2, FR-5, FR-6 | done |
| 1 | Register available agents/models | FR-3, FR-4 | done |
| 1 | Implement basic task decomposition | FR-2 | done |
| 2 | Agent capability profiles | FR-7 | done |
| 2 | Model capability evaluation | FR-8 | partial |
| 2 | Task classification | FR-9 | done |
| 2 | Agent selection algorithm | FR-10 | done |
| 2 | Task distribution | FR-11 | done |
| 2 | Agent status monitoring | FR-3, FR-4 | done |
| 3 | Agents execute programming tasks | FR-12 | partial |
| 3 | Communication between master and agents | FR-3, FR-12, NFR-2 | done |
| 3 | Shared project repository | FR-14 | done |
| 3 | Result collection | FR-12, FR-14 | done |
| 3 | Dependency management between tasks | FR-2, FR-13 | done |
| 4 | Code integration | FR-15 | partial |
| 4 | Automated testing | FR-16 | planned |
| 4 | Code review agent | FR-17 | planned |
| 4 | Error detection and recovery | FR-6, FR-18 | partial |
| 4 | Conflict resolution | FR-19 | done |
| 4 | Reassignment of failed tasks | FR-18 | partial |
| 5 | End-to-end workflow | FR-20 | partial |
| 5 | Dashboard | FR-21 | planned |
| 5 | Performance measurements | FR-21 | planned |
| 5 | Agent/model comparison | FR-8, FR-21 | planned |
| 5 | Documentation | this file, contract, `docs/SETUP.md`, folder READMEs | partial |
| 5 | Final testing and demonstration | FR-20, NFR-6 | planned |
| all | "The requirement will be a long document, not a single sentence" | FR-1 (up to 12 000 characters) | done |
| all | "The master agent does not simply distribute tasks randomly" | FR-7, FR-8, FR-10 | done |
| all | "Agents may use different LLM models" | FR-7, FR-8; contract section 10 | done |
| all | Demonstrate decompose, evaluate, distribute, coordinate, integrate | FR-2, FR-10, FR-11, FR-13, FR-15 | done |

Process items of the assignment (Scrum, Trello, GitHub repository, sprint
reports) are tracked in `docs/sprints/`, not here.

## 6. Where the partial items stand

- FR-8: the measurement script exists; one of the six models is measured
  (`docs/models.md`), the others use estimates.
- FR-12, FR-15, FR-20: the whole flow (decompose, assign, run on two workers,
  results, generated app with one commit per task) passes
  `scripts/e2e_local.py` with mock answers; runs with real local models on the
  tailnet are the next check. Starting a project still takes three buttons
  (Decompose, Assign agents, Run on agents).
- FR-18: failed and timed-out tasks are detected and shown; an offline agent's
  task is reassigned when a run starts. Retrying a failed task on another agent
  is Sprint 4.
