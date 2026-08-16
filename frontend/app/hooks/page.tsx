"use client";

import { useEffect, useState } from "react";
import { listHooks, toggleHookFavorite } from "@/lib/api";
import type { Hook } from "@/lib/types";
import { EmptyState } from "@/components/library/EmptyState";
import { HookCard } from "@/components/library/HookCard";
import { LibraryFilterBar } from "@/components/library/LibraryFilterBar";
import { useToast } from "@/components/shell/ToastProvider";

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

const PLATFORMS = ["Instagram Reels", "TikTok", "YouTube Shorts", "Facebook", "General"];
const TONES = ["Bold", "Playful", "Serious", "Empathetic", "Urgent"];
const PAGE_SIZE = 24;

export default function HooksPage() {
  const { showToast } = useToast();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [platform, setPlatform] = useState("");
  const [tone, setTone] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    listHooks({
      q: search || undefined,
      category: category ?? undefined,
      platform: platform || undefined,
      tone: tone || undefined,
      favorite: favoriteOnly || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((result) => {
        setHooks(result.items);
        setTotal(result.total);
      })
      .catch(() => showToast("Couldn't load hooks.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category, platform, tone, favoriteOnly, page]);

  function handleToggleFavorite(id: string, next: boolean) {
    setHooks((prev) => prev.map((h) => (h.id === id ? { ...h, is_favorite: next } : h)));
    void toggleHookFavorite(id, next).catch(() => {});
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Hooks Library</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          {total > 0 ? `${total} hooks` : "Hooks"} to open a script with — search, filter, favorite, and use them
          straight from the Content Pipeline.
        </p>
      </div>

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
        favoriteOnly={favoriteOnly}
        onFavoriteOnlyChange={(v) => {
          setFavoriteOnly(v);
          setPage(1);
        }}
        right={
          <>
            <select
              value={platform}
              onChange={(e) => {
                setPlatform(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
            >
              <option value="">All platforms</option>
              {PLATFORMS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <select
              value={tone}
              onChange={(e) => {
                setTone(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
            >
              <option value="">All tones</option>
              {TONES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </>
        }
      />

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading hooks…</p>
      ) : hooks.length === 0 ? (
        <EmptyState title="No hooks found" message="Try another search or category." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {hooks.map((hook) => (
              <HookCard key={hook.id} hook={hook} onToggleFavorite={handleToggleFavorite} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
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
        </>
      )}
    </div>
  );
}
