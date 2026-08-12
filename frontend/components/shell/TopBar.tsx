"use client";

import { Button } from "@/components/ui/Button";

export function TopBar({
  onSaveDraft,
  draftAvailable,
  onRestoreDraft,
}: {
  onSaveDraft: () => void;
  draftAvailable: boolean;
  onRestoreDraft: () => void;
}) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)]/60 px-6 py-4 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] text-white shadow-lg shadow-[var(--accent)]/20">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z" fill="white" />
          </svg>
        </div>
        <div>
          <h1 className="text-[16px] font-semibold tracking-tight">Content Factory</h1>
          <p className="text-[12px] text-[var(--muted)]">Human-in-the-loop pipeline review</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {draftAvailable && (
          <button
            type="button"
            onClick={onRestoreDraft}
            className="rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-[12px] font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent-soft)]/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
          >
            Draft available — Restore
          </button>
        )}
        <Button variant="secondary" size="sm" onClick={onSaveDraft}>
          <IconSave /> Save Draft
        </Button>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--border-strong)] bg-gradient-to-br from-[var(--surface-2)] to-[var(--surface-3)] text-[12px] font-semibold text-[var(--foreground)]">
          U
        </div>
      </div>
    </header>
  );
}

function IconSave() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path d="M5 4h11l3 3v13H5V4z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M8 4v6h8V4M8 14h8v6H8v-6z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}
