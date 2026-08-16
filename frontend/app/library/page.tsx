"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { listAssets, listProjects, updateAsset } from "@/lib/api";
import type { ContentAsset, ContentAssetType, Project } from "@/lib/types";
import { EmptyState } from "@/components/library/EmptyState";
import { ContentAssetCard } from "@/components/library/ContentAssetCard";
import { ScriptAssetCard } from "@/components/library/ScriptAssetCard";
import { LibraryFilterBar } from "@/components/library/LibraryFilterBar";
import { useToast } from "@/components/shell/ToastProvider";

const TABS: { key: ContentAssetType | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "script", label: "Scripts" },
  { key: "image", label: "Images" },
  { key: "video", label: "Videos" },
  { key: "voiceover", label: "Voiceovers" },
  { key: "render", label: "Renders" },
];

function LibraryPageInner() {
  const { showToast } = useToast();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");
  const highlightedRef = useRef<HTMLDivElement | null>(null);

  const [tab, setTab] = useState<ContentAssetType | "all">("all");
  const [search, setSearch] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [sort, setSort] = useState<"recent" | "oldest">("recent");
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void listProjects().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    listAssets({
      asset_type: tab === "all" ? undefined : tab,
      q: search || undefined,
      favorite: favoriteOnly || undefined,
      sort,
      project_id: projectId || undefined,
    })
      .then(setAssets)
      .catch(() => showToast("Couldn't load your content library.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, search, favoriteOnly, sort, projectId]);

  useEffect(() => {
    if (highlightId && highlightedRef.current) {
      highlightedRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightId, assets]);

  function handleToggleFavorite(id: string, next: boolean) {
    setAssets((prev) => prev.map((a) => (a.id === id ? { ...a, is_favorite: next } : a)));
    void updateAsset(id, { is_favorite: next }).catch(() => {});
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Content Library</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          Everything generated from the Content Pipeline, automatically saved here.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
              tab === t.key
                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <LibraryFilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by title or product…"
        favoriteOnly={favoriteOnly}
        onFavoriteOnlyChange={setFavoriteOnly}
        sort={sort}
        onSortChange={setSort}
        right={
          projects.length > 0 ? (
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
            >
              <option value="">All projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          ) : undefined
        }
      />

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading…</p>
      ) : assets.length === 0 ? (
        <EmptyState
          title="Your content will appear here"
          message="Generate your first script, image, or video from the Content Pipeline."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assets.map((asset) => {
            const isHighlighted = asset.id === highlightId;
            const wrapperRef = isHighlighted ? highlightedRef : undefined;
            return (
              <div key={asset.id} ref={wrapperRef}>
                {asset.asset_type === "script" ? (
                  <ScriptAssetCard asset={asset} onToggleFavorite={handleToggleFavorite} highlighted={isHighlighted} />
                ) : (
                  <ContentAssetCard asset={asset} onToggleFavorite={handleToggleFavorite} highlighted={isHighlighted} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={null}>
      <LibraryPageInner />
    </Suspense>
  );
}
