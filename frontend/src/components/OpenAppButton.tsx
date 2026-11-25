import { useState } from "react";
import { startPreview } from "../api/client";

// Starts a project's generated application on the master and opens it in a new tab,
// at the master's own address (so it works from every PC): http://<master>:<port>/.
// The tab opens at the click, before the answer, so no pop-up blocker stops it.
export default function OpenAppButton({
  projectId,
  label = "Open the app",
  primary = false,
}: {
  projectId: string;
  label?: string;
  primary?: boolean;
}) {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function open() {
    const tab = window.open("", "_blank");
    tab?.document.write(
      '<p style="font-family:system-ui,sans-serif;padding:2rem">Starting the application...</p>',
    );
    setStarting(true);
    setError(null);
    try {
      const { port } = await startPreview(projectId);
      const url = `${window.location.protocol}//${window.location.hostname}:${port}/`;
      if (tab) tab.location.href = url;
      else window.open(url, "_blank");
    } catch (e) {
      tab?.close();
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={open}
        disabled={starting}
        className={`btn ${primary ? "btn-primary" : ""}`}
        title="Starts the generated application on the master and opens it in a new tab"
      >
        {starting ? "Starting the app..." : `▶ ${label}`}
      </button>
      {error && (
        <p role="alert" className="max-w-md whitespace-pre-wrap text-right text-xs text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
