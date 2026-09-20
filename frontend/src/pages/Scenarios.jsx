import { useEffect, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { ArrowRight, Check, Loader2, TrendingDown } from 'lucide-react';

import { api } from '../lib/api';
import { CHART, inr, pct } from '../lib/format';
import {
  ChartTooltip, ErrorState, Loading, Panel, SectionHeading, StatCard,
} from '../components/ui';

const AXIS = { fill: CHART.axis, fontSize: 11 };

export default function Scenarios() {
  const [controls, setControls] = useState(null);
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [precomputed, setPrecomputed] = useState(null);

  useEffect(() => {
    api.precomputedScenarios().then(setPrecomputed).catch(() => setPrecomputed([]));
  }, []);

  useEffect(() => {
    api.scenarioControls().then(setControls).catch((e) => setError(e.friendlyMessage));
  }, []);

  const toggle = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function run() {
    if (!selected.length) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await api.simulate(selected));
    } catch (e) {
      setError(e.friendlyMessage);
    } finally {
      setRunning(false);
    }
  }

  if (error && !controls) return <ErrorState message={error} />;
  if (!controls) return <Loading label="Loading control catalogue…" />;

  const comparison = result
    ? [
        {
          metric: 'Risk score',
          Before: result.before.risk_score,
          After: result.after.risk_score,
        },
        {
          metric: 'Expected annual loss',
          Before: result.before.expected_annual_loss,
          After: result.after.expected_annual_loss,
        },
        {
          metric: 'Financial exposure',
          Before: result.before.financial_exposure,
          After: result.after.financial_exposure,
        },
      ]
    : [];

  return (
    <>
      <SectionHeading
        title="Scenario simulation"
        subtitle="Model the effect of security investments before committing budget"
      />

      <Panel
        title="Select security controls"
        subtitle="Combine multiple controls — overlapping coverage is accounted for"
        actions={
          <button className="btn-primary" onClick={run} disabled={!selected.length || running}>
            {running && <Loader2 className="h-4 w-4 animate-spin" />}
            {running ? 'Simulating…' : 'Run simulation'}
          </button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {controls.map((c) => {
            const on = selected.includes(c.control_id);
            return (
              <button
                key={c.control_id}
                onClick={() => toggle(c.control_id)}
                className={`rounded-xl border p-4 text-left transition-all duration-200 ${
                  on
                    ? 'border-cream/60 bg-cream/10 shadow-glow'
                    : 'border-sand/20 bg-cream/[0.04] hover:border-sand/45'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold text-cream">{c.name}</span>
                  <span
                    className={`grid h-4 w-4 flex-none place-items-center rounded border ${
                      on ? 'border-cream bg-cream' : 'border-sand/50'
                    }`}
                  >
                    {on && <Check className="h-3 w-3 text-ink" />}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted">{c.description}</p>
                <div className="mt-3 flex items-center justify-between text-xs">
                  <span className="text-risk-low">−{pct(c.expected_risk_reduction_pct)} risk</span>
                  <span className="tabular-nums text-cream/80">{inr(c.annual_cost)}/yr</span>
                </div>
              </button>
            );
          })}
        </div>
        {error && <p className="mt-3 text-xs text-risk-critical">{error}</p>}
      </Panel>

      {result && (
        <>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Risk reduction"
              value={pct(result.risk_reduction_pct)}
              sub="Combined effect of selected controls"
              icon={TrendingDown}
            />
            <StatCard
              label="Financial loss avoided"
              value={inr(result.financial_loss_avoided)}
              sub="Annual expected loss prevented"
            />
            <StatCard label="Investment cost" value={inr(result.investment_cost)} sub="Annual" />
            <StatCard
              label="ROSI"
              value={`${result.rosi.toFixed(2)}x`}
              sub={
                result.payback_months != null
                  ? `Payback in ${result.payback_months} months`
                  : 'Return on security investment'
              }
              level={result.rosi >= 2 ? 'Low' : result.rosi >= 0.5 ? 'Medium' : 'High'}
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <Panel title="Before vs after" subtitle="Each metric on its own scale">
              <div className="space-y-4">
                {comparison.map((row) => {
                  const isScore = row.metric === 'Risk score';
                  const fmt = isScore ? (v) => `${v.toFixed(1)}/100` : (v) => inr(v);
                  const max = Math.max(row.Before, row.After) || 1;
                  return (
                    <div key={row.metric}>
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <span className="text-muted">{row.metric}</span>
                        <span className="flex items-center gap-2 tabular-nums">
                          <span className="text-cream/60 line-through">{fmt(row.Before)}</span>
                          <ArrowRight className="h-3 w-3 text-muted" />
                          <span className="font-semibold text-risk-low">{fmt(row.After)}</span>
                        </span>
                      </div>
                      <div className="space-y-1.5">
                        <div className="h-2 overflow-hidden rounded-full bg-moss/45">
                          <div
                            className="h-full rounded-full bg-smoke"
                            style={{ width: `${(row.Before / max) * 100}%` }}
                          />
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-moss/45">
                          <div
                            className="h-full rounded-full bg-risk-low transition-all duration-700"
                            style={{ width: `${(row.After / max) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 flex items-center gap-4 border-t border-sand/15 pt-3 text-[11px] text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-smoke" /> Before
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-risk-low" /> After
                </span>
              </div>
            </Panel>

            <Panel title="Financial impact" subtitle="Expected annual loss and exposure">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={comparison.slice(1)} margin={{ left: 4, right: 8, top: 10 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="metric" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={AXIS}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => inr(v)}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(60,62,74,0.06)' }}
                    content={<ChartTooltip formatter={(v) => inr(v, { compact: false })} />}
                  />
                  <Bar dataKey="Before" fill={CHART.sand} radius={[4, 4, 0, 0]} barSize={38} />
                  <Bar dataKey="After" fill="#3F6B4A" radius={[4, 4, 0, 0]} barSize={38} />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-2 flex items-center gap-4 text-[11px] text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-smoke" /> Before
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-risk-low" /> After
                </span>
              </div>
            </Panel>
          </div>

          <Panel className="mt-4" title="Controls applied">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-sand/15">
                    <th className="table-head">Control</th>
                    <th className="table-head">Description</th>
                    <th className="table-head text-right">Risk reduction</th>
                    <th className="table-head text-right">Annual cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand/10">
                  {result.controls_applied.map((c) => (
                    <tr key={c.control_id}>
                      <td className="table-cell font-medium">{c.name}</td>
                      <td className="table-cell text-muted">{c.description}</td>
                      <td className="table-cell text-right tabular-nums text-risk-low">
                        −{pct(c.expected_risk_reduction_pct)}
                      </td>
                      <td className="table-cell text-right tabular-nums">{inr(c.annual_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="panel-sub mt-3">
              Combined reduction is {pct(result.risk_reduction_pct)}, not the sum of the individual
              figures — controls overlap, so their effects compose multiplicatively.
            </p>
          </Panel>
        </>
      )}

      <Panel
        className="mt-4"
        title="Pipeline scenarios"
        subtitle="Full FAIR re-simulations computed on every run — not an approximation"
      >
        {!precomputed ? (
          <Loading label="Loading scenarios…" />
        ) : !precomputed.length ? (
          <EmptyState message="No precomputed scenarios yet." hint="Run the pipeline first." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {precomputed.map((sc, i) => {
              const better = sc.percent_change < 0;
              return (
                <div key={`${sc.scenario}-${i}`} className="glass p-4">
                  <p className="text-sm font-semibold text-cream">{sc.scenario}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{sc.description}</p>
                  <p
                    className={`mt-3 text-lg font-semibold tabular-nums ${
                      better ? 'text-risk-low' : 'text-risk-critical'
                    }`}
                  >
                    {better ? '' : '+'}{pct(sc.percent_change)}
                  </p>
                  <p className="text-[11px] text-muted">
                    {inr(sc.baseline_expected_loss)} → {inr(sc.scenario_expected_loss)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </>
  );
}
