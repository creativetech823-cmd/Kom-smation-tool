"use client";

import { useEffect, useRef } from "react";
import { useMotionValueEvent, useSpring } from "framer-motion";

export function ConfidenceRing({ value, size = 56 }: { value: number; size?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const spring = useSpring(0, { stiffness: 60, damping: 20 });
  const pct = Math.round(value * 100);

  useEffect(() => {
    spring.set(pct);
  }, [pct, spring]);

  useMotionValueEvent(spring, "change", (latest) => {
    ref.current?.style.setProperty("--pct", String(latest));
  });

  return (
    <div
      ref={ref}
      style={{
        width: size,
        height: size,
        background:
          "conic-gradient(from -90deg, var(--accent) calc(var(--pct) * 1%), var(--surface-2) calc(var(--pct) * 1%))",
      }}
      className="relative shrink-0 rounded-full"
    >
      <div
        className="absolute inset-[4px] flex items-center justify-center rounded-full bg-[var(--surface)] text-[11px] font-semibold text-[var(--foreground)]"
      >
        {pct}%
      </div>
    </div>
  );
}
