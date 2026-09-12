"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Hook } from "@/lib/types";
import { HOOK_CATEGORIES, HOOK_PLATFORMS, HOOK_TONES } from "@/lib/constants";

export type HookEditPatch = { text: string; category: string; platform: string; tone: string };

export function EditHookModal({
  hook,
  onSave,
  onClose,
  saving,
}: {
  hook: Hook;
  onSave: (patch: HookEditPatch) => void;
  onClose: () => void;
  saving?: boolean;
}) {
  const [text, setText] = useState(hook.text);
  const [category, setCategory] = useState(hook.category);
  const [platform, setPlatform] = useState(hook.platform);
  const [tone, setTone] = useState(hook.tone);

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

  const trimmed = text.trim();
  const canSave = trimmed.length > 0 && !saving;

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
            <h3 className="text-[14px] font-semibold text-[var(--foreground)]">Edit Hook</h3>
            <button type="button" onClick={onClose} className="text-[13px] text-[var(--muted)] hover:text-[var(--foreground)]">
              ✕
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Hook Text</label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={3}
                className="w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] leading-relaxed text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
              />
              {trimmed.length === 0 && (
                <p className="mt-1 text-[11px] text-[var(--danger)]">Hook text can&apos;t be empty.</p>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12.5px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                >
                  {HOOK_CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Platform</label>
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12.5px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                >
                  {HOOK_PLATFORMS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Tone</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12.5px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
                >
                  {HOOK_TONES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              disabled={!canSave}
              onClick={() => onSave({ text: trimmed, category, platform, tone })}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3.5 py-2 text-[12.5px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:opacity-50"
            >
              {saving && (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" />
              )}
              Save Changes
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
