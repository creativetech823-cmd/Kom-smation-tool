"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { listHooks, toggleHookFavorite, ApiError } from "@/lib/api";
import type { Hook } from "@/lib/types";
import { HookCard } from "@/components/library/HookCard";
import { LibraryFilterBar } from "@/components/library/LibraryFilterBar";

const CATEGORIES = [
  "Curiosity",
  "Problem",
  "Question",
  "Educational",
  "Storytelling",
  "Controversial",
  "FOMO",
  "Product",
  "Emotional",
  "Trending",
];

const PAGE_SIZE = 12;

export function HookPickerModal({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (hook: Hook) => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    listHooks({ q: search || undefined, category: category ?? undefined, page, page_size: PAGE_SIZE })
      .then((result) => {
        setHooks(result.items);
        setTotal(result.total);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load hooks."))
      .finally(() => setLoading(false));
  }, [open, search, category, page]);

  function handleToggleFavorite(id: string, next: boolean) {
    setHooks((prev) => prev.map((h) => (h.id === id ? { ...h, is_favorite: next } : h)));
    void toggleHookFavorite(id, next).catch(() => {});
  }

  if (!open) return null;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      >
        <motion.div
          initial={{ scale: 0.97, opacity: 0, y: 8 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.97, opacity: 0, y: 8 }}
          transition={{ duration: 0.16 }}
          onClick={(e) => e.stopPropagation()}
          className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[var(--border-strong)] bg-[var(--surface)] shadow-[0_40px_100px_-20px_var(--shadow-color)]"
        >
          <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
            <div>
              <h3 className="text-[14px] font-semibold text-[var(--foreground)]">Choose a Hook</h3>
              <p className="text-[12px] text-[var(--muted)]">{total} hooks available</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-[13px] text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              ✕
            </button>
          </div>

          <div className="border-b border-[var(--border)] px-5 py-3">
            <LibraryFilterBar
              search={search}
              onSearchChange={(v) => {
                setSearch(v);
                setPage(1);
              }}
              searchPlaceholder="Search hooks…"
              chips={CATEGORIES}
              activeChip={category}
              onChipChange={(c) => {
                setCategory(c);
                setPage(1);
              }}
            />
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4">
            {error && <p className="mb-3 text-[13px] text-[var(--danger)]">{error}</p>}
            {loading ? (
              <p className="py-10 text-center text-[13px] text-[var(--muted)]">Loading hooks…</p>
            ) : hooks.length === 0 ? (
              <p className="py-10 text-center text-[13px] text-[var(--muted)]">No hooks found. Try another search or category.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {hooks.map((hook) => (
                  <HookCard key={hook.id} hook={hook} onToggleFavorite={handleToggleFavorite} onUse={onSelect} />
                ))}
              </div>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 border-t border-[var(--border)] px-5 py-3">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] text-[var(--foreground)] disabled:opacity-40"
              >
                Prev
              </button>
              <span className="text-[12px] text-[var(--muted)]">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] text-[var(--foreground)] disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
