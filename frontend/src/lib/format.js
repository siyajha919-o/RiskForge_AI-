/** Indian numbering — the audience reads exposure in lakh and crore. */
export function inr(value, { compact = true } = {}) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  const n = Number(value);
  const abs = Math.abs(n);
  if (!compact) return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  if (abs >= 1e3) return `₹${(n / 1e3).toFixed(1)} K`;
  return `₹${n.toFixed(0)}`;
}

export function pct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(digits)}%`;
}

export function signedPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${value >= 0 ? '+' : ''}${Number(value).toFixed(digits)}%`;
}

export function num(value) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('en-IN');
}

/** Tailwind classes per severity. One place so severity never drifts. */
export const RISK_STYLES = {
  Critical: {
    text: 'text-risk-critical',
    bg: 'bg-risk-critical/12',
    border: 'border-risk-critical/40',
    dot: 'bg-risk-critical',
    hex: '#9B3330',
  },
  High: {
    text: 'text-risk-high',
    bg: 'bg-risk-high/12',
    border: 'border-risk-high/40',
    dot: 'bg-risk-high',
    hex: '#9A5526',
  },
  Medium: {
    text: 'text-risk-medium',
    bg: 'bg-risk-medium/12',
    border: 'border-risk-medium/40',
    dot: 'bg-risk-medium',
    hex: '#7E601B',
  },
  Low: {
    text: 'text-risk-low',
    bg: 'bg-risk-low/12',
    border: 'border-risk-low/40',
    dot: 'bg-risk-low',
    hex: '#3F6B4A',
  },
};

export const riskStyle = (level) => RISK_STYLES[level] || RISK_STYLES.Low;

export const COMPLIANCE_STYLES = {
  Compliant: { text: 'text-risk-low', dot: 'bg-risk-low', hex: '#3F6B4A' },
  Partial: { text: 'text-risk-medium', dot: 'bg-risk-medium', hex: '#7E601B' },
  'Non-Compliant': { text: 'text-risk-critical', dot: 'bg-risk-critical', hex: '#9B3330' },
};

export const complianceStyle = (status) =>
  COMPLIANCE_STYLES[status] || COMPLIANCE_STYLES['Non-Compliant'];

/* Chart colours. Kept in sync with the brand tokens in tailwind.config.js —
   Recharts takes literal values, so it cannot read the Tailwind theme.

   Ivory / Moss / Smoke / Garden / Midnight. Series marks are drawn in the two
   mid-tones (Moss and Smoke) so they sit on Ivory without competing with the
   Midnight type; grid and axis are Midnight at low alpha. */
export const CHART = {
  cream: '#3C3E4A',  // Midnight — primary series, emphasised line
  sand: '#9FA3AD',   // Smoke    — secondary series
  moss: '#B6B8AB',   // Moss     — tertiary series, area fills
  warm: '#3C3E4A',   // Midnight — brand mark
  slate: '#E0DFD2',  // Garden   — tooltip and panel ground
  ink: '#F3F1EC',    // Ivory    — chart ground
  grid: 'rgba(60,62,74,0.10)',
  axis: 'rgba(60,62,74,0.55)',
  cursor: 'rgba(60,62,74,0.06)',
};
