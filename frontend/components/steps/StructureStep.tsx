"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { StructuredProduct } from "@/lib/types";

function confidenceTone(c: number): "success" | "warning" | "danger" {
  if (c >= 0.7) return "success";
  if (c >= 0.4) return "warning";
  return "danger";
}

export function StructureStep({
  data,
  onContinue,
  onBack,
  loading,
}: {
  data: StructuredProduct;
  onContinue: () => void;
  onBack: () => void;
  loading: boolean;
}) {
  const tone = confidenceTone(data.confidence);

  return (
    <Card glow className="animate-fade-up">
      <CardHeader
        title="Stage 3 — Structured Product Data"
        subtitle="Claude's read of the raw input. Review before scripting starts."
        icon={<IconLayers />}
        right={
          <Badge tone={tone}>{Math.round(data.confidence * 100)}% confidence</Badge>
        }
      />
      <CardBody className="space-y-5">
        {data.missing_fields.length > 0 && (
          <div className="rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-4 py-3 text-[13px] text-[var(--warning)]">
            Missing or unclear: {data.missing_fields.join(", ")}
          </div>
        )}

        <div className="grid grid-cols-2 gap-5">
          <InfoBlock label="Product">{data.product_name}</InfoBlock>
          <InfoBlock label="Audience">{data.target_audience}</InfoBlock>
        </div>

        <InfoBlock label="USP">{data.usp || <Empty />}</InfoBlock>
        <InfoBlock label="Tone">{data.tone || <Empty />}</InfoBlock>

        <div>
          <p className="mb-2 text-[13px] font-medium text-[var(--muted)]">Ingredients</p>
          <div className="flex flex-wrap gap-1.5">
            {data.ingredients.length ? (
              data.ingredients.map((ing) => (
                <Badge key={ing} tone="accent">
                  {ing}
                </Badge>
              ))
            ) : (
              <Empty />
            )}
          </div>
        </div>

        <div>
          <p className="mb-2 text-[13px] font-medium text-[var(--muted)]">Key benefits</p>
          <ul className="space-y-1.5">
            {data.key_benefits.length ? (
              data.key_benefits.map((b) => (
                <li key={b} className="flex items-center gap-2 text-[14px] text-[var(--foreground)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-2)]" />
                  {b}
                </li>
              ))
            ) : (
              <Empty />
            )}
          </ul>
        </div>

        <div className="flex justify-between pt-2">
          <Button variant="ghost" onClick={onBack}>
            ← Back
          </Button>
          <Button onClick={onContinue} loading={loading}>
            Generate script
            <IconArrow />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function InfoBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[13px] font-medium text-[var(--muted)]">{label}</p>
      <p className="text-[14px] text-[var(--foreground)]">{children}</p>
    </div>
  );
}

function Empty() {
  return <span className="text-[13px] italic text-[var(--muted)]">none detected</span>;
}

function IconLayers() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M2 12l10 5 10-5M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
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
