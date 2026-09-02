export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-soc-border bg-soc-panel p-6 ${className}`}>{children}</div>
  );
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">{children}</h2>;
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded border border-dashed border-soc-border py-10 text-center">
      <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
      <p className="max-w-sm text-sm text-slate-500">{children}</p>
    </div>
  );
}
