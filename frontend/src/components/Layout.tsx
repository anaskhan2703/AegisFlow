import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/alerts", label: "Alerts" },
  { to: "/playbooks", label: "Playbooks" },
  { to: "/incidents", label: "Incidents" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-soc-bg">
      {/* Thin accent line — a small nod to a "system is live" indicator without being gimmicky */}
      <div className="h-0.5 bg-gradient-to-r from-soc-accent/0 via-soc-accent/60 to-soc-accent/0" />
      <header className="border-b border-soc-border bg-soc-panel">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link to="/dashboard" className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-soc-accent" />
              <span className="text-lg font-bold tracking-tight text-slate-100">AegisFlow</span>
            </Link>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`rounded px-3 py-1.5 text-sm transition ${
                      isActive
                        ? "bg-soc-accent/15 text-soc-accent"
                        : "text-slate-400 hover:bg-soc-bg hover:text-slate-200"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          {user && (
            <div className="flex items-center gap-4 text-sm">
              <span className="hidden text-slate-400 sm:inline">{user.email}</span>
              <span className="rounded border border-soc-border bg-soc-bg px-2 py-0.5 font-mono text-xs uppercase text-soc-accent">
                {user.role}
              </span>
              <button
                onClick={handleLogout}
                className="rounded border border-soc-border px-3 py-1 text-slate-400 transition hover:border-soc-critical hover:text-soc-critical"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
