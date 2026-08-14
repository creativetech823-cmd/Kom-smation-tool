"use client";

import type { DurationStatus } from "@/lib/duration";

const STATUS_DOT: Record<DurationStatus, string> = { good: "🟢", warn: "🟡", bad: "🔴" };
const STATUS_LABEL: Record<DurationStatus, string> = { good: "Perfect", warn: "Close", bad: "Too long/short" };
const STATUS_COLOR: Record<DurationStatus, string> = {
  good: "text-[var(--success)]",
  warn: "text-[var(--warning)]",
  bad: "text-[var(--danger)]",
};

export function DurationMeter({
  estimatedSeconds,
  targetSeconds,
  status,
}: {
  estimatedSeconds: number;
  targetSeconds: number;
  status: DurationStatus;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-1.5">
      <span className="text-[12px] text-[var(--muted)]">🎙 Est. Voice Time</span>
      <span className="text-[13px] font-semibold text-[var(--foreground)]">{estimatedSeconds}s</span>
      <span className="text-[11px] text-[var(--muted)]">/ {targetSeconds}s target</span>
      <span className={`flex items-center gap-1 text-[11px] font-medium ${STATUS_COLOR[status]}`}>
        {STATUS_DOT[status]} {STATUS_LABEL[status]}
      </span>
    </div>
  );
}
