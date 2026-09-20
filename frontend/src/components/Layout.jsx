import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import {
  Activity, BarChart3, Bell, ClipboardList, FileText, LayoutDashboard, LogOut, Network,
  RefreshCw, Settings as SettingsIcon, ShieldCheck, Sliders, TrendingUp, Bug,
  Sparkles, History,
} from 'lucide-react';

import { BrandLockup } from './BrandMark';
import ParticleBrandBackground from './ParticleBrandBackground';
import { api, auth } from '../lib/api';
import { riskStyle } from '../lib/format';

const NAV = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/network', label: 'Cyber Risk Network', icon: Network },
  { to: '/app/risk', label: 'Risk Analysis', icon: TrendingUp },
  { to: '/app/threats', label: 'Threats & Vulnerabilities', icon: Bug },
  { to: '/app/scenarios', label: 'Scenario Simulation', icon: Sliders },
  { to: '/app/compliance', label: 'Compliance', icon: ShieldCheck },
  { to: '/app/investment', label: 'Investment Optimization', icon: BarChart3 },
  { to: '/app/remediation', label: 'Remediation', icon: ClipboardList },
  { to: '/app/reports', label: 'Reports', icon: FileText },
  { to: '/app/insights', label: 'AI Advisor', icon: Sparkles },
  // The engine gates /pipeline/audit-log to CISO/ADMIN, so hiding it from other
  // roles keeps the nav honest rather than offering a link that 403s.
  { to: '/app/audit', label: 'Audit Trail', icon: History, roles: ['ADMIN', 'CISO'] },
  { to: '/app/settings', label: 'Settings', icon: SettingsIcon },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = auth.user();
  const mainRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  // Incremented after a recompute to force the routed page to refetch.
  const [dataVersion, setDataVersion] = useState(0);
  const [alertData, setAlertData] = useState(null);
  const [bellOpen, setBellOpen] = useState(false);

  // Fade each route in rather than having content snap into place.
  useEffect(() => {
    if (!mainRef.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        mainRef.current,
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' }
      );
    });
    return () => ctx.revert();
  }, [location.pathname]);

  useEffect(() => {
    api.pipelineStatus().then(setStatus).catch(() => {});
    api.alerts().then(setAlertData).catch(() => {});
  }, [location.pathname]);

  const alerts = alertData?.alerts ?? [];
  const unread = alertData?.unacknowledged ?? 0;

  async function acknowledge(id) {
    try {
      await api.ackAlert(id);
      setAlertData(await api.alerts());
    } catch {
      // Non-fatal: the alert simply stays unread.
    }
  }

  useEffect(() => { setBellOpen(false); }, [location.pathname]);

  async function refresh() {
    setRefreshing(true);
    try {
      // POST /pipeline/recompute awaits the run, so once this resolves the new
      // outputs are already on disk.
      await api.recompute('incremental');
      setStatus(await api.pipelineStatus());
      // …but the page below is still holding the figures it fetched on mount.
      // Bumping this key remounts the routed page, which re-runs its loader —
      // one line here instead of a refresh subscription in all thirteen pages.
      setDataVersion((v) => v + 1);
    } catch {
      // Surfaced by the status pill; a failed refresh must not block the UI.
    } finally {
      setRefreshing(false);
    }
  }

  function logout() {
    auth.clear();
    navigate('/login');
  }

  const current = NAV.find((n) =>
    n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)
  );

  return (
    <div className="relative min-h-screen">
      <ParticleBrandBackground variant="ambient" className="brand-canvas" />

      <div className="relative z-10 flex min-h-screen">
        {/* Sidebar — fixed structure, per the requirements */}
        <aside className="sticky top-0 hidden h-screen w-64 flex-none flex-col border-r border-sand/15 bg-ink/80 backdrop-blur-xl lg:flex">
          <div className="px-5 py-6">
            <BrandLockup />
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
            {NAV.filter((n) => !n.roles || n.roles.includes(user?.role)).map(
              ({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'nav-link-active' : ''}`
                }
              >
                <Icon className="h-4 w-4 flex-none" />
                <span className="truncate">{label}</span>
              </NavLink>
              )
            )}
          </nav>

          <div className="border-t border-sand/15 px-3 py-4">
            <div className="mb-3 px-2">
              <p className="truncate text-xs font-medium text-cream">{user?.name || 'User'}</p>
              <p className="truncate text-[11px] text-muted">{user?.role}</p>
            </div>
            <button className="nav-link w-full" onClick={logout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top bar */}
          <header className="sticky top-0 z-20 flex items-center gap-4 border-b border-sand/15 bg-ink/70 px-6 py-3.5 backdrop-blur-xl">
            {/* The sidebar carries the brand from `lg` up, but it is hidden
                below that — without this the logo disappeared entirely on
                tablet and mobile. Same lockup component, no duplicated markup. */}
            <div className="flex-none lg:hidden">
              <BrandLockup compact />
            </div>

            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-cream">
                {current?.label || 'Dashboard'}
              </h2>
              {status?.last_run?.finished_at && (
                <p className="truncate text-[11px] text-muted">
                  Last computed{' '}
                  {new Date(status.last_run.finished_at).toLocaleString('en-IN')}
                </p>
              )}
            </div>

            <div className="ml-auto flex items-center gap-2">
              {status?.inputs_changed_since_last_run && (
                <span className="chip border-risk-medium/40 bg-risk-medium/12 text-risk-medium">
                  <Activity className="h-3 w-3" />
                  New telemetry
                </span>
              )}
              <button
                className="btn-ghost px-2.5 py-2"
                onClick={refresh}
                disabled={refreshing || status?.running}
                title="Recompute risk from current telemetry"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing || status?.running ? 'animate-spin' : ''}`} />
              </button>
              <div className="relative">
                <button
                  className="btn-ghost relative px-2.5 py-2"
                  title="Notifications"
                  aria-label={`Notifications (${unread} unread)`}
                  aria-expanded={bellOpen}
                  onClick={() => setBellOpen((v) => !v)}
                >
                  <Bell className="h-4 w-4" />
                  {unread > 0 && (
                    <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-risk-critical px-1 text-[10px] font-bold text-ink">
                      {unread}
                    </span>
                  )}
                </button>
                {bellOpen && (
                  <>
                    {/* Click-away layer; the panel itself sits above it. */}
                    <button
                      className="fixed inset-0 z-30 cursor-default"
                      aria-hidden="true"
                      tabIndex={-1}
                      onClick={() => setBellOpen(false)}
                    />
                    <div className="glass-strong absolute right-0 z-40 mt-2 w-80 p-2">
                      <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
                        Notifications
                      </p>
                      {!alerts.length ? (
                        <p className="px-2 py-3 text-xs text-muted">
                          Nothing needs attention.
                        </p>
                      ) : (
                        <div className="max-h-96 overflow-y-auto">
                          {alerts.map((a) => {
                            const s = riskStyle(a.severity);
                            return (
                              <div
                                key={a.id}
                                className={`flex gap-2.5 rounded-lg px-2 py-2 hover:bg-sand/5 ${
                                  a.acknowledged ? 'opacity-45' : ''
                                }`}
                              >
                                <span className={`mt-1.5 h-1.5 w-1.5 flex-none rounded-full ${s.dot}`} />
                                <div className="min-w-0 flex-1">
                                  <p className="text-xs font-medium text-cream">{a.title}</p>
                                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
                                    {a.detail}
                                  </p>
                                </div>
                                {!a.acknowledged && (
                                  <button
                                    className="mt-0.5 flex-none self-start text-[10px] uppercase tracking-wider text-muted hover:text-cream"
                                    onClick={() => acknowledge(a.id)}
                                    title="Acknowledge"
                                  >
                                    Ack
                                  </button>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
              <div className="ml-1 hidden h-8 w-8 place-items-center rounded-full bg-moss/45 text-xs font-semibold text-cream sm:grid">
                {(user?.name || 'U').slice(0, 1).toUpperCase()}
              </div>
            </div>
          </header>

          <main ref={mainRef} className="flex-1 px-6 py-6">
            {/* keyed on dataVersion: see refresh() */}
            <Outlet key={dataVersion} />
          </main>

          <footer className="border-t border-sand/15 px-6 py-4 text-center text-[11px] text-muted">
            RISHFORGEAI — AI-Powered Continuous Cyber Risk Quantification &amp; Investment Optimization
          </footer>
        </div>
      </div>
    </div>
  );
}
