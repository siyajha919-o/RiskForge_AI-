import { useEffect, useRef } from 'react';

/**
 * Pointer-following scroll indicator: a hollow pill that morphs into a solid,
 * glowing dot while the page is scrolling, and tracks the cursor horizontally.
 */
export default function CustomScrollbar() {
  const trackRef = useRef(null);
  const thumbRef = useRef(null);

  useEffect(() => {
    const track = trackRef.current;
    const thumb = thumbRef.current;
    if (!track || !thumb) return;

    let idleTimer;
    let frame;

    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        // Nothing to scroll (short page, or a locked full-viewport screen like
        // login) — stay out of the way rather than parking a static pill.
        track.style.opacity = maxScroll > 1 ? '1' : '0';
        const percent = maxScroll > 0 ? window.scrollY / maxScroll : 0;
        const travel = track.offsetHeight - thumb.offsetHeight;
        thumb.style.top = `${percent * travel}px`;
      });

      thumb.classList.add('is-scrolling');
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => thumb.classList.remove('is-scrolling'), 300);
    };

    const onMouseMove = (event) => {
      cancelAnimationFrame(frame);
      // Keep the track inside the viewport instead of letting it run off the edge.
      const half = track.offsetWidth / 2;
      const x = Math.min(Math.max(event.clientX, half), window.innerWidth - half);
      track.style.left = `${x}px`;
      track.style.right = 'auto';
    };

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    window.addEventListener('mousemove', onMouseMove);

    // Route changes swap page content without firing scroll or resize, so the
    // visibility check needs its own trigger.
    const observer = new ResizeObserver(onScroll);
    observer.observe(document.body);

    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      window.removeEventListener('mousemove', onMouseMove);
      observer.disconnect();
      clearTimeout(idleTimer);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div ref={trackRef} className="scroll-indicator" aria-hidden="true">
      <div ref={thumbRef} className="scroll-indicator-thumb" />
    </div>
  );
}
