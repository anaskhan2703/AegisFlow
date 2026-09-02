import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Incident, IncidentStatus, IncidentSeverity, Alert } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Card, SectionHeading, EmptyState } from "../components/Card";
import { SeverityBadge } from "../components/Badges";

const STATUS_VALUES: IncidentStatus[] = ["open", "in_progress", "resolved", "closed"];
const SEVERITY_VALUES: IncidentSeverity[] = ["low", "medium", "high", "critical"];

const STATUS_STYLES: Record<IncidentStatus, string> = {
  open: "bg-soc-critical/15 text-soc-critical border-soc-critical/40",
  in_progress: "bg-soc-medium/15 text-soc-medium border-soc-medium/40",
  resolved: "bg-soc-safe/15 text-soc-safe border-soc-safe/40",
  closed: "bg-slate-500/15 text-slate-400 border-slate-500/40",
};

function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function CreateIncidentForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<IncidentSeverity>("medium");
  const [relatedAlertId, setRelatedAlertId] = useState("");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Recent alerts to link, not exhaustive — this is a convenience picker,
    // not a search. Someone linking an older alert can still do so once the
    // detail page grows an "open incident" shortcut in a future pass.
    api
      .listAlerts({ limit: 30 })
      .then((res) => setAlerts(res.items))
      .catch(() => setAlerts([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.createIncident({
        title,
        description: description || null,
        severity,
        related_alert_id: relatedAlertId || null,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create incident.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="mb-6">
      <SectionHeading>New incident</SectionHeading>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Title</label>
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Severity</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}
              className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
            >
              {SEVERITY_VALUES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Related alert</label>
            <select
              value={relatedAlertId}
              onChange={(e) => setRelatedAlertId(e.target.value)}
              className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
            >
              <option value="">None</option>
              {alerts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.alert_type} — {a.hostname ?? "unknown host"} ({a.correlation_score}/100)
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
          />
        </div>
        {error && (
          <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-3 py-2 text-sm text-soc-critical">
            {error}
          </div>
        )}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-soc-accent px-4 py-1.5 text-sm font-semibold text-soc-bg transition hover:bg-soc-accent/90 disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create incident"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-soc-border px-4 py-1.5 text-sm text-slate-400 hover:text-slate-200"
          >
            Cancel
          </button>
        </div>
      </form>
    </Card>
  );
}

export function IncidentsPage() {
  const { user } = useAuth();
  const canAct = user?.role === "admin" || user?.role === "soc_analyst";

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [severityFilter, setSeverityFilter] = useState<IncidentSeverity | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listIncidents({
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        limit: 100,
      });
      setIncidents(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleStatusChange(incident: Incident, newStatus: IncidentStatus) {
    setUpdatingId(incident.id);
    setError(null);
    try {
      const updated = await api.updateIncident(incident.id, { status: newStatus });
      setIncidents((prev) => prev.map((i) => (i.id === incident.id ? updated : i)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update incident.");
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Incidents</h1>
          <p className="text-sm text-slate-500">
            {total} incident{total === 1 ? "" : "s"}
          </p>
        </div>
        {canAct && !showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="rounded border border-soc-accent/50 bg-soc-accent/10 px-4 py-2 text-sm font-medium text-soc-accent hover:bg-soc-accent/20"
          >
            New incident
          </button>
        )}
      </div>

      {canAct && showCreate && (
        <CreateIncidentForm
          onCancel={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}

      <div className="flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "")}
          className="rounded border border-soc-border bg-soc-panel px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
        >
          <option value="">All statuses</option>
          {STATUS_VALUES.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as IncidentSeverity | "")}
          className="rounded border border-soc-border bg-soc-panel px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
        >
          <option value="">All severities</option>
          {SEVERITY_VALUES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-4 py-3 text-sm text-soc-critical">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-center text-slate-500">Loading incidents…</p>
      ) : incidents.length === 0 ? (
        <EmptyState>
          No incidents match these filters.{" "}
          {canAct && "Incidents also open automatically when a playbook's create_incident step fires."}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {incidents.map((incident) => (
            <Card key={incident.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium text-slate-200">{incident.title}</h3>
                    <SeverityBadge severity={incident.severity} />
                    <IncidentStatusBadge status={incident.status} />
                  </div>
                  {incident.description && (
                    <p className="mt-1 text-sm text-slate-500">{incident.description}</p>
                  )}
                  {incident.related_alert && (
                    <p className="mt-1 text-xs text-slate-600">
                      Linked to alert: {incident.related_alert.alert_type} on{" "}
                      {incident.related_alert.hostname ?? "unknown host"}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-slate-600">
                    Opened {new Date(incident.created_at).toLocaleString()}
                    {incident.resolved_at && ` · Resolved ${new Date(incident.resolved_at).toLocaleString()}`}
                  </p>
                </div>
                {canAct && (
                  <select
                    value={incident.status}
                    disabled={updatingId === incident.id}
                    onChange={(e) => handleStatusChange(incident, e.target.value as IncidentStatus)}
                    className="rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent disabled:opacity-50"
                  >
                    {STATUS_VALUES.map((s) => (
                      <option key={s} value={s}>
                        Move to {s.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
