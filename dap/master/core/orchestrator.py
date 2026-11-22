"""Runs a project on the workers over A2A (contract sections 8 and 13).

Owner: Baran - Sprint 3.

    start_run(project_id) -> bool       False when this project is already running
    run_project(project_id, ...)        the work itself (start_run calls it in a thread)

For one run:
- Every assigned task goes to its agent when all the tasks in its depends_on are
  completed; it gets their files, and those of the tasks before them, as
  dependency_files (the testing task also sees backend/database.py). Tasks without open
  dependencies are sent at once, so they run in parallel on different agents
  (one agent runs its tasks one after another).
- An agent that is offline or has no A2A address is replaced with the section 8
  selection among the online agents; with none online the task fails with
  "no online agent". A task whose dependency failed fails with "dependency failed".
- The master asks each worker every A2A_POLL_INTERVAL_SEC. A task fails when it
  is not finished after TASK_TIMEOUT_SEC or when its worker is unreachable three
  times in a row. Every result is stored (results.store_task_result) and every
  completed task is committed to workspace/<project_id>/ (integrator).
- Project status: in_progress while running, then integrating, then completed
  (all tasks completed) or failed.
- Integrating: when all tasks completed, the master runs its acceptance check
  (acceptance.py) on workspace/<project_id>/; an application that does not even
  start fails the project. The result is acceptance.json in the project folder.
- A new run ("Run again" in the UI) sends the failed tasks again, to their agent
  (or a replacement, as above); attempt counts the tries, the old error stays stored.
Choosing another agent for a failed task within one run is Sprint 4.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

from dap.master import a2a_client
from dap.master.config import get_settings
from dap.master.core import acceptance, integrator, selector
from dap.master.db import repositories, results
from dap.shared.enums import (
    A2A_TO_TASK_STATUS,
    A2ATaskState,
    AgentStatus,
    ProjectStatus,
    TaskStatus,
)
from dap.shared.schemas import (
    A2ATask,
    Agent,
    DapTaskOutput,
    DapTaskPayload,
    GeneratedFile,
    Task,
    TaskResult,
    first_data,
)

logger = logging.getLogger(__name__)

UNREACHABLE_LIMIT = 3

_running: set[str] = set()
_running_lock = threading.Lock()


def is_running(project_id: str) -> bool:
    with _running_lock:
        return project_id in _running


def start_run(project_id: str) -> bool:
    """Start run_project in a background thread; False when it already runs."""
    with _running_lock:
        if project_id in _running:
            return False
        _running.add(project_id)

    def work() -> None:
        try:
            run_project(project_id)
        except Exception:  # never let a run die silently
            logger.exception("Run of project %s crashed", project_id)
            repositories.set_project_status(project_id, ProjectStatus.FAILED)
        finally:
            with _running_lock:
                _running.discard(project_id)

    threading.Thread(target=work, name=f"run-{project_id[:8]}", daemon=True).start()
    return True


@dataclass
class _Sent:
    agent: Agent
    remote_id: str
    sent_at: float
    unreachable: int = 0


@dataclass
class _Run:
    project_id: str
    run_id: str
    requirement_text: str
    token: str
    client: object
    timeout: float
    waiting: dict[str, Task]
    sent: dict[str, _Sent] = field(default_factory=dict)
    files: dict[str, list[GeneratedFile]] = field(default_factory=dict)
    status: dict[str, TaskStatus] = field(default_factory=dict)


def run_project(project_id: str, *, client=a2a_client, poll_interval: float | None = None,
                task_timeout: float | None = None) -> ProjectStatus:
    """Send, follow and collect every task of the project; return the final status."""
    settings = get_settings()
    project = repositories.get_project(project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} does not exist")
    poll = settings.a2a_poll_interval_sec if poll_interval is None else poll_interval
    tasks = repositories.list_tasks(project_id)
    run = _Run(
        project_id=project_id, run_id=str(uuid.uuid4()),
        requirement_text=project.requirement_text, token=settings.agent_token, client=client,
        timeout=settings.task_timeout_sec if task_timeout is None else task_timeout,
        # in_progress here means a run that stopped half way, failed one that failed in an
        # earlier run: send those tasks again.
        waiting={t.id: t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED,
                                                       TaskStatus.IN_PROGRESS, TaskStatus.FAILED)},
        status={t.id: t.status for t in tasks},
    )
    for task_id, task in run.waiting.items():
        run.status[task_id] = TaskStatus.ASSIGNED if task.assigned_agent_id else TaskStatus.PENDING
    # Tasks completed in an earlier run still give their files to the tasks that need them.
    for result in results.list_project_results(project_id):
        if result.success and run.status.get(result.task_id) == TaskStatus.COMPLETED:
            run.files[result.task_id] = result.files
    repositories.set_project_status(project_id, ProjectStatus.IN_PROGRESS)
    integrator.prepare(project_id)
    repositories.mark_stale_agents_offline(settings.heartbeat_timeout_sec)
    logger.info("Run %s of project %s: %d tasks", run.run_id, project_id, len(run.waiting))

    while run.waiting or run.sent:
        before = len(run.waiting)
        _send_ready_tasks(run)
        if not run.sent and len(run.waiting) == before:
            # Nothing runs and nothing can start: a dependency will never finish.
            for task in list(run.waiting.values()):
                del run.waiting[task.id]
                _fail(run, task, task.assigned_agent_id, "dependency never finished")
            break
        _poll_sent_tasks(run)
        if run.waiting or run.sent:
            time.sleep(poll)

    repositories.set_project_status(project_id, ProjectStatus.INTEGRATING)
    done = bool(run.status) and all(s == TaskStatus.COMPLETED for s in run.status.values())
    if done:
        report = acceptance.check(project_id, acceptance.expected_records(tasks))
        results.record_event("acceptance", report["summary"], project_id=project_id)
        done = report["started"]
    final = ProjectStatus.COMPLETED if done else ProjectStatus.FAILED
    repositories.set_project_status(project_id, final)
    logger.info("Run %s of project %s finished: %s", run.run_id, project_id, final.value)
    return final


# ------------------------------------------------------------------- sending


def _send_ready_tasks(run: _Run) -> None:
    for task_id, task in list(run.waiting.items()):
        deps = [run.status.get(dep) for dep in task.depends_on]
        if any(s == TaskStatus.FAILED for s in deps):
            del run.waiting[task_id]
            _fail(run, task, task.assigned_agent_id, "dependency failed")
        elif all(s == TaskStatus.COMPLETED for s in deps):
            del run.waiting[task_id]
            _send(run, task)


def _dependency_files(run: _Run, task: Task) -> list[GeneratedFile]:
    """Files of every completed task this one depends on, directly or through others."""
    depends = {t.id: t.depends_on for t in repositories.list_tasks(run.project_id)}
    seen: list[str] = []
    stack = list(task.depends_on)
    while stack:
        dep = stack.pop(0)
        if dep not in seen:
            seen.append(dep)
            stack.extend(depends.get(dep, []))
    files: dict[str, GeneratedFile] = {}
    for dep in reversed(seen):  # earlier tasks first; a later file of one path wins
        for file in run.files.get(dep, []):
            files[file.path] = file
    return list(files.values())


def _usable(agent: Agent | None) -> bool:
    return agent is not None and agent.status != AgentStatus.OFFLINE and bool(agent.a2a_url)


def _send(run: _Run, task: Task) -> None:
    agent = repositories.get_agent(task.assigned_agent_id) if task.assigned_agent_id else None
    if not _usable(agent):
        repositories.mark_stale_agents_offline(get_settings().heartbeat_timeout_sec)
        candidates = [a for a in repositories.list_agents() if _usable(a)]
        choice = selector.select_agent(task, candidates)
        if choice is None:
            _fail(run, task, task.assigned_agent_id, "no online agent")
            return
        agent, reason = choice
        task = repositories.assign_task(task.id, agent.agent_id, f"reassigned at run: {reason}")
        logger.info("Task %s reassigned to %s", task.title, agent.agent_id)

    payload = DapTaskPayload(
        task_id=task.id, project_id=run.project_id, type=task.type, title=task.title,
        description=task.description, requirement_text=run.requirement_text,
        target_files=integrator.TEMPLATE_FILES.get(task.type, []),
        dependency_files=_dependency_files(run, task),
    )
    repositories.increment_attempt(task.id)
    try:
        remote = run.client.send_task(agent.a2a_url, payload, run.token)
    except a2a_client.A2AError as exc:
        _fail(run, task, agent.agent_id, f"could not send the task: {exc}")
        return
    repositories.set_task_status(task.id, TaskStatus.IN_PROGRESS, remote_task_id=remote.id)
    run.status[task.id] = TaskStatus.IN_PROGRESS
    run.sent[task.id] = _Sent(agent=agent, remote_id=remote.id, sent_at=time.monotonic())
    logger.info("Sent %s to %s at %s (remote task %s)", task.title, agent.agent_id,
                agent.a2a_url, remote.id)


# ------------------------------------------------------------------- following


def _poll_sent_tasks(run: _Run) -> None:
    for task_id, sent in list(run.sent.items()):
        task = repositories.get_task(task_id)
        try:
            remote = run.client.get_task(sent.agent.a2a_url, sent.remote_id, run.token)
        except a2a_client.A2AError as exc:
            sent.unreachable += 1
            logger.warning("Task %s: %s (%d/%d)", task.title, exc, sent.unreachable,
                           UNREACHABLE_LIMIT)
            if sent.unreachable >= UNREACHABLE_LIMIT:
                del run.sent[task_id]
                _fail(run, task, sent.agent.agent_id, f"worker unreachable: {exc}")
            continue
        sent.unreachable = 0
        status = A2A_TO_TASK_STATUS[remote.status.state]
        if status == TaskStatus.COMPLETED:
            del run.sent[task_id]
            _complete(run, task, sent, remote)
        elif status == TaskStatus.FAILED:
            del run.sent[task_id]
            _fail(run, task, sent.agent.agent_id, _error_text(remote), sent)
        elif time.monotonic() - sent.sent_at > run.timeout:
            del run.sent[task_id]
            _fail(run, task, sent.agent.agent_id,
                  f"timeout: not finished after {run.timeout:g} s", sent)


def _error_text(remote: A2ATask) -> str:
    message = remote.status.message
    texts = [p.text for p in message.parts if p.text] if message else []
    return "; ".join(texts) or f"the worker reported {remote.status.state.value}"


def _complete(run: _Run, task: Task, sent: _Sent, remote: A2ATask) -> None:
    data = first_data(remote.artifacts[0].parts) if remote.artifacts else None
    try:
        output = DapTaskOutput.model_validate(data)
        result = TaskResult(
            task_id=task.id, agent_id=sent.agent.agent_id, success=True, summary=output.summary,
            files=output.files, duration_ms=max(output.duration_ms, 0),
            tokens_used=max(output.prompt_tokens + output.completion_tokens, 0),
        )
        integrator.commit_task(run.project_id, task, sent.agent.agent_id, output.files,
                               agent=sent.agent)
        results.store_task_result(result, run_id=run.run_id)
    except Exception as exc:  # bad output, unsafe path, disk problem
        _fail(run, task, sent.agent.agent_id, f"result could not be stored: {exc}", sent)
        return
    run.files[task.id] = output.files
    run.status[task.id] = TaskStatus.COMPLETED
    logger.info("Completed %s by %s", task.title, sent.agent.agent_id)


def _fail(run: _Run, task: Task, agent_id: str | None, error: str,
          sent: _Sent | None = None) -> None:
    """Mark the task failed and store the reason as a failed result when it has an agent."""
    run.status[task.id] = TaskStatus.FAILED
    current = repositories.get_task(task.id)
    if agent_id and current is not None and current.assigned_agent_id == agent_id \
            and current.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
        elapsed = int((time.monotonic() - sent.sent_at) * 1000) if sent else 0
        results.store_task_result(TaskResult(
            task_id=task.id, agent_id=agent_id, success=False, summary=task.title,
            error=error, duration_ms=elapsed, tokens_used=0,
        ), run_id=run.run_id)  # also sets the task to failed
    else:
        repositories.set_task_status(task.id, TaskStatus.FAILED)
        results.record_event("task_failed", error, task_id=task.id)
    logger.warning("Task %s failed: %s", task.title, error)
