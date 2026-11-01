// All calls to the master API go through this file. Pages never call fetch directly.
// Every function talks to the live master (VITE_API_BASE_URL, prefix /api/v1).
import type { Agent, Project, ProjectCreate, Task } from "./types";

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL}/api/v1`;

// Request helper: throws an Error with the body's `detail` text on failure.
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the default message
    }
    throw new Error(detail);
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
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(id)}`);
}

export function getTasks(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${encodeURIComponent(id)}/tasks`);
}

export function decomposeProject(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${encodeURIComponent(id)}/decompose`, {
    method: "POST",
  });
}

export function assignProject(id: string): Promise<Task[]> {
  return request<Task[]>(`/projects/${encodeURIComponent(id)}/assign`, {
    method: "POST",
  });
}
