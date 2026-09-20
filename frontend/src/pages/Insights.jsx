import { useEffect, useState } from 'react';
import { ClipboardList, Database, Loader2, Send, Sparkles } from 'lucide-react';

import { api } from '../lib/api';
import { inr, pct } from '../lib/format';
import { EmptyState, ErrorState, Loading, Panel, SectionHeading } from '../components/ui';

const SUGGESTIONS = [
  'What is the largest source of expected annual loss?',
  'Which controls should the board fund first?',
  'What are our biggest compliance gaps?',
];

export default function Insights() {
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [briefing, setBriefing] = useState(null);

  const loadHistory = () => {
    setError(null);
    api.insightHistory().then(setHistory).catch((e) => setError(e.friendlyMessage));
    // The board briefing is a separate, already-built endpoint; a failure here
    // must not take down the ask-and-answer flow, so it is caught on its own.
    api.recommendations().then(setBriefing).catch(() => setBriefing({ recommendations: [] }));
  };

  useEffect(() => { loadHistory(); }, []);

  async function ask(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.ask(question.trim());
      setAnswer(result);
      setQuestion('');
      setHistory(await api.insightHistory());
    } catch (e) {
      setError(e.friendlyMessage);
    } finally {
      setLoading(false);
    }
  }

  if (!history && !error) return <Loading label="Loading saved AI insights…" />;
  if (!history && error) return <ErrorState message={error} onRetry={loadHistory} />;

  return (
    <>
      <SectionHeading
        title="AI Advisor"
        subtitle="Ask questions against the latest FAIR, compliance and optimization results"
      />

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Ask the risk engine" subtitle="Every answer is grounded in computed engine output">
          <form onSubmit={ask}>
            <label className="label" htmlFor="risk-question">Question</label>
            <textarea
              id="risk-question"
              className="input mt-2 min-h-28 resize-y"
              placeholder="Ask about exposure, threats, controls or compliance…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              minLength={3}
              required
            />
            <button className="btn-primary mt-3" disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Ask advisor
            </button>
          </form>

          <div className="mt-5 flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                className="chip border-sand/25 bg-sand/10 text-left text-muted hover:bg-sand/20"
                onClick={() => setQuestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Latest answer" subtitle={answer ? `${answer.mode === 'llm' ? 'LLM' : 'Deterministic'} response` : 'Your next answer will appear here'}>
          {answer ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs text-risk-low">
                <Sparkles className="h-3.5 w-3.5" />
                Grounded in: {answer.context_used.join(', ')}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-cream/90">{answer.answer}</p>
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-muted">Ask a question to generate an insight from the current model results.</p>
          )}
        </Panel>
      </div>

      {error && <p className="mt-3 text-xs text-risk-critical">{error}</p>}

      <Panel className="mt-4" title="Saved insight history" subtitle="Persisted in the RiskEngine SQLite database">
        {history.length ? (
          <div className="space-y-3">
            {history.map((item) => (
              <button
                key={item.id}
                className="w-full rounded-lg border border-sand/15 bg-slate/40 p-4 text-left hover:border-sand/35"
                onClick={() => setAnswer(item)}
              >
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm font-medium text-cream">{item.question}</p>
                  <span className="flex-none text-[11px] uppercase tracking-wider text-muted">{item.mode}</span>
                </div>
                <p className="mt-2 line-clamp-2 whitespace-pre-wrap text-xs leading-relaxed text-muted">{item.answer}</p>
                <p className="mt-2 flex items-center gap-1.5 text-[11px] text-muted/70">
                  <Database className="h-3 w-3" /> {new Date(item.created_at).toLocaleString('en-IN')}
                </p>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">No saved questions yet.</p>
        )}
      </Panel>

      <Panel
        className="mt-4"
        title="Board briefing"
        subtitle="Prioritised controls with quantified risk reduction, straight from the optimizer"
        actions={
          briefing?.mode ? (
            <span className="chip border-sand/25 bg-sand/10 text-muted">
              {briefing.mode === 'llm' ? 'LLM narrative' : 'Deterministic'}
            </span>
          ) : null
        }
      >
        {!briefing ? (
          <Loading label="Loading briefing…" />
        ) : briefing.narrative ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-cream/90">
            {briefing.narrative}
          </p>
        ) : !briefing.recommendations?.length ? (
          <EmptyState
            message="No recommendations yet."
            hint="Run the pipeline so the optimizer has controls to rank."
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[34rem]">
                <thead>
                  <tr className="border-b border-sand/15">
                    <th className="table-head">Control</th>
                    <th className="table-head">Annual cost</th>
                    <th className="table-head">Risk reduction</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sand/10">
                  {briefing.recommendations.slice(0, 10).map((r, i) => (
                    <tr key={`${r.control_id}-${i}`} className="transition-colors hover:bg-sand/5">
                      <td className="table-cell">
                        <span className="flex items-center gap-2">
                          <ClipboardList className="h-3.5 w-3.5 flex-none text-muted" />
                          {r.control_name || r.control_id}
                        </span>
                      </td>
                      <td className="table-cell tabular-nums">{inr(r.cost)}</td>
                      <td className="table-cell tabular-nums text-risk-low">
                        {pct(r.risk_reduction)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {briefing.note && (
              <p className="mt-3 text-xs text-muted">{briefing.note}</p>
            )}
          </>
        )}
      </Panel>
    </>
  );
}