import type { ReactNode } from "react";
import type { AcceptanceReport } from "../api/acceptance";
import type { Agent, Task, TaskResult } from "../api/types";
import { duration, tokens } from "../lib/format";
import Badge from "./Badge";
import { TYPE_COLOR, TYPE_HINT } from "./TypeBadge";
import { Bar } from "./ui";

// The steps of a project in order: the four tasks (database -> backend -> frontend ->
// testing), each written by one agent, then the master's check of the finished app.
export default function Pipeline({
  tasks,
  results,
  agents,
  acceptance,
  projectStatus,
}: {
  tasks: Task[];
  results: Map<string, TaskResult>;
  agents: Agent[];
  acceptance: AcceptanceReport | null;
  projectStatus: string;
}) {
  return (
    <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      {tasks.map((task, i) => (
        <TaskStep key={task.id} number={i + 1} task={task} result={results.get(task.id)} agents={agents} />
      ))}
      <CheckStep number={tasks.length + 1} report={acceptance} projectStatus={projectStatus} />
    </ol>
  );
}

function Row({ label, children, title }: { label: string; children: ReactNode; title?: string }) {
  return (
    <div className="flex justify-between gap-2 text-xs" title={title}>
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-ink">{children}</dd>
    </div>
  );
}

// "S=90.0 (coding 40.0, ...)" -> "Chosen with score 90 · hover for why".
function scoreText(reason: string): string {
  const score = reason.match(/S=([\d.]+)/);
  return score ? `Chosen with score ${Math.round(Number(score[1]))} · hover for why` : reason;
}

function TaskStep({ number, task, result, agents }: { number: number; task: Task; result?: TaskResult; agents: Agent[] }) {
  const agent = agents.find((a) => a.agent_id === (result?.agent_id ?? task.assigned_agent_id));
  const color = TYPE_COLOR[task.type] ?? "var(--muted)";
  const seconds = result ? result.duration_ms / 1000 : 0;
  return (
    <li className="card flex min-w-0 flex-col gap-3 border-t-4 p-4" style={{ borderTopColor: color }}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted">Step {number}</p>
          <p className="text-sm font-semibold capitalize" style={{ color }} title={TYPE_HINT[task.type]}>
            {task.type}
          </p>
        </div>
        <Badge value={task.status} />
      </div>
      <p className="line-clamp-2 text-sm text-ink" title={task.title}>
        {task.title}
      </p>
      <dl className="space-y-1 border-t border-line pt-3">
        <Row label="Agent">{agent?.name ?? task.assigned_agent_id ?? "not chosen"}</Row>
        <Row label="Model" title={agent?.model}>{agent?.model ?? "-"}</Row>
        <Row label="Time">{result ? duration(result.duration_ms) : "-"}</Row>
        <Row label="Tokens">
          {result ? `${tokens(result.tokens_used)}${seconds > 0 ? ` · ${(result.tokens_used / seconds).toFixed(1)}/s` : ""}` : "-"}
        </Row>
        {task.attempt > 1 && <Row label="Attempt">{task.attempt}</Row>}
      </dl>
      {task.assignment_reason && (
        <p className="mt-auto truncate text-xs text-muted" title={`Why this agent (the master's score): ${task.assignment_reason}`}>
          {scoreText(task.assignment_reason)}
        </p>
      )}
    </li>
  );
}

function CheckStep({ number, report, projectStatus }: { number: number; report: AcceptanceReport | null; projectStatus: string }) {
  const tried = report ? report.passed + report.failed : 0;
  const state = report
    ? !report.started
      ? "failed"
      : report.failed === 0
        ? "completed"
        : "failed"
    : projectStatus === "integrating"
      ? "integrating"
      : "pending";
  return (
    <li className="card flex min-w-0 flex-col gap-3 border-t-4 border-t-accent p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-muted">Step {number}</p>
          <p className="text-sm font-semibold text-accent">Master check</p>
        </div>
        <Badge value={state} />
      </div>
      <p className="text-sm text-ink">The master starts the app and tries every page and API route.</p>
      <div className="mt-auto space-y-2 border-t border-line pt-3">
        {report ? (
          <>
            <p className="text-sm font-medium" style={{ color: report.started && report.failed === 0 ? "var(--ok)" : "var(--bad)" }}>
              {report.started ? `${report.passed} of ${tried} checks passed` : "The app does not start"}
            </p>
            {report.started && <Bar value={tried ? (report.passed / tried) * 100 : 0} tone={report.failed ? "warn" : "ok"} />}
            {report.rules > 0 && <p className="text-xs text-muted">{report.rules} stopped by a business rule (not an error)</p>}
          </>
        ) : (
          <p className="text-xs text-muted">Runs after the last task.</p>
        )}
      </div>
    </li>
  );
}
