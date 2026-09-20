import { memo, useEffect, useRef } from 'react';
import * as THREE from 'three';

/**
 * The RiskForgeAI brand mark, sampled into a point cloud.
 *
 * One implementation serves both places the animation appears, selected by
 * `variant`:
 *
 *   login   — the sign-in backdrop. Particles explode inward from a scatter,
 *             resolve into the wordmark, and hold — or, with `motionless`,
 *             render the formed wordmark in a single frame and stop.
 *   ambient — the same scene behind the authenticated app. The wordmark forms
 *             on load, disperses into a drifting field, and reforms on a slow
 *             cycle, at a fraction of the login opacity so charts and tables
 *             stay readable on top of it.
 *
 * Text targets come from an offscreen 2D canvas rather than a font geometry, so
 * nothing has to load before the scene can render.
 */

/* Moss for the body of the wordmark, Midnight for the accent layer behind it.
   Both are darker than the Ivory ground — see the blending note below. */
const STEEL = 0xb6b8ab;
const SAND = 0x3c3e4a;

const VARIANTS = {
  login: {
    assemble: 2.6,
    loop: false,
    textWidth: 620,
    gap: 4,
    baseSize: 2.1,
    accentSize: 1.1,
    // Tuned for the motionless treatment: a permanently-formed wordmark packs
    // every particle into the glyphs, so it reads far heavier than the settling
    // field these numbers were first set for. Low enough now to sit behind the
    // intro copy as a watermark rather than compete with it.
    baseOpacity: 0.18,
    accentOpacity: 0.06,
    parallaxX: 60,
    parallaxY: 40,
    spin: 0.05,
    cloudDrift: 0,
  },
  ambient: {
    assemble: 3.2,
    loop: true,
    hold: 4.5,
    disperse: 5,
    drift: 16,
    textWidth: 760,
    gap: 6,
    baseSize: 1.7,
    accentSize: 0.9,
    // A third of the login opacity: enough to read as the brand, not enough to
    // compete with the figures layered over it. On Ivory this matters more than
    // it did on black — at 0.3 the field showed through the gutters between
    // cards as smudges on the page rather than as a backdrop.
    baseOpacity: 0.13,
    accentOpacity: 0.05,
    parallaxX: 26,
    parallaxY: 16,
    spin: 0.1,
    cloudDrift: 1,
  },
};

