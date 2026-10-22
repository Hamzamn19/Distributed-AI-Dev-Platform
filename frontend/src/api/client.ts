// All calls to the master API go through this file. Pages never call fetch directly.
// The UI is served by the master itself (http://<master>:8000), so the API base is
// relative: "/api/v1". During development Vite proxies /api to the master (vite.config.js).
// Set VITE_API_BASE_URL only for unusual setups (for example "http://100.x.y.z:8000").
import type { Agent, Project, ProjectCreate, Task } from "./types";

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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  return response.json() as Promise<T>;
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
