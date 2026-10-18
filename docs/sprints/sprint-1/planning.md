# Sprint 1 Planning

Owner: Hamza (card S1-01). Add the meeting date, attendees and decisions below.

| Field | Value |
| --- | --- |
| Dates | 1–15 October 2026 (Thu→Thu, two weeks; sprint opened Thu 1 Oct, kickoff meeting Sun 4 Oct, first work 5 Oct) |
| Goal | A working master that takes a requirement, splits it into tasks, assigns each task to an agent and stores it all in the database; the result is visible in the web interface |
| Out of scope | LLM setup on the six worker PCs, capability measurement and score-based assignment (Sprint 2); workers taking tasks and writing code (Sprint 3) |
| Trello flow | Sprint Backlog -> In Progress -> Code Review -> Testing -> Done |

## Sprint backlog

| Code | Card | Owner | Label |
| --- | --- | --- | --- |
| S1-01 | Trello board + sprint planning | Hamza | Scrum |
| S1-02 | Repo skeleton + setup guide | Abdurrahman | DevOps/Test |
| S1-03 | Requirements + sample requirement document | Okan | Product |
| S1-04 | Web interface skeleton | Fatma | Frontend |
| S1-05 | Master Agent core + API | Baran | Master |
| S1-06 | Task breakdown + simple assignment | Baran | Master |
| S1-07 | LLM client + worker registration stub | Eray | Worker/LLM |
| S1-08 | Agent listing (hardware + model inventory) | Okan | Product |
| S1-09 | Database schema + repository | Can | Database |
| S1-10 | Test infrastructure + final checks | Abdurrahman | DevOps/Test |
| S1-11 | Sprint review, retrospective, report | Hamza | Scrum |

The subtasks and "done when" items of each card are in the shared plan document
and on the Trello cards.

## Success criteria

1. A requirement reaches the master from the form or the command line and is stored as a project.
2. The master splits it into frontend, backend, database and testing tasks with the local Ollama model.
3. Each task is assigned to the agent whose `role_hint` equals its type; the assignment and its reason are stored.
4. The interface shows the project, its tasks and the assigned agents.
5. At least one worker stub registers from a different PC and sends heartbeats.
6. The S1-10 final checks pass.

## Meeting notes

- Date: 4 October 2026, 21:00, Google Meet (plus fitting-going reminders in the WhatsApp
  group 30 Sep – 5 Oct). Sprint scope-cut decision taken separately on 12 October
  (written into `task-distribution.md`; Thursday 15 Oct emergency demo P0).
- Attendees: Hamza, Baran, Okan, Eray, Fatma, Can, Abdurrahman confirmed the slot
  ("Uygun/Bende uygunum/Olur"). Fatma joined partially (dorm lost power that evening);
  Abdurrahman ran the model on his machine the same night and reported with screenshots.
- Decisions:
  - Install a local model on every PC immediately and test it (`ollama pull qwen3:4b`
    posted by Hamza; `qwen2.5-coder:7b` suggested for stronger coding machines; the team
    later settled the six workers on `qwen3:4b` — see `task-distribution.md`).
  - Workflow: GitHub Issues are the task source, Trello mirrors them for the course;
    one branch per card, one PR per card, no direct pushes to `main`.
  - Roles per card as in the backlog table above (Eray switched from agent list to
    worker/LLM, Can owns the database — recorded in the Oct 12 distribution).
