// A status label that shows both a colour and a text (never colour alone).
const COLORS: Record<string, string> = {
  idle: "bg-emerald-100 text-emerald-700",
  busy: "bg-amber-100 text-amber-700",
  offline: "bg-slate-200 text-slate-600",
  created: "bg-slate-100 text-slate-600",
  decomposing: "bg-amber-100 text-amber-700",
  in_progress: "bg-amber-100 text-amber-700",
  integrating: "bg-amber-100 text-amber-700",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
};

export default function Badge({ value }: { value: string }) {
  const color = COLORS[value] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${color}`}>
      ● {value.replace("_", " ")}
    </span>
  );
}
