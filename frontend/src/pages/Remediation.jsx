import { useEffect, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { AlertTriangle, ClipboardList, IndianRupee, TrendingDown } from 'lucide-react';

import { api } from '../lib/api';
import { CHART, inr, num, pct, riskStyle } from '../lib/format';
import {
  ChartTooltip, EmptyState, ErrorState, Loading, Panel, RiskBadge, SectionHeading, StatCard,
} from '../components/ui';

const STATUS_ORDER = ['Overdue', 'Pending', 'In Progress', 'Completed'];

// Status is a state, not a series — reserved status colours, never the
// categorical ramp, and each is labelled so colour is never the only cue.
const STATUS_STYLE = {
  Overdue: { fill: '#9B3330', level: 'Critical' },
  Pending: { fill: '#9A5526', level: 'High' },
  'In Progress': { fill: '#9FA3AD', level: 'Medium' },
  Completed: { fill: '#3F6B4A', level: 'Low' },
};

export default function Remediation() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [category, setCategory] = useState('all');

  const load = () => {
    setError(null);
    api.remediation(50).then(setData).catch((e) => setError(e.friendlyMessage));
  };
  useEffect(() => { load(); }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading label="Ranking remediation actions…" />;

  const backlog = data.backlog || {};
  const byStatus = STATUS_ORDER
    .filter((s) => (backlog.by_status || {})[s] !== undefined)
    .map((s) => ({ status: s, count: backlog.by_status[s] }));

  const categories = backlog.by_category || [];
  const recommendations =
    category === 'all'
      ? data.recommendations
      : data.recommendations.filter((r) => r.category === category);

  return (
    <>
      <SectionHeading
        title="Remediation"
        subtitle="Actions ranked by loss reduction per rupee, not by severity label"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard label="Open actions" value={backlog.open_actions?.toLocaleString() ?? '—'} icon={ClipboardList} />
        <StatCard label="Overdue" value={backlog.overdue_actions?.toLocaleString() ?? '—'} level="Critical" icon={AlertTriangle} />
        <StatCard label="Cost to clear backlog" value={inr(backlog.open_cost_to_clear)} icon={IndianRupee} />
        <StatCard label="Loss reduction available" value={inr(backlog.open_loss_reduction_available)} level="Low" icon={TrendingDown} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Backlog by status" subtitle="Open work carried by the security team">
          {byStatus.length === 0 ? (
            <EmptyState message="No backlog data." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byStatus} margin={{ left: -8, right: 8, top: 8 }}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="status" stroke={CHART.axis} tickLine={false} fontSize={12} />
                <YAxis stroke={CHART.axis} tickLine={false} fontSize={12} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(60,62,74,0.06)' }} />
                <Bar dataKey="count" name="Actions" radius={[4, 4, 0, 0]}>
                  {byStatus.map((d) => (
                    <Cell key={d.status} fill={STATUS_STYLE[d.status]?.fill || CHART.sand} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Panel>

        <Panel title="Loss reduction by category" subtitle="Where the avoidable loss actually sits">
          {categories.length === 0 ? (
            <EmptyState message="No category data." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={[...categories].sort((a, b) => b.total_loss_reduction - a.total_loss_reduction)}
                layout="vertical"
                margin={{ left: 28, right: 16, top: 8 }}
              >
                <CartesianGrid stroke={CHART.grid} horizontal={false} />
                <XAxis type="number" stroke={CHART.axis} tickLine={false} fontSize={11}
                       tickFormatter={(v) => inr(v, { compact: true })} />
                <YAxis type="category" dataKey="category" stroke={CHART.axis} tickLine={false}
                       width={96} fontSize={11} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(60,62,74,0.06)' }} />
                <Bar dataKey="total_loss_reduction" name="Loss reduction" fill={CHART.sand}
                     radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Panel>
      </div>

      <Panel
        className="mt-4"
        title="Prioritized actions"
        subtitle="Highest expected loss reduction per rupee spent"
        actions={
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-sand/25 bg-ink px-2 py-1 text-xs text-cream"
          >
            <option value="all">All categories</option>
            {categories.map((c) => (
              <option key={c.category} value={c.category}>{c.category}</option>
            ))}
          </select>
        }
      >
        {recommendations.length === 0 ? (
          <EmptyState message="No open remediation actions." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-2 pr-3">Action</th>
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2 pr-3">Asset</th>
                  <th className="py-2 pr-3 text-right">Cost</th>
                  <th className="py-2 pr-3 text-right">Loss avoided</th>
                  <th className="py-2 pr-3 text-right">Return</th>
                  <th className="py-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand/20">
                {recommendations.map((r) => (
                  <tr key={r.remediation_id} className="text-cream">
                    <td className="py-2 pr-3">{r.action}</td>
                    <td className="py-2 pr-3 text-muted">{r.category}</td>
                    <td className="py-2 pr-3 text-muted">{r.asset_name || r.asset_id}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{inr(r.estimated_cost)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{inr(r.expected_loss_reduction)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.return_per_rupee?.toFixed(1)}×</td>
                    <td className="py-2 pr-3">
                      <RiskBadge level={STATUS_STYLE[r.status]?.level || 'Medium'} label={r.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>


      <Panel
        className="mt-4"
        title="Open actions by priority"
        subtitle="Where the outstanding work is concentrated"
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {['Critical', 'High', 'Medium', 'Low']
            .filter((level) => (backlog.by_priority || {})[level] !== undefined)
            .map((level) => {
              const s = riskStyle(level);
              return (
                <div key={level} className="glass relative overflow-hidden p-4">
                  <div className={`absolute inset-x-0 top-0 h-0.5 ${s.dot}`} />
                  <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
                    {level}
                  </p>
                  <p className="mt-1.5 text-2xl font-semibold tabular-nums text-cream">
                    {num(backlog.by_priority[level])}
                  </p>
                </div>
              );
            })}
        </div>
      </Panel>
    </>
  );
}
