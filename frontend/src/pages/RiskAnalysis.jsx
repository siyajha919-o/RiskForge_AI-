import { useEffect, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { X, Equal } from 'lucide-react';

import { api } from '../lib/api';
import { CHART, inr, pct, riskStyle } from '../lib/format';
import {
  ChartTooltip, EmptyState, ErrorState, Loading, Panel, RiskBadge, SectionHeading,
  StatCard,
} from '../components/ui';

const AXIS = { fill: CHART.axis, fontSize: 11 };

const CATEGORY_LABELS = {
  vulnerability: 'Vulnerabilities',
  threat: 'Threats',
  asset_criticality: 'Asset criticality',
  control_weakness: 'Control weaknesses',
};

export default function RiskAnalysis() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [curve, setCurve] = useState(null);
  const [units, setUnits] = useState(null);

  const load = () => {
    setError(null);
    api.riskAnalysis().then(setData).catch((e) => setError(e.friendlyMessage));
    // Supporting views: a failure in either must not blank the whole page, so
    // each falls back to an empty shape rather than surfacing as a page error.
    api.lossCurve().then(setCurve).catch(() => setCurve({ curve: [] }));
    api.businessUnits().then(setUnits).catch(() => setUnits([]));
  };
  useEffect(() => { load(); }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading label="Decomposing risk drivers…" />;

  const breakdown = Object.entries(data.contribution_breakdown).map(([key, value]) => ({
    name: CATEGORY_LABELS[key] || key,
    value,
  }));

  return (
    <>
      <SectionHeading
        title="Risk analysis"
        subtitle="Detailed quantification of enterprise cyber risk"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Overall risk score"
          value={`${data.overall_risk_score}/100`}
          level={data.risk_level}
        />
        <StatCard
          label="Incident probability"
          value={pct(data.incident_probability * 100, 2)}
          sub="Annual likelihood of a material incident"
        />
        <StatCard
          label="Estimated financial impact"
          value={inr(data.estimated_financial_impact)}
          sub="Loss magnitude should an incident occur"
        />
        <StatCard
          label="Expected annual loss"
          value={inr(data.expected_annual_loss)}
          sub="Probability × impact"
        />
      </div>

      {/* The identity the whole screen rests on, shown explicitly. */}
      <Panel
        className="mt-4"
        title="How cyber risk is derived"
        subtitle="Every figure on this page follows from this relationship"
      >
        <div className="flex flex-wrap items-center justify-center gap-4 py-4 sm:gap-6">
          <div className="text-center">
            <p className="text-[11px] uppercase tracking-wider text-muted">Incident probability</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-cream">
              {pct(data.incident_probability * 100, 2)}
            </p>
          </div>
          <X className="h-4 w-4 flex-none text-muted" />
          <div className="text-center">
            <p className="text-[11px] uppercase tracking-wider text-muted">Financial impact</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-cream">
              {inr(data.estimated_financial_impact)}
            </p>
          </div>
          <Equal className="h-4 w-4 flex-none text-muted" />
          <div className="rounded-xl border border-sand/30 bg-sand/10 px-5 py-3 text-center">
            <p className="text-[11px] uppercase tracking-wider text-muted">Cyber risk (EAL)</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-cream">
              {inr(data.expected_annual_loss)}
            </p>
          </div>
        </div>
      </Panel>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel title="Risk trend" subtitle="Enterprise risk score over 12 months">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.risk_trend} margin={{ left: -12, right: 8, top: 6 }}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} domain={[0, 100]} />
              <Tooltip content={<ChartTooltip formatter={(v) => `${v.toFixed(1)}/100`} />} />
              <Line
                type="monotone"
                dataKey="value"
                name="Risk score"
                stroke={CHART.cream}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        <Panel
          title="Contribution to expected loss"
          subtitle="Share of total EAL attributable to each driver category"
        >
          <ResponsiveContainer width="100%" height={250}>
            <BarChart
              data={breakdown}
              layout="vertical"
              margin={{ left: 12, right: 40, top: 6 }}
            >
              <CartesianGrid stroke={CHART.grid} horizontal={false} />
              <XAxis
                type="number"
                tick={AXIS}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={128}
                tick={{ fill: CHART.cream, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: 'rgba(60,62,74,0.06)' }}
                content={<ChartTooltip formatter={(v) => pct(v)} />}
              />
              <Bar dataKey="value" name="Share of EAL" radius={[0, 4, 4, 0]} barSize={18}>
                {breakdown.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? CHART.cream : CHART.sand} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel className="mt-4" title="Top risk drivers" subtitle="Ranked by contribution to expected annual loss">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-sand/15">
                <th className="table-head">Driver</th>
                <th className="table-head">Category</th>
                <th className="table-head">Detail</th>
                <th className="table-head text-right">Contribution</th>
                <th className="table-head text-right">Attributed EAL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand/10">
              {data.top_drivers.map((d) => (
                <tr key={d.driver} className="transition-colors hover:bg-sand/5">
                  <td className="table-cell">{d.driver}</td>
                  <td className="table-cell text-muted">
                    {CATEGORY_LABELS[d.category] || d.category}
                  </td>
                  <td className="table-cell text-muted">{d.detail}</td>
                  <td className="table-cell text-right tabular-nums">{pct(d.contribution_pct)}</td>
                  <td className="table-cell text-right tabular-nums">
                    {inr(d.expected_annual_loss)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel
          title="Loss exceedance curve"
          subtitle="Probability that annual loss exceeds a given amount — the core FAIR output"
        >
          {!curve ? (
            <Loading label="Loading curve…" />
          ) : !curve.curve?.length ? (
            <EmptyState message="No simulated loss distribution yet." />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={[...curve.curve].sort((a, b) => a.loss - b.loss)}
                  margin={{ top: 8, right: 8, left: 8, bottom: 4 }}
                >
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis
                    dataKey="loss"
                    tick={AXIS}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => inr(v)}
                  />
                  <YAxis
                    tick={AXIS}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    content={
                      <ChartTooltip
                        labelFormatter={(v) => `Loss ${inr(v)}`}
                        formatter={(v) => `${(v * 100).toFixed(2)}% chance of exceeding`}
                      />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="exceedance_prob"
                    name="Exceedance"
                    stroke={CHART.warm}
                    fill={CHART.sand}
                    fillOpacity={0.18}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted">
                <span>VaR 95%: <span className="tabular-nums text-cream">{inr(curve.var_95)}</span></span>
                <span>VaR 99%: <span className="tabular-nums text-cream">{inr(curve.var_99)}</span></span>
              </div>
            </>
          )}
        </Panel>

        <Panel
          title="Exposure by business unit"
          subtitle="Where the expected annual loss actually sits"
        >
          {!units ? (
            <Loading label="Loading business units…" />
          ) : !units.length ? (
            <EmptyState message="No business unit rollup available." />
          ) : (
            <div className="max-h-[17rem] overflow-y-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-ink/80 backdrop-blur">
                  <tr className="border-b border-sand/15">
                    <th className="table-head">Unit</th>
                    <th className="table-head text-right">EAL</th>
                    <th className="table-head text-right">VaR 95%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand/10">
                  {[...units]
                    .sort((a, b) => b.expected_annual_loss - a.expected_annual_loss)
                    .map((u, i) => (
                      <tr key={`${u.business_unit_id}-${i}`} className="hover:bg-sand/5">
                        <td className="table-cell">
                          {u.business_unit_name}
                          <span className="ml-2 text-[11px] text-muted">{u.business_function}</span>
                        </td>
                        <td className="table-cell text-right tabular-nums">
                          {inr(u.expected_annual_loss)}
                        </td>
                        <td className="table-cell text-right tabular-nums text-muted">
                          {inr(u.var_95)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
