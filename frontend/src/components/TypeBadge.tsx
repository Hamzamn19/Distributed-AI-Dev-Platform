// Task type label (frontend, backend, database, testing, ...).
const COLORS: Record<string, string> = {
  frontend: "bg-pink-100 text-pink-700",
  backend: "bg-indigo-100 text-indigo-700",
  database: "bg-sky-100 text-sky-700",
  testing: "bg-teal-100 text-teal-700",
};

export default function TypeBadge({ value }: { value: string }) {
  const color = COLORS[value] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-1 text-xs font-semibold uppercase ${color}`}>
      {value.replace("_", " ")}
    </span>
  );
}
