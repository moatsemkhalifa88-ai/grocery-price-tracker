"use client";

import { useEffect, useRef, useState } from "react";

type Props = { value: number; delayMs?: number; durationMs?: number; decimals?: number; prefix?: string };

/** Counts from 0 to `value` once, after `delayMs`. Shows the final value at once
 *  when the viewer prefers reduced motion (and on the server render). */
export default function CountUp({ value, delayMs = 0, durationMs = 1100, decimals = 2, prefix = "₪" }: Props) {
  const [shown, setShown] = useState(value);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setShown(0);
    let raf = 0;
    const t0 = performance.now() + delayMs;
    const tick = (now: number) => {
      const t = Math.min(Math.max((now - t0) / durationMs, 0), 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(value * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, delayMs, durationMs]);

  const text = shown.toLocaleString("he-IL", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return (
    <span className="countup" aria-label={`${prefix}${value.toFixed(decimals)}`}>
      {prefix}
      {text}
    </span>
  );
}
