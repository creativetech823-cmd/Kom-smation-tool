"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { RenderResult } from "@/lib/types";

export function RenderStep({
  rendering,
  renderResult,
  videoUrl,
  approved,
  onRender,
  onApprove,
  onBack,
}: {
  rendering: boolean;
  renderResult: RenderResult | null;
  videoUrl: string | null;
  approved: boolean;
  onRender: () => void;
  onApprove: () => void;
  onBack: () => void;
}) {
  return (
    <Card glow>
      <CardHeader
        title="Render & Review"
        subtitle="Final render from the Remotion mold, then human approval."
        icon={<IconClapper />}
        right={approved && <Badge tone="success">Approved</Badge>}
      />
      <CardBody>
        <div className="flex flex-col items-center gap-5">
          <div className="relative flex aspect-[9/16] w-full max-w-[280px] items-center justify-center overflow-hidden rounded-2xl border border-[var(--border-strong)] bg-black">
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                autoPlay
                loop
                className="h-full w-full object-cover"
              />
            ) : rendering ? (
              <div className="flex flex-col items-center gap-3 text-[var(--muted)]">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-[var(--accent)]" />
                <span className="text-[13px]">Rendering with Remotion…</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 px-6 text-center text-[var(--muted)]">
                <IconClapperBig />
                <span className="text-[13px]">No render yet</span>
              </div>
            )}
          </div>

          {renderResult && (
            <p className="text-[12px] text-[var(--muted)]">
              {renderResult.duration_seconds}s · saved to{" "}
              <span className="font-mono text-[11px]">{renderResult.output_path}</span>
            </p>
          )}

          <div className="flex w-full justify-between pt-2">
            <Button variant="ghost" onClick={onBack} disabled={rendering}>
              ← Back
            </Button>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={onRender} loading={rendering}>
                {videoUrl ? "Re-render" : "Render video"}
              </Button>
              {videoUrl && !approved && (
                <Button onClick={onApprove}>
                  Approve <IconCheck />
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function IconClapper() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M4 8l2-4h3l-2 4M9 8l2-4h3l-2 4M14 8l2-4h3l-2 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="3" y="8" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function IconClapperBig() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" opacity="0.4">
      <path d="M4 8l2-4h3l-2 4M9 8l2-4h3l-2 4M14 8l2-4h3l-2 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <rect x="3" y="8" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
