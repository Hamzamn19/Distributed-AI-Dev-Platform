import type { Agent, Task, TaskResult } from "../api/types";
import { duration } from "../lib/format";
import { TYPE_COLOR } from "./TypeBadge";

// When each task ran, on one time axis. A finished task ends when its status last
// changed and started `duration_ms` before; a running task grows until now.
export default function Timeline({
  tasks,
  results,
  agents,
  now,
}: {
  tasks: Task[];
  results: Map<string, TaskResult>;
  agents: Agent[];
  now: number;
}) {
  const bars = tasks
    .map((task) => {
      const result = results.get(task.id);
      const changed = new Date(task.updated_at).getTime();
      if (result && task.status !== "in_progress") {
        return { task, start: changed - result.duration_ms, end: changed, live: false };
      }
      if (task.status === "in_progress") return { task, start: changed, end: now, live: true };
      return null;
    })
    .filter((bar) => bar !== null);

  if (bars.length === 0) {
    return <p className="text-sm text-muted">Appears once the agents start working.</p>;
  }
  const from = Math.min(...bars.map((b) => b.start));
  const to = Math.max(...bars.map((b) => b.end));
  const span = Math.max(to - from, 1000);
  const agentName = (task: Task) =>
    agents.find((a) => a.agent_id === (results.get(task.id)?.agent_id ?? task.assigned_agent_id))?.name ?? "-";

  return (
    <div className="space-y-2.5">
      {bars.map(({ task, start, end, live }) => {
        const color = TYPE_COLOR[task.type] ?? "var(--accent)";
        return (
          <div key={task.id} className="grid grid-cols-[5.5rem_1fr] items-center gap-3">
            <span className="truncate text-xs font-medium capitalize" style={{ color }}>
              {task.type}
            </span>
            <div className="relative h-6 rounded-md bg-sunken">
              <div
                className={`absolute top-0 h-6 min-w-1 rounded-md ${live ? "animate-pulse" : ""}`}
                style={{
                  left: `${((start - from) / span) * 100}%`,
                  width: `${((end - start) / span) * 100}%`,
                  background: color,
                }}
                title={`${task.title} · ${agentName(task)} · ${duration(end - start)}`}
              />
            </div>
          </div>
        );
      })}
      <div className="grid grid-cols-[5.5rem_1fr] gap-3 text-xs text-muted">
        <span />
        <div className="flex justify-between">
          <span>start</span>
          <span>{duration(span / 2)}</span>
          <span>{duration(span)}</span>
        </div>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-muted">
        {bars.map(({ task, start, end }) => (
          <li key={task.id}>
            <span className="font-medium capitalize text-ink">{task.type}</span>: {agentName(task)}, {duration(end - start)}
          </li>
        ))}
      </ul>
    </div>
  );
}
