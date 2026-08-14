"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { visualFileUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { VisualConcept, VisualConceptScores, VisualSceneLabel, VisualVariationStyle } from "@/lib/types";

const SCENE_LABEL_META: Record<VisualSceneLabel, { emoji: string; color: string }> = {
  hook: { emoji: "🎬", color: "var(--accent)" },
  emotional: { emoji: "❤️", color: "var(--magenta)" },
  transformation: { emoji: "✨", color: "var(--success)" },
  product_shot: { emoji: "📦", color: "var(--accent-2)" },
  social_proof: { emoji: "👥", color: "var(--warning)" },
  testimonial: { emoji: "🗣️", color: "var(--accent)" },
  ugc: { emoji: "📱", color: "var(--accent-2)" },
  lifestyle: { emoji: "🌿", color: "var(--success)" },
};

const SCORE_LABELS: { key: keyof VisualConceptScores; label: string }[] = [
  { key: "visual_impact", label: "Visual Impact" },
  { key: "ad_quality", label: "Ad Quality" },
  { key: "ctr_prediction", label: "CTR Prediction" },
  { key: "emotion_score", label: "Emotion Score" },
  { key: "brand_match", label: "Brand Match" },
  { key: "photorealism", label: "Photorealism" },
];

const STYLE_PRESETS: { value: VisualVariationStyle; label: string }[] = [
  { value: "photorealistic", label: "Photorealistic" },
  { value: "luxury_product", label: "Luxury Product" },
  { value: "studio_photography", label: "Studio Photography" },
  { value: "commercial_advertisement", label: "Commercial Ad" },
  { value: "lifestyle", label: "Lifestyle" },
  { value: "fashion", label: "Fashion" },
  { value: "apple_style", label: "Apple Style" },
  { value: "nike_style", label: "Nike Style" },
  { value: "cinematic", label: "Cinematic" },
  { value: "moody", label: "Moody" },
  { value: "bollywood", label: "Bollywood" },
  { value: "documentary", label: "Documentary" },
  { value: "meta_glasses_pov", label: "Meta Glasses POV" },
  { value: "ugc", label: "UGC" },
  { value: "instagram_ad", label: "Instagram Ad" },
  { value: "facebook_ad", label: "Facebook Ad" },
  { value: "luxury_cosmetic", label: "Luxury Cosmetic" },
  { value: "minimal", label: "Minimal" },
  { value: "hyper_realistic", label: "Hyper Realistic" },
];

const DOWNLOAD_FORMATS: ("png" | "jpeg" | "webp")[] = ["png", "jpeg", "webp"];

