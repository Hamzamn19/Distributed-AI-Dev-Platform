import { useEffect, useRef, useState } from "react";

export type Tone = "info" | "ok" | "warn" | "bad" | "plan";

export interface LogLine {
  id: number;
  at: number;
  text: string;
  tone: Tone;
}

// One watched thing: its current state and how a change of it is told.
export interface Watched {
  state: string;
  told: (before: string | undefined, after: string) => { text: string; tone: Tone } | null;
}

let nextId = 1;

// A live console built from polling: every time a watched state changes between two
// polls, one line is added. The first snapshot gives a `greeting` line and one line
// per watched thing (told with `before` undefined), so the console starts with the picture.
export function useEventLog(
  watched: Record<string, Watched> | null,
  greeting: (count: number) => string,
  limit = 120,
): LogLine[] {
  const previous = useRef<Record<string, string> | null>(null);
  const [lines, setLines] = useState<LogLine[]>([]);

  useEffect(() => {
    if (!watched) return;
    const now = Date.now();
    const added: LogLine[] = [];
    const first = previous.current === null;
    if (first) {
      added.push({ id: nextId++, at: now, text: greeting(Object.keys(watched).length), tone: "info" });
    }
    for (const [key, item] of Object.entries(watched)) {
      const before = first ? undefined : previous.current?.[key];
      if (!first && before === item.state) continue;
      const line = item.told(before, item.state);
      if (line) added.push({ id: nextId++, at: now, ...line });
    }
    previous.current = Object.fromEntries(Object.entries(watched).map(([k, v]) => [k, v.state]));
    if (added.length) setLines((old) => [...old, ...added].slice(-limit));
  }, [watched, greeting, limit]);

  return lines;
}
