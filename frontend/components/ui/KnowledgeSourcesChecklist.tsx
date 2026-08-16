"use client";

import type { ReferenceKind, ReferenceMaterial } from "@/lib/types";

const DOC_KINDS: ReferenceKind[] = ["pdf", "docx", "pptx", "doc", "ppt", "txt", "csv", "xlsx", "zip"];
const LINK_KINDS: ReferenceKind[] = ["youtube", "google_drive", "dropbox", "notion"];

type RowState = "active" | "pending" | "absent";

function bucketState(materials: ReferenceMaterial[], kinds: ReferenceKind[]): RowState {
  const relevant = materials.filter((m) => kinds.includes(m.kind));
  if (relevant.length === 0) return "absent";
  return relevant.some((m) => m.analysis === "analyzed") ? "active" : "pending";
}

export function KnowledgeSourcesChecklist({
  hasDescription,
  urlState,
  referenceMaterials,
}: {
  hasDescription: boolean;
  urlState: RowState;
  referenceMaterials: ReferenceMaterial[];
}) {
  const allRows: { label: string; state: RowState }[] = [
    { label: "Product Description", state: hasDescription ? "active" : "absent" },
    { label: "Website", state: urlState },
    { label: "Documents", state: bucketState(referenceMaterials, DOC_KINDS) },
    { label: "Images", state: bucketState(referenceMaterials, ["image"]) },
    { label: "Video", state: bucketState(referenceMaterials, ["video"]) },
    { label: "Additional Links", state: bucketState(referenceMaterials, LINK_KINDS) },
  ];
  const rows = allRows.filter((r) => r.label === "Product Description" || r.label === "Website" || r.state !== "absent");

  if (rows.length <= 2 && rows.every((r) => r.state === "absent")) return null;

  return (
    <div>
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">Knowledge Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {rows.map((row) => (
          <span
            key={row.label}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
              row.state === "active"
                ? "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]"
                : row.state === "pending"
                ? "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]"
                : "border-[var(--border)] bg-[var(--foreground)]/[0.02] text-[var(--muted)]"
            }`}
          >
            {row.state === "active" ? "✓" : row.state === "pending" ? "⋯" : "○"} {row.label}
          </span>
        ))}
      </div>
    </div>
  );
}
