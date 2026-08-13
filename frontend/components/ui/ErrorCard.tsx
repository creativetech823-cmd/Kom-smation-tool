"use client";

import { Button } from "@/components/ui/Button";

export function ErrorCard({
  message,
  onRetry,
  retrying,
}: {
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  return (
    <div className="glass-card flex items-start gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/[0.06] px-4 py-3.5">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--danger)]/15 text-[var(--danger)]">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 8v5M12 15.5v.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] leading-snug text-[var(--foreground)]">{message}</p>
        {onRetry && (
          <div className="mt-2.5">
            <Button type="button" variant="secondary" size="sm" onClick={onRetry} loading={retrying}>
              Retry
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
