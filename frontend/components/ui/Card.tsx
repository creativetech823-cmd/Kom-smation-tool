import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  glow = false,
}: {
  children: ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur-xl",
        "shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_20px_60px_-30px_rgba(0,0,0,0.8)]",
        glow &&
          "before:absolute before:inset-0 before:-z-10 before:rounded-2xl before:bg-gradient-to-br before:from-[var(--accent)]/20 before:to-[var(--accent-2)]/10 before:blur-2xl",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  icon,
  right,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent-2)]">
            {icon}
          </div>
        )}
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight text-[var(--foreground)]">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-0.5 text-[13px] text-[var(--muted)]">{subtitle}</p>
          )}
        </div>
      </div>
      {right}
    </div>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("px-6 pb-6", className)}>{children}</div>;
}
