"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { ScriptRegenerateScope } from "@/lib/types";

const OPTIONS: { scope: ScriptRegenerateScope; label: string; hint: string }[] = [
  { scope: "full", label: "Entire Script", hint: "Regenerate everything from scratch" },
  { scope: "hook", label: "Hook Only", hint: "Fresh opening, rest stays the same" },
  { scope: "cta", label: "CTA Only", hint: "Fresh close, rest stays the same" },
  { scope: "science", label: "Science Section", hint: "Rewrite the why-this-happens beat" },
  { scope: "story", label: "Story Section", hint: "Rewrite the narrative/emotional beat" },
  { scope: "product_explanation", label: "Product Explanation", hint: "Rewrite product intro + ingredients" },
  { scope: "emotional_tone", label: "Emotional Tone", hint: "Push every line's feeling harder" },
  { scope: "length", label: "Make It Longer", hint: "Expand every beat with more depth" },
];

export function RegenerateMenu({
  onSelect,
  loading,
}: {
  onSelect: (scope: ScriptRegenerateScope) => void;
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
      <Button
        variant="secondary"
        size="sm"
        loading={loading}
        onClick={() => setOpen((o) => !o)}
      >
        {!loading && <IconRefresh />} Regenerate {!loading && <span className="ml-0.5">▾</span>}
      </Button>

      {open && (
        <div className="absolute right-0 top-full z-20 mt-1.5 w-64 overflow-hidden rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] shadow-[0_20px_40px_-20px_rgba(0,0,0,0.7)]">
          {OPTIONS.map((opt) => (
            <button
              key={opt.scope}
              type="button"
              onClick={() => {
                setOpen(false);
                onSelect(opt.scope);
              }}
              className="block w-full border-b border-[var(--border)] px-3.5 py-2.5 text-left transition-colors last:border-b-0 hover:bg-white/[0.06]"
            >
              <div className="text-[12.5px] font-medium text-[var(--foreground)]">{opt.label}</div>
              <div className="text-[11px] text-[var(--muted)]">{opt.hint}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function IconRefresh() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 4v6h6M20 20v-6h-6M4.5 15a8 8 0 0014.9 2.3M19.5 9A8 8 0 004.6 6.7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
