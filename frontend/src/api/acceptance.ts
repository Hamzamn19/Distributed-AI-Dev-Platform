// The master's acceptance check of a generated application: the file
// workspace/<project_id>/acceptance.json (dap/master/core/acceptance.py).
// Not a contract schema; it is read as a generated file.

export type CheckResult = "pass" | "fail" | "rule" | "skipped";

export interface AcceptanceCheck {
  record: string | null; // null: the page, /api/stats or the route list
  step: string; // page, stats, routes, list, search, create, get, update, delete, gone
  result: CheckResult;
  detail: string;
}

export interface AcceptanceReport {
  started: boolean;
  error: string | null;
  summary: string;
  passed: number;
  failed: number;
  rules: number;
  checks: AcceptanceCheck[];
}

export const ACCEPTANCE_FILE = "acceptance.json";
export const RECORD_STEPS = ["list", "search", "create", "get", "update", "delete", "gone"];
