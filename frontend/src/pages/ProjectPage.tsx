import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  assignProject,
  decomposeProject,
  getAgents,
  getProject,
  getTasks,
} from "../api/client";
import type { Task } from "../api/types";
import Badge from "../components/Badge";
import TypeBadge from "../components/TypeBadge";
import { usePolling } from "../hooks/usePolling";

export default function ProjectPage() {
  const { id = "" } = useParams();
  const [busy, setBusy] = useState<"decompose" | "assign" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [project, tasks, agents] = await Promise.all([
      getProject(id),
      getTasks(id),
      getAgents(),
    ]);
    return { project, tasks, agents };
  }, [id]);
  const { data, error, loading, refresh } = usePolling(load);

  async function run(kind: "decompose" | "assign") {
    setBusy(kind);
    setActionError(null);
    try {
      await (kind === "decompose" ? decomposeProject(id) : assignProject(id));
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <p className="text-slate-500">Loading project...</p>;
  if (error || !data) {
    return (
      <p role="alert" className="text-red-700">
        Could not load project: {error}{" "}
        <Link to="/" className="underline">
          Back to projects
        </Link>
      </p>
    );
  }

  const { project, tasks, agents } = data;
  const hasTasks = tasks.length > 0;
  const hasAssignments = tasks.some((t) => t.assigned_agent_id);

  const agentName = (agentId: string | null) =>
    agentId ? (agents.find((a) => a.agent_id === agentId)?.name ?? agentId) : "-";
  const dependsOn = (task: Task) =>
    task.depends_on.length
      ? task.depends_on.map((d) => tasks.find((t) => t.id === d)?.title ?? d).join(", ")
      : "-";

  const steps = [
    { label: "Requirement", done: true },
    { label: "Master", done: hasTasks },
    { label: "Tasks", done: hasAssignments },
  ];

  return (
    <>
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <Link to="/" className="text-sm text-violet-700 hover:underline">
          ← All projects
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-bold sm:text-3xl">{project.name}</h2>
          <Badge value={project.status} />
        </div>
        <p className="mt-3 text-slate-600">{project.requirement_text}</p>

        <ol className="mt-6 flex flex-wrap items-center gap-2 text-sm font-medium">
          {steps.map((step, i) => (
            <li key={step.label} className="flex items-center gap-2">
              <span
                className={`rounded-full px-3 py-1 ${
                  step.done ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                }`}
              >
                {step.done ? "✓ " : ""}
                {step.label}
              </span>
              {i < steps.length - 1 && <span className="text-slate-400">→</span>}
            </li>
          ))}
        </ol>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => run("decompose")}
            disabled={busy !== null}
            className="rounded-xl bg-violet-700 px-5 py-3 font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "decompose" ? "Decomposing..." : "Decompose"}
          </button>
          <button
            onClick={() => run("assign")}
            disabled={busy !== null || !hasTasks}
            className="rounded-xl border border-violet-700 px-5 py-3 font-semibold text-violet-800 hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "assign" ? "Assigning..." : "Assign agents"}
          </button>
        </div>
        {actionError && (
          <p role="alert" className="mt-3 text-red-700">
            {actionError}
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="text-2xl font-bold">Task board ({tasks.length})</h2>
        {!hasTasks ? (
          <p className="mt-4 text-slate-500">No tasks yet. Press "Decompose".</p>
        ) : (
          <>
            {/* Desktop: table */}
            <div className="mt-4 hidden overflow-x-auto md:block">
              <table className="w-full text-left text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">Title</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Assigned agent</th>
                    <th className="py-2 pr-4">Reason</th>
                    <th className="py-2">Depends on</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {tasks.map((task) => (
                    <tr key={task.id}>
                      <td className="py-3 pr-4 font-semibold">{task.title}</td>
                      <td className="py-3 pr-4">
                        <TypeBadge value={task.type} />
                      </td>
                      <td className="py-3 pr-4">
                        <Badge value={task.status} />
                      </td>
                      <td className="py-3 pr-4">{agentName(task.assigned_agent_id)}</td>
                      <td className="py-3 pr-4">{task.assignment_reason ?? "-"}</td>
                      <td className="py-3">{dependsOn(task)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Phone: one card per task */}
            <div className="mt-4 space-y-3 md:hidden">
              {tasks.map((task) => (
                <article key={task.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-semibold">{task.title}</h3>
                    <TypeBadge value={task.type} />
                  </div>
                  <div className="mt-2">
                    <Badge value={task.status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-700">
                    Agent: {agentName(task.assigned_agent_id)}
                  </p>
                  {task.assignment_reason && (
                    <p className="mt-1 text-sm text-slate-500">{task.assignment_reason}</p>
                  )}
                  <p className="mt-1 text-sm text-slate-500">Depends on: {dependsOn(task)}</p>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </>
  );
}
