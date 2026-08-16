"use client";

import type { ContentAsset } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

type ScriptLikeLine = { text?: string };
type ScriptLikeContent = { hook?: ScriptLikeLine; body?: ScriptLikeLine[]; cta?: ScriptLikeLine };

function flattenScriptText(content: Record<string, unknown> | null): string {
  if (!content) return "";
  const s = content as ScriptLikeContent;
  const lines = [s.hook?.text, ...(s.body ?? []).map((l) => l?.text), s.cta?.text].filter(Boolean);
  return lines.join("\n\n");
}

export function ScriptAssetCard({
  asset,
  onToggleFavorite,
  highlighted,
}: {
  asset: ContentAsset;
  onToggleFavorite: (id: string, next: boolean) => void;
  highlighted?: boolean;
}) {
  const scriptText = flattenScriptText(asset.content_json);
  const createdAt = new Date(asset.created_at);
  const dateLabel = Number.isNaN(createdAt.getTime())
    ? ""
    : createdAt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

  function handleCopy() {
    if (scriptText) void navigator.clipboard.writeText(scriptText);
  }

  function handleDownload() {
    const blob = new Blob([scriptText || asset.title], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(asset.title || "script").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      id={`asset-${asset.id}`}
      className={cn(
        "flex flex-col gap-3 rounded-2xl border bg-[var(--surface)] p-4",
        highlighted ? "border-[var(--accent)] shadow-[0_0_0_3px_var(--accent-soft)]" : "border-[var(--border)]"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <Badge tone="accent">Script</Badge>
          {asset.project_name && <Badge tone="neutral">{asset.project_name}</Badge>}
        </div>
        <button
          type="button"
          onClick={() => onToggleFavorite(asset.id, !asset.is_favorite)}
          title="Favorite"
          className="text-[16px] text-[var(--foreground)]"
        >
          {asset.is_favorite ? "♥" : "♡"}
        </button>
      </div>

      <div>
        <p className="text-[13.5px] font-medium text-[var(--foreground)]">{asset.title || asset.product_name}</p>
        <p className="text-[11.5px] text-[var(--muted)]">
          {asset.product_name}
          {asset.product_name && dateLabel ? " · " : ""}
          {dateLabel}
        </p>
        {asset.source_hook_text && (
          <p className="mt-1 truncate text-[11px] text-[var(--muted)]" title={asset.source_hook_text}>
            Hook: &ldquo;{asset.source_hook_text}&rdquo;
          </p>
        )}
      </div>

      {scriptText && (
        <p className="line-clamp-3 whitespace-pre-line text-[12.5px] leading-relaxed text-[var(--muted)]">
          {scriptText}
        </p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
        >
          Copy
        </button>
        <button
          type="button"
          onClick={handleDownload}
          className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
        >
          Download .txt
        </button>
      </div>
    </div>
  );
}
