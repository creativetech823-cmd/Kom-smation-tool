"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
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
  const blockers = result.violations.filter((v) => v.severity === "blocker");
  const warnings = result.violations.filter((v) => v.severity === "warning");

  return (
    <Card glow>
      <CardHeader
        title="Compliance Audit"
        subtitle="Independent Haiku pass, separate from the script writer."
        icon={<IconShield />}
        right={<StatusPill status={result.passed ? "pass" : "review"}>{result.passed ? "Passed" : "Blocked"}</StatusPill>}
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

        {result.violations.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-[var(--success)]/25 bg-[var(--success)]/5 px-6 py-10 text-center">
            <StatusPill status="pass" className="text-[13px] px-4 py-1.5">
              All clear
            </StatusPill>
            <p className="text-[13px] text-[var(--muted)]">No claims flagged — this script is ready for assets.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {blockers.length > 0 && (
              <ViolationGroup status="review" title="Needs Review" violations={blockers} />
            )}
            {warnings.length > 0 && <ViolationGroup status="warning" title="Warnings" violations={warnings} />}
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

function ViolationGroup({
  status,
  title,
  violations,
}: {
  status: "review" | "warning";
  title: string;
  violations: ComplianceResult["violations"];
}) {
  return (
    <div className="space-y-2">
      <StatusPill status={status}>
        {title} · {violations.length}
      </StatusPill>
      {violations.map((v, i) => (
        <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
          <p className="mb-1 font-mono text-[12.5px] text-[var(--foreground)]">&quot;{v.phrase}&quot;</p>
          <p className="text-[13px] text-[var(--muted)]">{v.reason}</p>
        </div>
      ))}
    </div>
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
