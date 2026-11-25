import { Dot, fg, soft, statusInfo } from "./ui";

// A status label: a dot, a plain word and, on hover, what it means.
export default function Badge({ value, large = false }: { value: string; large?: boolean }) {
  const { tone, label, hint } = statusInfo(value);
  return (
    <span
      title={hint}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium ${
        large ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs"
      }`}
      style={{ color: fg(tone), background: soft(tone) }}
    >
      <Dot status={value} />
      {label}
    </span>
  );
}
