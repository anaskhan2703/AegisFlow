import type { AlertSeverity, AlertStatus } from "../lib/api";

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  critical: "bg-soc-critical/15 text-soc-critical border-soc-critical/40",
  high: "bg-soc-high/15 text-soc-high border-soc-high/40",
  medium: "bg-soc-medium/15 text-soc-medium border-soc-medium/40",
  low: "bg-soc-low/15 text-soc-low border-soc-low/40",
};

export function SeverityBadge({ severity }: { severity: AlertSeverity | string }) {
  const style = SEVERITY_STYLES[severity as AlertSeverity] ?? SEVERITY_STYLES.low;
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${style}`}
    >
      {severity}
    </span>
  );
}

const STATUS_STYLES: Record<AlertStatus, string> = {
  open: "bg-soc-critical/15 text-soc-critical border-soc-critical/40",
  investigating: "bg-soc-medium/15 text-soc-medium border-soc-medium/40",
  resolved: "bg-soc-safe/15 text-soc-safe border-soc-safe/40",
};

export function StatusBadge({ status }: { status: AlertStatus | string }) {
  const style = STATUS_STYLES[status as AlertStatus] ?? "bg-slate-500/15 text-slate-400 border-slate-500/40";
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${style}`}
    >
      {status}
    </span>
  );
}

export function CorrelationScore({ score }: { score: number }) {
  let color = "text-soc-safe";
  if (score >= 80) color = "text-soc-critical";
  else if (score >= 50) color = "text-soc-high";
  else if (score >= 25) color = "text-soc-medium";

  return (
    <span className={`font-mono text-sm font-semibold ${color}`}>
      {score}
      <span className="text-slate-500">/100</span>
    </span>
  );
}
