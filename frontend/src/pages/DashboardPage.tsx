import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/api";
import type { Alert, Incident, PlaybookExecution } from "../lib/api";
import { StatCard, BreakdownBars } from "../components/Dashboard";
import { Card, SectionHeading, EmptyState } from "../components/Card";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-soc-critical",
  high: "bg-soc-high",
  medium: "bg-soc-medium",
  low: "bg-soc-low",
};

const ALERT_STATUS_COLORS: Record<string, string> = {
  open: "bg-soc-critical",
  investigating: "bg-soc-medium",
  resolved: "bg-soc-safe",
};

const INCIDENT_STATUS_COLORS: Record<string, string> = {
  open: "bg-soc-critical",
  in_progress: "bg-soc-medium",
  resolved: "bg-soc-safe",
  closed: "bg-slate-600",
};

interface Stats {
  alertsTotal: number;
  alertsOpen: number;
  alertsByStatus: { label: string; count: number }[];
  alertsBySeverity: { label: string; count: number }[];
  alertsSampleSize: number;
  incidentsTotal: number;
  incidentsByStatus: { label: string; count: number }[];
  incidentsBySeverity: { label: string; count: number }[];
  incidentsSampleSize: number;
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [recentIncidents, setRecentIncidents] = useState<Incident[]>([]);
  const [recentExecutions, setRecentExecutions] = useState<PlaybookExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        // Alert status counts come from the backend's exact filtered totals
        // (accurate regardless of table size). Severity has no server-side
        // filter on this endpoint, so it's approximated from a capped
        // sample of the most recent 200 alerts — accurate for a portfolio
        // dataset, worth revisiting with a real aggregate query if this
        // table ever grows past that.
        const [
          allAlerts,
          openAlerts,
          investigatingAlerts,
          resolvedAlerts,
          sampleAlerts,
          openIncidents,
          inProgressIncidents,
          resolvedIncidents,
          closedIncidents,
          sampleIncidents,
          executions,
        ] = await Promise.all([
          api.listAlerts({ limit: 1 }),
          api.listAlerts({ status: "open", limit: 1 }),
          api.listAlerts({ status: "investigating", limit: 1 }),
          api.listAlerts({ status: "resolved", limit: 1 }),
          api.listAlerts({ limit: 200 }),
          api.listIncidents({ status: "open", limit: 1 }),
          api.listIncidents({ status: "in_progress", limit: 1 }),
          api.listIncidents({ status: "resolved", limit: 1 }),
          api.listIncidents({ status: "closed", limit: 1 }),
          api.listIncidents({ limit: 200 }),
          api.listRecentExecutions(8),
        ]);

        if (cancelled) return;

        const severityCounts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
        for (const a of sampleAlerts.items) severityCounts[a.severity] = (severityCounts[a.severity] ?? 0) + 1;

        const incidentSeverityCounts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
        for (const i of sampleIncidents.items)
          incidentSeverityCounts[i.severity] = (incidentSeverityCounts[i.severity] ?? 0) + 1;

        setStats({
          alertsTotal: allAlerts.total,
          alertsOpen: openAlerts.total,
          alertsByStatus: [
            { label: "open", count: openAlerts.total },
            { label: "investigating", count: investigatingAlerts.total },
            { label: "resolved", count: resolvedAlerts.total },
          ],
          alertsBySeverity: [
            { label: "critical", count: severityCounts.critical },
            { label: "high", count: severityCounts.high },
            { label: "medium", count: severityCounts.medium },
            { label: "low", count: severityCounts.low },
          ],
          alertsSampleSize: sampleAlerts.items.length,
          incidentsTotal: openIncidents.total + inProgressIncidents.total + resolvedIncidents.total + closedIncidents.total,
          incidentsByStatus: [
            { label: "open", count: openIncidents.total },
            { label: "in_progress", count: inProgressIncidents.total },
            { label: "resolved", count: resolvedIncidents.total },
            { label: "closed", count: closedIncidents.total },
          ],
          incidentsBySeverity: [
            { label: "critical", count: incidentSeverityCounts.critical },
            { label: "high", count: incidentSeverityCounts.high },
            { label: "medium", count: incidentSeverityCounts.medium },
            { label: "low", count: incidentSeverityCounts.low },
          ],
          incidentsSampleSize: sampleIncidents.items.length,
        });
        setRecentAlerts(sampleAlerts.items.slice(0, 5));
        setRecentIncidents(sampleIncidents.items.slice(0, 5));
        setRecentExecutions(executions.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-slate-500">Loading dashboard…</div>;
  }

