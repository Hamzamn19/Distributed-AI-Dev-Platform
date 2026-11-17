import { RECORD_STEPS } from "../api/acceptance";
import type { AcceptanceCheck, AcceptanceReport, CheckResult } from "../api/acceptance";
import { fg, soft } from "./ui";
import type { ToneName } from "./ui";

const LOOK: Record<CheckResult | "none", { word: string; tone: ToneName; meaning: string }> = {
  pass: { word: "OK", tone: "ok", meaning: "worked" },
  fail: { word: "Fail", tone: "bad", meaning: "broken: an error or a wrong answer" },
  rule: { word: "Rule", tone: "warn", meaning: "a business rule said no (HTTP 400); not an error" },
  skipped: { word: "–", tone: "mute", meaning: "not tried, because an earlier step failed" },
  none: { word: "·", tone: "mute", meaning: "not tried" },
};

// The column titles in plain words; the hover text says the request.
const COLUMNS: Record<string, [string, string]> = {
  list: ["List", "GET /api/<records>"],
  search: ["Search", "GET /api/<records>?search=a"],
  create: ["Add", "POST /api/<records>"],
  get: ["Open", "GET /api/<records>/{id}"],
  update: ["Edit", "PUT /api/<records>/{id}"],
  delete: ["Delete", "DELETE /api/<records>/{id}"],
  gone: ["Gone", "GET after delete answers 404"],
};

function Cell({ check }: { check?: AcceptanceCheck }) {
  const look = LOOK[check?.result ?? "none"];
  return (
    <td className="p-1">
      <span
        className="flex h-7 items-center justify-center rounded-md text-xs font-semibold"
        style={{ color: fg(look.tone), background: soft(look.tone) }}
        title={check ? `${look.meaning}: ${check.detail}` : look.meaning}
      >
        {look.word}
      </span>
    </td>
  );
}

// The master's check of the generated app: one row per kind of record, one column
// per operation, plus the page and /api/stats. Hover a cell to see the request.
export default function AcceptanceMatrix({ report }: { report: AcceptanceReport | null }) {
  if (!report) {
    return (
      <p className="text-sm text-muted">
        After the last task the master starts the generated app and tries, for every kind of
        record: list, search, add, open, edit and delete. The result appears here.
      </p>
    );
  }
  if (!report.started) {
    return (
      <div className="rounded-lg bg-bad-soft p-3 text-sm text-bad">
        <p className="font-semibold">The generated app does not start.</p>
        <pre className="mt-2 whitespace-pre-wrap font-mono text-xs">{report.error}</pre>
      </div>
    );
  }
  const general = report.checks.filter((c) => c.record === null);
  const records = [...new Set(report.checks.map((c) => c.record).filter((r) => r !== null))];
  const find = (record: string, step: string) => report.checks.find((c) => c.record === record && c.step === step);

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-2">
        {general.map((c) => {
          const look = LOOK[c.result];
          return (
            <li
              key={c.step}
              className="rounded-md px-2 py-1 text-xs font-medium"
              style={{ color: fg(look.tone), background: soft(look.tone) }}
              title={c.detail}
            >
              {c.step === "page" ? "Web page" : c.step === "stats" ? "Dashboard numbers" : "Routes"}: {look.word}
            </li>
          );
        })}
      </ul>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left">
          <thead>
            <tr className="text-xs text-muted">
              <th className="p-1 font-medium">Record</th>
              {RECORD_STEPS.map((s) => (
                <th key={s} className="p-1 text-center font-medium" title={COLUMNS[s]?.[1]}>
                  {COLUMNS[s]?.[0] ?? s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((record) => {
              const missing = find(record, "routes");
              return (
                <tr key={record}>
                  <th className="p-1 font-mono text-xs font-medium text-ink">{record}</th>
                  {missing ? (
                    <td colSpan={RECORD_STEPS.length} className="p-1">
                      <span className="flex h-7 items-center rounded-md bg-bad-soft px-2 text-xs text-bad">{missing.detail}</span>
                    </td>
                  ) : (
                    RECORD_STEPS.map((step) => <Cell key={step} check={find(record, step)} />)
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {(["pass", "fail", "rule", "skipped"] as const).map((k) => (
          <span key={k}>
            <span className="font-semibold" style={{ color: fg(LOOK[k].tone) }}>{LOOK[k].word}</span> {LOOK[k].meaning}
          </span>
        ))}
      </p>
    </div>
  );
}
