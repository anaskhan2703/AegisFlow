import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

export function LoginPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in — don't show the login form.
  if (user) {
    const dest = (location.state as { from?: string } | null)?.from ?? "/dashboard";
    return <Navigate to={dest} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password);
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-soc-bg px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-soc-accent" />
            <h1 className="text-3xl font-bold tracking-tight text-slate-100">AegisFlow</h1>
          </div>
          <p className="text-sm text-slate-500">Security orchestration &amp; alert triage</p>
        </div>

        <div className="rounded-lg border border-soc-border bg-soc-panel p-6">
          <div className="mb-6 flex rounded border border-soc-border p-0.5 text-sm">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`flex-1 rounded py-1.5 transition ${
                mode === "login" ? "bg-soc-accent/15 text-soc-accent" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Log in
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={`flex-1 rounded py-1.5 transition ${
                mode === "register" ? "bg-soc-accent/15 text-soc-accent" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border border-soc-border bg-soc-bg px-3 py-2 text-sm text-slate-100 outline-none focus:border-soc-accent"
                placeholder="analyst@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded border border-soc-border bg-soc-bg px-3 py-2 text-sm text-slate-100 outline-none focus:border-soc-accent"
                placeholder="••••••••"
              />
            </div>

            {mode === "register" && (
              <p className="text-xs text-slate-500">
                New accounts start as <span className="font-mono text-slate-400">viewer</span>. An admin can
                promote your role afterward.
              </p>
            )}

            {error && (
              <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-3 py-2 text-sm text-soc-critical">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-soc-accent px-3 py-2 text-sm font-semibold text-soc-bg transition hover:bg-soc-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
