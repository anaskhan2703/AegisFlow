import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import type { Alert, AlertStatus } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { SeverityBadge, StatusBadge, CorrelationScore } from "../components/Badges";

const PAGE_SIZE = 20;

export function AlertsListPage() {
  const { user } = useAuth();
  const canGenerate = user?.role === "admin" || user?.role === "soc_analyst";

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "">("");
  const [minScore, setMinScore] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listAlerts({
        status: statusFilter || undefined,
        min_score: minScore ? Number(minScore) : undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setAlerts(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, minScore, page]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  async function handleGenerateDemo() {
    setGenerating(true);
    setError(null);
    try {
      await api.generateDemoAlerts(5);
      setPage(0);
      await fetchAlerts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate demo alerts.");
    } finally {
      setGenerating(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Alerts</h1>
          <p className="text-sm text-slate-500">
            {total} alert{total === 1 ? "" : "s"} · sorted by most recent
          </p>
        </div>
        {canGenerate && (
          <button
            onClick={handleGenerateDemo}
            disabled={generating}
            className="rounded border border-soc-accent/50 bg-soc-accent/10 px-4 py-2 text-sm font-medium text-soc-accent transition hover:bg-soc-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate demo alerts"}
          </button>
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setPage(0);
            setStatusFilter(e.target.value as AlertStatus | "");
          }}
          className="rounded border border-soc-border bg-soc-panel px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
        </select>
        <input
          type="number"
          min={0}
          max={100}
          placeholder="Min correlation score"
          value={minScore}
          onChange={(e) => {
            setPage(0);
            setMinScore(e.target.value);
          }}
          className="w-48 rounded border border-soc-border bg-soc-panel px-3 py-1.5 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
        />
      </div>

      {error && (
        <div className="mb-4 rounded border border-soc-critical/40 bg-soc-critical/10 px-3 py-2 text-sm text-soc-critical">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-soc-border bg-soc-panel">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-soc-border text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 font-medium">Alert type</th>
              <th className="px-4 py-3 font-medium">Hostname</th>
              <th className="px-4 py-3 font-medium">Severity</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Loading alerts…
                </td>
              </tr>
            )}
            {!loading && alerts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No alerts match these filters.{" "}
                  {canGenerate && "Generate some demo alerts to populate the queue."}
                </td>
              </tr>
            )}
            {!loading &&
              alerts.map((alert) => (
                <tr
                  key={alert.id}
                  className="border-b border-soc-border last:border-0 hover:bg-soc-bg/50"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/alerts/${alert.id}`}
                      className="font-medium text-slate-200 hover:text-soc-accent"
                    >
                      {alert.alert_type}
                    </Link>
                    {alert.mitre_technique && (
                      <div className="font-mono text-xs text-slate-500">{alert.mitre_technique}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{alert.hostname ?? "—"}</td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={alert.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={alert.status} />
                  </td>
                  <td className="px-4 py-3">
                    <CorrelationScore score={alert.correlation_score} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(alert.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded border border-soc-border px-3 py-1.5 transition hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="rounded border border-soc-border px-3 py-1.5 transition hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
