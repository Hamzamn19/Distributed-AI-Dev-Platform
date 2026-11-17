import { useCallback } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { getAgents, getHealth } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { useTheme } from "../lib/theme";
import type { ThemeChoice } from "../lib/theme";
import { Dot } from "./ui";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
    isActive ? "bg-info-soft text-accent" : "text-muted hover:bg-sunken hover:text-ink"
  }`;

const THEMES: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: "system", label: "Follow the computer", icon: "◐" },
  { value: "light", label: "Light", icon: "☀" },
  { value: "dark", label: "Dark", icon: "☾" },
];

function ThemeSwitch() {
  const [choice, setChoice] = useTheme();
  return (
    <div className="flex rounded-lg border border-line bg-sunken p-0.5" role="radiogroup" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.value}
          role="radio"
          aria-checked={choice === t.value}
          title={t.label}
          onClick={() => setChoice(t.value)}
          className={`h-7 w-8 rounded-md text-sm transition ${
            choice === t.value ? "bg-card text-ink shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          {t.icon}
        </button>
      ))}
    </div>
  );
}

export default function Layout() {
  const loadStatus = useCallback(async () => {
    const [health, agents] = await Promise.all([getHealth(), getAgents()]);
    return { health, agents };
  }, []);
  const { data, error } = usePolling(loadStatus, 5000);
  const online = data?.agents.filter((a) => a.status !== "offline").length ?? 0;
  const linked = data !== null && error === null;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-line bg-card/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-on-accent">
              D
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-ink">Distributed AI Dev Platform</p>
              <p className="text-xs text-muted">One master · worker agents · local models</p>
            </div>
          </div>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              Overview
            </NavLink>
            <NavLink to="/agents" className={linkClass}>
              Agents
            </NavLink>
          </nav>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-2 text-muted" title={error ?? "The master answers"}>
              <Dot status={linked ? "idle" : "failed"} />
              {linked ? "Master connected" : "Master not reachable"}
            </span>
            <span className="hidden text-muted sm:inline">
              <span className="font-semibold text-ink">{online}</span>/{data?.agents.length ?? 0} agents online
            </span>
            <ThemeSwitch />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
