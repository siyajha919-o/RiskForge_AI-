/**
 * RISHFORGEAI design tokens.
 *
 * The palette itself lives in src/index.css as `--color-*-rgb` channel triples;
 * this file only maps Tailwind's names onto them. Going through the variables
 * (rather than repeating hexes here) keeps one source of truth, and the
 * `<alpha-value>` form is what lets `border-sand/15` and `bg-ink/80` work.
 *
 * Risk severity is deliberately NOT drawn from the brand hues — status must
 * never be confused with surface, so severity gets its own reserved scale that
 * appears nowhere else in the interface.
 */
const channel = (name) => `rgb(var(--color-${name}-rgb) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      // Values live in src/index.css :root and are read from there, so the login
      // page and the app shell cannot drift apart again. The `<alpha-value>`
      // form is what keeps `border-sand/15` and `bg-ink/80` resolving against a
      // CSS variable — a plain `var()` would break every opacity modifier.
      colors: {
        ink: 'rgb(var(--color-ink-rgb) / <alpha-value>)',     // Ivory    — ground  (login --ink)
        slate: 'rgb(var(--color-slate-rgb) / <alpha-value>)', // Garden   — raised surface
        moss: 'rgb(var(--color-moss-rgb) / <alpha-value>)',   // Moss     — sage accent, dividers
        smoke: 'rgb(var(--color-smoke-rgb) / <alpha-value>)', // Smoke    — solid cool grey, legend dots
        sand: 'rgb(var(--color-sand-rgb) / <alpha-value>)',   // hairlines and washes, low alpha only
        muted: 'rgb(var(--color-muted-rgb) / <alpha-value>)', // Smoke→Midnight, the readable one
        cream: 'rgb(var(--color-cream-rgb) / <alpha-value>)', // Midnight — primary text (login --mist)
        warm: 'rgb(var(--color-warm-rgb) / <alpha-value>)',   // Midnight — brand mark  (login --sand)

        // Reserved risk scale, >=4.5:1 against the ink ground.
        risk: {
          low: 'rgb(var(--color-risk-low-rgb) / <alpha-value>)',
          medium: 'rgb(var(--color-risk-medium-rgb) / <alpha-value>)',
          high: 'rgb(var(--color-risk-high-rgb) / <alpha-value>)',
          critical: 'rgb(var(--color-risk-critical-rgb) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        // Matches the login panel's drop shadow. A light interface cannot spend
        // a luminous glow, so the two "glow" names now resolve to short lifts in
        // Midnight — the same emphasis, expressed as elevation instead of light.
        glass: '0 1px 2px rgb(var(--color-cream-rgb) / 0.06), 0 10px 28px rgb(var(--color-cream-rgb) / 0.09)',
        glow: 'inset 0 0 0 1px rgb(var(--color-cream-rgb) / 0.10)',
        'glow-strong': '0 4px 14px rgb(var(--color-cream-rgb) / 0.22)',
      },
      backdropBlur: { xs: '2px' },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-800px 0' },
          '100%': { backgroundPosition: '800px 0' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.7' },
          '70%': { transform: 'scale(1.4)', opacity: '0' },
          '100%': { transform: 'scale(1.4)', opacity: '0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        shimmer: 'shimmer 2s linear infinite',
        'pulse-ring': 'pulse-ring 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};
