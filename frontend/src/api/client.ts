// All calls to the master API go through this file. Pages never call fetch directly.
// While USING_MOCK is true, the functions return sample data from mock.ts.
// When S2-01 is in main: replace each body with request(...) and delete mock.ts.
import type { Agent, Project, ProjectCreate } from "./types";
import { mockAgents, mockProjects } from "./mock";

export const USING_MOCK = true;

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL}/api/v1`;

// Real request helper: throws an Error with the body's `detail` text on failure.
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

// ---- mock state (removed together with mock.ts) ----
const projects = [...mockProjects];
const delay = () => new Promise((resolve) => setTimeout(resolve, 300));

export async function getAgents(): Promise<Agent[]> {
  await delay();
  return mockAgents;
}

export async function getProjects(): Promise<Project[]> {
  await delay();
  return [...projects];
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  await delay();
  if (data.requirement_text.length < 20) {
    throw new Error("Requirement text must be at least 20 characters");
  }
  const now = new Date().toISOString();
  const project: Project = {
    id: `project-${projects.length + 1}`,
    name: data.name,
    requirement_text: data.requirement_text,
    status: "created",
    created_at: now,
    updated_at: now,
  };
  projects.unshift(project);
  return project;
}
