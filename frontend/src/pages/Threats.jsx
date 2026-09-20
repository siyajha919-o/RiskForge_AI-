import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Search, ShieldAlert, X } from 'lucide-react';

import { api } from '../lib/api';
import { num, riskStyle } from '../lib/format';
import {
  EmptyState, ErrorState, Loading, Panel, RiskBadge, SectionHeading, StatCard,
} from '../components/ui';

const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'];
const PAGE_SIZE = 25;

export default function Threats() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    severity: [],
    risk_level: [],
    known_exploited: null,
    min_cvss: '',
    max_cvss: '',
    product: '',
    date_from: '',
    date_to: '',
    asset_id: '',
    search: '',
  });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actors, setActors] = useState(null);

  const params = useMemo(() => {
    const p = { page, page_size: PAGE_SIZE, include_filters: true };
    if (filters.severity.length) p.severity = filters.severity.join(',');
    if (filters.risk_level.length) p.risk_level = filters.risk_level.join(',');
    if (filters.known_exploited !== null) p.known_exploited = filters.known_exploited;
    if (filters.min_cvss !== '') p.min_cvss = Number(filters.min_cvss);
    if (filters.max_cvss !== '') p.max_cvss = Number(filters.max_cvss);
    if (filters.product) p.product = filters.product;
    if (filters.date_from) p.date_from = filters.date_from;
    if (filters.date_to) p.date_to = filters.date_to;
    if (filters.asset_id) p.asset_id = filters.asset_id;
    if (filters.search) p.search = filters.search;
    return p;
  }, [page, filters]);

  useEffect(() => {
    api.threatActors({ limit: 100 }).then(setActors).catch(() => setActors([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .vulnerabilities(params)
      .then(setData)
      .catch((e) => setError(e.friendlyMessage))
      .finally(() => setLoading(false));
  }, [params]);

  // Debounced so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const update = (patch) => {
    setPage(1);
    setFilters((f) => ({ ...f, ...patch }));
  };

  const toggleIn = (key, value) =>
    update({
      [key]: filters[key].includes(value)
        ? filters[key].filter((v) => v !== value)
        : [...filters[key], value],
    });

  const activeCount =
    filters.severity.length +
    filters.risk_level.length +
    (filters.known_exploited !== null ? 1 : 0) +
    ['min_cvss', 'max_cvss', 'product', 'date_from', 'date_to', 'asset_id', 'search'].filter(
      (k) => filters[k] !== ''
    ).length;

  const clearAll = () =>
    update({
      severity: [], risk_level: [], known_exploited: null, min_cvss: '', max_cvss: '',
      product: '', date_from: '', date_to: '', asset_id: '', search: '',
    });

  if (error) return <ErrorState message={error} onRetry={load} />;

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <SectionHeading
        title="Threats &amp; vulnerabilities"
        subtitle="Ready for NVD, CISA KEV and MITRE ATT&CK enrichment through the backend"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Matching findings" value={num(data?.total ?? 0)} />
        <StatCard
          label="Known exploited (CISA KEV)"
          value={num(data?.known_exploited_count ?? 0)}
          level="Critical"
          icon={ShieldAlert}
        />
        <StatCard label="Active filters" value={num(activeCount)} sub={`Page ${page} of ${totalPages}`} />
      </div>

      <Panel
        className="mt-4"
        title="Filters"
        actions={
          activeCount > 0 && (
            <button className="btn-ghost px-2 py-1 text-xs" onClick={clearAll}>
              <X className="h-3 w-3" /> Clear all
            </button>
          )
        }
      >
        <div className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted/70" />
            <input
              className="input pl-10"
              placeholder="Search CVE ID or description…"
              value={filters.search}
              onChange={(e) => update({ search: e.target.value })}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <span className="label">Severity</span>
              <div className="flex flex-wrap gap-1.5">
                {SEVERITIES.map((s) => {
                  const on = filters.severity.includes(s);
                  const style = riskStyle(s);
                  return (
                    <button
                      key={s}
                      onClick={() => toggleIn('severity', s)}
                      className={`chip transition-colors ${
                        on ? `${style.bg} ${style.border} ${style.text}` : 'border-sand/25 text-muted hover:text-cream'
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                      {s}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <span className="label">Risk level</span>
              <div className="flex flex-wrap gap-1.5">
                {SEVERITIES.map((s) => {
                  const on = filters.risk_level.includes(s);
                  return (
                    <button
                      key={s}
                      onClick={() => toggleIn('risk_level', s)}
                      className={`chip transition-colors ${
                        on ? 'border-cream/50 bg-cream/10 text-cream' : 'border-sand/25 text-muted hover:text-cream'
                      }`}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <span className="label">Exploited status</span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { label: 'Known exploited', value: true },
                  { label: 'Not exploited', value: false },
                ].map((o) => (
                  <button
                    key={o.label}
                    onClick={() =>
                      update({ known_exploited: filters.known_exploited === o.value ? null : o.value })
                    }
                    className={`chip transition-colors ${
                      filters.known_exploited === o.value
                        ? 'border-risk-critical/40 bg-risk-critical/12 text-risk-critical'
                        : 'border-sand/25 text-muted hover:text-cream'
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="label">CVSS range</span>
              <div className="flex items-center gap-2">
                <input
                  type="number" min="0" max="10" step="0.1" placeholder="min"
                  className="input py-1.5 text-xs"
                  value={filters.min_cvss}
                  onChange={(e) => update({ min_cvss: e.target.value })}
                />
                <span className="text-muted">–</span>
                <input
                  type="number" min="0" max="10" step="0.1" placeholder="max"
                  className="input py-1.5 text-xs"
                  value={filters.max_cvss}
                  onChange={(e) => update({ max_cvss: e.target.value })}
                />
              </div>
            </div>

            <div>
              <span className="label">Product / service</span>
              <input
                className="input py-1.5 text-xs"
                placeholder="e.g. Apache"
                value={filters.product}
                onChange={(e) => update({ product: e.target.value })}
              />
            </div>

            <div>
              <span className="label">Asset</span>
              <input
                className="input py-1.5 text-xs"
                placeholder="Asset ID"
                value={filters.asset_id}
                onChange={(e) => update({ asset_id: e.target.value })}
              />
            </div>

            <div>
              <span className="label">Date from</span>
              <input
                type="date"
                className="input py-1.5 text-xs"
                value={filters.date_from}
                onChange={(e) => update({ date_from: e.target.value })}
              />
            </div>

            <div>
              <span className="label">Date to</span>
              <input
                type="date"
                className="input py-1.5 text-xs"
                value={filters.date_to}
                onChange={(e) => update({ date_to: e.target.value })}
              />
            </div>
          </div>
        </div>
      </Panel>

      <Panel className="mt-4" title="Vulnerabilities">
        {loading && !data ? (
          <Loading />
        ) : !data?.items.length ? (
          <EmptyState message="No vulnerabilities match these filters." hint="Try clearing one or more filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-sand/15">
                    <th className="table-head">CVE ID</th>
                    <th className="table-head">Description</th>
                    <th className="table-head text-right">CVSS</th>
                    <th className="table-head">Severity</th>
                    <th className="table-head">Exploited</th>
                    <th className="table-head">Vendor</th>
                    <th className="table-head">Product</th>
                    <th className="table-head">Date added</th>
                    <th className="table-head">Risk level</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand/10">
                  {data.items.map((v) => (
                    <tr
                      key={v.vulnerability_id}
                      /* KEV entries get a persistent left rail — they are the
                         rows an analyst is looking for. */
                      className={`transition-colors hover:bg-sand/5 ${
                        v.known_exploited ? 'bg-risk-critical/[0.06]' : ''
                      }`}
                    >
                      <td className="table-cell font-mono text-xs">
                        <div className="flex items-center gap-2">
                          {v.known_exploited && (
                            <span className="h-3 w-0.5 flex-none rounded-full bg-risk-critical" />
                          )}
                          {v.cve_id || v.vulnerability_id}
                        </div>
                      </td>
                      <td className="table-cell max-w-sm truncate text-muted" title={v.description}>
                        {v.description}
                      </td>
                      <td className="table-cell text-right tabular-nums">{v.cvss_score.toFixed(1)}</td>
                      <td className="table-cell"><RiskBadge level={v.severity} /></td>
                      <td className="table-cell">
                        {v.known_exploited ? (
                          <span className="chip border-risk-critical/40 bg-risk-critical/12 text-risk-critical">
                            <ShieldAlert className="h-3 w-3" /> CISA KEV
                          </span>
                        ) : (
                          <span className="text-xs text-muted">
                            {v.exploit_available ? 'Exploit available' : 'No'}
                          </span>
                        )}
                      </td>
                      <td className="table-cell text-muted">{v.vendor || '—'}</td>
                      <td className="table-cell max-w-[12rem] truncate">{v.product || '—'}</td>
                      <td className="table-cell text-muted">{v.date_added || '—'}</td>
                      <td className="table-cell"><RiskBadge level={v.risk_level} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-sand/15 pt-4">
              <p className="text-xs text-muted">
                Showing {(page - 1) * PAGE_SIZE + 1}–
                {Math.min(page * PAGE_SIZE, data.total)} of {num(data.total)}
              </p>
              <div className="flex items-center gap-2">
                <button
                  className="btn-secondary px-2.5 py-1.5"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-xs tabular-nums text-muted">
                  {page} / {totalPages}
                </span>
                <button
                  className="btn-secondary px-2.5 py-1.5"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>

      <Panel
        className="mt-4"
        title="Threat actors"
        subtitle="Active campaigns and techniques observed against this estate"
      >
        {!actors ? (
          <Loading label="Loading threat intelligence…" />
        ) : !actors.length ? (
          <EmptyState message="No threat intelligence available." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem]">
              <thead>
                <tr className="border-b border-sand/15">
                  <th className="table-head">Actor</th>
                  <th className="table-head">Category</th>
                  <th className="table-head">Technique</th>
                  <th className="table-head">Severity</th>
                  <th className="table-head text-right">Exploit prob.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand/10">
                {actors.slice(0, 25).map((a, i) => (
                  <tr key={`${a.threat_id}-${i}`} className="transition-colors hover:bg-sand/5">
                    <td className="table-cell">
                      <span className="flex items-center gap-2">
                        {a.threat_actor}
                        {a.campaign_active && (
                          <span className="chip border-risk-critical/40 bg-risk-critical/12 text-risk-critical">
                            Active
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="table-cell text-muted">{a.threat_category}</td>
                    <td className="table-cell font-mono text-xs">{a.attack_technique}</td>
                    <td className="table-cell"><RiskBadge level={a.severity} /></td>
                    <td className="table-cell text-right tabular-nums">
                      {(a.exploit_probability * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
