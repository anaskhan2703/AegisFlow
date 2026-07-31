import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
  environment: string;
};

const API_BASE_URL = "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`Backend returned ${res.status}`);
        return res.json();
      })
      .then((data: HealthResponse) => setHealth(data))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 px-4">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-soc-accent tracking-tight">
          AegisFlow
        </h1>
        <p className="text-slate-400 mt-2">SOAR Platform — Phase 1 Foundation</p>
      </div>

      <div className="w-full max-w-md rounded-lg border border-soc-border bg-soc-panel p-6">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
          Backend Connectivity
        </h2>
        {health && (
          <div className="flex items-center gap-2 text-soc-safe">
            <span className="h-2 w-2 rounded-full bg-soc-safe animate-pulse" />
            <span>
              {health.service} — {health.status} ({health.environment})
            </span>
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 text-soc-critical">
            <span className="h-2 w-2 rounded-full bg-soc-critical" />
            <span>Could not reach backend: {error}</span>
          </div>
        )}
        {!health && !error && (
          <div className="flex items-center gap-2 text-slate-400">
            <span className="h-2 w-2 rounded-full bg-slate-500 animate-pulse" />
            <span>Checking backend status…</span>
          </div>
        )}
      </div>
    </div>
  );
}
