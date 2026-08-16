"use client";

import type { Template } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

const GRADIENTS: Record<string, string> = {
  "gradient-purple-teal": "from-[var(--accent)] to-[var(--accent-2)]",
  "gradient-magenta-indigo": "from-[var(--magenta)] to-[var(--indigo)]",
  "gradient-teal-indigo": "from-[var(--accent-2)] to-[var(--indigo)]",
  "gradient-magenta-purple": "from-[var(--magenta)] to-[var(--accent)]",
  "gradient-purple-magenta": "from-[var(--accent)] to-[var(--magenta)]",
  "gradient-indigo-teal": "from-[var(--indigo)] to-[var(--accent-2)]",
  "gradient-teal-purple": "from-[var(--accent-2)] to-[var(--accent)]",
  "gradient-magenta-teal": "from-[var(--magenta)] to-[var(--accent-2)]",
  "gradient-indigo-magenta": "from-[var(--indigo)] to-[var(--magenta)]",
  "gradient-purple-indigo": "from-[var(--accent)] to-[var(--indigo)]",
  "gradient-teal-magenta": "from-[var(--accent-2)] to-[var(--magenta)]",
  "gradient-indigo-purple": "from-[var(--indigo)] to-[var(--accent)]",
};

export function TemplateCard({
  template,
  onToggleFavorite,
  onUse,
  onDuplicate,
}: {
  template: Template;
  onToggleFavorite: (id: string, next: boolean) => void;
  onUse?: (template: Template) => void;
  onDuplicate?: (template: Template) => void;
}) {
  const gradient = GRADIENTS[template.thumbnail_key] ?? "from-[var(--accent)] to-[var(--accent-2)]";

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
      <div className={`relative flex aspect-video items-center justify-center bg-gradient-to-br ${gradient}`}>
        <span className="text-[13px] font-semibold tracking-wide text-white/90 drop-shadow">{template.name}</span>
        <button
          type="button"
          onClick={() => onToggleFavorite(template.id, !template.is_favorite)}
          title="Favorite"
          className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-black/30 text-[15px] text-white backdrop-blur-sm transition-transform hover:scale-105"
        >
          {template.is_favorite ? "♥" : "♡"}
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center gap-1.5">
          <Badge tone={template.kind === "video" ? "accent" : "neutral"}>
            {template.kind === "video" ? "Video" : "Static"}
          </Badge>
          <Badge tone="neutral">{template.category}</Badge>
          {template.is_official ? <Badge tone="success">Official</Badge> : <Badge tone="warning">Mine</Badge>}
        </div>
        <p className="text-[13.5px] font-medium text-[var(--foreground)]">{template.name}</p>
        {template.description && (
          <p className="line-clamp-2 text-[12px] leading-relaxed text-[var(--muted)]">{template.description}</p>
        )}

        <div className="mt-auto flex items-center gap-2 pt-2">
          {onUse && (
            <Button size="sm" onClick={() => onUse(template)}>
              Use
            </Button>
          )}
          {onDuplicate && (
            <button
              type="button"
              onClick={() => onDuplicate(template)}
              className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
            >
              Duplicate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
