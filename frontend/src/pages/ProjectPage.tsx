import { useCallback, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ACCEPTANCE_FILE } from "../api/acceptance";
import type { AcceptanceReport } from "../api/acceptance";
import {
  assignProject,
  cancelProject,
  decomposeProject,
  getAcceptance,
  getAgents,
  getFiles,
  getProject,
  getResults,
  getTasks,
  requestFollowup,
  runProject,
} from "../api/client";
import type { Project, Task, TaskResult } from "../api/types";
import AcceptanceMatrix from "../components/AcceptanceMatrix";
import Badge from "../components/Badge";
import FileExplorer from "../components/FileExplorer";
import OpenAppButton from "../components/OpenAppButton";
import Pipeline from "../components/Pipeline";
import Timeline from "../components/Timeline";
import TypeBadge from "../components/TypeBadge";
import { ActivityList, Card, Stat, fg, soft } from "../components/ui";
import type { ToneName } from "../components/ui";
import { useEventLog } from "../hooks/useEventLog";
import type { Watched } from "../hooks/useEventLog";
import { useNow } from "../hooks/useNow";
import { usePolling } from "../hooks/usePolling";
import { duration, stamp, tokens } from "../lib/format";

type Action = "decompose" | "assign" | "run";

const greeting = () => "Following this project.";

function taskLine(task: Task, agentName: (id: string | null) => string): Watched["told"] {
  const what = `${task.type[0].toUpperCase()}${task.type.slice(1)} task`;
  return (before, after) => {
    if (before === undefined) return null; // the steps above show the current state
    if (after === "assigned") return { text: `${what} given to ${agentName(task.assigned_agent_id)}.`, tone: "plan" };
    if (after === "in_progress") return { text: `${what} sent to ${agentName(task.assigned_agent_id)}.`, tone: "warn" };
    if (after === "completed") return { text: `${what} completed; its files are saved.`, tone: "ok" };
    if (after === "failed") return { text: `${what} failed.`, tone: "bad" };
    return { text: `${what}: ${after}.`, tone: "info" };
  };
}

// What the user should do (or wait for) now, in plain words.
function nextStep(project: Project, tasks: Task[], acceptance: AcceptanceReport | null) {
  const failedTask = tasks.find((t) => t.status === "failed");
  const running = tasks.some((t) => t.status === "in_progress");
  const step = (tone: ToneName, title: string, text: string, action?: Action, button?: string) => ({ tone, title, text, action, button });

  if (project.status === "decomposing") return step("plan", "The master is planning", "It reads the requirement and splits it into tasks. This takes a few seconds.");
  if (tasks.length === 0)
    return step("info", "Step 1 of 3: plan the work", "The master reads the requirement and splits it into four tasks: database, backend, frontend and testing.", "decompose", "Decompose");
  if (!tasks.some((t) => t.assigned_agent_id))
    return step("info", "Step 2 of 3: choose the agents", "The master scores every online agent for every task (its skills, its role and how busy it is) and picks the best one.", "assign", "Assign agents");
  if (running) {
    const now = tasks.find((t) => t.status === "in_progress");
    return step("warn", "Agents are working", `Now: the ${now?.type} task. Tasks run in order, because each one builds on the files of the one before.`);
  }
  if (project.status === "integrating") return step("plan", "The master is checking the app", "It starts the generated application and tries every page and route.");
  if (project.status === "completed")
    return step(
      "ok",
      "Done",
      (acceptance ? `All tasks are completed. Master check: ${acceptance.summary}. ` : "All tasks are completed. ")
        + 'Press "Open the app" to use the generated application; the files are below.',
    );
  if (project.status === "failed" || failedTask)
    return step("bad", "Something failed", failedTask ? `The ${failedTask.type} task failed; open its report below. You can run the project again.` : "Open the task reports below, then run again.", "run", "Run again");
  return step("info", "Step 3 of 3: run on the agents", "Each task is sent to its agent. The agents write the code; the master saves it and checks the finished app.", "run", "Run on agents");
}