  if (error || !stats) {
    return (
      <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-4 py-3 text-sm text-soc-critical">
        {error ?? "Failed to load dashboard."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Overview</h1>
        <p className="text-sm text-slate-500">Snapshot of current alert and incident volume.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total alerts" value={stats.alertsTotal} />
        <StatCard
          label="Open alerts"
          value={stats.alertsOpen}
          accent={stats.alertsOpen > 0 ? "text-soc-critical" : "text-soc-safe"}
        />
        <StatCard label="Total incidents" value={stats.incidentsTotal} />
        <StatCard
          label="Open incidents"
          value={stats.incidentsByStatus[0].count}
          accent={stats.incidentsByStatus[0].count > 0 ? "text-soc-critical" : "text-soc-safe"}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <SectionHeading>Alerts by severity</SectionHeading>
          <BreakdownBars
            total={stats.alertsSampleSize}
            rows={stats.alertsBySeverity.map((r) => ({ ...r, color: SEVERITY_COLORS[r.label] }))}
          />
          {stats.alertsSampleSize < stats.alertsTotal && (
            <p className="mt-3 text-xs text-slate-600">
              Based on the {stats.alertsSampleSize} most recent of {stats.alertsTotal} alerts.
            </p>
          )}
        </Card>
        <Card>
          <SectionHeading>Alerts by status</SectionHeading>
          <BreakdownBars
            total={stats.alertsTotal}
            rows={stats.alertsByStatus.map((r) => ({ ...r, color: ALERT_STATUS_COLORS[r.label] }))}
          />
        </Card>
        <Card>
          <SectionHeading>Incidents by severity</SectionHeading>
          <BreakdownBars
            total={stats.incidentsSampleSize}
            rows={stats.incidentsBySeverity.map((r) => ({ ...r, color: SEVERITY_COLORS[r.label] }))}
          />
        </Card>
        <Card>
          <SectionHeading>Incidents by status</SectionHeading>
          <BreakdownBars
            total={stats.incidentsTotal}
            rows={stats.incidentsByStatus.map((r) => ({ ...r, color: INCIDENT_STATUS_COLORS[r.label] }))}
          />
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <SectionHeading>Recent alerts</SectionHeading>
            <Link to="/alerts" className="text-xs text-soc-accent hover:underline">
              View all →
            </Link>
          </div>
          {recentAlerts.length === 0 ? (
            <EmptyState>No alerts yet. Generate some demo alerts from the Alerts page to get started.</EmptyState>
          ) : (
            <div className="space-y-2">
              {recentAlerts.map((a) => (
                <Link
                  key={a.id}
                  to={`/alerts/${a.id}`}
                  className="flex items-center justify-between rounded border border-soc-border bg-soc-bg px-3 py-2 text-sm hover:border-soc-accent/50"
                >
                  <span className="text-slate-300">{a.alert_type}</span>
                  <span className="font-mono text-xs text-slate-500">{a.correlation_score}/100</span>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <SectionHeading>Recent incidents</SectionHeading>
            <Link to="/incidents" className="text-xs text-soc-accent hover:underline">
              View all →
            </Link>
          </div>
          {recentIncidents.length === 0 ? (
            <EmptyState>No incidents yet. Incidents show up here once opened manually or by a playbook.</EmptyState>
          ) : (
            <div className="space-y-2">
              {recentIncidents.map((i) => (
                <Link
                  key={i.id}
                  to={`/incidents`}
                  className="flex items-center justify-between rounded border border-soc-border bg-soc-bg px-3 py-2 text-sm hover:border-soc-accent/50"
                >
                  <span className="truncate text-slate-300">{i.title}</span>
                  <span className="ml-2 shrink-0 font-mono text-xs uppercase text-slate-500">{i.status}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <SectionHeading>Recent playbook activity</SectionHeading>
          <Link to="/playbooks" className="text-xs text-soc-accent hover:underline">
            View playbooks →
          </Link>
        </div>
        {recentExecutions.length === 0 ? (
          <EmptyState>No playbooks have run yet.</EmptyState>
        ) : (
          <div className="space-y-2">
            {recentExecutions.map((exec) => (
              <div
                key={exec.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-soc-border bg-soc-bg px-3 py-2 text-sm"
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
                </div>
                <span className="text-xs text-slate-500">{new Date(exec.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
