import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../lib/api";
import type {
  AlertWithDetails,
  AlertStatus,
  AIReport,
  Playbook,
  PlaybookExecution,
} from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { SeverityBadge, StatusBadge, CorrelationScore } from "../components/Badges";

const STATUS_OPTIONS: AlertStatus[] = ["open", "investigating", "resolved"];

export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>();
  const { user } = useAuth();
  const canAct = user?.role === "admin" || user?.role === "soc_analyst";

  const [alert, setAlert] = useState<AlertWithDetails | null>(null);
  const [reports, setReports] = useState<AIReport[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [executions, setExecutions] = useState<PlaybookExecution[]>([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState<string>("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [runningPlaybook, setRunningPlaybook] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    if (!alertId) return;
    setLoading(true);
    setError(null);
    try {
      const [alertRes, reportsRes, playbooksRes, executionsRes] = await Promise.all([
        api.getAlert(alertId),
        api.listAIReports(alertId),
        api.listActivePlaybooks(),
        api.listExecutionsForAlert(alertId),
      ]);
      setAlert(alertRes);
      setReports(reportsRes.items);
      setPlaybooks(playbooksRes.items);
      setExecutions(executionsRes.items);
      setSelectedPlaybook((prev) => prev || playbooksRes.items[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert.");
    } finally {
      setLoading(false);
    }
  }, [alertId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleStatusChange(newStatus: AlertStatus) {
    if (!alertId) return;
    setStatusUpdating(true);
    setActionError(null);
    try {
      const updated = await api.updateAlertStatus(alertId, newStatus);
      setAlert((prev) => (prev ? { ...prev, status: updated.status } : prev));
      // A status change can trigger automatic playbooks server-side, so
      // re-pull execution history rather than assuming nothing happened.
      const executionsRes = await api.listExecutionsForAlert(alertId);
      setExecutions(executionsRes.items);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setStatusUpdating(false);
    }
  }

  async function handleGenerateReport() {
    if (!alertId) return;
    setGeneratingReport(true);
    setActionError(null);
    try {
      const report = await api.generateAIReport(alertId);
      setReports((prev) => [report, ...prev]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to generate AI report.");
    } finally {
      setGeneratingReport(false);
    }
  }

  async function handleRunPlaybook() {
    if (!alertId || !selectedPlaybook) return;
    setRunningPlaybook(true);
    setActionError(null);
    try {
      const execution = await api.runPlaybookManually(selectedPlaybook, alertId);
      setExecutions((prev) => [execution, ...prev]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to run playbook.");
    } finally {
      setRunningPlaybook(false);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-slate-500">Loading alert…</div>;
  }

  if (error || !alert) {
    return (
      <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-4 py-3 text-sm text-soc-critical">
        {error ?? "Alert not found."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/alerts" className="text-sm text-slate-500 hover:text-soc-accent">
          ← Back to alerts
        </Link>
      </div>

      {actionError && (
        <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-4 py-3 text-sm text-soc-critical">
          {actionError}
        </div>
      )}

      {/* Header */}
      <div className="rounded-lg border border-soc-border bg-soc-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">{alert.alert_type}</h1>
            <p className="mt-1 font-mono text-xs text-slate-500">{alert.id}</p>
          </div>
          <div className="flex items-center gap-3">
            <SeverityBadge severity={alert.severity} />
            <CorrelationScore score={alert.correlation_score} />
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">Hostname</div>
            <div className="mt-0.5 text-slate-300">{alert.hostname ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">User</div>
            <div className="mt-0.5 text-slate-300">{alert.user ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">MITRE technique</div>
            <div className="mt-0.5 font-mono text-slate-300">{alert.mitre_technique ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">Created</div>
            <div className="mt-0.5 text-slate-300">{new Date(alert.created_at).toLocaleString()}</div>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3 border-t border-soc-border pt-5">
          <span className="text-xs uppercase tracking-wide text-slate-500">Status</span>
          <StatusBadge status={alert.status} />
          {canAct && (
            <select
              value={alert.status}
              disabled={statusUpdating}
              onChange={(e) => handleStatusChange(e.target.value as AlertStatus)}
              className="ml-auto rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent disabled:opacity-50"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  Move to {s}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Indicators */}
      <div className="rounded-lg border border-soc-border bg-soc-panel p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Extracted indicators ({alert.extracted_indicators.length})
        </h2>
        {alert.indicator_details.length === 0 ? (
          <p className="text-sm text-slate-500">
            {alert.extracted_indicators.length === 0
              ? "No indicators were extracted from this alert."
              : "Indicators were extracted but no threat intel data is cached yet."}
          </p>
        ) : (
          <div className="overflow-hidden rounded border border-soc-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-soc-border text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-2 font-medium">Indicator</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Reputation</th>
                  <th className="px-3 py-2 font-medium">Risk score</th>
                  <th className="px-3 py-2 font-medium">Severity</th>
                </tr>
              </thead>
              <tbody>
                {alert.indicator_details.map((ind) => (
                  <tr key={ind.indicator} className="border-b border-soc-border last:border-0">
                    <td className="px-3 py-2 font-mono text-slate-300">{ind.indicator}</td>
                    <td className="px-3 py-2 text-slate-400">{ind.type}</td>
                    <td className="px-3 py-2 text-slate-400">{ind.reputation ?? "—"}</td>
                    <td className="px-3 py-2 text-slate-300">{ind.risk_score}</td>
                    <td className="px-3 py-2">
                      <SeverityBadge severity={ind.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* AI Reports */}
      <div className="rounded-lg border border-soc-border bg-soc-panel p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">AI triage reports</h2>
          {canAct && (
            <button
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className="rounded border border-soc-accent/50 bg-soc-accent/10 px-3 py-1.5 text-xs font-medium text-soc-accent transition hover:bg-soc-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generatingReport ? "Generating…" : "Generate new report"}
            </button>
          )}
        </div>
        {reports.length === 0 ? (
          <p className="text-sm text-slate-500">No AI reports have been generated for this alert yet.</p>
        ) : (
          <div className="space-y-4">
            {reports.map((report) => (
              <div key={report.id} className="rounded border border-soc-border bg-soc-bg p-4">
                <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                  <span className="font-mono uppercase text-soc-accent">
                    {report.ai_provider_used ?? "unknown provider"}
                  </span>
                  <span>{new Date(report.created_at).toLocaleString()}</span>
                </div>
                {report.summary && <p className="text-sm text-slate-300">{report.summary}</p>}
                {report.recommended_actions && report.recommended_actions.length > 0 && (
                  <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-400">
                    {report.recommended_actions.map((action, i) => (
                      <li key={i}>{action}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Playbooks */}
      <div className="rounded-lg border border-soc-border bg-soc-panel p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">Playbook response</h2>

        {canAct && (
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <select
              value={selectedPlaybook}
              onChange={(e) => setSelectedPlaybook(e.target.value)}
              className="rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
            >
              {playbooks.length === 0 && <option value="">No active playbooks</option>}
              {playbooks.map((pb) => (
                <option key={pb.id} value={pb.id}>
                  {pb.name} ({pb.trigger_type})
                </option>
              ))}
            </select>
            <button
              onClick={handleRunPlaybook}
              disabled={runningPlaybook || !selectedPlaybook}
              className="rounded border border-soc-accent/50 bg-soc-accent/10 px-3 py-1.5 text-xs font-medium text-soc-accent transition hover:bg-soc-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runningPlaybook ? "Running…" : "Run manually"}
            </button>
            <span className="text-xs text-slate-500">
              A manual run always executes, regardless of trigger conditions.
            </span>
          </div>
        )}

        <h3 className="mb-2 text-xs uppercase tracking-wide text-slate-500">Execution history</h3>
        {executions.length === 0 ? (
          <p className="text-sm text-slate-500">No playbooks have run against this alert yet.</p>
        ) : (
          <div className="space-y-2">
            {executions.map((exec) => (
              <div
                key={exec.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-soc-border bg-soc-bg px-4 py-2.5 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium uppercase ${
                      exec.status === "success"
                        ? "bg-soc-safe/15 text-soc-safe"
                        : exec.status === "failed"
                          ? "bg-soc-critical/15 text-soc-critical"
                          : "bg-soc-medium/15 text-soc-medium"
                    }`}
                  >
                    {exec.status}
                  </span>
                  <span className="text-slate-400">{exec.trigger_source}</span>
                  <span className="text-xs text-slate-500">
                    {exec.actions_taken?.length ?? 0} action{exec.actions_taken?.length === 1 ? "" : "s"}
                  </span>
                </div>
                <span className="text-xs text-slate-500">{new Date(exec.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
