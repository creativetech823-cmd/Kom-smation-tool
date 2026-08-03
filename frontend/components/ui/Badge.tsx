import { cn } from "@/lib/utils";

type Tone = "neutral" | "accent" | "success" | "danger" | "warning";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-white/[0.06] text-[var(--muted)] border-[var(--border-strong)]",
  accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/30",
  success: "bg-[var(--success)]/12 text-[var(--success)] border-[var(--success)]/30",
  danger: "bg-[var(--danger)]/12 text-[var(--danger)] border-[var(--danger)]/30",
  warning: "bg-[var(--warning)]/12 text-[var(--warning)] border-[var(--warning)]/30",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
