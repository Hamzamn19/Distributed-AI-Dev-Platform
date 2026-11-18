import { useState } from "react";
import { getFile } from "../api/client";

// The files of workspace/<project_id>/, by folder, with a viewer (line numbers).
export default function FileExplorer({ projectId, files }: { projectId: string; files: string[] }) {
  const [open, setOpen] = useState<{ path: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function show(path: string) {
    setError(null);
    try {
      setOpen({ path, text: await getFile(projectId, path) });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (files.length === 0) {
    return <p className="text-sm text-muted">The files appear here after the first run.</p>;
  }
  const folders = new Map<string, string[]>();
  for (const path of files) {
    const cut = path.lastIndexOf("/");
    const folder = cut < 0 ? "" : path.slice(0, cut);
    folders.set(folder, [...(folders.get(folder) ?? []), path]);
  }
  const lines = open ? open.text.split("\n") : [];

  return (
    <div className="grid gap-4 lg:grid-cols-[15rem_1fr]">
      <nav className="space-y-3" aria-label="Generated files">
        {[...folders.entries()].map(([folder, paths]) => (
          <div key={folder}>
            <p className="mb-1 text-xs font-medium text-muted">{folder ? `${folder}/` : "Project folder"}</p>
            <ul>
              {paths.map((path) => (
                <li key={path}>
                  <button
                    onClick={() => show(path)}
                    className={`w-full truncate rounded-md px-2 py-1 text-left font-mono text-xs transition ${
                      open?.path === path ? "bg-info-soft text-accent" : "text-ink hover:bg-sunken"
                    }`}
                  >
                    {path.slice(path.lastIndexOf("/") + 1)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="min-w-0">
        {error && (
          <p role="alert" className="mb-2 text-sm text-bad">
            {error}
          </p>
        )}
        {open ? (
          <div className="overflow-hidden rounded-lg border border-line">
            <div className="flex items-center justify-between border-b border-line bg-sunken px-3 py-2 text-xs">
              <span className="font-mono text-ink">{open.path}</span>
              <span className="text-muted">{lines.length} lines</span>
            </div>
            <pre className="max-h-[32rem] overflow-auto bg-card py-2 font-mono text-xs leading-relaxed">
              {lines.map((line, i) => (
                <div key={i} className="flex hover:bg-sunken">
                  <span className="w-11 shrink-0 select-none pr-3 text-right text-muted/60">{i + 1}</span>
                  <code className="whitespace-pre text-ink">{line || " "}</code>
                </div>
              ))}
            </pre>
          </div>
        ) : (
          <p className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-line text-sm text-muted">
            Choose a file on the left to read it.
          </p>
        )}
      </div>
    </div>
  );
}
