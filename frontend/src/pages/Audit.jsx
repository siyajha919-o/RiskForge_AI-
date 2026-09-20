import { useEffect, useMemo, useState } from 'react';
import { Download, History, Search, ShieldCheck, TriangleAlert } from 'lucide-react';

import { api } from '../lib/api';
import { num } from '../lib/format';
import { EmptyState, ErrorState, Loading, Panel, SectionHeading, StatCard } from '../components/ui';

/**
 * Audit trail — the evidence surface for regulators and governance committees.
 *
 * Renders the append-only log written by src/audit.py. The endpoint is gated to
 * CISO/ADMIN, so a viewer landing here sees the 403 as a plain explanation
 * rather than an empty table.
 */

const OK = new Set(['ok', 'success']);

/** Actions are free-form strings from the engine; render them as words. */
const humanize = (s) =>
  String(s || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

function StatusChip({ status }) {
  const good = OK.has(String(status).toLowerCase());
  return (
    <span
      className={`chip ${
        good
          ? 'border-risk-low/40 bg-risk-low/12 text-risk-low'
          : 'border-risk-critical/40 bg-risk-critical/12 text-risk-critical'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${good ? 'bg-risk-low' : 'bg-risk-critical'}`} />
      {status || 'unknown'}
    </span>
  );
}

export default function Audit() {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [action, setAction] = useState('all');

  const load = () =>
    api
      .auditLog()
      .then((d) => {
        // Newest first — an auditor reads the most recent activity, not 2019.
        setEntries(Array.isArray(d) ? [...d].reverse() : []);
        setError(null);
      })
      .catch((e) => setError(e.friendlyMessage || 'Could not load the audit log.'));

  useEffect(() => {
    load();
  }, []);

  const actions = useMemo(
    () => ['all', ...new Set((entries || []).map((e) => e.action).filter(Boolean))],
    [entries]
  );

  const rows = useMemo(() => {
    if (!entries) return [];
    const q = query.trim().toLowerCase();
    return entries.filter((e) => {
      if (action !== 'all' && e.action !== action) return false;
      if (!q) return true;
      return JSON.stringify(e).toLowerCase().includes(q);
    });
  }, [entries, query, action]);

  const failures = useMemo(
    () => (entries || []).filter((e) => !OK.has(String(e.status).toLowerCase())).length,
    [entries]
  );

  /** Exports exactly what is on screen, so a filtered view is defensible evidence. */
  function exportJson() {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `riskforge-audit-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (error) {
    return (
      <>
        <SectionHeading title="Audit Trail" subtitle="Recorded platform activity" />
        <ErrorState
          message={error}
          onRetry={load}
          hint="The audit log is restricted to CISO and administrator roles."
        />
      </>
    );
  }
  if (!entries) return <Loading label="Loading audit trail…" />;

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Audit Trail"
        subtitle="Append-only record of pipeline runs, recomputes and telemetry ingest"
        actions={
          <button className="btn-secondary" onClick={exportJson} disabled={!rows.length}>
            <Download className="h-4 w-4" />
            Export view
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Recorded events" value={num(entries.length)} icon={History} />
        <StatCard label="Distinct actions" value={num(actions.length - 1)} icon={ShieldCheck} />
        <StatCard
          label="Failed events"
          value={num(failures)}
          icon={TriangleAlert}
          level={failures ? 'High' : 'Low'}
        />
      </div>

      <Panel
        title="Events"
        subtitle={`${num(rows.length)} of ${num(entries.length)} shown`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted/70" />
              <input
                className="input py-2 pl-9 text-xs"
                placeholder="Search actor, action, detail…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <select
              className="input w-auto py-2 text-xs"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              {actions.map((a) => (
                <option key={a} value={a}>
                  {a === 'all' ? 'All actions' : humanize(a)}
                </option>
              ))}
            </select>
          </div>
        }
      >
        {!rows.length ? (
          <EmptyState
            message="No matching events."
            hint="Clear the search or choose a different action."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem]">
              <thead>
                <tr className="border-b border-sand/15">
                  <th className="table-head">When</th>
                  <th className="table-head">Actor</th>
                  <th className="table-head">Action</th>
                  <th className="table-head">Status</th>
                  <th className="table-head">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand/10">
                {rows.slice(0, 300).map((e, i) => (
                  <tr
                    key={`${e.timestamp}-${i}`}
                    className="transition-colors hover:bg-sand/5"
                  >
                    <td className="table-cell font-mono text-xs">
                      {e.timestamp
                        ? new Date(e.timestamp).toLocaleString('en-IN')
                        : '—'}
                    </td>
                    <td className="table-cell text-muted">{e.actor || '—'}</td>
                    <td className="table-cell">{humanize(e.action)}</td>
                    <td className="table-cell">
                      <StatusChip status={e.status} />
                    </td>
                    <td className="table-cell max-w-[26rem] truncate text-cream/80">
                      {e.detail ? (
                        <span title={JSON.stringify(e.detail)}>
                          {Object.entries(e.detail)
                            .map(([k, v]) => `${humanize(k)}: ${v}`)
                            .join(' · ')}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 300 && (
              <p className="mt-3 text-xs text-muted">
                Showing the 300 most recent of {num(rows.length)} matching events. Export
                the view for the full set.
              </p>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
