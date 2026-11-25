// Shared building blocks: cards, status dots, numbers, bars and the activity list.
import type { ReactNode } from "react";
import type { LogLine, Tone } from "../hooks/useEventLog";
import { clock } from "../lib/format";

export type ToneName = Tone | "mute";

export const fg = (tone: ToneName) => `var(--${tone})`;
export const soft = (tone: ToneName) => `var(--${tone}-soft)`;

// Every agent, task and project status: its colour, a plain label and what it means.
const STATUS: Record<string, { tone: ToneName; label: string; hint: string }> = {
  idle: { tone: "ok", label: "Ready", hint: "Online and waiting for a task" },
  busy: { tone: "warn", label: "Working", hint: "Running a task right now" },
  offline: { tone: "mute", label: "Offline", hint: "No heartbeat in the last 30 seconds" },
  created: { tone: "mute", label: "New", hint: "Not planned yet: press Decompose" },
  decomposing: { tone: "plan", label: "Planning", hint: "The master is splitting the requirement into tasks" },
  in_progress: { tone: "warn", label: "Running", hint: "Agents are working on the tasks" },
  integrating: { tone: "plan", label: "Checking", hint: "The master is testing the generated application" },
  completed: { tone: "ok", label: "Completed", hint: "Finished successfully" },
  failed: { tone: "bad", label: "Failed", hint: "Something went wrong: see the details" },
  pending: { tone: "mute", label: "Waiting", hint: "No agent chosen yet" },
  assigned: { tone: "plan", label: "Assigned", hint: "An agent is chosen; the task has not started" },
};
const ACTIVE = new Set(["busy", "decomposing", "in_progress", "integrating"]);

export function statusInfo(status: string) {
  return STATUS[status] ?? { tone: "info" as ToneName, label: status.replace("_", " "), hint: status };
}

// A small coloured dot; it pulses while something is happening.
export function Dot({ status }: { status: string }) {
  const color = fg(statusInfo(status).tone);
  return (
    <span className="relative inline-flex h-2 w-2 shrink-0">
      {ACTIVE.has(status) && (
        <span className="absolute inset-0 animate-ping rounded-full opacity-60" style={{ background: color }} />
      )}
      <span className="relative h-2 w-2 rounded-full" style={{ background: color }} />
    </span>
  );
}

export function Card({
  title,
  description,
  right,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card min-w-0 p-4 sm:p-5 ${className}`}>
      {(title || right) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-ink">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: ToneName;
}) {
  return (
    <div className="card min-w-0 px-4 py-3">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold" style={{ color: tone ? fg(tone) : undefined }}>
        {value}
      </p>
      {hint && <p className="mt-0.5 truncate text-xs text-muted">{hint}</p>}
    </div>
  );
}

// A thin bar for a 0-100 value.
export function Bar({ value, tone = "info" }: { value: number; tone?: ToneName }) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-sunken" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full transition-all" style={{ width: `${width}%`, background: fg(tone) }} />
    </div>
  );
}

// What happened, newest first, in plain sentences.
export function ActivityList({ lines, empty, height = "max-h-80" }: { lines: LogLine[]; empty: string; height?: string }) {
  if (lines.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ol className={`${height} space-y-2 overflow-y-auto pr-1`} aria-live="polite">
      {[...lines].reverse().map((line) => (
        <li key={line.id} className="flex gap-3 text-sm">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: fg(line.tone) }} />
          <span className="min-w-0 flex-1 text-ink">{line.text}</span>
          <time className="shrink-0 font-mono text-xs text-muted">{clock(line.at)}</time>
        </li>
      ))}
    </ol>
  );
}
