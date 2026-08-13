"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { DurationSelector } from "@/components/ui/DurationSelector";
import { RegenerateMenu } from "@/components/ui/RegenerateMenu";
import { AiActionChipRow } from "@/components/ui/AiActionChip";
import { angleAccent, angleEmoji } from "@/lib/creativeAngles";
import { renderBold } from "@/lib/renderBold";
import {
  flattenScript,
  type FlatLine,
  type GeneratedScript,
  type RewriteDirective,
  type ScriptLanguage,
  type ScriptRegenerateScope,
  type StorySituation,
} from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };
const ROLE_TONE: Record<string, "accent" | "success" | "neutral"> = { hook: "accent", body: "neutral", cta: "success" };
const ROLE_MARKER: Record<string, string> = { hook: "var(--accent)", body: "var(--border-strong)", cta: "var(--accent-2)" };
const SECTION_LABEL: Record<string, string> = {
  hook: "Hook",
  problem: "Problem",
  science: "Science",
  story: "Story",
  product_intro: "Product Intro",
  ingredients: "Ingredients",
  benefits: "Benefits",
  objection_handling: "Objection Handling",
  cta: "CTA",
};

export function ScriptStep({
  script,
  situation,
  creativeAngle,
  scriptLanguage,
  onScriptLanguageChange,
  targetDuration,
  onTargetDurationChange,
  onRegenerateScope,
  onContinue,
  onBack,
  regenerating,
  continuing,
  onRewriteLine,
  rewriting,
}: {
  script: GeneratedScript;
  situation: StorySituation;
  creativeAngle?: string;
  scriptLanguage?: ScriptLanguage;
  onScriptLanguageChange?: (language: ScriptLanguage) => void;
  targetDuration?: string;
  onTargetDurationChange?: (duration: string) => void;
  onRegenerateScope: (scope: ScriptRegenerateScope) => void;
  onContinue: () => void;
  onBack: () => void;
  regenerating: boolean;
  continuing: boolean;
  onRewriteLine: (lineId: string, directive: RewriteDirective) => void;
  rewriting: Record<string, RewriteDirective | undefined>;
}) {
  const lines = flattenScript(script);
  const [view, setView] = useState<"shotlist" | "sheet">("shotlist");

  return (
    <Card glow>
      <CardHeader
        title="Cinematic Script"
        subtitle="Full cinematic script for your chosen story — plus literal search tags for Stage 8."
        icon={<IconPen />}
        right={<RegenerateMenu onSelect={onRegenerateScope} loading={regenerating} />}
      />
      <CardBody className="space-y-4">
        <div className="flex items-start justify-between gap-3 rounded-xl border border-[var(--accent)]/20 bg-[var(--accent-soft)] px-4 py-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Badge tone="accent">{situation.category}</Badge>
              <span className="text-[13px] font-semibold text-[var(--foreground)]">{situation.title}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Chip>🎭 {situation.emotion}</Chip>
              <Chip>👤 {situation.persona}</Chip>
              {creativeAngle && (
                <span
                  className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium text-white"
                  style={{ background: angleAccent(creativeAngle), borderColor: "transparent" }}
                >
                  {angleEmoji(creativeAngle)} {creativeAngle}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 whitespace-nowrap text-[12px] font-medium text-[var(--accent-2)] hover:underline"
          >
            Different angle
          </button>
        </div>

        {onScriptLanguageChange && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[12px] font-medium text-[var(--muted)]">Language</p>
              <LanguageSelector value={scriptLanguage ?? "english"} onChange={onScriptLanguageChange} />
              {onTargetDurationChange && (
                <>
                  <p className="ml-1 text-[12px] font-medium text-[var(--muted)]">Duration</p>
                  <DurationSelector value={targetDuration || script.target_duration || "30s"} onChange={onTargetDurationChange} />
                </>
              )}
              <span className="text-[11px] text-[var(--muted)]">— change, then Regenerate</span>
            </div>
            <div className="inline-flex items-center gap-1 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] p-1">
              {(["shotlist", "sheet"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors ${
                    view === v ? "bg-[var(--accent)] text-white" : "text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {v === "shotlist" ? "Shot List" : "Script Sheet"}
                </button>
              ))}
            </div>
          </div>
        )}

        <p className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
          <span>🎙</span> Voiceover for every line happens in Stage 9, after Compliance and Assets are locked in.
        </p>

        {view === "shotlist" ? (
          <div className="relative">
            <div className="pointer-events-none absolute bottom-4 left-[15px] top-4 w-px bg-gradient-to-b from-[var(--accent)] via-[var(--border-strong)] to-[var(--accent-2)]" />
            <div className="space-y-3">
              {lines.map((line) => (
                <TimelineNode
                  key={line.id}
                  line={line}
                  defaultExpanded={line.role === "hook"}
                  onRewriteLine={onRewriteLine}
                  loadingDirective={rewriting[line.id] ?? null}
                />
              ))}
            </div>
          </div>
        ) : (
          <ScriptSheet title={situation.title} lines={lines} />
        )}

        {script.bgm_suggestion && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3.5">
            <p className="text-[13px] text-[var(--foreground)]">
              <span className="mr-1.5">🎵</span>
              <span className="font-medium">Background music:</span> {script.bgm_suggestion}
            </p>
          </div>
        )}

        <div className="flex justify-between pt-2">
          <Button variant="ghost" onClick={onBack}>
            ← Back
          </Button>
          <Button onClick={onContinue} loading={continuing}>
            Run compliance audit
            <IconArrow />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function ScriptSheet({ title, lines }: { title: string; lines: FlatLine[] }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)]/50 px-6 py-8 sm:px-10">
      <h2 className="mb-6 text-center text-[19px] font-bold tracking-tight text-[var(--foreground)]">{title}</h2>
      <div className="mx-auto max-w-[640px] space-y-4">
        {lines.map((line) => (
          <p
            key={line.id}
            className={
              line.role === "hook" || line.role === "cta"
                ? "text-[15px] font-semibold leading-relaxed text-[var(--foreground)]"
                : "text-[15px] leading-relaxed text-[var(--foreground)]/90"
            }
          >
            {renderBold(line.text)}
          </p>
        ))}
      </div>
    </div>
  );
}

