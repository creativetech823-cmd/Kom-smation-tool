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
        "relative rounded-2xl border border-[var(--border)] bg-[var(--surface)]",
        "shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_8px_24px_-12px_var(--shadow-color)]",
        glow && "border-[var(--accent)]/40",
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
