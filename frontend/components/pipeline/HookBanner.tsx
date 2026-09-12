"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

export function HookBanner({
  text,
  onChangeText,
  onChooseHook,
}: {
  text: string;
  onChangeText: (next: string) => void;
  onChooseHook: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);

  if (editing) {
    return (
      <div className="mb-4 flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
        <p className="text-[12px] font-medium text-[var(--muted)]">Your Hook</p>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          autoFocus
          className="w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[13px] leading-relaxed text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={draft.trim().length === 0}
            onClick={() => {
              onChangeText(draft.trim());
              setEditing(false);
            }}
          >
            Save
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setDraft(text);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
      <div className="flex min-w-0 items-center gap-2">
        <p className="shrink-0 text-[12px] font-medium text-[var(--muted)]">Your Hook</p>
        <span className="truncate text-[12.5px] text-[var(--foreground)]">&ldquo;{text}&rdquo;</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setDraft(text);
            setEditing(true);
          }}
        >
          Edit Hook
        </Button>
        <Button variant="secondary" size="sm" onClick={onChooseHook}>
          Change Hook
        </Button>
      </div>
    </div>
  );
}
