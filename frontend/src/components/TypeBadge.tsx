// Task type label (requirements analysis, frontend, backend, ...).
const COLORS: Record<string, string> = {
  requirements_analysis: "bg-violet-100 text-violet-700",
  frontend: "bg-pink-100 text-pink-700",
  backend: "bg-indigo-100 text-indigo-700",
  database: "bg-sky-100 text-sky-700",
  testing: "bg-teal-100 text-teal-700",
  code_review: "bg-orange-100 text-orange-700",
  integration: "bg-lime-100 text-lime-700",
  documentation: "bg-amber-100 text-amber-700",
};

export default function TypeBadge({ value }: { value: string }) {
  const color = COLORS[value] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-1 text-xs font-semibold uppercase ${color}`}>
      {value.replace("_", " ")}
    </span>
  );
}
