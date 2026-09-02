export function StatCard({
  label,
  value,
  accent = "text-slate-100",
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="rounded-lg border border-soc-border bg-soc-panel p-5">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 font-mono text-3xl font-bold tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}

interface BreakdownRow {
  label: string;
  count: number;
  color: string; // tailwind bg-* class
}

export function BreakdownBars({ rows, total }: { rows: BreakdownRow[]; total: number }) {
  if (total === 0) {
    return <p className="text-sm text-slate-500">No data yet.</p>;
  }
  return (
    <div className="space-y-3">
      {rows.map((row) => {
        const pct = total > 0 ? Math.round((row.count / total) * 100) : 0;
        return (
          <div key={row.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="uppercase tracking-wide text-slate-400">{row.label}</span>
              <span className="font-mono text-slate-500">{row.count}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-soc-bg">
              <div className={`h-full rounded-full ${row.color}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
