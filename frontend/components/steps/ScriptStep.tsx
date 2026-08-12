"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { AiActionChipRow } from "@/components/ui/AiActionChip";
import { flattenScript, type FlatLine, type GeneratedScript, type RewriteDirective, type StorySituation } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };
const ROLE_TONE: Record<string, "accent" | "success" | "neutral"> = { hook: "accent", body: "neutral", cta: "success" };
const ROLE_MARKER: Record<string, string> = { hook: "var(--accent)", body: "var(--border-strong)", cta: "var(--accent-2)" };

export function ScriptStep({
  script,
  situation,
  onRegenerate,
  onContinue,
  onBack,
  regenerating,
  continuing,
  onRewriteLine,
  rewriting,
}: {
  script: GeneratedScript;
  situation: StorySituation;
  onRegenerate: () => void;
  onContinue: () => void;
  onBack: () => void;
  regenerating: boolean;
  continuing: boolean;
  onRewriteLine: (lineId: string, directive: RewriteDirective) => void;
  rewriting: Record<string, RewriteDirective | undefined>;
}) {
  const lines = flattenScript(script);

  return (
    <Card glow>
      <CardHeader
        title="Cinematic Script"
        subtitle="Full cinematic script for your chosen story — plus literal search tags for Stage 8."
        icon={<IconPen />}
        right={
          <Button variant="secondary" size="sm" onClick={onRegenerate} loading={regenerating}>
            <IconRefresh /> Regenerate
          </Button>
        }
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
            </div>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 whitespace-nowrap text-[12px] font-medium text-[var(--accent-2)] hover:underline"
          >
            Different situation
          </button>
        </div>

        <p className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
          <span>🎙</span> Voiceover for every line happens in Stage 9, after Compliance and Assets are locked in.
        </p>

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
          {line.camera_angle && <MetaChip>📷 {line.camera_angle}</MetaChip>}
          {line.emotion && <MetaChip>🎭 {line.emotion}</MetaChip>}
          {!expanded && (
            <span className="ml-1 flex-1 truncate text-[13px] text-[var(--muted)]">{line.text}</span>
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
                <p className="text-[15px] leading-snug text-[var(--foreground)]">{line.text}</p>
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
                  {line.lighting && <MetaChip>💡 {line.lighting}</MetaChip>}
                </div>
                {line.transition_note && (
                  <p className="text-[12px] text-[var(--muted)]">↳ {line.transition_note}</p>
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

function IconArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
