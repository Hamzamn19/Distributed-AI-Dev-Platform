import { useCallback } from "react";
import { getAgentCard, getAgents } from "../api/client";
import type { Agent } from "../api/types";
import Badge from "../components/Badge";
import { usePolling } from "../hooks/usePolling";

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

function A2A({ agent, reach }: { agent: Agent; reach: Reach }) {
  if (!agent.a2a_url) return <span className="text-slate-400">no A2A address</span>;
  const state = reach[agent.agent_id];
  return (
    <span>
      <span className="font-mono text-xs">{agent.a2a_url}</span>{" "}
      {agent.status === "offline" ? null : !state ? (
        <span className="text-slate-400">checking...</span>
      ) : (
        <span className={state.ok ? "text-emerald-700" : "text-red-700"} title={state.text}>
          {state.ok ? "✓ reachable" : "✗ not reachable"}
        </span>
      )}
    </span>
  );
}

function Scores({ agent }: { agent: Agent }) {
  const { coding, reasoning, context } = agent.capabilities;
  return (
    <span className="text-sm text-slate-700">
      Coding {coding} · Reasoning {reasoning} · Context {context}
    </span>
  );
}

export default function AgentsPage() {
  const { data: agents, error, loading } = usePolling(getAgents);
  const reach = useReachability(agents);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <p className="text-sm font-medium text-violet-700">LIVE</p>
      <h2 className="mt-1 text-2xl font-bold">Agents</h2>

      {loading && <p className="mt-4 text-slate-500">Loading agents...</p>}
      {error && (
        <p role="alert" className="mt-4 text-red-700">
          Could not load agents: {error}
        </p>
      )}
      {agents && agents.length === 0 && (
        <p className="mt-4 text-slate-500">No agents registered yet.</p>
      )}

      {agents && agents.length > 0 && (
        <>
          {/* Desktop: table */}
          <div className="mt-4 hidden overflow-x-auto md:block">
            <table className="w-full text-left text-sm">
              <thead className="text-slate-500">
                <tr>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Owner</th>
                  <th className="py-2 pr-4">Model</th>
                  <th className="py-2 pr-4">Role hint</th>
                  <th className="py-2 pr-4">Coding</th>
                  <th className="py-2 pr-4">Reasoning</th>
                  <th className="py-2 pr-4">Context</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">A2A server</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {agents.map((agent) => (
                  <tr key={agent.agent_id}>
                    <td className="py-3 pr-4 font-semibold">{agent.name}</td>
                    <td className="py-3 pr-4">{agent.owner}</td>
                    <td className="py-3 pr-4">{agent.model}</td>
                    <td className="py-3 pr-4">{agent.role_hint ?? "-"}</td>
                    <td className="py-3 pr-4">{agent.capabilities.coding}</td>
                    <td className="py-3 pr-4">{agent.capabilities.reasoning}</td>
                    <td className="py-3 pr-4">{agent.capabilities.context}</td>
                    <td className="py-3 pr-4">
                      <Badge value={agent.status} />
                    </td>
                    <td className="py-3">
                      <A2A agent={agent} reach={reach} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phone: one card per agent */}
          <div className="mt-4 space-y-3 md:hidden">
            {agents.map((agent) => (
              <article
                key={agent.agent_id}
                className="rounded-xl border border-slate-200 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold">{agent.name}</h3>
                  <Badge value={agent.status} />
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {agent.owner} · {agent.model} · {agent.role_hint ?? "no role hint"}
                </p>
                <p className="mt-2">
                  <Scores agent={agent} />
                </p>
                <p className="mt-2 text-sm">
                  <A2A agent={agent} reach={reach} />
                </p>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
