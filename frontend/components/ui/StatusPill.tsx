import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Status = "pass" | "warning" | "review";

const statusClasses: Record<Status, string> = {
  pass: "bg-[var(--success)]/12 text-[var(--success)] border-[var(--success)]/30",
  warning: "bg-[var(--warning)]/12 text-[var(--warning)] border-[var(--warning)]/30",
  review: "bg-[var(--danger)]/12 text-[var(--danger)] border-[var(--danger)]/30",
};

function StatusIcon({ status }: { status: Status }) {
  if (status === "pass") {
    return (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
        <path d="M8 12.5l2.5 2.5L16 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === "warning") {
    return (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path d="M12 3.5L22 20H2L12 3.5z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path d="M12 10v4.5M12 17.5v.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M8.5 3h7L21 8.5v7L15.5 21h-7L3 15.5v-7L8.5 3z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function StatusPill({
  status,
  children,
  className,
}: {
  status: Status;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
        statusClasses[status],
        className
      )}
    >
      <StatusIcon status={status} />
      {children}
    </span>
  );
}
