import { NavLink, Outlet } from "react-router-dom";
import { USING_MOCK } from "../api/client";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium ${
    isActive ? "bg-violet-100 text-violet-800" : "text-slate-600 hover:bg-slate-100"
  }`;

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div>
            <p className="text-sm font-semibold text-violet-700">DISTRIBUTED AI</p>
            <h1 className="text-xl font-bold">Development Platform</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {USING_MOCK && (
              <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-700">
                Sample data
              </span>
            )}
            <nav className="flex gap-2">
              <NavLink to="/" end className={linkClass}>
                Projects
              </NavLink>
              <NavLink to="/agents" className={linkClass}>
                Agents
              </NavLink>
            </nav>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>
    </div>
  );
}
