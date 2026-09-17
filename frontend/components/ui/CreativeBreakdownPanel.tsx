"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { CreativeBreakdown, CreativeQualityAssessment, CreativeQualityDimension } from "@/lib/types";

/** Both sections render nothing at all when their data is absent (e.g. a
 * narrow regeneration, which has no creative pre-stage chain to draw from)
 * — no placeholder card, no error, no loading state, since this data is
 * never fetched separately; it either arrived with the script or it didn't. */
export function CreativeBreakdownSection({
  breakdown,
  qualityAssessment,
}: {
  breakdown?: CreativeBreakdown | null;
  qualityAssessment?: CreativeQualityAssessment | null;
}) {
  if (!breakdown && !qualityAssessment) return null;
  return (
    <div className="space-y-4">
      {breakdown && <CreativeBreakdownCard breakdown={breakdown} />}
      {qualityAssessment && <CreativeQualityAssessmentCard assessment={qualityAssessment} />}
    </div>
  );
}

function isUnavailableText(value: string): boolean {
  return /not available|not scored/i.test(value);
}

/** Display-only formatting of an internal issue code ("title_story_mismatch"
 * -> "Title story mismatch") — never changes or adds to the underlying
 * information, only makes the existing string readable instead of raw
 * snake_case jargon. */
function humanizeCode(code: string): string {
  const spaced = code.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function BreakdownRow({ label, value }: { label: string; value: string }) {
  const unavailable = !value || isUnavailableText(value);
  return (
    <div className="py-2.5 first:pt-0 last:pb-0">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <p className={cn("mt-0.5 text-[13px] leading-snug", unavailable ? "italic text-[var(--muted)]" : "text-[var(--foreground)]")}>
        {unavailable ? "Not available for this script" : value}
      </p>
    </div>
  );
}

function CreativeBreakdownCard({ breakdown }: { breakdown: CreativeBreakdown }) {
  return (
    <Card>
      <CardHeader
        title="Creative Breakdown"
        subtitle="Why this script was built this way — grounded in the actual creative decisions behind it."
        icon={<IconLightbulb />}
      />
      <CardBody className="divide-y divide-[var(--border)]">
        <BreakdownRow label="Why this hook?" value={breakdown.hook_reason} />
        <BreakdownRow label="Why this creative territory?" value={breakdown.territory_reason} />
        <BreakdownRow label="Human insight" value={breakdown.human_insight} />
        <BreakdownRow label="Behavioral tension" value={breakdown.behavioral_tension} />
        <BreakdownRow label="Why this situation?" value={breakdown.situation_reason} />
        <BreakdownRow label="Why this product role?" value={breakdown.product_entry_reason} />
        <BreakdownRow label="Why this narrative device?" value={breakdown.narrative_device_reason} />
        <BreakdownRow label="Why this payoff?" value={breakdown.payoff_reason} />
        <BreakdownRow label="What makes it memorable?" value={breakdown.memorability_reason} />
        <BreakdownRow label="Visually executable" value={breakdown.visual_executability_reason} />
        <BreakdownRow label="What makes it distinctive?" value={breakdown.distinctiveness_reason} />

        {breakdown.claims_avoided.length > 0 && (
          <div className="py-2.5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">Claim / brand safety</div>
            <ul className="mt-1 space-y-1">
              {breakdown.claims_avoided.map((claim, i) => (
                <li key={i} className="text-[13px] text-[var(--foreground)]">
                  <span className="text-[var(--danger)]">🚫</span> {claim}
                </li>
              ))}
            </ul>
          </div>
        )}

        {breakdown.remaining_weaknesses.length > 0 && (
          <div className="py-2.5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">Remaining creative weaknesses</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {breakdown.remaining_weaknesses.map((w, i) => (
                <Badge key={i} tone="warning">{humanizeCode(w)}</Badge>
              ))}
            </div>
          </div>
        )}

        {!breakdown.fully_grounded && (
          <p className="pt-2.5 text-[11.5px] text-[var(--muted)]">
            Some of the above weren&apos;t available for this script — usually because it was a targeted
            regeneration rather than a fresh script.
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function scoreTone(name: string, score: number): "success" | "warning" | "danger" | "neutral" {
  // Claim Safety / Genericness Risk are 0.0-1.0 (1 = good); every other
  // dimension is 1-5 — both real scales returned by the backend as-is, only
  // the color threshold is a display choice, not an invented number.
  if (name === "Claim Safety" || name === "Genericness Risk") {
    return score >= 1 ? "success" : "danger";
  }
  if (score >= 4) return "success";
  if (score <= 2) return "warning";
  return "neutral";
}

function formatScore(name: string, score: number): string {
  if (name === "Claim Safety" || name === "Genericness Risk") {
    return score >= 1 ? "Clear" : "Flagged";
  }
  return `${score}/5`;
}

function QualityDimensionRow({ dimension }: { dimension: CreativeQualityDimension }) {
  const unscored = dimension.score === null;
  const hasSource = Boolean(dimension.source_creative_decision) && !isUnavailableText(dimension.source_creative_decision);
  return (
    <div className="py-2.5 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] font-medium text-[var(--foreground)]">{dimension.name}</span>
        {unscored ? (
          <Badge tone="neutral">Not scored</Badge>
        ) : (
          <Badge tone={scoreTone(dimension.name, dimension.score as number)}>
            {formatScore(dimension.name, dimension.score as number)}
          </Badge>
        )}
      </div>
      <p className={cn("mt-0.5 text-[12.5px] leading-snug", unscored ? "italic text-[var(--muted)]" : "text-[var(--muted)]")}>
        {dimension.evidence}
      </p>
      {hasSource && (
        <details className="mt-1 text-[12px]">
          <summary className="cursor-pointer select-none text-[var(--accent-2)] hover:underline">
            Source creative decision
          </summary>
          <p className="mt-1 text-[var(--muted)]">{dimension.source_creative_decision}</p>
        </details>
      )}
    </div>
  );
}

function CreativeQualityAssessmentCard({ assessment }: { assessment: CreativeQualityAssessment }) {
  return (
    <Card>
      <CardHeader
        title="Creative Quality Assessment"
        subtitle="Structured dimensions, each traced to an actual creative decision — not a single overall score."
        icon={<IconGauge />}
        right={
          assessment.overall_passed !== null && (
            <Badge tone={assessment.overall_passed ? "success" : "warning"}>
              {assessment.overall_passed ? "Passed review" : "Flagged for review"}
            </Badge>
          )
        }
      />
      <CardBody className="divide-y divide-[var(--border)]">
        {assessment.dimensions.map((d) => (
          <QualityDimensionRow key={d.name} dimension={d} />
        ))}
      </CardBody>
    </Card>
  );
}

function IconLightbulb() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 18h6M10 21h4M12 3a6 6 0 00-4 10.5c.7.7 1 1.3 1 2.5h6c0-1.2.3-1.8 1-2.5A6 6 0 0012 3z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconGauge() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 14l3-3M4 14a8 8 0 1116 0M4 14h1M19 14h1M12 6v1"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
