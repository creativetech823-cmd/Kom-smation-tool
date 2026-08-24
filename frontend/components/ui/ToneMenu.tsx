"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { TONE_OPTIONS } from "@/lib/contentFormats";

export function ToneMenu({
  currentTone,
  onSelect,
  loading,
}: {
  currentTone?: string;
  onSelect: (tone: string) => void;
  loading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <Button variant="secondary" size="sm" loading={loading} onClick={() => setOpen((o) => !o)}>
        {!loading && "\u{1F3AD} "}
        {currentTone || "Change Tone"} {!loading && <span className="ml-0.5">▾</span>}
      </Button>

      {open && (
        <div className="absolute right-0 top-full z-20 mt-1.5 w-48 overflow-hidden rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] shadow-[0_20px_40px_-20px_var(--shadow-color)]">
          {TONE_OPTIONS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => {
                setOpen(false);
                onSelect(t.value);
              }}
              className={`block w-full border-b border-[var(--border)] px-3.5 py-2 text-left text-[12.5px] font-medium transition-colors last:border-b-0 hover:bg-[var(--foreground)]/[0.06] ${
                currentTone === t.value ? "text-[var(--accent)]" : "text-[var(--foreground)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
