"use client";

import { Input } from "@/components/ui/Field";
import { cn } from "@/lib/utils";

export function LibraryFilterBar({
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  chips,
  activeChip,
  onChipChange,
  favoriteOnly,
  onFavoriteOnlyChange,
  sort,
  onSortChange,
  right,
}: {
  search?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  chips?: string[];
  activeChip?: string | null;
  onChipChange?: (chip: string | null) => void;
  favoriteOnly?: boolean;
  onFavoriteOnlyChange?: (value: boolean) => void;
  sort?: "recent" | "oldest";
  onSortChange?: (value: "recent" | "oldest") => void;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        {onSearchChange && (
          <div className="min-w-[220px] flex-1">
            <Input
              value={search ?? ""}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
            />
          </div>
        )}
        {onFavoriteOnlyChange && (
          <button
            type="button"
            onClick={() => onFavoriteOnlyChange(!favoriteOnly)}
            className={cn(
              "flex items-center gap-1.5 rounded-xl border px-3 py-2.5 text-[13px] font-medium transition-colors",
              favoriteOnly
                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)]"
            )}
          >
            {favoriteOnly ? "♥" : "♡"} Favorites
          </button>
        )}
        {onSortChange && (
          <select
            value={sort ?? "recent"}
            onChange={(e) => onSortChange(e.target.value as "recent" | "oldest")}
            className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
          >
            <option value="recent">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        )}
        {right}
      </div>

      {chips && chips.length > 0 && onChipChange && (
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => onChipChange(null)}
            className={cn(
              "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
              !activeChip
                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
            )}
          >
            All
          </button>
          {chips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => onChipChange(chip)}
              className={cn(
                "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
                activeChip === chip
                  ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
              )}
            >
              {chip}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
