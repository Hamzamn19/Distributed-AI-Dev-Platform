// Mirror of dap/shared/enums.py and dap/shared/schemas.py.
// Field names stay snake_case: do not convert them to camelCase.
// Change this file only together with docs/PROJECT_CONTRACT.md.

export type AgentStatus = "idle" | "busy" | "offline";

export type TaskType =
  | "requirements_analysis"
  | "frontend"
  | "backend"
  | "database"
  | "testing"
  | "code_review"
  | "integration"
  | "documentation";

export type TaskStatus =
  | "pending"
  | "assigned"
  | "in_progress"
  | "completed"
  | "failed";

export type ProjectStatus =
  | "created"
  | "decomposing"
  | "in_progress"
  | "integrating"
  | "completed"
  | "failed";

export interface Capabilities {
  coding: number; // 0-100
  reasoning: number; // 0-100
  context: number; // 0-100
}

export interface Agent {
  agent_id: string;
  name: string;
  owner: string;
  role_hint: TaskType | null;
  model: string;
  provider: string;
  capabilities: Capabilities;
  status: AgentStatus;
  current_task_id: string | null;
  registered_at: string; // ISO 8601, UTC
  last_heartbeat_at: string | null;
}

export interface ProjectCreate {
  name: string;
  requirement_text: string; // at least 20 characters, otherwise HTTP 422
}

export interface Project {
  id: string;
  name: string;
  requirement_text: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  type: TaskType;
  status: TaskStatus;
  depends_on: string[];
  assigned_agent_id: string | null;
  assignment_reason: string | null;
  attempt: number;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

// Every error answer from the master has this shape.
export interface ApiError {
  detail: string;
}
