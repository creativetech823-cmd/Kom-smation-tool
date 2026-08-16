"use client";

import { useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { ReferenceMaterialCard } from "@/components/ui/ReferenceMaterialCard";
import type { ReferenceMaterial } from "@/lib/types";

const UPLOAD_SHORTCUTS: { label: string; icon: string; accept: string }[] = [
  { label: "Upload PDF", icon: "\u{1F4C4}", accept: ".pdf" },
  { label: "Upload Video", icon: "\u{1F3AC}", accept: ".mp4,.mov,.webm,.avi,.mkv" },
  { label: "Upload Images", icon: "\u{1F5BC}\u{FE0F}", accept: "image/*" },
];

const ACCEPTED_EXTENSIONS =
  ".pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,.xlsx,.zip,.mp4,.mov,.webm,.avi,.mkv,.mp3,.wav,.m4a,.aac,.ogg,.flac,image/*";

export function ReferenceMaterialsPanel({
  materials,
  uploadingIds,
  onAddFiles,
  onAddUrl,
  onRemove,
}: {
  materials: ReferenceMaterial[];
  uploadingIds: Set<string>;
  onAddFiles: (files: FileList | File[]) => void;
  onAddUrl: (url: string) => void;
  onRemove: (id: string) => void;
}) {
  const [linkInputOpen, setLinkInputOpen] = useState(false);
  const [linkValue, setLinkValue] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const shortcutInputRef = useRef<HTMLInputElement>(null);

  function openPicker(accept: string) {
    if (shortcutInputRef.current) {
      shortcutInputRef.current.accept = accept;
      shortcutInputRef.current.click();
    }
  }

  function handleLinkSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!linkValue.trim()) return;
    onAddUrl(linkValue.trim());
    setLinkValue("");
    setLinkInputOpen(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-[var(--muted)]">Reference Materials</p>
        <p className="text-[11px] text-[var(--muted)]">Optional — sharpens the AI&apos;s understanding</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {UPLOAD_SHORTCUTS.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => openPicker(s.accept)}
            className="hover-glow inline-flex items-center gap-1.5 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] font-medium text-[var(--foreground)]"
          >
            <span>{s.icon}</span>
            {s.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setLinkInputOpen((v) => !v)}
          className="hover-glow inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-[12px] font-medium text-[var(--accent)]"
        >
          <span>{"\u{1F517}"}</span>
          Add Reference Link
        </button>
      </div>

      {linkInputOpen && (
        <form onSubmit={handleLinkSubmit} className="flex gap-2">
          <input
            autoFocus
            value={linkValue}
            onChange={(e) => setLinkValue(e.target.value)}
            placeholder="https://... (website, YouTube, Google Drive, Dropbox, Notion)"
            className="h-9 flex-1 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
          />
          <button
            type="submit"
            disabled={!linkValue.trim()}
            className="h-9 rounded-lg bg-[var(--accent)] px-3 text-[13px] font-medium text-[var(--on-accent)] disabled:opacity-40"
          >
            Add
          </button>
        </form>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files.length) onAddFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`glass-card cursor-pointer rounded-xl border border-dashed px-4 py-5 text-center transition-colors ${
          dragActive ? "border-[var(--accent)] bg-[var(--accent-soft)]" : "border-[var(--border-strong)]"
        }`}
      >
        <p className="text-[12px] text-[var(--muted)]">
          Drag &amp; drop files here, or <span className="text-[var(--accent-2)]">click to browse</span>
        </p>
        <p className="mt-1 text-[10px] text-[var(--muted)]">
          PDF, DOC(X), PPT(X), TXT, CSV, XLSX, ZIP, images, video, audio
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onAddFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={shortcutInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onAddFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {materials.length > 0 && (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <AnimatePresence initial={false}>
            {materials.map((m) => (
              <ReferenceMaterialCard
                key={m.id}
                material={m}
                uploading={uploadingIds.has(m.id)}
                onRemove={() => onRemove(m.id)}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
