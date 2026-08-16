import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export function EmptyState({
  icon,
  title,
  message,
  actionLabel,
  onAction,
}: {
  icon?: ReactNode;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <Card className="flex flex-col items-center gap-3 px-8 py-14 text-center">
      {icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] text-[var(--accent-2)]">
          {icon}
        </div>
      )}
      <h3 className="text-[15px] font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="max-w-sm text-[13px] leading-relaxed text-[var(--muted)]">{message}</p>
      {actionLabel && onAction && (
        <Button size="sm" onClick={onAction} className="mt-1">
          {actionLabel}
        </Button>
      )}
    </Card>
  );
}
