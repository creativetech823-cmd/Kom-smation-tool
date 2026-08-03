"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { ComplianceResult } from "@/lib/types";

export function ComplianceStep({
  result,
  onContinue,
  onBack,
  onRegenerateScript,
  regenerating,
  continuing,
}: {
  result: ComplianceResult;
  onContinue: () => void;
  onBack: () => void;
  onRegenerateScript: () => void;
  regenerating: boolean;
  continuing: boolean;
}) {
  return (
    <Card glow className="animate-fade-up">
      <CardHeader
        title="Stage 7 — Compliance Audit"
        subtitle="Independent Haiku pass, separate from the script writer."
        icon={<IconShield />}
        right={
          <Badge tone={result.passed ? "success" : "danger"}>
            {result.passed ? "Passed" : "Blocked"}
          </Badge>
        }
      />
      <CardBody className="space-y-4">
        <div
          className={`rounded-xl border px-4 py-3 text-[13px] ${
            result.passed
              ? "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]"
              : "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]"
          }`}
        >
          {result.notes}
        </div>

        {result.violations.length > 0 && (
          <div className="space-y-2">
            {result.violations.map((v, i) => (
              <div
                key={i}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3"
              >
                <div className="mb-1 flex items-center gap-2">
                  <Badge tone={v.severity === "blocker" ? "danger" : "warning"}>{v.severity}</Badge>
                  <span className="font-mono text-[12.5px] text-[var(--foreground)]">
                    &quot;{v.phrase}&quot;
                  </span>
                </div>
                <p className="text-[13px] text-[var(--muted)]">{v.reason}</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-between pt-2">
          <Button variant="ghost" onClick={onBack}>
            ← Back
          </Button>
          {result.passed ? (
            <Button onClick={onContinue} loading={continuing}>
              Source assets
              <IconArrow />
            </Button>
          ) : (
            <Button variant="danger" onClick={onRegenerateScript} loading={regenerating}>
              Regenerate script
            </Button>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function IconShield() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 2l8 3v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5l8-3z"
        stroke="currentColor"
        strokeWidth="1.8"
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
