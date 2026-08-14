"use client";

const OPTIONS: { value: string; label: string }[] = [
  { value: "15s", label: "15s" },
  { value: "20s", label: "20s" },
  { value: "30s", label: "30s" },
  { value: "45s", label: "45s" },
  { value: "60s", label: "60s" },
  { value: "90s", label: "90s" },
  { value: "120s", label: "120s" },
];

export function DurationSelector({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (duration: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex flex-wrap items-center gap-1 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] p-1">
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
