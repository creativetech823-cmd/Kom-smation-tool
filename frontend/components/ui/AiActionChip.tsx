"use client";

import type { RewriteDirective } from "@/lib/types";
import { cn } from "@/lib/utils";

const ACTIONS: { directive: RewriteDirective; emoji: string; label: string }[] = [
  { directive: "improve", emoji: "✨", label: "Improve" },
  { directive: "make_viral", emoji: "🔥", label: "Make Viral" },
  { directive: "make_emotional", emoji: "❤️", label: "Make Emotional" },
  { directive: "increase_conversion", emoji: "🎯", label: "Increase Conversion" },
  { directive: "rewrite", emoji: "🧠", label: "Rewrite" },
];

export function AiActionChipRow({
  onAction,
  loadingDirective,
  disabled = false,
}: {
  onAction: (directive: RewriteDirective) => void;
  loadingDirective: RewriteDirective | null;
  disabled?: boolean;
}) {
  const anyLoading = loadingDirective !== null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {ACTIONS.map((action) => {
        const isLoading = loadingDirective === action.directive;
        return (
          <button
            key={action.directive}
            type="button"
            disabled={disabled || anyLoading}
            onClick={() => onAction(action.directive)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1 text-[11px] font-medium text-[var(--foreground)] transition-colors",
              "hover:border-[var(--accent)]/50 hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]",
              "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-[var(--border-strong)] disabled:hover:bg-[var(--surface-2)] disabled:hover:text-[var(--foreground)]"
            )}
          >
            {isLoading ? (
              <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-white/30 border-t-[var(--accent)]" />
            ) : (
              <span>{action.emoji}</span>
            )}
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
