// Temporary sample data (Sprint 2, S2-06). Delete this file when the real API
// is connected (after S2-01 is in main). Typed with types.ts so the shapes
// match the contract.
import type { Agent, Project } from "./types";

const now = new Date().toISOString();

export const mockAgents: Agent[] = [
  {
    agent_id: "agent-fatma",
    name: "Fatma-PC",
    owner: "Fatma",
    role_hint: "frontend",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 72, reasoning: 55, context: 60 },
    status: "idle",
    current_task_id: null,
    registered_at: now,
    last_heartbeat_at: now,
  },
  {
    agent_id: "agent-eray",
    name: "Eray-PC",
    owner: "Eray",
    role_hint: "backend",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 80, reasoning: 62, context: 58 },
    status: "busy",
    current_task_id: "task-2",
    registered_at: now,
    last_heartbeat_at: now,
  },
  {
    agent_id: "agent-can",
    name: "Can-PC",
    owner: "Can",
    role_hint: "database",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 68, reasoning: 70, context: 64 },
    status: "idle",
    current_task_id: null,
    registered_at: now,
    last_heartbeat_at: now,
  },
  {
    agent_id: "agent-abdurrahman",
    name: "Abdurrahman-PC",
    owner: "Abdurrahman",
    role_hint: "testing",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 60, reasoning: 66, context: 55 },
    status: "offline",
    current_task_id: null,
    registered_at: now,
    last_heartbeat_at: null,
  },
  {
    agent_id: "agent-okan",
    name: "Okan-PC",
    owner: "Okan",
    role_hint: "integration",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 65, reasoning: 74, context: 52 },
    status: "idle",
    current_task_id: null,
    registered_at: now,
    last_heartbeat_at: now,
  },
  {
    agent_id: "agent-hamza",
    name: "Hamza-PC",
    owner: "Hamza",
    role_hint: "code_review",
    model: "qwen3:4b",
    provider: "ollama",
    capabilities: { coding: 58, reasoning: 78, context: 61 },
    status: "busy",
    current_task_id: "task-4",
    registered_at: now,
    last_heartbeat_at: now,
  },
];

export const mockProjects: Project[] = [
  {
    id: "project-1",
    name: "Library management system",
    requirement_text:
      "Develop an online library management system where members can search and borrow books.",
    status: "created",
    created_at: now,
    updated_at: now,
  },
];
