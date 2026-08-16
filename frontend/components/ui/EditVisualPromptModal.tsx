"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { VisualConcept, VisualConceptStyleParams } from "@/lib/types";

const FIELDS: { key: keyof VisualConceptStyleParams; label: string }[] = [
  { key: "style", label: "Style" },
  { key: "lighting", label: "Lighting" },
  { key: "camera", label: "Camera" },
  { key: "mood", label: "Mood" },
  { key: "background", label: "Background" },
  { key: "characters", label: "Characters" },
  { key: "composition", label: "Composition" },
  { key: "brand_colors", label: "Brand Colors" },
  { key: "logo_placement", label: "Logo Placement" },
  { key: "product_position", label: "Product Position" },
];

export function EditVisualPromptModal({
  concept,
  onRegenerate,
  onClose,
  loading,
}: {
  concept: VisualConcept;
  onRegenerate: (patch: { prompt: string; style_params: VisualConceptStyleParams }) => void;
  onClose: () => void;
  loading: boolean;
}) {
  const [prompt, setPrompt] = useState(concept.prompt);
  const [styleParams, setStyleParams] = useState<VisualConceptStyleParams>(concept.style_params);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  function set(key: keyof VisualConceptStyleParams, value: string) {
    setStyleParams((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      >
        <motion.div
          initial={{ scale: 0.97, opacity: 0, y: 8 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.97, opacity: 0, y: 8 }}
          transition={{ duration: 0.16 }}
          onClick={(e) => e.stopPropagation()}
          className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-[var(--border-strong)] bg-[var(--surface)] p-5 shadow-[0_40px_100px_-20px_var(--shadow-color)]"
        >
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-[var(--foreground)]">Edit Prompt — {concept.scene_title}</h3>
            <button type="button" onClick={onClose} className="text-[13px] text-[var(--muted)] hover:text-[var(--foreground)]">
              ✕
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Prompt</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={5}
                className="w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] leading-relaxed text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Negative Prompt</label>
              <textarea
                value={styleParams.negative_prompt}
                onChange={(e) => set("negative_prompt", e.target.value)}
                rows={2}
                className="w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] leading-relaxed text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
              />
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              {FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">{f.label}</label>
                  <input
                    value={styleParams[f.key]}
                    onChange={(e) => set(f.key, e.target.value)}
                    className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12.5px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => onRegenerate({ prompt, style_params: styleParams })}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3.5 py-2 text-[12.5px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:opacity-50"
            >
              {loading && <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" />}
              Regenerate with these changes
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[var(--border-strong)] px-3.5 py-2 text-[12.5px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
