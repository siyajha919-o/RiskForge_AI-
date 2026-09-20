/**
 * The RiskForge AI mark.
 *
 * A shield — the security half — carrying a loss-distribution histogram, which
 * is literally what the engine computes: bars rising to a mode and tailing off
 * to the right, the shape every FAIR Monte Carlo run produces. The two halves
 * together say the one thing the product does that a vulnerability scanner
 * does not: it puts a number on the risk.
 *
 * Monochrome by design. The severity scale (low/medium/high/critical) is
 * reserved for status anywhere in this interface, so the brand never borrows
 * from it — a logo that turns red would read as an alert.
 *
 * Drawn on a 32x32 grid and scaled by `size`; strokes stay legible down to the
 * 26px compact mark in the mobile header.
 *
 * Inline SVG on purpose: there is no file to 404, no external host to go down,
 * and no flash of missing logo while a request is in flight. That is the
 * fallback story — the mark cannot fail to load because nothing is loaded.
 */
export function BrandLockup({ compact = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark size={compact ? 26 : 32} className="flex-none text-cream" />
      <div className="leading-tight">
        <p
          className={`font-bold tracking-tight text-cream ${
            compact ? 'text-[13px]' : 'text-sm'
          }`}
        >
          RISKFORGE<span className="text-muted">AI</span>
        </p>
        {!compact && (
          <p className="text-[10px] uppercase tracking-widest text-muted">Cyber Risk</p>
        )}
      </div>
    </div>
  );
}

export default function BrandMark({ size = 34, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      role="img"
      aria-label="RiskForge AI"
    >
      {/* Shield */}
      <path
        d="M16 2.5 L27.5 6.9 V15.3 C27.5 22.3 22.6 27.5 16 29.5 C9.4 27.5 4.5 22.3 4.5 15.3 V6.9 Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      {/* Loss distribution: rises to a mode, tails right. */}
      <rect x="9.1" y="18.4" width="2.4" height="3.6" rx="0.5" fill="currentColor" opacity="0.45" />
      <rect x="12.4" y="14.2" width="2.4" height="7.8" rx="0.5" fill="currentColor" opacity="0.75" />
      <rect x="15.7" y="11.6" width="2.4" height="10.4" rx="0.5" fill="currentColor" />
      <rect x="19" y="16.1" width="2.4" height="5.9" rx="0.5" fill="currentColor" opacity="0.6" />
      {/* Baseline the bars stand on. */}
      <path
        d="M8.2 23.1 H23.2"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        opacity="0.5"
      />
    </svg>
  );
}
