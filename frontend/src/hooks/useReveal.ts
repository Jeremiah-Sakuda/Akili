import { useEffect, useRef, useState } from 'react';

/**
 * Triggers the CSS `.visible` class on mount (after a short delay) for entrance animations.
 * Attach `revealClass` to the element's className and `ref` to its DOM node.
 */
export function useReveal(variant: 'reveal' | 'reveal-scale' | 'reveal-left' = 'reveal', delayMs = 60) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delayMs);
    return () => clearTimeout(t);
  }, [delayMs]);

  const revealClass = `${variant}${visible ? ' visible' : ''}`;
  return { ref, revealClass };
}

/**
 * Marks children as visible using IntersectionObserver for scroll-triggered reveals.
 */
export function useScrollReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, visible };
}
