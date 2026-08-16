"use client";

import { audioFileUrl, motionFileUrl, renderFileUrl, visualFileUrl } from "@/lib/api";
import type { ContentAsset } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<ContentAsset["asset_type"], string> = {
  script: "Script",
  image: "Image",
  video: "Video",
  voiceover: "Voiceover",
  render: "Render",
};

function fileUrlFor(asset: ContentAsset): string | null {
  if (!asset.file_path) return null;
  switch (asset.asset_type) {
    case "image":
      return visualFileUrl(asset.file_path);
    case "video":
      return motionFileUrl(asset.file_path);
    case "render":
      return renderFileUrl(asset.file_path);
    case "voiceover":
      return audioFileUrl(asset.file_path);
    default:
      return null;
  }
}

function downloadFilename(asset: ContentAsset, url: string): string {
  const ext = url.split(".").pop()?.split("?")[0] || "bin";
  const base = (asset.title || asset.product_name || asset.asset_type).replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  return `${base}.${ext}`;
}

export function ContentAssetCard({
  asset,
  onToggleFavorite,
  highlighted,
}: {
  asset: ContentAsset;
  onToggleFavorite: (id: string, next: boolean) => void;
  highlighted?: boolean;
}) {
  const url = fileUrlFor(asset);
  const createdAt = new Date(asset.created_at);
  const dateLabel = Number.isNaN(createdAt.getTime())
    ? ""
    : createdAt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

  return (
    <div
      id={`asset-${asset.id}`}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border bg-[var(--surface)] transition-shadow",
        highlighted ? "border-[var(--accent)] shadow-[0_0_0_3px_var(--accent-soft)]" : "border-[var(--border)]"
      )}
    >
      <div className="relative aspect-video w-full overflow-hidden bg-[var(--surface-2)]">
        {asset.asset_type === "image" && url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={asset.title} className="h-full w-full object-cover" />
        ) : asset.asset_type === "video" || asset.asset_type === "render" ? (
          url ? (
            <video src={url} className="h-full w-full object-cover" muted playsInline preload="metadata" />
          ) : (
            <PlaceholderIcon type={asset.asset_type} />
          )
        ) : asset.asset_type === "voiceover" ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4">
            <PlaceholderIcon type="voiceover" />
            {url && <audio src={url} controls className="h-8 w-full max-w-[220px]" />}
          </div>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
            <PlaceholderIcon type="script" />
            <p className="line-clamp-3 px-3 text-[11px] leading-snug text-[var(--muted)]">
              {typeof asset.content_json?.hook === "object" &&
              asset.content_json?.hook &&
              "text" in (asset.content_json.hook as Record<string, unknown>)
                ? String((asset.content_json.hook as Record<string, unknown>).text)
                : asset.title}
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={() => onToggleFavorite(asset.id, !asset.is_favorite)}
          title="Favorite"
          className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/50 text-[15px] text-white backdrop-blur-sm transition-transform hover:scale-105"
        >
          {asset.is_favorite ? "♥" : "♡"}
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center gap-1.5">
          <Badge tone="accent">{TYPE_LABEL[asset.asset_type]}</Badge>
          {asset.project_name && <Badge tone="neutral">{asset.project_name}</Badge>}
        </div>
        <p className="truncate text-[13.5px] font-medium text-[var(--foreground)]" title={asset.title}>
          {asset.title || asset.product_name || "Untitled"}
        </p>
        <p className="text-[11.5px] text-[var(--muted)]">
          {asset.product_name}
          {asset.product_name && dateLabel ? " · " : ""}
          {dateLabel}
        </p>
        {asset.model_used && <p className="truncate text-[11px] text-[var(--muted)]">Model: {asset.model_used}</p>}
        {asset.source_hook_text && (
          <p className="truncate text-[11px] text-[var(--muted)]" title={asset.source_hook_text}>
            Hook: &ldquo;{asset.source_hook_text}&rdquo;
          </p>
        )}

        <div className="mt-auto flex items-center gap-2 pt-1">
          {url ? (
            <a
              href={url}
              download={downloadFilename(asset, url)}
              className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
            >
              Download
            </a>
          ) : (
            <span className="text-[11px] text-[var(--muted)]">No file</span>
          )}
        </div>
      </div>
    </div>
  );
}

function PlaceholderIcon({ type }: { type: ContentAsset["asset_type"] }) {
  const paths: Record<ContentAsset["asset_type"], React.ReactNode> = {
    script: (
      <path d="M6 2h9l3 3v17H6V2z M15 2v3h3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M21 15l-5-5-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      </>
    ),
    video: <path d="M4 5h12v14H4zM16 9l5-3v12l-5-3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />,
    voiceover: (
      <>
        <rect x="9" y="2" width="6" height="12" rx="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M5 11a7 7 0 0014 0M12 18v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </>
    ),
    render: (
      <path d="M4 5h12v14H4zM16 9l5-3v12l-5-3" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    ),
  };
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-[var(--muted)]">
      {paths[type]}
    </svg>
  );
}
