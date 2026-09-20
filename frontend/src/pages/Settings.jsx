import { useEffect, useState } from 'react';
import { Activity, Clock, Database, RefreshCw, Shield } from 'lucide-react';

import { api, auth } from '../lib/api';
import { Panel, SectionHeading, StatCard } from '../components/ui';

export default function Settings() {
  const user = auth.user();
  const [status, setStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = () => api.pipelineStatus().then(setStatus).catch(() => {});
  useEffect(() => { load(); }, []);

  async function recompute(mode) {
    setRefreshing(true);
    try {
      await api.recompute(mode);
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <>
      <SectionHeading title="Settings" subtitle="Account and platform configuration" />

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Account" className="xl:col-span-1">
          <div className="space-y-3 text-sm">
            <div>
              <p className="label">Name</p>
              <p className="text-cream">{user?.name || '—'}</p>
            </div>
            <div>
              <p className="label">Email</p>
              <p className="text-cream">{user?.email || '—'}</p>
            </div>
            <div>
              <p className="label">Role</p>
              <p className="text-cream">{user?.role || '—'}</p>
            </div>
          </div>
        </Panel>

        <Panel title="Risk engine" subtitle="Continuous quantification pipeline" className="xl:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              label="Status"
              value={status?.running ? 'Running' : 'Idle'}
              icon={Activity}
              level={status?.running ? 'Medium' : 'Low'}
            />
            <StatCard
              label="Refresh interval"
              value={status ? `${Math.round(status.refresh_interval_seconds / 60)} min` : '—'}
              icon={Clock}
            />
            <StatCard
              label="New telemetry"
              value={status?.inputs_changed_since_last_run ? 'Yes' : 'No'}
              icon={Database}
              level={status?.inputs_changed_since_last_run ? 'Medium' : 'Low'}
            />
            <StatCard label="Last run" value={status?.last_run?.status || '—'} icon={Shield} />
          </div>

          <div className="mt-5 flex flex-wrap gap-2 border-t border-sand/15 pt-4">
            <button
              className="btn-secondary"
              disabled={refreshing}
              onClick={() => recompute('incremental')}
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              Incremental refresh
            </button>
            <button
              className="btn-secondary"
              disabled={refreshing}
              onClick={() => recompute('full')}
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              Full retrain
            </button>
          </div>
          <p className="panel-sub mt-2">
            Incremental reuses saved models and only re-runs FAIR simulation and optimization —
            seconds, not minutes. Full retrains the classification and regression models.
          </p>
        </Panel>
      </div>
    </>
  );
}
