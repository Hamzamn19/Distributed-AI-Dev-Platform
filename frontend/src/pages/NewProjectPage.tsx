import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createProject, getProjects } from "../api/client";
import Badge from "../components/Badge";
import { usePolling } from "../hooks/usePolling";

const MIN_LENGTH = 20;

export default function NewProjectPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(() => getProjects(), []);
  const { data: projects, error: listError, loading } = usePolling(loadProjects);

  const length = text.trim().length;
  const canSubmit = name.trim().length > 0 && length >= MIN_LENGTH && !submitting;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const project = await createProject({
        name: name.trim(),
        requirement_text: text.trim(),
      });
      navigate(`/projects/${project.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }

  return (
    <>
      <section className="rounded-2xl bg-gradient-to-br from-violet-700 to-indigo-800 p-5 text-white shadow-lg sm:p-8">
        <p className="text-sm font-medium text-violet-200">NEW PROJECT</p>
        <h2 className="mt-2 text-2xl font-bold sm:text-3xl">Turn your idea into tasks</h2>
        <p className="mt-3 max-w-xl text-violet-100">
          Describe the software you need. The master agent analyzes it and
          distributes the work to suitable agents.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-3">
          <label htmlFor="name" className="sr-only">
            Project name
          </label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            className="w-full rounded-xl border border-white/20 bg-white p-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-violet-300"
          />
          <label htmlFor="requirement" className="sr-only">
            Software requirement
          </label>
          <textarea
            id="requirement"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Example: An online library where members can search and borrow books..."
            className="min-h-32 w-full rounded-xl border border-white/20 bg-white p-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-violet-300"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-violet-100" role={error ? "alert" : undefined}>
              {error ??
                (length < MIN_LENGTH
                  ? `At least ${MIN_LENGTH} characters needed (${length}/${MIN_LENGTH})`
                  : "")}
            </span>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-xl bg-white px-5 py-3 font-semibold text-violet-800 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create project"}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="text-2xl font-bold">Existing projects</h2>
        {loading && <p className="mt-4 text-slate-500">Loading projects...</p>}
        {listError && (
          <p role="alert" className="mt-4 text-red-700">
            Could not load projects: {listError}
          </p>
        )}
        {projects && projects.length === 0 && (
          <p className="mt-4 text-slate-500">No projects yet.</p>
        )}
        <div className="mt-4 divide-y divide-slate-100">
          {projects?.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="flex flex-wrap items-center justify-between gap-3 py-4 hover:bg-slate-50"
            >
              <span className="font-semibold">{project.name}</span>
              <Badge value={project.status} />
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
