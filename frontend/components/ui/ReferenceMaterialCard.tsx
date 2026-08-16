"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { StatusPill } from "@/components/ui/StatusPill";
import { referenceFileUrl } from "@/lib/api";
import type { ReferenceKind, ReferenceMaterial } from "@/lib/types";

const KIND_ICON: Record<ReferenceKind, string> = {
  pdf: "\u{1F4C4}",
  docx: "\u{1F4DD}",
  pptx: "\u{1F4CA}",
  doc: "\u{1F4C4}",
  ppt: "\u{1F4CA}",
  txt: "\u{1F4C3}",
  csv: "\u{1F4C8}",
  xlsx: "\u{1F4CA}",
  zip: "\u{1F5DC}️",
  image: "\u{1F5BC}️",
  video: "\u{1F3AC}",
  audio: "\u{1F3B5}",
  website: "\u{1F310}",
  google_drive: "\u{1F5C2}️",
  youtube: "▶️",
  dropbox: "\u{1F4E6}",
  notion: "\u{1F4D3}",
};

const KIND_LABEL: Record<ReferenceKind, string> = {
  pdf: "PDF",
  docx: "Word doc",
  pptx: "Slides",
  doc: "Word doc (legacy)",
  ppt: "Slides (legacy)",
  txt: "Text",
  csv: "CSV",
  xlsx: "Spreadsheet",
  zip: "ZIP archive",
  image: "Image",
  video: "Video",
  audio: "Audio",
  website: "Website",
  google_drive: "Google Drive",
  youtube: "YouTube",
  dropbox: "Dropbox",
  notion: "Notion",
};

export function ReferenceMaterialCard({
  material,
  uploading,
  onRemove,
}: {
  material: ReferenceMaterial;
  uploading?: boolean;
  onRemove: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const name = material.filename || material.source_url || "Untitled";
  const fileUrl = material.stored_path ? referenceFileUrl(material.stored_path) : null;

  const status =
    material.analysis === "analyzed"
      ? ("pass" as const)
      : material.analysis === "failed"
      ? ("review" as const)
      : ("warning" as const);

  const statusLabel = uploading
    ? "Reading..."
    : material.analysis === "analyzed"
    ? "Analyzed"
    : material.analysis === "coming_soon"
    ? "Coming soon"
    : material.analysis === "not_supported"
    ? "Not supported"
    : "Failed";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      className="hover-glow glass-card rounded-xl border border-[var(--border)] px-3.5 py-3"
    >
      <div className="flex items-start gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--foreground)]/[0.05] text-[15px]">
          {KIND_ICON[material.kind]}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-[var(--foreground)]" title={name}>
            {name}
          </p>
          <p className="mt-0.5 text-[11px] text-[var(--muted)]">{KIND_LABEL[material.kind]}</p>
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--foreground)]/[0.06] hover:text-[var(--foreground)]"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <StatusPill status={uploading ? "review" : status}>{statusLabel}</StatusPill>

        {!uploading && (material.extracted_text || fileUrl) && (
          <div className="flex items-center gap-2 text-[11px]">
            {material.kind === "image" && fileUrl && (
              <a href={fileUrl} target="_blank" rel="noreferrer" className="font-medium text-[var(--accent-2)] hover:underline">
                Preview
              </a>
            )}
            {(material.kind === "video" || material.kind === "audio" || material.kind === "pdf") && fileUrl && (
              <a href={fileUrl} target="_blank" rel="noreferrer" className="font-medium text-[var(--accent-2)] hover:underline">
                Open
              </a>
            )}
            {material.extracted_text && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="font-medium text-[var(--accent-2)] hover:underline"
              >
                {expanded ? "Hide text" : "View text"}
              </button>
            )}
          </div>
        )}
      </div>

      {material.kind === "image" && fileUrl && !uploading && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={fileUrl} alt={name} className="mt-2.5 h-24 w-full rounded-lg object-cover" />
      )}

      {material.note && !uploading && (
        <p className="mt-2 text-[11px] leading-snug text-[var(--warning)]">{material.note}</p>
      )}

      {expanded && material.extracted_text && (
        <div className="mt-2.5 max-h-32 overflow-y-auto rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[11px] leading-snug text-[var(--muted)]">
          {material.extracted_text}
          {material.truncated && <span className="italic"> (trimmed for length)</span>}
        </div>
      )}
    </motion.div>
  );
}
