"use client";

import { motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { audioFileUrl } from "@/lib/api";
import { renderBold } from "@/lib/renderBold";
import type { FlatLine, VoiceoverResult } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };
const ROLE_ACCENT: Record<string, string> = { hook: "var(--accent)", body: "var(--border-strong)", cta: "var(--accent-2)" };

const listVariants = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } };
const rowVariants = { hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.25 } } };

export function VoiceoverStep({
  lines,
  voiceovers,
  loadingIds,
  onRegenerateLine,
  onContinue,
  onBack,
  continuing,
}: {
  lines: FlatLine[];
  voiceovers: Record<string, VoiceoverResult | undefined>;
  loadingIds: Set<string>;
  onRegenerateLine: (id: string) => void;
  onContinue: () => void;
  onBack: () => void;
  continuing: boolean;
}) {
  const allReady = lines.every((l) => voiceovers[l.id] && !loadingIds.has(l.id));

  return (
    <Card glow>
      <CardHeader
        title="Hindi Voiceover"
        subtitle="Each line translated to spoken Hindi and synthesized (gTTS)."
        icon={<IconMic />}
      />
      <CardBody>
        <motion.div variants={listVariants} initial="hidden" animate="show" className="space-y-2.5">
          {lines.map((line) => {
            const vo = voiceovers[line.id];
            const isLoading = loadingIds.has(line.id);
            return (
              <motion.div
                key={line.id}
                variants={rowVariants}
                style={{ borderLeftColor: ROLE_ACCENT[line.role], borderLeftWidth: 3 }}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3.5"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Badge tone={line.role === "hook" ? "accent" : line.role === "cta" ? "success" : "neutral"}>
                      {ROLE_LABEL[line.role]}
                    </Badge>
                    {vo && (
                      <span className="text-[11px] text-[var(--muted)]">{vo.duration_seconds}s</span>
                    )}
                  </div>
                  <button
                    onClick={() => onRegenerateLine(line.id)}
                    disabled={isLoading}
                    className="flex h-6 w-6 items-center justify-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--foreground)]/[0.06] hover:text-[var(--foreground)] disabled:opacity-40"
                    title="Regenerate this voiceover"
                  >
                    <IconRefresh />
                  </button>
                </div>

                <p className="text-[13px] text-[var(--muted)]">{renderBold(line.text)}</p>

                {isLoading ? (
                  <div className="animate-shimmer mt-2.5 h-10 w-full rounded-lg" />
                ) : vo ? (
                  <div className="mt-2.5 space-y-2">
                    <p className="text-[15px] leading-snug text-[var(--foreground)]">{vo.hindi_text}</p>
                    <audio
                      controls
                      src={audioFileUrl(vo.audio_path)}
                      className="h-9 w-full"
                    />
                  </div>
                ) : null}
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

function IconMic() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="9" y="2" width="6" height="12" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M5 11a7 7 0 0014 0M12 18v4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
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