export default function ProjectPage() {
  const { id = "" } = useParams();
  const now = useNow();
  const [busy, setBusy] = useState<Action | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [changeText, setChangeText] = useState("");
  const [sendingChange, setSendingChange] = useState(false);

  const load = useCallback(async () => {
    const [project, tasks, agents, results, files] = await Promise.all([
      getProject(id),
      getTasks(id),
      getAgents(),
      getResults(id),
      getFiles(id),
    ]);
    const acceptance = files.includes(ACCEPTANCE_FILE) ? await getAcceptance(id) : null;
    return { project, tasks, agents, results, files, acceptance };
  }, [id]);
  const { data, error, loading, refresh } = usePolling(load);

  // The newest result of every task (an earlier run may have left an older one).
  const latest = useMemo(() => {
    const map = new Map<string, TaskResult>();
    for (const r of data?.results ?? []) map.set(r.task_id, r);
    return map;
  }, [data]);

  const watched = useMemo(() => {
    if (!data) return null;
    const agentName = (agentId: string | null) => data.agents.find((a) => a.agent_id === agentId)?.name ?? agentId ?? "an agent";
    const items: Record<string, Watched> = {};
    for (const t of data.tasks) items[t.id] = { state: t.status, told: taskLine(t, agentName) };
    if (data.acceptance) {
      const failed = data.acceptance.failed;
      items.acceptance = {
        state: data.acceptance.summary,
        told: (_b, after) => ({ text: `Master check: ${after}.`, tone: failed ? "warn" : "ok" }),
      };
    }
    return items;
  }, [data]);
  const lines = useEventLog(watched, greeting);

  async function act(kind: Action) {
    setBusy(kind);
    setActionError(null);
    const action = { decompose: decomposeProject, assign: assignProject, run: runProject }[kind];
    try {
      await action(id);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function cancelRun() {
    if (!window.confirm("Stop this project? Its unfinished tasks will fail; \"Run again\" continues later.")) return;
    setCancelling(true);
    setActionError(null);
    try {
      await cancelProject(id);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setCancelling(false);
    }
  }

  async function sendChange() {
    const instruction = changeText.trim();
    if (instruction.length < 10) {
      setActionError("Describe the change in at least 10 characters.");
      return;
    }
    setSendingChange(true);
    setActionError(null);
    try {
      await requestFollowup(id, instruction);
      setChangeText("");
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setSendingChange(false);
    }
  }

  if (loading) return <p className="text-sm text-muted">Loading the project...</p>;
  if (!data) {
    return (
      <p role="alert" className="text-sm text-bad">
        Could not load the project: {error}{" "}
        <Link to="/" className="underline">
          Back to the overview
        </Link>
      </p>
    );
  }

  const { project, tasks, agents, files, acceptance } = data;
  const hasTasks = tasks.length > 0;
  const hasAssignments = tasks.some((t) => t.assigned_agent_id);
  const running = tasks.some((t) => t.status === "in_progress") || ["decomposing", "integrating"].includes(project.status);
  // A run can be stopped while tasks run or wait to be sent (not while decomposing).
  const stoppable = tasks.some((t) => t.status === "in_progress") || ["in_progress", "integrating"].includes(project.status);
  const next = nextStep(project, tasks, acceptance);
  const results = [...latest.values()];
  const totalTokens = results.reduce((sum, r) => sum + r.tokens_used, 0);
  const agentTime = results.reduce((sum, r) => sum + r.duration_ms, 0);
  const settled = project.status === "completed" || project.status === "failed";
  const elapsed = (settled ? new Date(project.updated_at).getTime() : now) - new Date(project.created_at).getTime();
  const done = tasks.filter((t) => t.status === "completed").length;
  const tried = acceptance ? acceptance.passed + acceptance.failed : 0;
  // The template's main.py is there from the start; the app exists once the backend task wrote it.
  const hasApp = tasks.some((t) => t.type === "backend" && t.status === "completed");
  const labels: Record<Action, string> = { decompose: "Decompose", assign: "Assign agents", run: "Run on agents" };
  const allowed: Record<Action, boolean> = { decompose: true, assign: hasTasks, run: hasAssignments };

  return (
    <>
      <div>
        <Link to="/" className="text-sm text-accent hover:underline">
          ← Overview
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold text-ink">{project.name}</h1>
            <p className="text-sm text-muted">Created {stamp(project.created_at)}</p>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            {hasApp && <OpenAppButton projectId={project.id} primary={project.status === "completed"} />}
            <Badge value={project.status} large />
          </div>
        </div>
      </div>

      <section className="card flex flex-wrap items-center justify-between gap-4 border-l-4 p-4 sm:p-5" style={{ borderLeftColor: fg(next.tone) }}>
        <div className="min-w-0 max-w-3xl">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: fg(next.tone) }}>
            Next step
          </p>
          <p className="mt-0.5 text-lg font-semibold text-ink">{next.title}</p>
          <p className="mt-1 text-sm text-muted">{next.text}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {next.action && (
            <button onClick={() => act(next.action!)} disabled={busy !== null || running} className="btn btn-primary">
              {busy === next.action ? "Working..." : next.button}
            </button>
          )}
          {stoppable && (
            <button onClick={cancelRun} disabled={cancelling} className="btn btn-danger" title="Stops the run; unfinished tasks fail">
              {cancelling ? "Stopping..." : "■ Cancel run"}
            </button>
          )}
          <details className="relative">
            <summary className="btn cursor-pointer list-none">More actions</summary>
            <div className="card absolute right-0 z-10 mt-1 w-56 space-y-1 p-2">
              {(["decompose", "assign", "run"] as Action[]).map((a, i) => (
                <button
                  key={a}
                  onClick={() => act(a)}
                  disabled={busy !== null || running || !allowed[a]}
                  className="w-full rounded-md px-3 py-2 text-left text-sm text-ink hover:bg-sunken disabled:opacity-40"
                >
                  {i + 1}. {labels[a]}
                </button>
              ))}
            </div>
          </details>
        </div>
        {actionError && (
          <p role="alert" className="w-full rounded-md px-3 py-2 text-sm" style={{ color: fg("bad"), background: soft("bad") }}>
            {actionError}
          </p>
        )}
        {error && <p className="w-full text-xs text-warn">Connection problem, retrying: {error}</p>}
      </section>

      {project.status === "completed" && (
        <section className="card p-4 sm:p-5">
          <p className="text-sm font-semibold text-ink">Request a change</p>
          <p className="mt-0.5 text-sm text-muted">
            The agents apply your request to the finished application and run it again (they keep what works).
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={changeText}
              onChange={(e) => setChangeText(e.target.value)}
              placeholder="e.g. Add a due date to every task and sort the list by it"
              className="input flex-1"
              onKeyDown={(e) => e.key === "Enter" && sendChange()}
            />
            <button
              onClick={sendChange}
              disabled={sendingChange || changeText.trim().length < 10}
              className="btn btn-primary"
            >
              {sendingChange ? "Working..." : "Apply the change"}
            </button>
          </div>
        </section>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Stat label="Tasks done" value={`${done} / ${tasks.length}`} hint={`${tasks.filter((t) => t.status === "failed").length} failed`} tone={done && done === tasks.length ? "ok" : undefined} />
        <Stat label="Total time" value={duration(elapsed)} hint={settled ? "from creation to the end" : "since the project was created"} />
        <Stat label="Agent time" value={duration(agentTime)} hint="time the agents spent, added up" />
        <Stat label="Tokens" value={tokens(totalTokens)} hint={agentTime ? `${(totalTokens / (agentTime / 1000)).toFixed(1)} tokens per second` : "words the models wrote"} />
        <Stat
          label="Master check"
          value={acceptance ? (acceptance.started ? `${acceptance.passed} / ${tried}` : "Failed") : "–"}
          hint={acceptance ? "checks passed" : "after the last task"}
          tone={acceptance ? (acceptance.started && !acceptance.failed ? "ok" : "bad") : undefined}
        />
      </div>

      <Card title="Steps" description="Each task is written by one agent, in this order; the master checks the result at the end. Hover a value for details.">
        {hasTasks ? (
          <Pipeline tasks={tasks} results={latest} agents={agents} acceptance={acceptance} projectStatus={project.status} />
        ) : (
          <p className="text-sm text-muted">No tasks yet. Press "Decompose" above.</p>
        )}
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Master check" description="Does the generated app really work? One row per kind of record.">
          <AcceptanceMatrix report={acceptance} />
        </Card>
        <Card title="Timeline" description="When each task ran and how long it took.">
          <Timeline tasks={tasks} results={latest} agents={agents} now={now} />
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-5">
        <Card title="Task reports" description="What the master asked for, and what the agent answered. Click a task to open it." className="xl:col-span-3">
          {!hasTasks ? (
            <p className="text-sm text-muted">Nothing planned yet.</p>
          ) : (
            <div className="space-y-2">
              {tasks.map((task) => {
                const result = latest.get(task.id);
                return (
                  <details key={task.id} className="group rounded-lg border border-line">
                    <summary className="flex cursor-pointer list-none items-center gap-3 px-3 py-2.5 hover:bg-sunken">
                      <TypeBadge value={task.type} />
                      <span className="min-w-0 flex-1 truncate text-sm text-ink">{task.title}</span>
                      <Badge value={task.status} />
                      <span className="text-muted transition group-open:rotate-180">▾</span>
                    </summary>
                    <div className="space-y-3 border-t border-line px-3 py-3 text-sm">
                      <div>
                        <p className="text-xs font-medium text-muted">The master's instructions</p>
                        <p className="mt-1 whitespace-pre-wrap text-ink">{task.description}</p>
                      </div>
                      {result && (
                        <div>
                          <p className="text-xs font-medium" style={{ color: fg(result.success ? "ok" : "bad") }}>
                            {result.success ? "The agent's answer" : "Why it failed"}
                          </p>
                          <p className="mt-1 whitespace-pre-wrap" style={{ color: result.success ? undefined : fg("bad") }}>
                            {result.success ? result.summary : result.error}
                          </p>
                          <p className="mt-1 text-xs text-muted">
                            Files: {result.files.map((f) => f.path).join(", ") || "none"} · {duration(result.duration_ms)} · {tokens(result.tokens_used)} tokens
                          </p>
                        </div>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </Card>
        <Card title="Activity" description="Changes since you opened the page, newest first." className="xl:col-span-2">
          <ActivityList lines={lines.filter((l) => l.text !== greeting())} empty="Nothing has changed yet." />
        </Card>
      </div>

      <Card title={`Generated application (${files.length} files)`} description={`Saved in workspace/${project.id}/ on the master, one git commit per task.`}>
        <FileExplorer projectId={id} files={files} />
      </Card>

      <details className="card p-4 text-sm">
        <summary className="cursor-pointer font-medium text-ink">Requirement text</summary>
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap font-sans text-sm text-muted">{project.requirement_text}</pre>
      </details>
    </>
  );
}
