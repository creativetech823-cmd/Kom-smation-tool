"use client";

import { motion } from "framer-motion";
import { motionFileUrl } from "@/lib/api";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { renderBold } from "@/lib/renderBold";
import type { FlatLine, MotionGenerationResult, SelectedAsset } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };

const gridVariants = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const tileVariants = { hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

export function AssetsStep({
  lines,
  assets,
  loadingIds,
  onRegenerateLine,
  motions,
  loadingMotionIds,
  onGenerateMotion,
  onContinue,
  onBack,
  continuing,
}: {
  lines: FlatLine[];
  assets: Record<string, SelectedAsset | undefined>;
  loadingIds: Set<string>;
  onRegenerateLine: (id: string) => void;
  motions: Record<string, MotionGenerationResult | undefined>;
  loadingMotionIds: Set<string>;
  onGenerateMotion: (id: string) => void;
  onContinue: () => void;
  onBack: () => void;
  continuing: boolean;
}) {
  const allReady = lines.every((l) => assets[l.id] && !loadingIds.has(l.id));

  return (
    <Card glow>
      <CardHeader
        title="Asset Sourcing"
        subtitle="Pexels + Pixabay search, auto-broadened, ranked by Gemini Vision."
        icon={<IconImage />}
      />
      <CardBody>
        <motion.div
          variants={gridVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 gap-4 sm:grid-cols-3"
        >
          {lines.map((line) => {
            const asset = assets[line.id];
            const isLoading = loadingIds.has(line.id);
            const clip = motions[line.id];
            const isAnimating = loadingMotionIds.has(line.id);
            return (
              <motion.div
                key={line.id}
                variants={tileVariants}
                whileHover={{ y: -4 }}
                className="group relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-2)] shadow-[0_1px_0_rgba(255,255,255,0.04)_inset] transition-shadow hover:shadow-[0_20px_40px_-20px_var(--shadow-color)]"
              >
                <div className="relative aspect-[9/16] w-full overflow-hidden bg-black/40">
                  {isLoading ? (
                    <div className="animate-shimmer h-full w-full" />
                  ) : clip ? (
                    <video
                      src={motionFileUrl(clip.video_path)}
                      autoPlay
                      loop
                      muted
                      playsInline
                      className="h-full w-full object-cover"
                    />
                  ) : asset?.candidate ? (
                    <img
                      src={asset.candidate.thumbnail_url}
                      alt={line.text.replace(/\*\*/g, "")}
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-[12px] text-[var(--danger)]">
                      No match found
                    </div>
                  )}

                  <div className="absolute left-2 top-2 flex gap-1.5">
                    <Badge tone={line.role === "hook" ? "accent" : line.role === "cta" ? "success" : "neutral"}>
                      {ROLE_LABEL[line.role]}
                    </Badge>
                    {clip && <Badge tone="accent">Motion</Badge>}
                  </div>

                  <button
                    onClick={() => onRegenerateLine(line.id)}
                    disabled={isLoading}
                    className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 disabled:opacity-50"
                    title="Regenerate this image"
                  >
                    <IconRefresh />
                  </button>

                  {asset?.candidate && !isLoading && (
                    <button
                      onClick={() => onGenerateMotion(line.id)}
                      disabled={isAnimating}
                      className="absolute bottom-2 right-2 flex items-center gap-1 rounded-full bg-black/65 px-2.5 py-1.5 text-[11px] font-medium text-white backdrop-blur transition-colors hover:bg-black/80 disabled:opacity-60"
                      title="Animate this image with AI motion (Hugging Face, uses free-tier credits)"
                    >
                      {isAnimating ? (
                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      ) : (
                        <IconSparkle />
                      )}
                      {isAnimating ? "Animating…" : clip ? "Re-animate" : "Animate"}
                    </button>
                  )}
                </div>
                <div className="p-2.5">
                  <p className="line-clamp-2 text-[12px] text-[var(--muted)]">{renderBold(line.text)}</p>
                  {asset?.broadened && (
                    <p className="mt-1 text-[10.5px] text-[var(--warning)]">
                      broadened → {asset.tag_used}
                    </p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </motion.div>

        <div className="flex justify-between pt-5">
          <Button variant="ghost" onClick={onBack}>
            ← Back
          </Button>
          <Button onClick={onContinue} disabled={!allReady} loading={continuing}>
            Render video
            <IconArrow />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function IconImage() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
      <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 4v6h6M20 20v-6h-6M4.5 15a8 8 0 0014.9 2.3M19.5 9A8 8 0 004.6 6.7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconSparkle() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
      <path d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z" fill="currentColor" />
    </svg>
  );
}

function IconArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