/** Samples opaque pixels of rendered text into 2D points, normalized to a width. */
function sampleTextPoints(text, targetWidth, gap) {
  const off = document.createElement('canvas');
  const scale = 2;
  const fontSize = 200;
  off.width = 2200 * scale;
  off.height = 500 * scale;
  const octx = off.getContext('2d', { willReadFrequently: true });
  octx.fillStyle = '#000';
  octx.fillRect(0, 0, off.width, off.height);
  octx.fillStyle = '#fff';
  octx.font = `700 ${fontSize * scale}px Georgia, serif`;
  octx.textAlign = 'center';
  octx.textBaseline = 'middle';
  octx.fillText(text, off.width / 2, off.height / 2);

  const { data } = octx.getImageData(0, 0, off.width, off.height);
  const pts = [];
  for (let y = 0; y < off.height; y += gap) {
    for (let x = 0; x < off.width; x += gap) {
      if (data[(y * off.width + x) * 4] > 128) {
        pts.push({
          x: (x - off.width / 2) / scale,
          y: -(y - off.height / 2) / scale,
        });
      }
    }
  }

  let minX = Infinity;
  let maxX = -Infinity;
  for (const p of pts) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
  }
  const s = targetWidth / (maxX - minX || 1);
  for (const p of pts) {
    p.x *= s;
    p.y *= s;
  }
  return pts;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function ParticleBrandBackground({
  variant = 'ambient',
  text = 'RiskForgeAI',
  className,
  // Renders the wordmark already assembled and then stops: no assembly, no
  // drift, no parallax, no rAF loop at all. Same end state the reduced-motion
  // path has always produced, exposed as a deliberate choice.
  motionless = false,
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const cfg = VARIANTS[variant] || VARIANTS.ambient;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: variant === 'login',
        alpha: true,
        powerPreference: 'low-power',
      });
    } catch {
      // No WebGL — every screen still works, it just loses the backdrop.
      return;
    }

    // Coarse pointers are phones and tablets: fewer particles, lower pixel
    // ratio, so the field costs less on the hardware least able to afford it.
    const compact = window.matchMedia('(max-width: 768px), (pointer: coarse)').matches;
    const gap = compact ? Math.round(cfg.gap * 1.6) : cfg.gap;
    const maxDpr = compact ? 1.5 : 2;

    // Hoisted above `resize` because a frozen scene has no animation loop to
    // repaint it — the resize handler has to draw the single frame itself.
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const frozen = motionless || reduceMotion;
    // A plain `let`, not a reference to the `const animate` below: `resize()`
    // runs during setup, before that binding is initialised, and `typeof` does
    // not shield a const from its temporal dead zone.
    let renderFrame = null;

    // updateStyle=false: the canvas is sized by CSS at 100%/100% of a fixed
    // container, so the renderer must not write pixel widths onto it. An inline
    // width of window.innerWidth includes the scrollbar and would overflow.
    const resize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, maxDpr));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      // A frozen scene never schedules another frame, so repaint here or the
      // canvas keeps the pre-resize image stretched to the new size.
      if (frozen && renderFrame) renderFrame();
    };

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      50,
      window.innerWidth / window.innerHeight,
      0.1,
      2000
    );
    camera.position.z = 420;
    resize();

    const textPoints = sampleTextPoints(text, cfg.textWidth, gap);
    const COUNT = textPoints.length;

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(COUNT * 3);
    const targets = new Float32Array(COUNT * 3);
    const startPositions = new Float32Array(COUNT * 3);
    const speeds = new Float32Array(COUNT);

    for (let i = 0; i < COUNT; i++) {
      const p = textPoints[i];
      // Random scattered start — the explosion origin, and the resting cloud
      // the ambient variant disperses back into.
      const sx = (Math.random() - 0.5) * 1400;
      const sy = (Math.random() - 0.5) * 900;
      const sz = (Math.random() - 0.5) * 900;
      startPositions[i * 3] = sx;
      startPositions[i * 3 + 1] = sy;
      startPositions[i * 3 + 2] = sz;

      positions[i * 3] = sx;
      positions[i * 3 + 1] = sy;
      positions[i * 3 + 2] = sz;

      targets[i * 3] = p.x;
      targets[i * 3 + 1] = p.y;
      targets[i * 3 + 2] = (Math.random() - 0.5) * 30;

      speeds[i] = 0.4 + Math.random() * 0.6;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    /* Normal, not additive. Additive blending only ever brightens toward white,
       which on the Ivory ground renders the whole field invisible; the particles
       now have to darken the ground instead. */
    const material = new THREE.PointsMaterial({
      color: STEEL,
      size: cfg.baseSize,
      transparent: true,
      opacity: cfg.baseOpacity,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Subtle secondary layer in the sand tone for depth.
    const material2 = new THREE.PointsMaterial({
      color: SAND,
      size: cfg.accentSize,
      transparent: true,
      opacity: cfg.accentOpacity,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    const points2 = new THREE.Points(geometry, material2);
    points2.position.z = -8;
    scene.add(points2);

    const clock = new THREE.Clock();

    // How assembled the wordmark is, 0 (scattered) to 1 (formed).
    let formation = frozen ? 1 : 0;
    let cycleT = 0;
    const cycle = cfg.loop
      ? cfg.assemble + cfg.hold + cfg.disperse + cfg.drift
      : 0;

    const formationAt = (t) => {
      if (t < cfg.assemble) return t / cfg.assemble;
      if (t < cfg.assemble + cfg.hold) return 1;
      const d = t - cfg.assemble - cfg.hold;
      if (d < cfg.disperse) return 1 - d / cfg.disperse;
      return 0;
    };

    const pointer = { x: 0, y: 0 };
    const onMouseMove = (e) => {
      pointer.x = (e.clientX / window.innerWidth - 0.5) * 2;
      pointer.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    if (!frozen) window.addEventListener('mousemove', onMouseMove);

    let frame = null;
    const animate = () => {
      // Frozen: draw exactly one frame and never queue another.
      if (!frozen) frame = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.1);
      const elapsed = clock.getElapsedTime();

      if (!frozen) {
        if (cfg.loop) {
          cycleT = (cycleT + dt) % cycle;
          formation = formationAt(cycleT);
        } else {
          formation = Math.min(formation + dt / cfg.assemble, 1);
        }
      }

      const posAttr = geometry.attributes.position;
      const arr = posAttr.array;

      for (let i = 0; i < COUNT; i++) {
        const idx = i * 3;
        // Per-particle speed staggers arrival so the word resolves — and later
        // dissolves — unevenly rather than as one rigid block.
        const e = easeOutCubic(Math.min(1, formation * (0.7 + speeds[i] * 0.6)));

        // The cloud the particles return to drifts, so a dispersed field keeps
        // moving instead of freezing into static noise.
        const dx = cfg.cloudDrift && !frozen
          ? Math.sin(elapsed * 0.08 + i * 0.7) * 22
          : 0;
        const dy = cfg.cloudDrift && !frozen
          ? Math.cos(elapsed * 0.06 + i * 0.9) * 16
          : 0;

        const sx = startPositions[idx] + dx;
        const sy = startPositions[idx + 1] + dy;
        const sz = startPositions[idx + 2];

        const bx = sx + (targets[idx] - sx) * e;
        const by = sy + (targets[idx + 1] - sy) * e;
        const bz = sz + (targets[idx + 2] - sz) * e;

        // Gentle ambient float, faded in as the particle settles.
        const fx = frozen ? 0 : Math.sin(elapsed * 0.5 + i) * 0.6 * e;
        const fy = frozen ? 0 : Math.cos(elapsed * 0.4 + i * 1.3) * 0.6 * e;

        arr[idx] = bx + fx;
        arr[idx + 1] = by + fy;
        arr[idx + 2] = bz;
      }
      posAttr.needsUpdate = true;

      // Parallax camera drift toward the pointer.
      camera.position.x += (pointer.x * cfg.parallaxX - camera.position.x) * 0.03;
      camera.position.y += (-pointer.y * cfg.parallaxY - camera.position.y) * 0.03;
      camera.lookAt(0, 0, 0);

      points.rotation.y = frozen ? 0 : Math.sin(elapsed * 0.05) * cfg.spin;
      points2.rotation.y = points.rotation.y;

      renderer.render(scene, camera);
    };
    renderFrame = animate;
    animate();

    // A hidden tab still runs rAF in some browsers, and always burns battery on
    // wake. Stop entirely, and swallow the accumulated delta on return so the
    // cycle resumes where it left off instead of jumping.
    const onVisibility = () => {
      if (document.hidden) {
        if (frame !== null) cancelAnimationFrame(frame);
        frame = null;
      } else if (frame === null) {
        clock.getDelta();
        animate();
      }
    };
    // A frozen scene has no loop to pause, and its single painted frame
    // survives a tab switch on its own.
    if (!frozen) document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('resize', resize);

    return () => {
      if (frame !== null) cancelAnimationFrame(frame);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('resize', resize);
      scene.remove(points);
      scene.remove(points2);
      geometry.dispose();
      material.dispose();
      material2.dispose();
      renderer.dispose();
    };
  }, [variant, text, motionless]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      aria-hidden="true"
    />
  );
}

// The scene is built once in an effect and mutated imperatively — no particle
// ever touches React state. Memoising keeps a parent re-render (Layout runs one
// on every route change) from re-rendering the canvas element too.
export default memo(ParticleBrandBackground);