function TimelineNode({
  line,
  defaultExpanded,
  onRewriteLine,
  loadingDirective,
}: {
  line: FlatLine;
  defaultExpanded: boolean;
  onRewriteLine: (lineId: string, directive: RewriteDirective) => void;
  loadingDirective: RewriteDirective | null;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="relative flex gap-4">
      <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center">
        <span
          className="h-4 w-4 rounded-full border-2 bg-[var(--surface)]"
          style={{ borderColor: ROLE_MARKER[line.role] }}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-2)]">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center gap-2 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <Badge tone={ROLE_TONE[line.role]}>{line.scene_label || ROLE_LABEL[line.role]}</Badge>
          {line.section && <MetaChip>{SECTION_LABEL[line.section] ?? line.section}</MetaChip>}
          {line.camera_angle && <MetaChip>📷 {line.camera_angle}</MetaChip>}
          {line.emotion && <MetaChip>🎭 {line.emotion}</MetaChip>}
          {typeof line.duration_seconds === "number" && <MetaChip>⏱ {line.duration_seconds}s</MetaChip>}
          {!expanded && (
            <span className="ml-1 flex-1 truncate text-[13px] text-[var(--muted)]">{renderBold(line.text)}</span>
          )}
          <IconChevron expanded={expanded} className="ml-auto shrink-0" />
        </button>

        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="space-y-2.5 px-4 pb-4">
                <p className="text-[15px] leading-snug text-[var(--foreground)]">{renderBold(line.text)}</p>
                {line.on_screen_text && line.on_screen_text !== line.text && (
                  <p className="text-[12.5px] text-[var(--accent-2)]">
                    <span className="mr-1 text-[var(--muted)]">On-screen:</span>
                    {renderBold(line.on_screen_text)}
                  </p>
                )}
                {line.visual_direction && (
                  <p className="text-[13px] italic leading-snug text-[var(--muted)]">{line.visual_direction}</p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {line.visual_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-[var(--border)] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]"
                    >
                      🎞 {tag}
                    </span>
                  ))}
                  {(line.b_roll ?? []).map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-[var(--border)] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]"
                    >
                      🎬 {tag}
                    </span>
                  ))}
                  {line.lighting && <MetaChip>💡 {line.lighting}</MetaChip>}
                  {line.sfx && <MetaChip>🔊 {line.sfx}</MetaChip>}
                </div>
                {line.transition_note && (
                  <p className="text-[12px] text-[var(--muted)]">↳ {line.transition_note}</p>
                )}
                {(line.ai_image_prompt || line.ai_video_prompt) && (
                  <AiPrompts imagePrompt={line.ai_image_prompt} videoPrompt={line.ai_video_prompt} />
                )}
                <AiActionChipRow
                  onAction={(directive) => onRewriteLine(line.id, directive)}
                  loadingDirective={loadingDirective}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function AiPrompts({ imagePrompt, videoPrompt }: { imagePrompt?: string; videoPrompt?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-[var(--border)] bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
      >
        <IconChevron expanded={open} /> AI Prompts
      </button>
      {open && (
        <div className="space-y-1.5 px-2.5 pb-2.5 text-[11.5px] text-[var(--muted)]">
          {imagePrompt && (
            <p>
              <span className="font-medium text-[var(--foreground)]">🖼 Image:</span> {imagePrompt}
            </p>
          )}
          {videoPrompt && (
            <p>
              <span className="font-medium text-[var(--foreground)]">🎥 Video:</span> {videoPrompt}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--accent)]/25 bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-[var(--foreground)]">
      {children}
    </span>
  );
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--border-strong)] bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-[var(--muted)]">
      {children}
    </span>
  );
}

function IconChevron({ expanded, className }: { expanded: boolean; className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      style={{ transform: expanded ? "rotate(180deg)" : undefined, transition: "transform .2s" }}
    >
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPen() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20h9M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
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
