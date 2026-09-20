import { useEffect, useState } from 'react';
import { Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react';

import { api } from '../lib/api';
import { ErrorState, Loading, Panel, SectionHeading } from '../components/ui';

export default function Reports() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(null);
  const [open, setOpen] = useState(null);
  const [exporting, setExporting] = useState(null);

  const load = () => {
    setError(null);
    api.reports().then(setReports).catch((e) => setError(e.friendlyMessage));
  };
  useEffect(() => { load(); }, []);

  async function generate(reportType) {
    setGenerating(reportType);
    setError(null);
    try {
      setOpen(await api.generateReport(reportType));
    } catch (e) {
      setError(e.friendlyMessage);
    } finally {
      setGenerating(null);
    }
  }

  /** Turns a report response into a saved file, text or binary. */
  function save(report) {
    // PDF and XLSX arrive base64'd inside the JSON envelope; markdown is plain.
    const body =
      report.encoding === 'base64'
        ? Uint8Array.from(atob(report.content), (c) => c.charCodeAt(0))
        : report.content;
    const blob = new Blob([body], { type: report.mime_type || 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.report_type}-${report.generated_at.slice(0, 10)}.${
      report.file_extension || 'md'
    }`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function download() {
    if (open) save(open);
  }

  /** Regenerates the open report in another format, then saves it. */
  async function exportAs(format) {
    if (!open) return;
    setExporting(format);
    setError(null);
    try {
      save(await api.generateReport(open.report_type, format));
    } catch (e) {
      setError(e.friendlyMessage);
    } finally {
      setExporting(null);
    }
  }

  if (error && !reports) return <ErrorState message={error} onRetry={load} />;
  if (!reports) return <Loading label="Loading report catalogue…" />;

  return (
    <>
      <SectionHeading title="Reports" subtitle="Generate evidence-based reports for boards, auditors and regulators" />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {reports.map((r) => (
          <Panel key={r.id} title={r.title} subtitle={r.description}>
            <div className="flex items-center justify-between">
              <span className={`text-xs ${r.available ? 'text-risk-low' : 'text-muted'}`}>
                {r.available ? 'Data ready' : 'Awaiting pipeline run'}
              </span>
              <button
                className="btn-secondary px-3 py-1.5 text-xs"
                disabled={!r.available || generating === r.id}
                onClick={() => generate(r.id)}
              >
                {generating === r.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileText className="h-3.5 w-3.5" />
                )}
                Generate
              </button>
            </div>
          </Panel>
        ))}
      </div>

      {error && <p className="mt-3 text-xs text-risk-critical">{error}</p>}

      {open && (
        <Panel
          className="mt-4"
          title={open.title}
          subtitle={`Generated ${new Date(open.generated_at).toLocaleString('en-IN')}`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn-secondary px-3 py-1.5 text-xs" onClick={download}>
                <Download className="h-3.5 w-3.5" /> .md
              </button>
              <button
                className="btn-secondary px-3 py-1.5 text-xs"
                onClick={() => exportAs('pdf')}
                disabled={exporting === 'pdf'}
              >
                {exporting === 'pdf' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileText className="h-3.5 w-3.5" />
                )}
                PDF
              </button>
              <button
                className="btn-secondary px-3 py-1.5 text-xs"
                onClick={() => exportAs('xlsx')}
                disabled={exporting === 'xlsx'}
              >
                {exporting === 'xlsx' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                )}
                Excel
              </button>
            </div>
          }
        >
          <div className="max-h-[560px] overflow-y-auto rounded-lg bg-slate/50 p-5">
            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-cream/90">
              {open.content}
            </pre>
          </div>
        </Panel>
      )}
    </>
  );
}
