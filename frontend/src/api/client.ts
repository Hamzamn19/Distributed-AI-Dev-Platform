// All calls to the master API go through this file. Pages never call fetch directly.
// While USING_MOCK is true, the functions return sample data from mock.ts.
// When S2-01 is in main: replace each body with request(...) and delete mock.ts.
import type { Agent, Project, ProjectCreate, Task, TaskType } from "./types";
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
const tasks: Task[] = [];
const delay = () => new Promise((resolve) => setTimeout(resolve, 300));
const stamp = () => new Date().toISOString();

function findProject(id: string): Project {
  const project = projects.find((p) => p.id === id);
  if (!project) throw new Error("Project not found");
  return project;
}

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
  const now = stamp();
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

export async function getProject(id: string): Promise<Project> {
  await delay();
  return findProject(id);
}

export async function getTasks(id: string): Promise<Task[]> {
  await delay();
  return tasks.filter((t) => t.project_id === id);
}

export async function decomposeProject(id: string): Promise<Task[]> {
  await delay();
  // Contract: decompose on a project that already has tasks returns them.
  const existing = tasks.filter((t) => t.project_id === id);
  if (existing.length > 0) return existing;
  const project = findProject(id);
  const sample: { title: string; type: TaskType; deps: number[] }[] = [
    { title: "Design database schema", type: "database", deps: [] },
    { title: "Build REST API", type: "backend", deps: [0] },
    { title: "Build web pages", type: "frontend", deps: [1] },
    { title: "Write tests", type: "testing", deps: [1, 2] },
  ];
  const now = stamp();
  const created: Task[] = sample.map((s, i) => ({
    id: `${id}-task-${i + 1}`,
    project_id: id,
    title: s.title,
    description: "",
    type: s.type,
    status: "pending",
    depends_on: s.deps.map((d) => `${id}-task-${d + 1}`),
    assigned_agent_id: null,
    assignment_reason: null,
    attempt: 0,
    created_at: now,
    updated_at: now,
  }));
  tasks.push(...created);
  project.status = "in_progress";
  project.updated_at = now;
  return created;
}

export async function assignProject(id: string): Promise<Task[]> {
  await delay();
  const projectTasks = tasks.filter((t) => t.project_id === id);
  if (projectTasks.length === 0) throw new Error("Decompose the project first");
  for (const task of projectTasks) {
    // Contract: no candidate with a matching role hint -> the task stays pending.
    const agent = mockAgents.find((a) => a.role_hint === task.type);
    if (!agent) continue;
    task.assigned_agent_id = agent.agent_id;
    task.assignment_reason = `Role hint "${agent.role_hint}" matches task type "${task.type}"; coding score ${agent.capabilities.coding}`;
    task.status = "assigned";
    task.updated_at = stamp();
  }
  return projectTasks;
}
