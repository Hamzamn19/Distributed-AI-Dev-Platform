import { useCallback } from "react";
import type { ReactNode } from "react";
import { getAgentCard, getAgents } from "../api/client";
import type { Agent, Capabilities } from "../api/types";
import Badge from "../components/Badge";
import { Bar, Card, Stat, fg } from "../components/ui";
import { useNow } from "../hooks/useNow";
import { usePolling } from "../hooks/usePolling";
import { ago, shortId, stamp } from "../lib/format";

type Reach = Record<string, { ok: boolean; text: string }>;

// Asks the master to fetch each online worker's A2A agent card (every 10 s).
// "reachable" means the master can send tasks to that worker.
function useReachability(agents: Agent[] | null) {
  const key = (agents ?? [])
    .filter((a) => a.a2a_url && a.status !== "offline")
    .map((a) => a.agent_id)
    .join(",");
  const check = useCallback(async () => {
    const result: Reach = {};
    await Promise.all(
      key.split(",").filter(Boolean).map(async (id) => {
        try {
          await getAgentCard(id);
          result[id] = { ok: true, text: "reachable" };
        } catch (e) {
          result[id] = { ok: false, text: e instanceof Error ? e.message : String(e) };
        }
      }),
    );
    return result;
  }, [key]);
  return usePolling(check, 10000).data ?? {};
}

const SKILLS: { key: keyof Capabilities; label: string; hint: string }[] = [
  { key: "coding", label: "Coding", hint: "Measured with two programming tasks and unit tests" },
  { key: "reasoning", label: "Reasoning", hint: "Measured with two questions that have one right answer" },
  { key: "context", label: "Context", hint: "Measured by finding one fact in a long text" },
];

function Info({ label, children, title }: { label: string; children: ReactNode; title?: string }) {
  return (
    <div className="flex justify-between gap-3 text-sm" title={title}>
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-ink">{children}</dd>
    </div>
  );
}

function AgentCard({ agent, reach, now }: { agent: Agent; reach: Reach; now: number }) {
  const state = reach[agent.agent_id];
  const seen = agent.last_heartbeat_at ? now - new Date(agent.last_heartbeat_at).getTime() : null;
  return (
    <article className="card flex flex-col gap-4 p-4" style={{ opacity: agent.status === "offline" ? 0.7 : 1 }}>
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-ink">{agent.name}</h3>
          <p className="text-sm text-muted">
            {agent.owner} · <span className="font-mono text-xs">{agent.agent_id}</span>
          </p>
        </div>
        <Badge value={agent.status} />
      </header>

      <dl className="space-y-1.5">
        <Info label="Model" title={agent.model}>{agent.model}</Info>
        <Info label="Runs on">{agent.provider}</Info>
        <Info label="Preferred task" title="role_hint: a small bonus in the master's choice">{agent.role_hint ?? "any"}</Info>
        <Info label="Last heartbeat">
          <span style={{ color: seen !== null && seen < 15000 ? fg("ok") : fg("warn") }}>{ago(agent.last_heartbeat_at, now)}</span>
        </Info>
        <Info label="Current task">{agent.current_task_id ? `#${shortId(agent.current_task_id)}` : "none"}</Info>
      </dl>

      <div className="space-y-2 border-t border-line pt-3">
        <p className="text-xs font-medium text-muted">Skills (0–100), used to choose the agent for a task</p>
        {SKILLS.map((s) => (
          <div key={s.key} title={s.hint}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-ink">{s.label}</span>
              <span className="font-medium text-ink">{agent.capabilities[s.key]}</span>
            </div>
            <Bar value={agent.capabilities[s.key]} />
          </div>
        ))}
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 rounded-lg bg-sunken px-3 py-2 text-xs">
        <span className="min-w-0 truncate font-mono text-muted" title={agent.a2a_url ?? undefined}>
          {agent.a2a_url ?? "no A2A address"}
        </span>
        {agent.a2a_url && agent.status !== "offline" && (
          <span
            className="shrink-0 font-medium"
            style={{ color: !state ? fg("mute") : state.ok ? fg("ok") : fg("bad") }}
            title={state ? (state.ok ? "The master can send tasks to this agent" : state.text) : "Checking..."}
          >
            {!state ? "checking..." : state.ok ? "✓ master can reach it" : "✗ master cannot reach it"}
          </span>
        )}
      </div>
      <p className="-mt-2 text-xs text-muted">Registered {stamp(agent.registered_at)}</p>
    </article>
  );
}

export default function AgentsPage() {
  const now = useNow();
  const { data: agents, error, loading } = usePolling(getAgents);
  const reach = useReachability(agents);
  const list = agents ?? [];
  const online = list.filter((a) => a.status !== "offline").length;

  return (
    <>
      <div>
        <h1 className="text-2xl font-semibold text-ink">Agents</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Each agent is a worker PC with a local model. It registers with the master, sends a
          heartbeat every few seconds and receives tasks over A2A. The master picks an agent for a
          task from its skills, its preferred task and how busy it is.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Registered" value={list.length} hint="known to the master" />
        <Stat label="Online" value={online} hint="heartbeat in the last 30 s" tone="ok" />
        <Stat label="Working" value={list.filter((a) => a.status === "busy").length} hint="running a task now" tone="warn" />
        <Stat label="Offline" value={list.filter((a) => a.status === "offline").length} hint="no heartbeat" tone={list.length - online ? "bad" : undefined} />
      </div>

      <Card title="All agents">
        {loading && <p className="text-sm text-muted">Loading...</p>}
        {error && (
          <p role="alert" className="text-sm text-bad">
            Could not load the agents: {error}
          </p>
        )}
        {agents && agents.length === 0 && (
          <p className="text-sm text-muted">No agent has registered yet. On a worker PC run: python -m dap.worker.main</p>
        )}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} reach={reach} now={now} />
          ))}
        </div>
      </Card>
    </>
  );
}
