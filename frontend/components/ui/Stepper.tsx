import { cn } from "@/lib/utils";

export type Step = { key: string; label: string };

export function Stepper({
  steps,
  activeIndex,
  furthestIndex,
}: {
  steps: Step[];
  activeIndex: number;
  furthestIndex: number;
}) {
  return (
    <ol className="flex items-center gap-1.5">
      {steps.map((step, i) => {
        const isActive = i === activeIndex;
        const isDone = i < furthestIndex;
        const isReachable = i <= furthestIndex;
        return (
          <li key={step.key} className="flex items-center gap-1.5">
            <div
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors",
                isActive
                  ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                  : isDone
                  ? "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--foreground)]"
                  : "border-[var(--border)] text-[var(--muted)]",
                !isReachable && "opacity-50"
              )}
            >
              <span
                className={cn(
                  "flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold",
                  isActive
                    ? "bg-[var(--accent)] text-white"
                    : isDone
                    ? "bg-[var(--success)] text-black"
                    : "bg-white/10 text-[var(--muted)]"
                )}
              >
                {isDone ? "✓" : i + 1}
              </span>
              {step.label}
            </div>
            {i < steps.length - 1 && (
              <div
                className={cn(
                  "h-px w-4",
                  isDone ? "bg-[var(--success)]/50" : "bg-[var(--border)]"
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
