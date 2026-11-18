import { useCallback, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createProject, getAgents, getProjects } from "../api/client";
import type { Agent, Project } from "../api/types";
import Badge from "../components/Badge";
import { ActivityList, Card, Stat } from "../components/ui";
import { useEventLog } from "../hooks/useEventLog";
import type { Tone, Watched } from "../hooks/useEventLog";
import { useNow } from "../hooks/useNow";
import { usePolling } from "../hooks/usePolling";
import { ago, stamp } from "../lib/format";

// Same limits as the master (dap/shared/schemas.py).
const MIN_LENGTH = 20;
const MAX_LENGTH = 12000;

const STEPS = [
  ["Write the requirement", "Describe the application you need, in plain words."],
  ["The master plans", "It splits the work into four tasks and picks an agent for each."],
  ["Agents build, the master checks", "Each agent writes its part; the master then tests the finished app."],
];

const greeting = () => "Connected to the master.";

function agentLine(agent: Agent): Watched["told"] {
  return (before, after) => {
    if (before === undefined) return null; // the agent list shows the current state
    if (after === "offline") return { text: `${agent.name} went offline (no heartbeat).`, tone: "bad" };
    if (before === "offline") return { text: `${agent.name} is back online.`, tone: "ok" };
    if (after === "busy") return { text: `${agent.name} started a task.`, tone: "warn" };
    return { text: `${agent.name} finished its task.`, tone: "ok" };
  };
}

function projectLine(project: Project): Watched["told"] {
  const told: Record<string, [string, Tone]> = {
    created: [`New project "${project.name}".`, "info"],
    decomposing: [`The master is planning "${project.name}".`, "plan"],
    in_progress: [`Agents are working on "${project.name}".`, "warn"],
    integrating: [`The master is checking "${project.name}".`, "plan"],
    completed: [`"${project.name}" is completed.`, "ok"],
    failed: [`"${project.name}" failed.`, "bad"],
  };
  return (before, after) => {
    if (before === undefined) return null;
    const [text, tone] = told[after] ?? [`"${project.name}": ${after}.`, "info"];
    return { text, tone };
  };
}

export default function OverviewPage() {
  const navigate = useNavigate();
  const now = useNow();
  const load = useCallback(async () => {
    const [agents, projects] = await Promise.all([getAgents(), getProjects()]);
    return { agents, projects };
  }, []);
  const { data, error, loading } = usePolling(load);

  const watched = useMemo(() => {
    if (!data) return null;
    const items: Record<string, Watched> = {};
    for (const a of data.agents) items[`a:${a.agent_id}`] = { state: a.status, told: agentLine(a) };
    for (const p of data.projects) items[`p:${p.id}`] = { state: p.status, told: projectLine(p) };
    return items;
  }, [data]);
  const lines = useEventLog(watched, greeting);

  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const length = text.trim().length;
  const canSubmit =
    name.trim().length > 0 && length >= MIN_LENGTH && length <= MAX_LENGTH && !submitting;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const project = await createProject({ name: name.trim(), requirement_text: text.trim() });
      navigate(`/projects/${project.id}`);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const agents = data?.agents ?? [];
  const projects = data?.projects.slice().reverse() ?? [];
  const online = agents.filter((a) => a.status !== "offline").length;
  const working = agents.filter((a) => a.status === "busy").length;
  const completed = projects.filter((p) => p.status === "completed").length;
  const failed = projects.filter((p) => p.status === "failed").length;

  return (
    <>
      <section className="card grid gap-4 p-4 sm:grid-cols-3 sm:p-5">
        {STEPS.map(([title, text], i) => (
          <div key={title} className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-info-soft text-sm font-semibold text-accent">
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">{title}</p>
              <p className="text-sm text-muted">{text}</p>
            </div>
          </div>
        ))}
      </section>

      {error && (
        <p role="alert" className="rounded-lg bg-bad-soft px-4 py-3 text-sm text-bad">
          Cannot reach the master: {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Agents online" value={`${online} / ${agents.length}`} hint="sent a heartbeat in the last 30 s" tone="ok" />
        <Stat label="Working now" value={working} hint="agents running a task" tone={working ? "warn" : undefined} />
        <Stat label="Projects" value={projects.length} hint="on this master" />
        <Stat label="Completed" value={completed} hint={failed ? `${failed} failed` : "none failed"} tone="ok" />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card title="New project" description="The master will turn this text into tasks." className="lg:col-span-2">
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-ink">
                Name
              </label>
              <input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Library system" className="input" />
            </div>
            <div>
              <label htmlFor="requirement" className="mb-1 block text-sm font-medium text-ink">
                Requirement
              </label>
              <textarea
                id="requirement"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="An online library where members can search and borrow books..."
                className="input min-h-40"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-muted" role={formError ? "alert" : undefined}>
                {formError ? (
                  <span className="text-bad">{formError}</span>
                ) : length < MIN_LENGTH ? (
                  `At least ${MIN_LENGTH} characters (${length} so far)`
                ) : length > MAX_LENGTH ? (
                  <span className="text-bad">Too long: {length} of {MAX_LENGTH}</span>
                ) : (
                  `${length} characters`
                )}
              </span>
              <button type="submit" disabled={!canSubmit} className="btn btn-primary">
                {submitting ? "Creating..." : "Create project"}
              </button>
            </div>
          </form>
        </Card>

        <Card title="Projects" description="Open a project to plan it, run it and see the result." className="lg:col-span-3">
          {loading ? (
            <p className="text-sm text-muted">Loading...</p>
          ) : projects.length === 0 ? (
            <p className="text-sm text-muted">No projects yet. Create the first one on the left.</p>
          ) : (
            <ul className="-mx-2 max-h-[22rem] divide-y divide-line overflow-y-auto">
              {projects.map((p) => (
                <li key={p.id}>
                  <Link to={`/projects/${p.id}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 hover:bg-sunken">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-ink">{p.name}</span>
                      <span className="block text-xs text-muted">
                        Created {stamp(p.created_at)} · updated {ago(p.updated_at, now)}
                      </span>
                    </span>
                    <Badge value={p.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card
          title="Agents"
          description="The worker PCs that write the code."
          right={<Link to="/agents" className="text-sm font-medium text-accent hover:underline">Details →</Link>}
          className="lg:col-span-3"
        >
          {agents.length === 0 ? (
            <p className="text-sm text-muted">No agent has registered yet. On a worker PC run: python -m dap.worker.main</p>
          ) : (
            <ul className="divide-y divide-line">
              {agents.map((a) => (
                <li key={a.agent_id} className="flex items-center justify-between gap-3 py-2.5">
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">
                      {a.name} <span className="font-normal text-muted">· {a.owner}</span>
                    </span>
                    <span className="block truncate text-xs text-muted">
                      {a.model} · seen {ago(a.last_heartbeat_at, now)}
                    </span>
                  </span>
                  <Badge value={a.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Activity" description="What changed, newest first." className="lg:col-span-2">
          <ActivityList lines={lines.filter((l) => l.text !== greeting())} empty="Nothing has changed since you opened the page." />
        </Card>
      </div>
    </>
  );
}
