"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DurationSelector } from "@/components/ui/DurationSelector";
import { angleAccent, angleEmoji } from "@/lib/creativeAngles";
import { STATIC_FORMATS, TONE_OPTIONS, VIDEO_FORMATS, type FormatOption } from "@/lib/contentFormats";
import { cn } from "@/lib/utils";
import type { ContentType, StorySituation } from "@/lib/types";

const CUSTOM_FORMAT_MAX = 300;

export function FormatStep({
  situation,
  angle,
  contentType,
  targetDuration,
  onTargetDurationChange,
  onBack,
  onGenerate,
  generating,
}: {
  situation: StorySituation;
  angle: string;
  contentType: ContentType;
  targetDuration: string;
  onTargetDurationChange: (duration: string) => void;
  onBack: () => void;
  onGenerate: (selection: { format: string; formatDescription: string; tone: string }) => void;
  generating: boolean;
}) {
  const options: FormatOption[] = contentType === "video" ? VIDEO_FORMATS : STATIC_FORMATS;
  const [format, setFormat] = useState("");
  const [customDescription, setCustomDescription] = useState("");
  const [tone, setTone] = useState("");

  const isCustom = format === "custom";
  const canGenerate = format !== "" && (!isCustom || customDescription.trim().length > 0);

  return (
    <Card glow>
      <CardHeader
        title={contentType === "video" ? "Select Video Format" : "Select Static Format"}
        subtitle="The format shapes the entire script structure — pick the one that matches what you're producing."
        icon={<IconGrid />}
      />
      <CardBody className="space-y-5">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-4 py-3">
          <span className="text-[12px] font-medium text-[var(--muted)]">Story:</span>
          <span className="text-[13px] font-semibold text-[var(--foreground)]">{situation.title}</span>
          {angle && (
            <span
              className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium text-white"
              style={{ background: angleAccent(angle), borderColor: "transparent" }}
            >
              {angleEmoji(angle)} {angle}
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--foreground)]">
            {contentType === "video" ? "\u{1F3A5} Video" : "\u{1F5BC}\u{FE0F} Static"}
          </span>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3"
        >
          {options.map((opt) => {
            const active = format === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFormat(opt.value)}
                className={cn(
                  "flex items-start gap-3 rounded-xl border px-3.5 py-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
                  active
                    ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                    : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)]/40"
                )}
              >
                <span className="text-[18px] leading-none">{opt.emoji}</span>
                <span>
                  <span className="block text-[13px] font-semibold text-[var(--foreground)]">{opt.label}</span>
                  <span className="block text-[11.5px] text-[var(--muted)]">{opt.hint}</span>
                </span>
              </button>
            );
          })}
        </motion.div>

        {isCustom && (
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[var(--muted)]">
              Describe the {contentType === "video" ? "video" : "static"} format you want
            </label>
            <textarea
              autoFocus
              value={customDescription}
              onChange={(e) => setCustomDescription(e.target.value)}
              maxLength={CUSTOM_FORMAT_MAX}
              rows={2}
              placeholder={
                contentType === "video"
                  ? "e.g. \"a stop-motion product unboxing\""
                  : "e.g. \"a minimalist black-and-white poster\""
              }
              className="w-full resize-none rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
            />
          </div>
        )}

        <div className="space-y-2">
          <p className="text-[12px] font-medium text-[var(--muted)]">Tone (optional)</p>
          <div className="flex flex-wrap gap-1.5">
            {TONE_OPTIONS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTone((cur) => (cur === t.value ? "" : t.value))}
                className={cn(
                  "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
                  tone === t.value
                    ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--on-accent)]"
                    : "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--foreground)] hover:border-[var(--accent)]/40"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {contentType === "video" && (
          <div className="space-y-2">
            <p className="text-[12px] font-medium text-[var(--muted)]">Duration</p>
            <DurationSelector value={targetDuration} onChange={onTargetDurationChange} />
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button variant="ghost" onClick={onBack} disabled={generating}>
            ← Back
          </Button>
          <Button
            onClick={() => onGenerate({ format, formatDescription: customDescription.trim(), tone })}
            disabled={!canGenerate}
            loading={generating}
          >
            {!generating && "\u{2728} "}Generate Script
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function IconGrid() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}
