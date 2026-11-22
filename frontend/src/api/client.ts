// All calls to the master API go through this file. Pages never call fetch directly.
// The UI is served by the master itself (http://<master>:8000), so the API base is
// relative: "/api/v1". During development Vite proxies /api to the master (vite.config.js).
// Set VITE_API_BASE_URL only for unusual setups (for example "http://100.x.y.z:8000").
import { ACCEPTANCE_FILE, type AcceptanceReport } from "./acceptance";
import type {
  Agent,
  AgentCard,
  HealthResponse,
  Project,
  ProjectCreate,
  Task,
  TaskResult,
} from "./types";

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL || ""}/api/v1`;

// Turns FastAPI's error body into one readable sentence.
function errorText(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // 422 validation errors: [{"loc": [...], "msg": "..."}]
    return detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join("; ");
  }
  return `Request failed (${status})`;
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error("Cannot reach the master. Is it running?");
  }
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // keep body null
    }
    throw new Error(errorText(response.status, body));
  }
  return response;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await send(path, init)).json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getAgents(): Promise<Agent[]> {
  return request<Agent[]>("/agents");
}

export function getProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function createProject(data: ProjectCreate): Promise<Project> {
  return request<Project>("/projects", { method: "POST", body: JSON.stringify(data) });
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}`);
}

export function getTasks(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${id}/tasks`);
}

export function decomposeProject(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${id}/decompose`, { method: "POST" });
}

export function assignProject(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${id}/assign`, { method: "POST" });
}

// Sends the assigned tasks to the workers (A2A); the master answers 202 at once.
export function runProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}/run`, { method: "POST" });
}

export function getResults(id: string): Promise<TaskResult[]> {
  return request<TaskResult[]>(`/projects/${id}/results`);
}

export function getFiles(id: string): Promise<string[]> {
  return request<string[]>(`/projects/${id}/files`);
}

// The text of one generated file.
export async function getFile(id: string, path: string): Promise<string> {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  return (await send(`/projects/${id}/files/${encoded}`)).text();
}

// Runs the project's generated application on the master; it answers on this port.
export function startPreview(id: string): Promise<{ project_id: string; port: number }> {
  return request(`/projects/${id}/preview`, { method: "POST" });
}

// The master's acceptance check of the generated app, once it has run (else null).
export async function getAcceptance(id: string): Promise<AcceptanceReport | null> {
  try {
    return JSON.parse(await getFile(id, ACCEPTANCE_FILE)) as AcceptanceReport;
  } catch {
    return null;
  }
}

// The master asks the worker for its A2A agent card: success means the master
// reaches the worker, the direction tasks are sent in.
export function getAgentCard(agentId: string): Promise<AgentCard> {
  return request<AgentCard>(`/agents/${agentId}/card`);
}
