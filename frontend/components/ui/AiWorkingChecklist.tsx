"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export type ChecklistStep = { id: string; label: string };

/**
 * Simulated progressive "the AI is working" checklist. Ticks through `steps` on a timer
 * while `active` is true. If the real work finishes before all steps have ticked, it
 * fast-forwards to fully-ticked rather than lying about partial progress. If the real work
 * outruns the simulated steps, it holds on `holdLabel` instead of looping or stalling.
 */
export function AiWorkingChecklist({
  steps,
  active,
  minStepMs = 900,
  holdLabel = "Almost ready...",
  onSettled,
}: {
  steps: ChecklistStep[];
  active: boolean;
  minStepMs?: number;
  holdLabel?: string;
  onSettled?: () => void;
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const settledRef = useRef(false);

  useEffect(() => {
    if (!active) return;
    // Resetting the tick counter each time this effect (re)starts a fresh interval is
    // the point of this effect, not a value that could be derived during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrentIndex(0);
    settledRef.current = false;
    const interval = setInterval(() => {
      setCurrentIndex((i) => (i < steps.length ? i + 1 : i));
    }, minStepMs);
    return () => clearInterval(interval);
  }, [active, steps.length, minStepMs]);

  useEffect(() => {
    if (active || settledRef.current) return;
    settledRef.current = true;
    setCurrentIndex(steps.length);
    const t = setTimeout(() => onSettled?.(), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  return (
    <div className="space-y-2.5">
      {steps.map((step, i) => {
        const isDone = i < currentIndex;
        const isCurrent = i === currentIndex && currentIndex < steps.length;
        return (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25 }}
            className="flex items-center gap-2.5 text-[13px]"
          >
            {isDone ? (
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--success)]/15 text-[var(--success)]">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12l5 5L20 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            ) : isCurrent ? (
              <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-[var(--foreground)]/20 border-t-[var(--accent)]" />
            ) : (
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--border-strong)]" />
            )}
            <span
              className={
                isDone
                  ? "text-[var(--foreground)]"
                  : isCurrent
                  ? "text-[var(--foreground)]"
                  : "text-[var(--muted)]"
              }
            >
              {step.label}
            </span>
          </motion.div>
        );
      })}
      <AnimatePresence>
        {currentIndex >= steps.length && active && (
          <motion.div
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2.5 text-[13px] italic text-[var(--muted)]"
          >
            <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-[var(--foreground)]/20 border-t-[var(--accent)]" />
            {holdLabel}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
