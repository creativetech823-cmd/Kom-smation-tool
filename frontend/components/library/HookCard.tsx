"use client";

import { useState } from "react";
import type { Hook } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export function HookCard({
  hook,
  onToggleFavorite,
  onUse,
  onEdit,
  onGenerateScript,
}: {
  hook: Hook;
  onToggleFavorite: (id: string, next: boolean) => void;
  onUse?: (hook: Hook) => void;
  onEdit?: (hook: Hook) => void;
  onGenerateScript?: (hook: Hook) => void;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void navigator.clipboard.writeText(hook.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="accent">{hook.category}</Badge>
          <Badge tone="neutral">{hook.platform}</Badge>
          <Badge tone="neutral">{hook.tone}</Badge>
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          {onEdit && (
            <button
              type="button"
              onClick={() => onEdit(hook)}
              title="Edit hook"
              className="text-[11.5px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              Edit
            </button>
          )}
          <button
            type="button"
            onClick={() => onToggleFavorite(hook.id, !hook.is_favorite)}
            title="Favorite"
            className="text-[16px] text-[var(--foreground)]"
          >
            {hook.is_favorite ? "♥" : "♡"}
          </button>
        </div>
      </div>

      <p className="text-[13.5px] leading-relaxed text-[var(--foreground)]">&ldquo;{hook.text}&rdquo;</p>

      <div className="flex items-center justify-between gap-2 pt-1">
        <p className="text-[11px] text-[var(--muted)]">Used {hook.usage_count}x</p>
        <div className="flex items-center gap-2">
          {onGenerateScript && (
            <Button size="sm" onClick={() => onGenerateScript(hook)}>
              Generate Script
            </Button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
          >
            {copied ? "Copied" : "Copy"}
          </button>
          {onUse && (
            <Button size="sm" onClick={() => onUse(hook)}>
              Use in Script
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
