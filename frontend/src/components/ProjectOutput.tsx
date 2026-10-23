import { useCallback, useState } from "react";
import { getFile, getFiles, getResults } from "../api/client";
import type { Agent, Task } from "../api/types";
import { usePolling } from "../hooks/usePolling";

// What the agents produced: one result per task (summary or error) and the files of
// workspace/<project_id>/ with a simple viewer. Refreshed every 3 seconds.
export default function ProjectOutput({
  projectId,
  tasks,
  agents,
}: {
  projectId: string;
  tasks: Task[];
  agents: Agent[];
}) {
  const load = useCallback(async () => {
    const [results, files] = await Promise.all([getResults(projectId), getFiles(projectId)]);
    return { results, files };
  }, [projectId]);
  const { data } = usePolling(load);
  const [open, setOpen] = useState<{ path: string; text: string } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  async function show(path: string) {
    setFileError(null);
    try {
      setOpen({ path, text: await getFile(projectId, path) });
    } catch (e) {
      setFileError(e instanceof Error ? e.message : String(e));
    }
  }

  const title = (taskId: string) => tasks.find((t) => t.id === taskId)?.title ?? taskId;
  const agent = (agentId: string) => {
    const found = agents.find((a) => a.agent_id === agentId);
    return found ? `${found.name} · ${found.model}` : agentId;
  };
  const results = data?.results ?? [];
  const files = data?.files ?? [];

  return (
    <>
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="text-2xl font-bold">Results ({results.length})</h2>
        {results.length === 0 ? (
          <p className="mt-4 text-slate-500">No results yet. Press "Run on agents".</p>
        ) : (
          <div className="mt-4 space-y-3">
            {results.map((r, i) => (
              <article
                key={`${r.task_id}-${i}`}
                className={`rounded-xl border p-4 ${
                  r.success ? "border-emerald-200" : "border-red-200 bg-red-50"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold">{title(r.task_id)}</h3>
                  <span className={r.success ? "text-emerald-700" : "text-red-700"}>
                    {r.success ? "✓ completed" : "✗ failed"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {agent(r.agent_id)} · {(r.duration_ms / 1000).toFixed(1)} s ·{" "}
                  {r.tokens_used} tokens · {r.files.length} files
                </p>
                <p className="mt-2 text-sm">{r.success ? r.summary : r.error}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="text-2xl font-bold">Files ({files.length})</h2>
        {files.length === 0 ? (
          <p className="mt-4 text-slate-500">
            The generated application appears in workspace/{projectId}/ after a run.
          </p>
        ) : (
          <div className="mt-4 grid gap-4 md:grid-cols-[16rem_1fr]">
            <ul className="space-y-1 text-sm">
              {files.map((path) => (
                <li key={path}>
                  <button
                    onClick={() => show(path)}
                    className={`w-full rounded-lg px-3 py-2 text-left font-mono hover:bg-slate-100 ${
                      open?.path === path ? "bg-violet-100 text-violet-800" : ""
                    }`}
                  >
                    {path}
                  </button>
                </li>
              ))}
            </ul>
            <div className="min-w-0">
              {fileError && (
                <p role="alert" className="text-red-700">
                  {fileError}
                </p>
              )}
              {open ? (
                <>
                  <p className="mb-2 font-mono text-sm text-slate-500">{open.path}</p>
                  <pre className="max-h-[32rem] overflow-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">
                    {open.text}
                  </pre>
                </>
              ) : (
                <p className="text-slate-500">Choose a file to see its content.</p>
              )}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
