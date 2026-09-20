import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';

import { api } from '../lib/api';
import { complianceStyle, inr, pct } from '../lib/format';
import {
  EmptyState, ErrorState, Loading, Panel, SectionHeading, StatCard,
} from '../components/ui';

export default function Compliance() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [framework, setFramework] = useState('all');

  const load = () => {
    setError(null);
    api.compliance().then(setData).catch((e) => setError(e.friendlyMessage));
  };
  useEffect(() => { load(); }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading label="Mapping controls to frameworks…" />;

  const controls =
    framework === 'all' ? data.controls : data.controls.filter((c) => c.framework === framework);

  return (
    <>
      <SectionHeading
        title="Compliance"
        subtitle="NIST CSF · ISO/IEC 27001 · CIS Controls · RBI CSF · SEBI CSCRF"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard
          label="Overall compliance score"
          value={pct(data.overall_compliance_score)}
          icon={ShieldCheck}
        />
        <StatCard label="Compliant controls" value={data.total_compliant} level="Low" />
        <StatCard label="Partially compliant" value={data.total_partial} level="Medium" />
        <StatCard label="Compliance gaps" value={data.total_gaps} level="Critical" />
      </div>

      <Panel className="mt-4" title="Framework posture">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {data.frameworks.map((fw) => (
            <button
              key={fw.framework}
              onClick={() => setFramework(framework === fw.framework ? 'all' : fw.framework)}
              className={`rounded-xl border p-4 text-left transition-all ${
                framework === fw.framework
                  ? 'border-cream/60 bg-cream/10 shadow-glow'
                  : 'border-sand/20 bg-cream/[0.04] hover:border-sand/45'
              }`}
            >
              <p className="truncate text-xs font-semibold text-cream">{fw.framework}</p>
              <p className="mt-2 text-xl font-semibold tabular-nums text-cream">
                {pct(fw.compliance_score)}
              </p>
              <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-moss/45">
                <div
                  className="h-full bg-risk-low"
                  style={{ width: `${(fw.compliant / fw.total_requirements) * 100}%` }}
                />
                <div
                  className="h-full bg-risk-medium"
                  style={{ width: `${(fw.partial / fw.total_requirements) * 100}%` }}
                />
                <div
                  className="h-full bg-risk-critical"
                  style={{ width: `${(fw.gaps / fw.total_requirements) * 100}%` }}
                />
              </div>
              <p className="mt-2 text-[11px] text-muted">
                {fw.total_requirements} requirements · {pct(fw.evidence_coverage_pct)} evidenced
              </p>
            </button>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-4 text-[11px] text-muted">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-risk-low" /> Compliant</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-risk-medium" /> Partial</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-risk-critical" /> Gap</span>
        </div>
      </Panel>

      <Panel
        className="mt-4"
        title="Control-wise status"
        subtitle={framework === 'all' ? 'All frameworks' : framework}
      >
        {!controls.length ? (
          <EmptyState
            message="No control-level detail available yet."
            hint="Run the pipeline with `python main.py --mode full` to generate the evidence-based compliance report."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-sand/15">
                  <th className="table-head">Requirement</th>
                  <th className="table-head">Framework</th>
                  <th className="table-head">Control</th>
                  <th className="table-head">Status</th>
                  <th className="table-head">Evidence</th>
                  <th className="table-head text-right">Associated risk</th>
                  <th className="table-head">Recommended action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand/10">
                {/* requirement_id repeats across the estate (the same NIST-13
                    control is assessed on many assets), so it cannot key rows
                    on its own — React was dropping the duplicates. */}
                {controls.slice(0, 200).map((c, i) => {
                  const s = complianceStyle(c.status);
                  return (
                    <tr
                      key={`${c.requirement_id}-${c.control_id ?? i}-${i}`}
                      className="transition-colors hover:bg-sand/5"
                    >
                      <td className="table-cell font-mono text-xs">{c.requirement_id}</td>
                      <td className="table-cell text-muted">{c.framework}</td>
                      <td className="table-cell max-w-[10rem] truncate">{c.control_name || c.control_id}</td>
                      <td className="table-cell">
                        <span className={`chip border-current/30 ${s.text}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
                          {c.status}
                        </span>
                      </td>
                      <td className="table-cell text-muted">
                        {c.evidence_available ? c.evidence_quality : 'None'}
                      </td>
                      <td className="table-cell text-right tabular-nums">
                        {c.associated_risk ? inr(c.associated_risk) : '—'}
                      </td>
                      <td className="table-cell max-w-xs truncate text-muted">
                        {c.recommended_action || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
