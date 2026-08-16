"use client";

import { motion } from "framer-motion";

export type ProgressStage = { id: string; label: string };

/**
 * Like AiWorkingChecklist, but driven by real external state (currentIndex)
 * instead of a timer — for flows made of genuinely separate awaited calls
 * (e.g. fetch a URL, then run a Gemini call on the result).
 */
export function StagedProgress({ stages, currentIndex }: { stages: ProgressStage[]; currentIndex: number }) {
  return (
    <div className="space-y-2.5">
      {stages.map((stage, i) => {
        const isDone = i < currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <motion.div
            key={stage.id}
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
            <span className={isDone || isCurrent ? "text-[var(--foreground)]" : "text-[var(--muted)]"}>{stage.label}</span>
          </motion.div>
        );
      })}
    </div>
  );
}
