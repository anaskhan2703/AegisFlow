import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Playbook, PlaybookInput } from "../lib/api";
import { CONDITION_FIELDS, CONDITION_OPERATORS, PLAYBOOK_ACTIONS } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Card, SectionHeading, EmptyState } from "../components/Card";

interface ConditionRow {
  field: string;
  op: string;
  value: string;
}

interface StepRow {
  action: string;
  // Flat param bag — which keys matter depends on `action`. Kept as strings
  // in the form and coerced to the right shape in buildPayload().
  status?: string;
  reason?: string;
  severity?: string;
  title?: string;
  description?: string;
  message?: string;
}

const ALERT_STATUS_VALUES = ["open", "investigating", "resolved"];
const SEVERITY_VALUES = ["low", "medium", "high", "critical"];

function emptyCondition(): ConditionRow {
  return { field: CONDITION_FIELDS[0], op: "==", value: "" };
}

function emptyStep(): StepRow {
  return { action: PLAYBOOK_ACTIONS[0].name };
}

function conditionsToRows(conditions: Record<string, unknown>[] | null | undefined): ConditionRow[] {
  if (!conditions || conditions.length === 0) return [];
  return conditions.map((c) => ({
    field: String(c.field ?? CONDITION_FIELDS[0]),
    op: String(c.op ?? "=="),
    value: Array.isArray(c.value) ? c.value.join(", ") : String(c.value ?? ""),
  }));
}

function stepsToRows(steps: Record<string, unknown>[] | null | undefined): StepRow[] {
  if (!steps || steps.length === 0) return [emptyStep()];
  return steps.map((s) => {
    const params = (s.params as Record<string, unknown>) ?? {};
    return {
      action: String(s.action ?? PLAYBOOK_ACTIONS[0].name),
      status: params.status as string | undefined,
      reason: params.reason as string | undefined,
      severity: params.severity as string | undefined,
      title: params.title as string | undefined,
      description: params.description as string | undefined,
      message: params.message as string | undefined,
    };
  });
}

function buildPayload(
  name: string,
  description: string,
  triggerType: "automatic" | "manual",
  isActive: boolean,
  conditions: ConditionRow[],
  steps: StepRow[]
): PlaybookInput {
  const trigger_conditions =
    conditions.length === 0
      ? null
      : conditions.map((c) => {
          let value: unknown = c.value;
          if (c.field === "correlation_score") {
            value = c.op === "in" ? c.value.split(",").map((v) => Number(v.trim())) : Number(c.value);
          } else if (c.op === "in") {
            value = c.value.split(",").map((v) => v.trim());
          }
          return { field: c.field, op: c.op, value };
        });

  const builtSteps = steps.map((s) => {
    const params: Record<string, unknown> = {};
    switch (s.action) {
      case "update_alert_status":
        if (s.status) params.status = s.status;
        break;
      case "flag_indicator":
        if (s.reason) params.reason = s.reason;
        break;
      case "create_incident":
        if (s.severity) params.severity = s.severity;
        if (s.title) params.title = s.title;
        if (s.description) params.description = s.description;
        break;
      case "notify_analyst":
        if (s.message) params.message = s.message;
        break;
      default:
        break;
    }
    return { action: s.action, params };
  });

  return {
    name,
    description: description || null,
    trigger_type: triggerType,
    trigger_conditions,
    steps: builtSteps,
    is_active: isActive,
  };
}

