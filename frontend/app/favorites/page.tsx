"use client";

import { useEffect, useState } from "react";
import { listAssets, listHooks, listTemplates, toggleHookFavorite, updateAsset, updateTemplate } from "@/lib/api";
import type { ContentAsset, Hook, Template } from "@/lib/types";
import { EmptyState } from "@/components/library/EmptyState";
import { ContentAssetCard } from "@/components/library/ContentAssetCard";
import { ScriptAssetCard } from "@/components/library/ScriptAssetCard";
import { HookCard } from "@/components/library/HookCard";
import { TemplateCard } from "@/components/library/TemplateCard";
import { useToast } from "@/components/shell/ToastProvider";

type TabKey = "all" | "script" | "hook" | "image" | "video" | "template" | "voiceover";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "script", label: "Scripts" },
  { key: "hook", label: "Hooks" },
  { key: "image", label: "Images" },
  { key: "video", label: "Videos" },
  { key: "template", label: "Templates" },
  { key: "voiceover", label: "Voiceovers" },
];

export default function FavoritesPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<TabKey>("all");
  const [loading, setLoading] = useState(true);
  const [scripts, setScripts] = useState<ContentAsset[]>([]);
  const [images, setImages] = useState<ContentAsset[]>([]);
  const [videos, setVideos] = useState<ContentAsset[]>([]);
  const [voiceovers, setVoiceovers] = useState<ContentAsset[]>([]);
  const [renders, setRenders] = useState<ContentAsset[]>([]);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    Promise.all([
      listAssets({ asset_type: "script", favorite: true }),
      listAssets({ asset_type: "image", favorite: true }),
      listAssets({ asset_type: "video", favorite: true }),
      listAssets({ asset_type: "voiceover", favorite: true }),
      listAssets({ asset_type: "render", favorite: true }),
      listHooks({ favorite: true, page_size: 200 }),
      listTemplates({ favorite: true }),
    ])
      .then(([s, i, v, vo, r, h, t]) => {
        setScripts(s);
        setImages(i);
        setVideos(v);
        setVoiceovers(vo);
        setRenders(r);
        setHooks(h.items);
        setTemplates(t);
      })
      .catch(() => showToast("Couldn't load favorites.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAssetFavorite(setter: React.Dispatch<React.SetStateAction<ContentAsset[]>>) {
    return (id: string, next: boolean) => {
      if (!next) setter((prev) => prev.filter((a) => a.id !== id));
      void updateAsset(id, { is_favorite: next }).catch(() => {});
    };
  }

  function handleHookFavorite(id: string, next: boolean) {
    if (!next) setHooks((prev) => prev.filter((h) => h.id !== id));
    void toggleHookFavorite(id, next).catch(() => {});
  }

  function handleTemplateFavorite(id: string, next: boolean) {
    if (!next) setTemplates((prev) => prev.filter((t) => t.id !== id));
    void updateTemplate(id, { is_favorite: next }).catch(() => {});
  }

  const totalCount = scripts.length + images.length + videos.length + voiceovers.length + renders.length + hooks.length + templates.length;

  const sections: { key: TabKey; label: string; node: React.ReactNode; count: number }[] = [
    {
      key: "script",
      label: "Scripts",
      count: scripts.length,
      node: (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {scripts.map((a) => (
            <ScriptAssetCard key={a.id} asset={a} onToggleFavorite={handleAssetFavorite(setScripts)} />
          ))}
        </div>
      ),
    },
    {
      key: "hook",
      label: "Hooks",
      count: hooks.length,
      node: (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {hooks.map((h) => (
            <HookCard key={h.id} hook={h} onToggleFavorite={handleHookFavorite} />
          ))}
        </div>
      ),
    },
    {
      key: "image",
      label: "Images",
      count: images.length,
      node: (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {images.map((a) => (
            <ContentAssetCard key={a.id} asset={a} onToggleFavorite={handleAssetFavorite(setImages)} />
          ))}
        </div>
      ),
    },
    {
      key: "video",
      label: "Videos",
      count: videos.length + renders.length,
      node: (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...videos, ...renders].map((a) => (
            <ContentAssetCard key={a.id} asset={a} onToggleFavorite={handleAssetFavorite(a.asset_type === "video" ? setVideos : setRenders)} />
          ))}
        </div>
      ),
    },
    {
      key: "template",
      label: "Templates",
      count: templates.length,
      node: (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <TemplateCard key={t.id} template={t} onToggleFavorite={handleTemplateFavorite} />
          ))}
        </div>
      ),
    },
    {
      key: "voiceover",
      label: "Voiceovers",
      count: voiceovers.length,
      node: (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {voiceovers.map((a) => (
            <ContentAssetCard key={a.id} asset={a} onToggleFavorite={handleAssetFavorite(setVoiceovers)} />
          ))}
        </div>
      ),
    },
  ];

  const visibleSections = tab === "all" ? sections.filter((s) => s.count > 0) : sections.filter((s) => s.key === tab);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Favorites</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          Scripts, hooks, images, videos, templates and voiceovers you&apos;ve saved for reuse.
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

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading favorites…</p>
      ) : totalCount === 0 ? (
        <EmptyState
          title="No favorites yet"
          message="Save scripts, hooks, images, videos, and templates you want to reuse."
        />
      ) : visibleSections.length === 0 ? (
        <EmptyState title="Nothing here yet" message="Favorite something in this category to see it here." />
      ) : (
        <div className="flex flex-col gap-8">
          {visibleSections.map((section) => (
            <div key={section.key} className="flex flex-col gap-3">
              {tab === "all" && (
                <h2 className="text-[13px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                  {section.label}
                </h2>
              )}
              {section.node}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
