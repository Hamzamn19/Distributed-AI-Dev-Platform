// Task type (database, backend, frontend, testing), one colour per layer of the app.
export const TYPE_COLOR: Record<string, string> = {
  database: "var(--t-database)",
  backend: "var(--t-backend)",
  frontend: "var(--t-frontend)",
  testing: "var(--t-testing)",
};

export const TYPE_HINT: Record<string, string> = {
  database: "Tables and storage functions (backend/database.py)",
  backend: "API routes (backend/main.py)",
  frontend: "The web page (frontend/index.html)",
  testing: "Tests of the business rules (tests/test_app.py)",
};

export default function TypeBadge({ value }: { value: string }) {
  const color = TYPE_COLOR[value] ?? "var(--muted)";
  return (
    <span
      title={TYPE_HINT[value]}
      className="inline-block rounded-md border px-2 py-0.5 text-xs font-medium capitalize"
      style={{ color, borderColor: `color-mix(in srgb, ${color} 35%, transparent)` }}
    >
      {value.replace("_", " ")}
    </span>
  );
}
