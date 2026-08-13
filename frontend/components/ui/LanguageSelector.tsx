"use client";

import type { ScriptLanguage } from "@/lib/types";

const OPTIONS: { value: ScriptLanguage; label: string }[] = [
  { value: "english", label: "English" },
  { value: "hindi", label: "हिंदी" },
  { value: "hinglish", label: "Hinglish" },
];

export function LanguageSelector({
  value,
  onChange,
  disabled,
}: {
  value: ScriptLanguage;
  onChange: (language: ScriptLanguage) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] p-1">
      {OPTIONS.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={`rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              active ? "bg-[var(--accent)] text-white" : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
