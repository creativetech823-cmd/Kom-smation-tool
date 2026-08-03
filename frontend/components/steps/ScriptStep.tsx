"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { flattenScript, type GeneratedScript } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };

export function ScriptStep({
  script,
  onRegenerate,
  onContinue,
  onBack,
  regenerating,
  continuing,
}: {
  script: GeneratedScript;
  onRegenerate: () => void;
  onContinue: () => void;
  onBack: () => void;
  regenerating: boolean;
  continuing: boolean;
}) {
  const lines = flattenScript(script);

  return (
    <Card glow className="animate-fade-up">
      <CardHeader
        title="Stage 6 — Script + Visual Tags"
        subtitle="Hook, body, CTA — plus literal search tags for Stage 8."
        icon={<IconPen />}
        right={
          <Button variant="secondary" size="sm" onClick={onRegenerate} loading={regenerating}>
            <IconRefresh /> Regenerate
          </Button>
        }
      />
      <CardBody className="space-y-3">
        {lines.map((line) => (
          <div
            key={line.id}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3.5"
          >
            <div className="mb-2 flex items-center gap-2">
              <Badge tone={line.role === "hook" ? "accent" : line.role === "cta" ? "success" : "neutral"}>
                {ROLE_LABEL[line.role]}
              </Badge>
            </div>
            <p className="text-[15px] leading-snug text-[var(--foreground)]">{line.text}</p>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {line.visual_tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-[var(--border)] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]"
                >
                  🎞 {tag}
                </span>
              ))}
            </div>
          </div>
        ))}

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
