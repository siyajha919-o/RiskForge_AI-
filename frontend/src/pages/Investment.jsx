import { useEffect, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { IndianRupee, Loader2 } from 'lucide-react';

import { api } from '../lib/api';
import { CHART, inr, pct, riskStyle } from '../lib/format';
import {
  ChartTooltip, EmptyState, ErrorState, Loading, Panel, RiskBadge, SectionHeading,
  StatCard,
} from '../components/ui';

const AXIS = { fill: CHART.axis, fontSize: 11 };

export default function Investment() {
  const [budget, setBudget] = useState(10000000); // ₹1 Cr default, per the brief's own example
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [frontier, setFrontier] = useState(null);

  // The frontier is computed by the pipeline and does not depend on the budget
  // the user types, so it loads once rather than on every optimize.
  useEffect(() => {
    api.frontier().then(setFrontier).catch(() => setFrontier([]));
  }, []);

  async function optimize(e) {
    e?.preventDefault();
    if (!budget || budget <= 0) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.optimize(Number(budget)));
    } catch (err) {
      setError(err.friendlyMessage);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <SectionHeading
        title="Investment optimization"
        subtitle="Recommend the control portfolio that maximises risk reduction for a given budget"
      />

      <Panel title="Available security budget">
        <form onSubmit={optimize} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="label" htmlFor="budget">Annual budget (INR)</label>
            <div className="relative">
              <IndianRupee className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted/70" />
              <input
                id="budget"
                type="number"
                min="1"
                step="100000"
                className="input pl-9"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>
          </div>
          <button className="btn-primary" disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? 'Optimising…' : 'Optimize allocation'}
          </button>
          <div className="flex gap-2">
            {[5000000, 10000000, 25000000, 50000000].map((v) => (
              <button
                key={v}
                type="button"
                className="chip border-sand/25 text-muted hover:text-cream"
                onClick={() => setBudget(v)}
              >
                {inr(v)}
              </button>
            ))}
          </div>
        </form>
        {error && <p className="mt-3 text-xs text-risk-critical">{error}</p>}
      </Panel>

      {result && (
        <>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Budget" value={inr(result.budget)} />
            <StatCard
              label="Allocated"
              value={inr(result.total_allocated)}
              sub={`${inr(result.unallocated)} unallocated`}
            />
            <StatCard
              label="Total risk reduction"
              value={pct(result.total_risk_reduction_pct)}
              level="Low"
            />
            <StatCard
              label="Portfolio ROSI"
              value={`${result.portfolio_rosi.toFixed(2)}x`}
              sub={inr(result.total_loss_avoided) + ' loss avoided'}
            />
          </div>

          <Panel
            className="mt-4"
            title="Investment vs risk reduction"
            subtitle="Diminishing returns and the optimal spend zone"
          >
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ left: 4, right: 20, top: 10, bottom: 4 }}>
                <CartesianGrid stroke={CHART.grid} />
                <XAxis
                  type="number"
                  dataKey="investment"
                  name="Investment"
                  tick={AXIS}
                  axisLine={{ stroke: 'rgba(60,62,74,0.28)' }}
                  tickLine={false}
                  tickFormatter={(v) => inr(v)}
                />
                <YAxis
                  type="number"
                  dataKey="risk_reduction_pct"
                  name="Risk reduction"
                  tick={AXIS}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `${v}%`}
                />
                <ZAxis range={[50, 50]} />
                <Tooltip
                  cursor={{ stroke: CHART.sand, strokeDasharray: '3 3' }}
                  content={
                    <ChartTooltip
                      formatter={(v, name) => (name === 'Investment' ? inr(v, { compact: false }) : pct(v))}
                    />
                  }
                />
                <Scatter
                  data={result.frontier}
                  fill={CHART.cream}
                  shape={(props) => {
                    const { cx, cy, payload } = props;
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={payload.is_optimal ? 6 : 3.5}
                        fill={payload.is_optimal ? '#3F6B4A' : CHART.sand}
                        stroke={payload.is_optimal ? CHART.ink : 'none'}
                        strokeWidth={payload.is_optimal ? 2 : 0}
                      />
                    );
                  }}
                />
              </ScatterChart>
            </ResponsiveContainer>
            <p className="panel-sub">
              The green point marks your selected budget. The curve flattening shows where
              additional spend stops paying for itself.
            </p>
          </Panel>

          <Panel className="mt-4" title="Recommended allocation" subtitle="Ranked by ROSI">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-sand/15">
                    <th className="table-head">Control</th>
                    <th className="table-head">Category</th>
                    <th className="table-head text-right">Cost</th>
                    <th className="table-head text-right">Risk reduction</th>
                    <th className="table-head text-right">Loss avoided</th>
                    <th className="table-head text-right">ROSI</th>
                    <th className="table-head">Priority</th>
                    <th className="table-head">Included</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand/10">
                  {result.recommendations.map((r) => (
                    <tr
                      key={r.control_id}
                      className={`transition-colors hover:bg-sand/5 ${
                        r.selected ? '' : 'opacity-50'
                      }`}
                    >
                      <td className="table-cell font-medium">{r.name}</td>
                      <td className="table-cell text-muted">{r.category || '—'}</td>
                      <td className="table-cell text-right tabular-nums">{inr(r.investment_cost)}</td>
                      <td className="table-cell text-right tabular-nums text-risk-low">
                        −{pct(r.expected_risk_reduction_pct)}
                      </td>
                      <td className="table-cell text-right tabular-nums">
                        {inr(r.financial_loss_avoided)}
                      </td>
                      <td className="table-cell text-right tabular-nums">{r.rosi.toFixed(2)}x</td>
                      <td className="table-cell"><RiskBadge level={r.priority} /></td>
                      <td className="table-cell">
                        {r.selected ? (
                          <span className="text-risk-low">✓ Selected</span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}

      <Panel
        className="mt-4"
        title="Investment vs. risk reduction"
        subtitle="The efficient frontier — where additional spend stops buying meaningful reduction"
      >
        {!frontier ? (
          <Loading label="Loading frontier…" />
        ) : !frontier.length ? (
          <EmptyState message="No frontier computed yet." hint="Run the pipeline first." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={frontier}
              margin={{ top: 8, right: 16, left: 8, bottom: 4 }}
            >
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis
                dataKey="investment"
                tick={AXIS}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => inr(v)}
              />
              <YAxis
                tick={AXIS}
                axisLine={false}
                tickLine={false}
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                content={
                  <ChartTooltip
                    labelFormatter={(v) => `Spend ${inr(v)}`}
                    formatter={(v, name) =>
                      name === 'Risk reduction' ? pct(v) : Number(v).toLocaleString('en-IN')
                    }
                  />
                }
              />
              <Line
                type="monotone"
                dataKey="risk_reduction"
                name="Risk reduction"
                stroke={CHART.warm}
                strokeWidth={2}
                dot={{ r: 2, fill: CHART.warm }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Panel>
    </>
  );
}
