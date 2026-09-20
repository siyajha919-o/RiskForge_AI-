import { useEffect, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Activity, AlertTriangle, Bug, Gauge, IndianRupee, Wallet } from 'lucide-react';

import { api } from '../lib/api';
import { CHART, inr, num, pct, riskStyle } from '../lib/format';
import {
  ChartTooltip, ErrorState, Loading, Panel, RiskBadge, SectionHeading, StatCard,
} from '../components/ui';

const AXIS = { fill: CHART.axis, fontSize: 11 };

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setError(null);
    api.dashboard().then(setData).catch((e) => setError(e.friendlyMessage));
  };
  useEffect(() => { load(); }, []);

  if (error) {
    return (
      <ErrorState
        message={error}
        hint="Start the API with `uvicorn api.main:app --port 8000`, then run the pipeline with `python main.py --mode full`."
        onRetry={load}
      />
    );
  }
  if (!data) return <Loading label="Computing enterprise risk posture…" />;

  const { cards, risk_distribution: dist } = data;

  const distributionRows = [
    { name: 'Critical', value: dist.critical, level: 'Critical' },
    { name: 'High', value: dist.high, level: 'High' },
    { name: 'Medium', value: dist.medium, level: 'Medium' },
    { name: 'Low', value: dist.low, level: 'Low' },
  ];

  // The engine returns `trend_is_measured`, but two snapshots recorded on the
  // same day are not a trend. Require three distinct dates before presenting
  // either series as recorded history; otherwise it is a modelled back-cast.
  const distinctDates = (rows) =>
    new Set((rows || []).map((r) => r.date).filter(Boolean)).size;
  const measured =
    data.trend_is_measured &&
    distinctDates(data.risk_trend) >= 3 &&
    distinctDates(data.financial_exposure_trend) >= 3;
  const trendNote = measured
    ? `Recorded from ${distinctDates(data.risk_trend)} pipeline runs.`
    : 'Modelled projection — back-cast from the current snapshot, not recorded history.';
  const trendDash = measured ? undefined : '5 4';

  return (
    <>
      <SectionHeading
        title="Executive overview"
        subtitle="Enterprise cybersecurity posture expressed in financial terms"
        actions={
          data.generated_at && (
            <span className="chip border-sand/25 bg-sand/10 text-muted">
              <Activity className="h-3 w-3" />
              {new Date(data.generated_at).toLocaleDateString('en-IN')}
              {data.run_mode ? ` · ${data.run_mode}` : ''}
            </span>
          )
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Overall cyber risk score"
          value={`${cards.overall_risk_score}/100`}
          level={cards.risk_level}
          icon={Gauge}
        />
        <StatCard
          label="Expected annual loss"
          value={inr(cards.expected_annual_loss)}
          sub="Probability-weighted yearly loss"
          icon={IndianRupee}
        />
        <StatCard
          label="Total financial exposure"
          value={inr(cards.total_financial_exposure)}
          sub="Value at Risk, 95th percentile"
          icon={Wallet}
        />
        <StatCard
          label="Critical vulnerabilities"
          value={num(cards.critical_vulnerabilities)}
          sub="CVSS 9.0 and above"
          level="Critical"
          icon={Bug}
        />
        <StatCard
          label="Active high-risk threats"
          value={num(cards.active_high_risk_threats)}
          sub="Live campaigns, high or critical"
          level="High"
          icon={AlertTriangle}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel
          title="Cyber risk trend"
          subtitle={measured ? 'Enterprise risk score across recorded runs' : 'Enterprise risk score — modelled'}
        >
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
                strokeDasharray={trendDash}
                dot={false}
                activeDot={{ r: 5, fill: CHART.cream, stroke: CHART.ink, strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className={`panel-sub ${measured ? '' : 'text-risk-medium'}`}>{trendNote}</p>
        </Panel>

        <Panel
          title="Financial exposure"
          subtitle={measured ? 'Expected annual loss across recorded runs' : 'Expected annual loss — modelled'}
        >
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data.financial_exposure_trend} margin={{ left: 4, right: 8, top: 6 }}>
              <defs>
                {/* Moss, not Smoke: on Ivory a grey fill reads as a dead slab
                    rather than a measured quantity. */}
                <linearGradient id="expFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART.moss} stopOpacity={0.72} />
                  <stop offset="100%" stopColor={CHART.moss} stopOpacity={0.06} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} tickFormatter={(v) => inr(v)} />
              <Tooltip content={<ChartTooltip formatter={(v) => inr(v, { compact: false })} />} />
              <Area
                type="monotone"
                dataKey="value"
                name="Expected annual loss"
                stroke={CHART.cream}
                strokeWidth={2}
                strokeDasharray={trendDash}
                fill="url(#expFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
          <p className={`panel-sub ${measured ? '' : 'text-risk-medium'}`}>{trendNote}</p>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Panel title="Risk distribution" subtitle="Open findings by severity">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={distributionRows} margin={{ left: -14, right: 8, top: 10 }}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} tickFormatter={num} />
              <Tooltip cursor={{ fill: 'rgba(60,62,74,0.06)' }} content={<ChartTooltip formatter={num} />} />
              <Bar dataKey="value" name="Findings" radius={[4, 4, 0, 0]} barSize={38}>
                {distributionRows.map((r, i) => (
                  <Cell key={`${r.name}-${i}`} fill={riskStyle(r.level).hex} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel
          title="Top risk contributors"
          subtitle="Share of total expected annual loss"
          className="xl:col-span-2"
        >
          <div className="space-y-2.5">
            {/* Business unit names are not unique — the estate has two
                "Security Operations" units — so the name alone drops rows. */}
            {data.top_contributors.map((c, i) => (
              <div key={`${c.name}-${i}`} className="flex items-center gap-3">
                <div className="w-40 flex-none truncate text-xs text-cream/90" title={c.name}>
                  {c.name}
                </div>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-moss/45">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.min(100, c.contribution_pct)}%`,
                      background: riskStyle(c.risk_level).hex,
                    }}
                  />
                </div>
                <span className="w-14 flex-none text-right text-xs tabular-nums text-muted">
                  {pct(c.contribution_pct)}
                </span>
                <span className="hidden w-24 flex-none text-right text-xs tabular-nums text-cream/80 sm:block">
                  {c.expected_annual_loss ? inr(c.expected_annual_loss) : '—'}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel
        className="mt-4"
        title="Top 5 organisational risks"
        subtitle="Ranked by quantified financial impact"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-sand/15">
                <th className="table-head w-10">#</th>
                <th className="table-head">Risk</th>
                <th className="table-head">Driver</th>
                <th className="table-head text-right">Expected annual loss</th>
                <th className="table-head text-right">Level</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand/10">
              {data.top_risks.map((r) => (
                <tr key={r.rank} className="transition-colors hover:bg-sand/5">
                  <td className="table-cell text-muted">{r.rank}</td>
                  <td className="table-cell max-w-xs truncate">{r.title}</td>
                  <td className="table-cell max-w-xs truncate text-muted">{r.driver}</td>
                  <td className="table-cell text-right tabular-nums">
                    {r.expected_annual_loss ? inr(r.expected_annual_loss) : '—'}
                  </td>
                  <td className="table-cell text-right">
                    <RiskBadge level={r.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
