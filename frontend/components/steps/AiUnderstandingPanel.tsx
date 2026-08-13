"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ConfidenceRing } from "@/components/ui/ConfidenceRing";
import { AiWorkingChecklist } from "@/components/ui/AiWorkingChecklist";
import type { StructuredProduct } from "@/lib/types";

const LOADING_STEPS = [
  { id: "read", label: "Reading description" },
  { id: "ingredients", label: "Identifying ingredients & USP" },
  { id: "audience", label: "Finding audience fit" },
  { id: "confidence", label: "Scoring confidence" },
];

export type ActivityEntry = { id: string; label: string; tone: "info" | "success" | "error"; ts: number };

function ActivityFeed({ entries }: { entries: ActivityEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <div className="mb-3 space-y-1.5 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-3">
      <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-2)] animate-pulse-dot" />
        AI Activity
      </p>
      <div className="space-y-1">
        {entries.slice(0, 5).map((entry, i) => (
          <p
            key={entry.id}
            className={`text-[12px] leading-snug ${
              i === 0
                ? entry.tone === "error"
                  ? "text-[var(--danger)]"
                  : entry.tone === "success"
                  ? "text-[var(--success)]"
                  : "text-[var(--foreground)]"
                : "text-[var(--muted)]"
            }`}
          >
            {entry.label}
          </p>
        ))}
      </div>
    </div>
  );
}

export function AiUnderstandingPanel({
  data,
  loading,
  onContinue,
  continueLoading,
  activityLog = [],
}: {
  data: StructuredProduct | null;
  loading: boolean;
  onContinue: () => void;
  continueLoading: boolean;
  activityLog?: ActivityEntry[];
}) {
  const state: "placeholder" | "loading" | "populated" = loading ? "loading" : data ? "populated" : "placeholder";

  return (
    <Card glow>
      <CardHeader
        title="AI Understanding"
        subtitle="Our AI is analyzing your product information in real time."
        icon={<IconBrain />}
        right={
          <div className="flex items-center gap-3">
            <LiveBadge state={state} />
            <ConfidenceRing value={data?.confidence ?? 0} />
          </div>
        }
      />
      <CardBody className="space-y-3">
        <ActivityFeed entries={activityLog} />

        {state === "placeholder" && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--surface-2)]/40 px-6 py-14 text-center">
            <span className="text-[22px]">✨</span>
            <p className="text-[13px] text-[var(--muted)]">
              Fill in the product details on the left — I&apos;ll show what I understand here.
            </p>
          </div>
        )}

        {state === "loading" && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-4 py-6">
            <AiWorkingChecklist steps={LOADING_STEPS} active={loading} />
          </div>
        )}

        {state === "populated" && data && (
          <>
            <Row icon={<IconFactory />} label="Industry">
              {data.industry || <Empty />}
            </Row>
            <Row icon={<IconUsers />} label="Target Audience">
              {data.target_audience || <Empty />}
            </Row>
            <Row icon={<IconSmile />} label="Tone">
              <span className="text-[var(--warning)]">{data.tone || <Empty />}</span>
            </Row>
            <Row icon={<IconGem />} label="USP">
              {data.usp || <Empty />}
            </Row>
            <Row icon={<IconAlert />} label="Pain Points">
              <ChipList items={data.pain_points} />
            </Row>
            <Row icon={<IconCheck />} label="Benefits">
              <ChipList items={data.key_benefits} />
            </Row>
            <Row icon={<IconTarget />} label="Marketing Angle">
              {data.marketing_angle || <Empty />}
            </Row>
            <Row icon={<IconHeart />} label="Key Emotions">
              <ChipList items={data.key_emotions} />
            </Row>
            <Row icon={<IconHash />} label="Keywords">
              <ChipList items={data.keywords} />
            </Row>
            <Row icon={<IconLeaf />} label="Ingredients">
              <ChipList items={data.ingredients} />
            </Row>

            {data.missing_fields.length > 0 && (
              <div className="rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-4 py-3.5">
                <p className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-[var(--accent)]">
                  <span>💡</span> AI suggestion
                </p>
                <p className="text-[12px] text-[var(--foreground)]">
                  Consider clarifying: {data.missing_fields.join(", ")} — more detail here will sharpen every
                  later stage.
                </p>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button onClick={onContinue} loading={continueLoading}>
                Generate story ideas
                <IconArrow />
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function LiveBadge({ state }: { state: "placeholder" | "loading" | "populated" }) {
  const label = state === "populated" ? "Synced" : state === "loading" ? "Live" : "Waiting";
  const dotClass =
    state === "populated" ? "bg-[var(--success)]" : state === "loading" ? "bg-[var(--accent)] animate-pulse-dot" : "bg-[var(--muted)]";
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-[var(--border-strong)] bg-white/[0.03] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      {label}
    </span>
  );
}

function Row({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-3">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] text-[var(--accent-2)]">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">{label}</p>
        <div className="mt-1 text-[13px] leading-snug text-[var(--foreground)]">{children}</div>
      </div>
    </div>
  );
}

function ChipList({ items }: { items: string[] }) {
  if (!items.length) return <Empty />;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-[var(--border)] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--foreground)]"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function Empty() {
  return <span className="italic text-[var(--muted)]">none detected</span>;
}

function IconArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconBrain() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 4a3 3 0 00-3 3 3 3 0 00-2 5 3 3 0 002 5 3 3 0 003 3M9 4a3 3 0 013 3v10a3 3 0 01-3 3M9 4v16"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconFactory() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M3 21V10l6 4V10l6 4V6l6 4v11H3z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconSmile() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8.5 14.5c1 1 2.2 1.5 3.5 1.5s2.5-.5 3.5-1.5M9 9.5v.01M15 9.5v.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconGem() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M6 3h12l3 6-9 12L3 9l3-6z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M3 9h18M9 3l3 6-3 12M15 3l-3 6 3 12" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M12 3.5L22 20H2L12 3.5z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12 10v4.5M12 17.5v.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 12.5l2.5 2.5L16 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconTarget() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="0.8" fill="currentColor" />
    </svg>
  );
}

function IconHeart() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20s-7.5-4.5-9.5-9A5 5 0 0112 6a5 5 0 019.5 5c-2 4.5-9.5 9-9.5 9z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconHash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 9h14M5 15h14M10 4L8 20M16 4l-2 16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconLeaf() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M20 4S9 3 5 9s-1 12-1 12 8 2 12-4 4-13 4-13z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M4 20l6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
