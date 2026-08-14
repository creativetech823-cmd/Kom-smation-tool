"use client";

import { useState, type ReactNode } from "react";
import { AiRewriteMenu } from "./AiRewriteMenu";
import type { RewriteDirective, ScriptLanguage } from "@/lib/types";
import { cn } from "@/lib/utils";

export function EditableLine({
  text,
  onSave,
  className,
  textClassName,
  renderText,
  onApplyDirective,
  onGenerateAlternatives,
  onSelectAlternative,
  onTranslate,
  currentLanguage,
  aiLoading,
  glow,
}: {
  text: string;
  onSave: (newText: string) => void;
  className?: string;
  textClassName?: string;
  renderText?: (text: string) => ReactNode;
  onApplyDirective?: (directive: RewriteDirective) => void;
  onGenerateAlternatives?: () => Promise<string[]>;
  onSelectAlternative?: (text: string) => void;
  onTranslate?: (language: ScriptLanguage) => void;
  currentLanguage?: ScriptLanguage;
  aiLoading?: boolean;
  glow?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);

  function startEdit() {
    setDraft(text);
    setEditing(true);
  }
  function save() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== text) onSave(trimmed);
    setEditing(false);
  }
  function cancel() {
    setDraft(text);
    setEditing(false);
  }

  if (editing) {
    return (
      <div className={cn("space-y-1.5", className)}>
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          className="w-full resize-none rounded-lg border border-[var(--accent)]/40 bg-[var(--surface)] px-2.5 py-1.5 text-[14px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
        />
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={save}
            className="rounded-md bg-[var(--accent)] px-2.5 py-1 text-[11px] font-medium text-white hover:brightness-110"
          >
            Save
          </button>
          <button
            type="button"
            onClick={cancel}
            className="rounded-md border border-[var(--border-strong)] px-2.5 py-1 text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  const hasAiMenu = onApplyDirective || onGenerateAlternatives || onTranslate;

  return (
    <div
      className={cn(
        "group/line flex items-start gap-1.5 rounded-md transition-shadow",
        glow && "animate-glow",
        className
      )}
    >
      <span className={cn("min-w-0 flex-1", textClassName)}>{renderText ? renderText(text) : text}</span>
      <span className="ml-1 flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover/line:opacity-100 group-focus-within/line:opacity-100">
        <button
          type="button"
          onClick={startEdit}
          title="Edit"
          className="rounded p-0.5 text-[12px] hover:bg-white/[0.08]"
        >
          ✏️
        </button>
        {hasAiMenu && (
          <AiRewriteMenu
            onApplyDirective={onApplyDirective}
            onGenerateAlternatives={onGenerateAlternatives}
            onSelectAlternative={onSelectAlternative}
            onTranslate={onTranslate}
            currentLanguage={currentLanguage}
            loading={aiLoading}
          />
        )}
      </span>
    </div>
  );
}
