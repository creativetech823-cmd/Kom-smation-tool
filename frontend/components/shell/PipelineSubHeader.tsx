"use client";

export type SaveStatus = "idle" | "saving" | "saved" | "error";

const STATUS_LABEL: Record<Exclude<SaveStatus, "idle">, string> = {
  saving: "Saving…",
  saved: "Saved ✓",
  error: "Unable to save",
};

export function PipelineSubHeader({ saveStatus }: { saveStatus: SaveStatus }) {
  if (saveStatus === "idle") return <span />;
  return (
    <div className="flex items-center justify-end gap-3">
      <span
        className={`text-[12px] font-medium ${
          saveStatus === "error" ? "text-[var(--danger)]" : "text-[var(--muted)]"
        }`}
      >
        {STATUS_LABEL[saveStatus]}
      </span>
    </div>
  );
}
