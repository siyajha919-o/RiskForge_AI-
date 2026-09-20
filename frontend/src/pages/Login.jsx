import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import BrandMark from '../components/BrandMark';
import ParticleBrandBackground from '../components/ParticleBrandBackground';
import { api, auth } from '../lib/api';
import './login.css';

/**
 * Demo account, shown on the page so a reviewer can get in without being handed
 * credentials out of band.
 *
 * These MUST match ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD in
 * RiskEngine/.env — the API creates this account from those values on first
 * start. Change one and you have to change the other.
 *
 * This is a demo convenience running against synthetic data. Delete this block
 * (and the panel that renders it) before the engine ever points at a real
 * estate: a password on the sign-in page is a password anyone who reaches the
 * sign-in page has.
 */
const DEMO = {
  email: 'admin@riskforge.io',
  password: 'changeme-at-least-12-chars',
};

/** What the engine actually does, for the reviewer who has never seen it. */
const CAPABILITIES = [
  ['FAIR Monte Carlo', 'Annualised loss in rupees, with P90/P95/P99 tails'],
  ['Bayesian attack paths', 'EPSS-weighted compromise routes across the estate'],
  ['Gordon-Loeb optimiser', 'Which controls to buy inside a fixed budget'],
];

const FRAMEWORKS = ['ISO 27001', 'NIST CSF', 'CIS v8', 'RBI CSF', 'SEBI CSCRF'];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (auth.token()) navigate('/app', { replace: true });
  }, [navigate]);

  // The design is a fixed, full-viewport stage; scrolling is suppressed only
  // while it is mounted so the rest of the app keeps its normal overflow.
  useEffect(() => {
    const { style: html } = document.documentElement;
    const { style: body } = document.body;
    const prev = [html.overflow, body.overflow];
    html.overflow = 'hidden';
    body.overflow = 'hidden';
    return () => {
      html.overflow = prev[0];
      body.overflow = prev[1];
    };
  }, []);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(email, password, remember);
      auth.save(res.access_token, res.user);
      navigate('/app', { replace: true });
    } catch (err) {
      setError(err.friendlyMessage || 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  }

  function useDemoAccount() {
    setEmail(DEMO.email);
    setPassword(DEMO.password);
    setError(null);
  }

  return (
    <div id="stage">
      {/* Formed on the first frame and then still — see `motionless`. */}
      <ParticleBrandBackground variant="login" className="stage-canvas" motionless />
      <div className="grain" />

      <div className="topbar">
        <BrandMark size={34} className="mark" />
        <div className="brand">
          RISKFORGE<small>ENTERPRISE CYBER RISK PLATFORM</small>
        </div>
      </div>

      <div className="stage-body">
        <section className="intro">
          <div className="intro-eyebrow">CYBER RISK QUANTIFICATION</div>
          <h2 className="intro-title">Your exposure, in rupees.</h2>
          <p className="intro-lede">
            RiskForge AI turns an asset estate — vulnerabilities, controls, threat
            intelligence and business impact — into a single financial figure a
            board can act on, then tells you which controls to buy to bring it
            down.
          </p>

          <ul className="cap-list">
            {CAPABILITIES.map(([name, detail]) => (
              <li key={name}>
                <span className="cap-name">{name}</span>
                <span className="cap-detail">{detail}</span>
              </li>
            ))}
          </ul>

          <div className="frameworks">
            <span className="frameworks-label">MAPPED TO</span>
            <span className="frameworks-list">{FRAMEWORKS.join(' · ')}</span>
          </div>
        </section>

        <div className="panel-wrap">
          <form className="panel" onSubmit={submit}>
            <div className="eyebrow">SECURE ACCESS</div>
            <h1>Sign in</h1>
            <div className="sub">Your risk data requires an authenticated session.</div>

            <div className="field">
              <label htmlFor="login-email">EMAIL OR USERNAME</label>
              <div className="input-row">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#646672" strokeWidth="1.6">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="M2 6l10 7 10-7" />
                </svg>
                <input
                  id="login-email"
                  type="text"
                  autoComplete="username"
                  placeholder="you@organisation.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="login-password">PASSWORD</label>
              <div className="input-row">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#646672" strokeWidth="1.6">
                  <rect x="4" y="10" width="16" height="10" rx="2" />
                  <path d="M8 10V7a4 4 0 018 0v3" />
                </svg>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="eye"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#646672" strokeWidth="1.6">
                    <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                    <circle cx="12" cy="12" r="3" />
                    {!showPassword && <path d="M4 4l16 16" />}
                  </svg>
                </button>
              </div>
            </div>

            <div className="row">
              <label>
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />{' '}
                Remember me
              </label>
              <button
                type="button"
                className="link"
                onClick={() => setError('Password resets are handled by your administrator.')}
              >
                Forgot password?
              </button>
            </div>

            <button className="submit" type="submit" disabled={loading} aria-busy={loading}>
              {loading ? 'Signing in…' : 'Login'}
            </button>

            {error && (
              <p className="alert" role="alert">
                {error}
              </p>
            )}

            <div className="demo">
              <div className="demo-head">
                <span className="demo-label">DEMO ACCESS</span>
                <button type="button" className="demo-fill" onClick={useDemoAccount}>
                  Use these
                </button>
              </div>
              <dl className="demo-creds">
                <dt>Email</dt>
                <dd>{DEMO.email}</dd>
                <dt>Password</dt>
                <dd>{DEMO.password}</dd>
              </dl>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