export function VisualConceptCard({
  concept,
  regenerating,
  scoring,
  downloading,
  onView,
  onDownload,
  onEditPrompt,
  onRegenerate,
  onGenerateVariation,
  onToggleFavorite,
}: {
  concept: VisualConcept;
  regenerating: boolean;
  scoring: boolean;
  downloading: boolean;
  onView: () => void;
  onDownload: (format: "png" | "jpeg" | "webp") => void;
  onEditPrompt: () => void;
  onRegenerate: (variationStyle?: VisualVariationStyle) => void;
  onGenerateVariation: (variationStyle: "generate_similar" | "different_angle") => void;
  onToggleFavorite: () => void;
}) {
  const [styleMenuOpen, setStyleMenuOpen] = useState(false);
  const [downloadMenuOpen, setDownloadMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const styleRef = useRef<HTMLDivElement>(null);
  const downloadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (styleRef.current && !styleRef.current.contains(e.target as Node)) setStyleMenuOpen(false);
      if (downloadRef.current && !downloadRef.current.contains(e.target as Node)) setDownloadMenuOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleCopyPrompt() {
    navigator.clipboard.writeText(concept.prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  }

  const labelMeta = SCENE_LABEL_META[concept.scene_label] ?? SCENE_LABEL_META.hook;
  const isBusy = regenerating || downloading;

  return (
    <motion.div
      whileHover={{ y: -3 }}
      className="group relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur-xl shadow-[0_1px_0_rgba(255,255,255,0.05)_inset,0_20px_60px_-30px_rgba(0,0,0,0.85)] transition-shadow duration-300 hover:shadow-[0_0_0_1px_rgba(124,92,255,0.35),0_30px_70px_-25px_rgba(124,92,255,0.35)]"
    >
      <div className="relative aspect-[9/16] w-full overflow-hidden bg-black/40">
        {isBusy ? (
          <div className="animate-shimmer h-full w-full" />
        ) : concept.image_path ? (
          <img
            src={visualFileUrl(concept.image_path)}
            alt={concept.scene_title}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[12px] text-[var(--muted)]">No image yet</div>
        )}

        <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5">
          <span
            className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-white"
            style={{ background: labelMeta.color, borderColor: "transparent" }}
          >
            {labelMeta.emoji} {concept.scene_label.replace(/_/g, " ")}
          </span>
        </div>
        <span className="absolute right-2.5 top-2.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/55 text-[11px] font-semibold text-white backdrop-blur">
          {concept.scene_number}
        </span>

        {/* Hover action row */}
        <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-1 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-2.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <HoverButton title="View Fullscreen" onClick={onView}>
            🔍
          </HoverButton>
          <div className="relative" ref={downloadRef}>
            <HoverButton title="Download 4K" onClick={() => setDownloadMenuOpen((o) => !o)} loading={downloading}>
              ⬇
            </HoverButton>
            {downloadMenuOpen && (
              <div className="absolute bottom-full left-0 z-20 mb-1.5 w-28 overflow-hidden rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] shadow-lg">
                {DOWNLOAD_FORMATS.map((fmt) => (
                  <button
                    key={fmt}
                    type="button"
                    onClick={() => {
                      setDownloadMenuOpen(false);
                      onDownload(fmt);
                    }}
                    className="block w-full px-3 py-1.5 text-left text-[11.5px] uppercase text-[var(--foreground)] hover:bg-white/[0.08]"
                  >
                    {fmt}
                  </button>
                ))}
              </div>
            )}
          </div>
          <HoverButton title="Edit Prompt" onClick={onEditPrompt}>
            ✏️
          </HoverButton>
          <HoverButton title="Regenerate" onClick={() => onRegenerate()} loading={regenerating}>
            🔄
          </HoverButton>
          <HoverButton title="Generate Similar" onClick={() => onGenerateVariation("generate_similar")}>
            🎲
          </HoverButton>
          <HoverButton title="Generate Different Angle" onClick={() => onGenerateVariation("different_angle")}>
            🔀
          </HoverButton>
          <HoverButton title="Copy Prompt" onClick={handleCopyPrompt}>
            {copied ? "✅" : "📋"}
          </HoverButton>
          <HoverButton title="Favorite" onClick={onToggleFavorite}>
            {concept.favorite ? "★" : "☆"}
          </HoverButton>
          <div className="relative ml-auto" ref={styleRef}>
            <button
              type="button"
              onClick={() => setStyleMenuOpen((o) => !o)}
              className="rounded-full border border-white/20 bg-black/50 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur hover:bg-black/70"
            >
              Style ▾
            </button>
            {styleMenuOpen && (
              <div className="absolute bottom-full right-0 z-20 mb-1.5 max-h-56 w-44 overflow-y-auto rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] shadow-lg">
                {STYLE_PRESETS.map((s) => (
                  <button
                    key={s.value}
                    type="button"
                    onClick={() => {
                      setStyleMenuOpen(false);
                      onRegenerate(s.value);
                    }}
                    className="block w-full px-3 py-1.5 text-left text-[11.5px] text-[var(--foreground)] hover:bg-white/[0.08]"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-2.5 p-3.5">
        <div>
          <p className="text-[13px] font-semibold text-[var(--foreground)]">{concept.scene_title}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {concept.creative_angle && (
              <span className="rounded-full border border-[var(--accent)]/25 bg-white/[0.04] px-2 py-0.5 text-[10.5px] text-[var(--foreground)]">
                {concept.creative_angle}
              </span>
            )}
            <span className="rounded-full border border-[var(--border-strong)] bg-white/[0.04] px-2 py-0.5 text-[10.5px] text-[var(--muted)]">
              {concept.aspect_ratio}
            </span>
          </div>
        </div>

        <PromptDisclosure prompt={concept.prompt} />

        <MetadataDisclosure concept={concept} />

        <ScoreBlock scores={concept.scores} loading={scoring} />
      </div>
    </motion.div>
  );
}

function HoverButton({
  children,
  title,
  onClick,
  loading,
}: {
  children: React.ReactNode;
  title: string;
  onClick: () => void;
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={loading}
      className="flex h-7 w-7 items-center justify-center rounded-full border border-white/20 bg-black/50 text-[12px] text-white backdrop-blur transition-colors hover:bg-black/70 disabled:opacity-50"
    >
      {loading ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" /> : children}
    </button>
  );
}

function PromptDisclosure({ prompt }: { prompt: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-[var(--border)] bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
      >
        Prompt
        <span className={cn("transition-transform", open && "rotate-180")}>⌄</span>
      </button>
      {open && <p className="border-t border-[var(--border)] px-2.5 py-2 text-[11.5px] leading-relaxed text-[var(--muted)]">{prompt}</p>}
    </div>
  );
}

function MetadataDisclosure({ concept }: { concept: VisualConcept }) {
  const [open, setOpen] = useState(false);
  const rows: { label: string; value: string }[] = [
    { label: "Style", value: concept.style_params.style || "—" },
    { label: "Aspect Ratio", value: concept.aspect_ratio || "—" },
    { label: "Resolution", value: concept.resolution || "—" },
    { label: "Seed", value: concept.seed != null ? String(concept.seed) : "—" },
    { label: "Generation Time", value: concept.generation_time_seconds ? `${concept.generation_time_seconds}s` : "—" },
    { label: "Model Used", value: concept.used_model || "—" },
    { label: "Negative Prompt", value: concept.style_params.negative_prompt || "—" },
  ];
  return (
    <div className="rounded-lg border border-[var(--border)] bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
      >
        Metadata
        <span className={cn("transition-transform", open && "rotate-180")}>⌄</span>
      </button>
      {open && (
        <div className="space-y-1 border-t border-[var(--border)] px-2.5 py-2">
          {rows.map((r) => (
            <div key={r.label} className="flex items-start justify-between gap-2 text-[11px]">
              <span className="shrink-0 text-[var(--muted)]">{r.label}</span>
              <span className="text-right text-[var(--foreground)]">{r.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ScoreBlock({ scores, loading }: { scores: VisualConceptScores | null; loading: boolean }) {
  if (loading || !scores) {
    return (
      <div className="space-y-1.5">
        {loading && <p className="text-[10.5px] text-[var(--muted)]">AI Assessment — scoring…</p>}
        <div className="animate-shimmer h-14 w-full rounded-lg" />
      </div>
    );
  }
  return (
    <div className="space-y-1">
      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--muted)]">AI Assessment</p>
      {SCORE_LABELS.map(({ key, label }) => {
        const value = scores[key] as number;
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="w-[92px] shrink-0 text-[10.5px] text-[var(--muted)]">{label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[var(--accent)] to-[var(--accent-2)]"
                style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
              />
            </div>
            <span className="w-8 shrink-0 text-right text-[10.5px] font-medium text-[var(--foreground)]">{value}%</span>
          </div>
        );
      })}
    </div>
  );
}
