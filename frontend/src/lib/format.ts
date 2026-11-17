// Small formatters shared by the HUD pages.

export function duration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "-";
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}m ${String(rest).padStart(2, "0")}s`;
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

// "12 s ago" from an ISO time; `now` comes from useNow so it ticks.
export function ago(iso: string | null, now: number): string {
  if (!iso) return "never";
  const ms = now - new Date(iso).getTime();
  if (ms < 1500) return "just now";
  return `${duration(ms)} ago`;
}

export function tokens(count: number): string {
  if (count >= 10000) return `${(count / 1000).toFixed(1)}k`;
  return count.toLocaleString("en-US");
}

export function shortId(id: string): string {
  return id.slice(0, 8).toUpperCase();
}

export function clock(time: number): string {
  return new Date(time).toLocaleTimeString("en-GB", { hour12: false });
}

export function stamp(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Agent names like "Eray-PC" -> "ER" for the nodes of the map.
export function initials(name: string): string {
  return name.replace(/-PC$/i, "").slice(0, 2).toUpperCase();
}