function StepParamFields({ step, onChange }: { step: StepRow; onChange: (patch: Partial<StepRow>) => void }) {
  switch (step.action) {
    case "update_alert_status":
      return (
        <select
          value={step.status ?? ""}
          onChange={(e) => onChange({ status: e.target.value })}
          className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none focus:border-soc-accent"
        >
          <option value="">Choose status…</option>
          {ALERT_STATUS_VALUES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      );
    case "flag_indicator":
      return (
        <input
          value={step.reason ?? ""}
          onChange={(e) => onChange({ reason: e.target.value })}
          placeholder="Reason (optional)"
          className="w-full rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
        />
      );
    case "create_incident":
      return (
        <div className="grid gap-2 sm:grid-cols-3">
          <select
            value={step.severity ?? ""}
            onChange={(e) => onChange({ severity: e.target.value })}
            className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none focus:border-soc-accent"
          >
            <option value="">Severity: alert's own</option>
            {SEVERITY_VALUES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            value={step.title ?? ""}
            onChange={(e) => onChange({ title: e.target.value })}
            placeholder="Title (optional)"
            className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
          />
          <input
            value={step.description ?? ""}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="Description (optional)"
            className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
          />
        </div>
      );
    case "notify_analyst":
      return (
        <input
          value={step.message ?? ""}
          onChange={(e) => onChange({ message: e.target.value })}
          placeholder="Message (optional)"
          className="w-full rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
        />
      );
    default:
      return <span className="text-xs text-slate-600">Recorded as recommended-only — no params needed.</span>;
  }
}

function PlaybookForm({
  initial,
  onCancel,
  onSaved,
}: {
  initial: Playbook | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [triggerType, setTriggerType] = useState<"automatic" | "manual">(
    (initial?.trigger_type as "automatic" | "manual") ?? "manual"
  );
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [conditions, setConditions] = useState<ConditionRow[]>(conditionsToRows(initial?.trigger_conditions));
  const [steps, setSteps] = useState<StepRow[]>(stepsToRows(initial?.steps));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateCondition(i: number, patch: Partial<ConditionRow>) {
    setConditions((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function updateStep(i: number, patch: Partial<StepRow>) {
    setSteps((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (steps.length === 0) {
      setError("A playbook needs at least one step.");
      return;
    }
    setSaving(true);
    try {
      const payload = buildPayload(name, description, triggerType, isActive, conditions, steps);
      if (initial) {
        await api.updatePlaybook(initial.id, payload);
      } else {
        await api.createPlaybook(payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save playbook.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="mb-6">
      <SectionHeading>{initial ? `Edit: ${initial.name}` : "New playbook"}</SectionHeading>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Trigger type</label>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as "automatic" | "manual")}
              className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none focus:border-soc-accent"
            >
              <option value="manual">Manual — run on demand only</option>
              <option value="automatic">Automatic — evaluated on every alert ingest/status change</option>
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What this playbook is for (optional)"
            className="w-full rounded border border-soc-border bg-soc-bg px-3 py-1.5 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active
        </label>

        {/* Trigger conditions */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Trigger conditions {triggerType === "automatic" ? "(ANDed — empty always matches)" : "(ignored for manual runs)"}
            </span>
            <button
              type="button"
              onClick={() => setConditions((prev) => [...prev, emptyCondition()])}
              className="text-xs text-soc-accent hover:underline"
            >
              + Add condition
            </button>
          </div>
          {conditions.length === 0 && <p className="text-xs text-slate-600">No conditions — always matches.</p>}
          <div className="space-y-2">
            {conditions.map((c, i) => (
              <div key={i} className="flex items-center gap-2">
                <select
                  value={c.field}
                  onChange={(e) => updateCondition(i, { field: e.target.value })}
                  className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none focus:border-soc-accent"
                >
                  {CONDITION_FIELDS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
                <select
                  value={c.op}
                  onChange={(e) => updateCondition(i, { op: e.target.value })}
                  className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none focus:border-soc-accent"
                >
                  {CONDITION_OPERATORS.map((op) => (
                    <option key={op} value={op}>
                      {op}
                    </option>
                  ))}
                </select>
                <input
                  value={c.value}
                  onChange={(e) => updateCondition(i, { value: e.target.value })}
                  placeholder={c.op === "in" ? "comma, separated, values" : "value"}
                  className="flex-1 rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none placeholder:text-slate-600 focus:border-soc-accent"
                />
                <button
                  type="button"
                  onClick={() => setConditions((prev) => prev.filter((_, idx) => idx !== i))}
                  className="px-2 text-slate-600 hover:text-soc-critical"
                  aria-label="Remove condition"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Steps */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs uppercase tracking-wide text-slate-500">Steps (run in order)</span>
            <button
              type="button"
              onClick={() => setSteps((prev) => [...prev, emptyStep()])}
              className="text-xs text-soc-accent hover:underline"
            >
              + Add step
            </button>
          </div>
          <div className="space-y-2">
            {steps.map((s, i) => (
              <div key={i} className="rounded border border-soc-border bg-soc-bg/50 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-600">{i + 1}.</span>
                  <select
                    value={s.action}
                    onChange={(e) => updateStep(i, { action: e.target.value })}
                    className="rounded border border-soc-border bg-soc-bg px-2 py-1 text-sm text-slate-300 outline-none focus:border-soc-accent"
                  >
                    {PLAYBOOK_ACTIONS.map((a) => (
                      <option key={a.name} value={a.name}>
                        {a.name} {a.auto ? "" : "(recommend-only)"}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setSteps((prev) => prev.filter((_, idx) => idx !== i))}
                    className="ml-auto px-2 text-slate-600 hover:text-soc-critical"
                    aria-label="Remove step"
                  >
                    ✕
                  </button>
                </div>
                <StepParamFields step={s} onChange={(patch) => updateStep(i, patch)} />
              </div>
            ))}
          </div>
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
            {saving ? "Saving…" : initial ? "Save changes" : "Create playbook"}
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

export function PlaybooksPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<"none" | "create" | string>("none");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listPlaybooks();
      setPlaybooks(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load playbooks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleToggleActive(pb: Playbook) {
    try {
      await api.updatePlaybook(pb.id, { is_active: !pb.is_active });
      setPlaybooks((prev) => prev.map((p) => (p.id === pb.id ? { ...p, is_active: !p.is_active } : p)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update playbook.");
    }
  }

  const editingPlaybook =
    typeof formMode === "string" && formMode !== "none" && formMode !== "create"
      ? playbooks.find((p) => p.id === formMode) ?? null
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Playbooks</h1>
          <p className="text-sm text-slate-500">
            {playbooks.length} playbook{playbooks.length === 1 ? "" : "s"}
          </p>
        </div>
        {isAdmin && formMode === "none" && (
          <button
            onClick={() => setFormMode("create")}
            className="rounded border border-soc-accent/50 bg-soc-accent/10 px-4 py-2 text-sm font-medium text-soc-accent hover:bg-soc-accent/20"
          >
            New playbook
          </button>
        )}
      </div>

      {error && (
        <div className="rounded border border-soc-critical/40 bg-soc-critical/10 px-4 py-3 text-sm text-soc-critical">
          {error}
        </div>
      )}

      {isAdmin && formMode === "create" && (
        <PlaybookForm
          initial={null}
          onCancel={() => setFormMode("none")}
          onSaved={() => {
            setFormMode("none");
            load();
          }}
        />
      )}
      {isAdmin && editingPlaybook && (
        <PlaybookForm
          initial={editingPlaybook}
          onCancel={() => setFormMode("none")}
          onSaved={() => {
            setFormMode("none");
            load();
          }}
        />
      )}

      {loading ? (
        <p className="text-center text-slate-500">Loading playbooks…</p>
      ) : playbooks.length === 0 ? (
        <EmptyState>
          No playbooks yet. {isAdmin ? "Create one to automate a response." : "An admin needs to create one."}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {playbooks.map((pb) => (
            <Card key={pb.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-slate-200">{pb.name}</h3>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-xs uppercase ${
                        pb.is_active
                          ? "border-soc-safe/40 bg-soc-safe/10 text-soc-safe"
                          : "border-slate-600 bg-slate-800 text-slate-500"
                      }`}
                    >
                      {pb.is_active ? "active" : "inactive"}
                    </span>
                    <span className="rounded border border-soc-border px-1.5 py-0.5 text-xs uppercase text-slate-500">
                      {pb.trigger_type}
                    </span>
                  </div>
                  {pb.description && <p className="mt-1 text-sm text-slate-500">{pb.description}</p>}
                  <p className="mt-1 text-xs text-slate-600">
                    {pb.trigger_conditions?.length ?? 0} condition{(pb.trigger_conditions?.length ?? 0) === 1 ? "" : "s"} ·{" "}
                    {pb.steps?.length ?? 0} step{(pb.steps?.length ?? 0) === 1 ? "" : "s"}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setFormMode(pb.id)}
                      className="rounded border border-soc-border px-3 py-1 text-xs text-slate-400 hover:text-slate-200"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleToggleActive(pb)}
                      className="rounded border border-soc-border px-3 py-1 text-xs text-slate-400 hover:text-slate-200"
                    >
                      {pb.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
