"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--accent)] text-[var(--on-accent)] hover:brightness-110 active:brightness-95",
  secondary:
    "bg-[var(--surface-2)] text-[var(--foreground)] border border-[var(--border-strong)] hover:bg-[var(--hover-surface)]",
  ghost: "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.05]",
  danger:
    "bg-[var(--danger)]/15 text-[var(--danger)] border border-[var(--danger)]/30 hover:bg-[var(--danger)]/25",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-10 px-4 text-[14px] gap-2 rounded-xl",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  className,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium transition-all duration-150",
        "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:brightness-100",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span
          className={cn(
            "h-3.5 w-3.5 animate-spin rounded-full border-2",
            variant === "primary" ? "border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" : "border-[var(--foreground)]/30 border-t-[var(--foreground)]"
          )}
        />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
