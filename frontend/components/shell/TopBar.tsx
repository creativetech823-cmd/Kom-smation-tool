"use client";

import Link from "next/link";
import { useActiveProject } from "@/lib/project-context";
import { ThemeToggle } from "@/components/shell/ThemeToggle";

export function TopBar() {
  const { activeProjectId, activeProjectName } = useActiveProject();

  return (
    <header className="flex items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--on-accent)]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z" fill="currentColor" />
          </svg>
        </div>
        <div>
          <h1 className="text-[16px] font-semibold tracking-tight">Content Factory</h1>
          <p className="text-[12px] text-[var(--muted)]">Human-in-the-loop pipeline review</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {activeProjectId && activeProjectName && (
          <Link
            href={`/projects/${activeProjectId}`}
            className="flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-[12px] font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent-soft)]/80"
          >
            <IconFolder />
            <span className="max-w-[160px] truncate">{activeProjectName}</span>
          </Link>
        )}
        <ThemeToggle />
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--border-strong)] bg-[var(--surface-3)] text-[12px] font-semibold text-[var(--foreground)]">
          U
        </div>
      </div>
    </header>
  );
}

function IconFolder() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
      <path
        d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
