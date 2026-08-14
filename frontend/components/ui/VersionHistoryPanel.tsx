"use client";

import { useEffect, useRef, useState } from "react";
import { flattenScript, type GeneratedScript } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ScriptVersion = { script: GeneratedScript; label: string; ts: number };

export function VersionHistoryPanel({
  entries,
  currentIndex,
  onRestore,
}: {
  entries: ScriptVersion[];
  currentIndex: number;
  onRestore: (index: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [compareA, setCompareA] = useState<number | null>(null);
  const [compareB, setCompareB] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  function toggleCompare(i: number) {
    if (compareA === i) return setCompareA(null);
    if (compareB === i) return setCompareB(null);
    if (compareA === null) return setCompareA(i);
    if (compareB === null) return setCompareB(i);
    setCompareA(i);
    setCompareB(null);
  }

  const diffLines =
    compareA !== null && compareB !== null
      ? (() => {
          const a = flattenScript(entries[compareA].script);
          const b = flattenScript(entries[compareB].script);
          return b.map((line) => {
            const match = a.find((l) => l.id === line.id);
            return { id: line.id, text: line.text, changed: !match || match.text !== line.text };
          });
        })()
      : null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12px] font-medium text-[var(--foreground)] hover:bg-white/[0.06]"
      >
        🕓 History ({entries.length})
      </button>

      {open && (
        <div className="absolute right-0 top-full z-20 mt-1.5 max-h-96 w-80 overflow-y-auto rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] shadow-[0_20px_40px_-20px_rgba(0,0,0,0.7)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
            <p className="text-[11px] font-medium text-[var(--muted)]">
              {compareA !== null || compareB !== null ? "Click two versions to compare" : "Click a version to restore it"}
            </p>
          </div>

          {entries
            .map((e, i) => ({ e, i }))
            .slice()
            .reverse()
            .map(({ e, i }) => {
              const active = i === currentIndex;
              const selected = i === compareA || i === compareB;
              return (
                <div
                  key={i}
                  className={cn(
                    "flex items-center gap-2 border-b border-[var(--border)] px-3 py-2 last:border-b-0",
                    active && "bg-white/[0.04]",
                    selected && "bg-[var(--accent-soft)]"
                  )}
                >
                  <button type="button" onClick={() => toggleCompare(i)} title="Select for compare" className="text-[13px]">
                    {selected ? "☑" : "☐"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onRestore(i);
                      setOpen(false);
                    }}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="truncate text-[12px] font-medium text-[var(--foreground)]">{e.label}</div>
                    <div className="text-[10.5px] text-[var(--muted)]">
                      {new Date(e.ts).toLocaleTimeString()}
                      {active ? " — current" : ""}
                    </div>
                  </button>
                </div>
              );
            })}

          {diffLines && (
            <div className="space-y-1.5 border-t border-[var(--border-strong)] bg-black/20 p-3">
              <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                Changed lines ({entries[compareA!].label} → {entries[compareB!].label})
              </p>
              {diffLines.filter((l) => l.changed).length === 0 && (
                <p className="text-[11.5px] text-[var(--muted)]">No differences.</p>
              )}
              {diffLines
                .filter((l) => l.changed)
                .map((l) => (
                  <p key={l.id} className="rounded-md border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-2 py-1 text-[11.5px] text-[var(--foreground)]">
                    {l.text}
                  </p>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
