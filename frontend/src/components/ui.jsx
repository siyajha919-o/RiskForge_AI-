import { AlertTriangle, Loader2, ShieldAlert } from 'lucide-react';
import { riskStyle } from '../lib/format';

export function Panel({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h3 className="panel-title">{title}</h3>}
            {subtitle && <p className="panel-sub">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function RiskBadge({ level, label, className = '' }) {
  // `label` lets a badge show its own wording (e.g. a remediation status) while
  // still borrowing the risk palette for severity.
  const s = riskStyle(level);
  return (
    <span className={`chip ${s.bg} ${s.border} ${s.text} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {label ?? level}
    </span>
  );
}

export function StatCard({ label, value, sub, level, icon: Icon, accent }) {
  const s = level ? riskStyle(level) : null;
  return (
    <div className="glass group relative overflow-hidden p-5 transition-all duration-300 hover:border-sand/35">
      {/* Accent bar carries the severity so the number itself stays legible ink. */}
      {s && <div className={`absolute inset-x-0 top-0 h-0.5 ${s.dot}`} />}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold tabular-nums tracking-tight text-cream">
            {value}
          </p>
          {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
        </div>
        {Icon && (
          <div className={`rounded-lg p-2 ${s ? s.bg : 'bg-sand/10'}`}>
            <Icon className={`h-4 w-4 ${s ? s.text : 'text-muted'}`} />
          </div>
        )}
      </div>
      {level && (
        <div className="mt-3">
          <RiskBadge level={level} />
        </div>
      )}
      {accent}
    </div>
  );
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-3 py-20 text-muted">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry, hint }) {
  return (
    <div className="glass flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="rounded-full bg-risk-critical/12 p-3">
        <AlertTriangle className="h-5 w-5 text-risk-critical" />
      </div>
      <p className="text-sm font-medium text-cream">{message}</p>
      {hint && <p className="max-w-md text-xs leading-relaxed text-muted">{hint}</p>}
      {onRetry && (
        <button className="btn-secondary mt-2" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message, hint }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <ShieldAlert className="h-5 w-5 text-muted/60" />
      <p className="text-sm text-cream/80">{message}</p>
      {hint && <p className="max-w-md text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Tooltip shared by every chart, so hover reads identically across the app. */
export function ChartTooltip({ active, payload, label, formatter, labelFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-strong px-3 py-2 text-xs">
      {label != null && (
        <p className="mb-1.5 font-semibold text-cream">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      )}
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span
            className="h-2 w-2 flex-none rounded-sm"
            style={{ background: entry.color || entry.fill }}
          />
          <span className="text-muted">{entry.name}</span>
          <span className="ml-auto font-semibold tabular-nums text-cream">
            {formatter ? formatter(entry.value, entry.name, entry) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SectionHeading({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-cream">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}
