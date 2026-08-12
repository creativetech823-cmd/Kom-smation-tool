"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export type Step = { key: string; label: string; sublabel?: string };

export function Stepper({
  steps,
  activeIndex,
  furthestIndex,
  onSelect,
}: {
  steps: Step[];
  activeIndex: number;
  furthestIndex: number;
  onSelect?: (index: number) => void;
}) {
  return (
    <ol className="flex items-center">
      {steps.map((step, i) => {
        const isActive = i === activeIndex;
        const isDone = i < furthestIndex;
        const isReachable = i <= furthestIndex;
        return (
          <li key={step.key} className="flex flex-1 items-center last:flex-initial">
            <motion.button
              type="button"
              disabled={!isReachable}
              onClick={() => isReachable && onSelect?.(i)}
              whileHover={isReachable ? { y: -2 } : undefined}
              className={cn(
                "flex items-center gap-2.5 whitespace-nowrap rounded-xl px-2 py-1.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
                isReachable ? "cursor-pointer" : "cursor-default",
                !isReachable && "opacity-45"
              )}
            >
              <span className="relative flex h-8 w-8 shrink-0 items-center justify-center">
                {isDone ? (
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--success)] text-black">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M5 12l5 5L20 7"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                ) : isActive ? (
                  <>
                    <span className="absolute h-8 w-8 rounded-full border-2 border-[var(--accent)]" />
                    <motion.span
                      className="h-3 w-3 rounded-full bg-[var(--accent)]"
                      animate={{ scale: [1, 1.4, 1] }}
                      transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                    />
                  </>
                ) : (
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--border-strong)] text-[12px] font-semibold text-[var(--muted)]">
                    {i + 1}
                  </span>
                )}
              </span>
              <span className="flex flex-col leading-tight">
                <span
                  className={cn(
                    "text-[13px] font-semibold",
                    isActive ? "text-[var(--accent)]" : isDone ? "text-[var(--foreground)]" : "text-[var(--muted)]"
                  )}
                >
                  {step.label}
                </span>
                {step.sublabel && <span className="text-[11px] text-[var(--muted)]">{step.sublabel}</span>}
              </span>
            </motion.button>

            {i < steps.length - 1 && (
              <div className="relative mx-1 h-[2px] min-w-6 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                <motion.div
                  className="absolute inset-y-0 left-0 w-full origin-left rounded-full bg-gradient-to-r from-[var(--accent)] to-[var(--accent-2)]"
                  initial={false}
                  animate={{ scaleX: isDone ? 1 : 0 }}
                  transition={{ duration: 0.4, ease: "easeInOut" }}
                />
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
