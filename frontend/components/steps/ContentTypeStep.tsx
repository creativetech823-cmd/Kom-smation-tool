"use client";

import { motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { angleAccent, angleEmoji } from "@/lib/creativeAngles";
import type { ContentType, StorySituation } from "@/lib/types";

const OPTIONS: { type: ContentType; emoji: string; title: string; description: string }[] = [
  {
    type: "video",
    emoji: "\u{1F3A5}",
    title: "Video",
    description: "A scripted video — an ad, podcast, whiteboard explainer, reel, or any other motion format.",
  },
  {
    type: "static",
    emoji: "\u{1F5BC}\u{FE0F}",
    title: "Static",
    description: "A single graphic or slide set — an Instagram post, carousel, banner, or other still creative.",
  },
];

export function ContentTypeStep({
  situation,
  angle,
  onSelect,
  onBack,
}: {
  situation: StorySituation;
  angle: string;
  onSelect: (type: ContentType) => void;
  onBack: () => void;
}) {
  return (
    <Card glow>
      <CardHeader
        title="What do you want to create?"
        subtitle={angle ? "Same story, same angle — pick the format of the final creative." : "Pick the format of the final creative."}
        icon={<IconSparkles />}
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
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {OPTIONS.map((opt, i) => (
            <motion.button
              key={opt.type}
              type="button"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.05 }}
              onClick={() => onSelect(opt.type)}
              className="group relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 text-left transition-all hover:-translate-y-0.5 hover:border-[var(--accent)]/50 hover:shadow-[0_16px_40px_-20px_var(--shadow-color)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              <span className="absolute inset-0 bg-[var(--accent-soft)] opacity-0 transition-opacity group-hover:opacity-100" />
              <div className="relative">
                <span className="text-[32px]">{opt.emoji}</span>
                <h3 className="mt-3 text-[17px] font-semibold text-[var(--foreground)]">{opt.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--muted)]">{opt.description}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-[12.5px] font-medium text-[var(--accent-2)]">
                  Choose {opt.title} <IconArrow />
                </span>
              </div>
            </motion.button>
          ))}
        </div>

        <div className="flex justify-between pt-1">
          <Button variant="ghost" onClick={onBack}>
            {angle ? "← Back to angles" : "← Back"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function IconArrow() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconSparkles() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
