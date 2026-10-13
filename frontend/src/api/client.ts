// All calls to the master API go through this file. Pages never call fetch directly.
import type { Agent } from "./types";

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL}/api/v1`;

// Throws an Error with the body's `detail` text when the answer is not OK.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
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
