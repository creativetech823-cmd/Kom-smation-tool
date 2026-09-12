"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { StagedProgress, type ProgressStage } from "@/components/ui/StagedProgress";
import { KnowledgeSourcesChecklist } from "@/components/ui/KnowledgeSourcesChecklist";
import { ReferenceMaterialsPanel } from "@/components/steps/ReferenceMaterialsPanel";
import { ApiError, autofillProduct, fetchUrlContent } from "@/lib/api";
import type { ProductInput, ReferenceMaterial, SourceType } from "@/lib/types";

const SOURCE_OPTIONS: { value: SourceType; label: string; hint: string; icon: React.ReactNode }[] = [
  { value: "description", label: "Description", hint: "Paste or type product details", icon: <IconDoc /> },
  { value: "url", label: "Website URL", hint: "AI reads and understands the page", icon: <IconGlobe /> },
  { value: "none", label: "Manual only", hint: "No source — enter ingredients + USP", icon: <IconEdit /> },
];

const URL_STAGES: ProgressStage[] = [
  { id: "fetch", label: "Fetching website..." },
  { id: "extract", label: "Extracting content..." },
  { id: "understand", label: "Understanding product..." },
];

const DESCRIPTION_MAX = 5000;

export function InputStep({
  onSubmit,
  loading,
  error,
  onImproveDescription,
  improvingDescription,
  referenceMaterials,
  uploadingMaterialIds,
  onAddReferenceFiles,
  onAddReferenceUrl,
  onRemoveReferenceMaterial,
  sourceUrlRawText,
  onSourceUrlRawTextChange,
  onActivity,
  initialProductName,
  initialCategory,
}: {
  onSubmit: (input: ProductInput, category: string) => void;
  loading: boolean;
  error: string | null;
  onImproveDescription?: (text: string) => Promise<string>;
  improvingDescription?: boolean;
  referenceMaterials: ReferenceMaterial[];
  uploadingMaterialIds: Set<string>;
  onAddReferenceFiles: (files: FileList | File[]) => void;
  onAddReferenceUrl: (url: string) => void;
  onRemoveReferenceMaterial: (id: string) => void;
  sourceUrlRawText: string | undefined;
  onSourceUrlRawTextChange: (text: string | undefined) => void;
  onActivity: (label: string, tone?: "info" | "success" | "error") => void;
  initialProductName?: string;
  initialCategory?: string;
}) {
  const [productName, setProductName] = useState(() => initialProductName ?? "");
  const [targetAudience, setTargetAudience] = useState("");
  const [category, setCategory] = useState(() => initialCategory ?? "");
  const [sourceType, setSourceType] = useState<SourceType>("description");
  const [sourceDescription, setSourceDescription] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [manualIngredients, setManualIngredients] = useState("");
  const [manualUsp, setManualUsp] = useState("");

  const [urlStatus, setUrlStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [urlStageIndex, setUrlStageIndex] = useState(0);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [urlSummary, setUrlSummary] = useState<string | null>(null);
  const analyzedUrlRef = useRef<string | null>(null);

  async function runUrlAnalysis(url: string) {
    if (analyzedUrlRef.current === url && urlStatus === "done") return;
    analyzedUrlRef.current = url;
    setUrlStatus("loading");
    setUrlStageIndex(0);
    setUrlError(null);
    onActivity(`Fetching ${url}...`);
    try {
      const fetched = await fetchUrlContent({ url });
      onSourceUrlRawTextChange(fetched.raw_text);
      setUrlStageIndex(1);
      onActivity("Extracting content...");
      setUrlStageIndex(2);
      onActivity("Understanding product...");
      const suggestion = await autofillProduct({ raw_text: fetched.raw_text, source_url: url });
      if (suggestion.product_name) setProductName(suggestion.product_name);
      if (suggestion.target_audience) setTargetAudience(suggestion.target_audience);
      if (suggestion.product_category) setCategory(suggestion.product_category);
      if (suggestion.source_description) setSourceDescription(suggestion.source_description);
      setUrlSummary(suggestion.source_description || fetched.title || "Website analyzed.");
      setUrlStageIndex(3);
      setUrlStatus("done");
      onActivity("Understood product ✓", "success");
    } catch (e) {
      analyzedUrlRef.current = null;
      setUrlStatus("error");
      setUrlError(e instanceof ApiError ? e.message : "Couldn't analyze that website.");
      onActivity("Website analysis failed", "error");
    }
  }

  useEffect(() => {
    if (sourceType !== "url") return;
    const trimmed = sourceUrl.trim();
    if (!/^https?:\/\/.+/i.test(trimmed)) return;
    if (analyzedUrlRef.current === trimmed) return;
    if (urlStatus === "loading") return;
    const t = setTimeout(() => runUrlAnalysis(trimmed), 900);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceUrl, sourceType]);

  function handleAddFiles(files: FileList | File[]) {
    onAddReferenceFiles(files);
  }

  const hasAnalyzedReference = referenceMaterials.some((m) => m.analysis === "analyzed");

  const canSubmit =
    productName.trim() &&
    targetAudience.trim() &&
    category.trim() &&
    (sourceType === "description"
      ? sourceDescription.trim()
      : sourceType === "url"
      ? sourceUrl.trim()
      : (manualIngredients.trim() && manualUsp.trim()) || hasAnalyzedReference);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(
      {
        product_name: productName,
        target_audience: targetAudience,
        source_type: sourceType,
        source_description: sourceType === "description" ? sourceDescription : undefined,
        source_url: sourceType === "url" ? sourceUrl : undefined,
        source_url_raw_text: sourceType === "url" ? sourceUrlRawText : undefined,
        manual_ingredients: sourceType === "none" ? manualIngredients : undefined,
        manual_usp: sourceType === "none" ? manualUsp : undefined,
        reference_materials: referenceMaterials,
      },
      category
    );
  }

  async function handleImprove() {
    if (!onImproveDescription || !sourceDescription.trim()) return;
    const improved = await onImproveDescription(sourceDescription);
    setSourceDescription(improved);
  }

  return (
    <Card glow>
      <CardHeader
        title="Let's understand your product"
        subtitle="Everything you enter here becomes the foundation for stories, scripts, and assets."
        icon={<IconSparkle />}
      />
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <FieldLabel icon={<IconBox />}>Product name</FieldLabel>
              <Input
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="GreenLeaf Herbal Tea"
                autoComplete="off"
              />
            </div>
            <div>
              <FieldLabel icon={<IconUsers />}>Target audience</FieldLabel>
              <Input
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="Health-conscious millennials"
                autoComplete="off"
              />
            </div>
          </div>

          <div>
            <FieldLabel icon={<IconTag />}>Product category</FieldLabel>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="beverages, supplements, finance..."
              autoComplete="off"
            />
            <p className="mt-1 text-[12px] text-[var(--muted)]">
              Used to select the right compliance rules in Stage 7.
            </p>
          </div>

          <div>
            <FieldLabel icon={<IconGlobe />}>Source</FieldLabel>
            <div className="grid grid-cols-3 gap-2">
              {SOURCE_OPTIONS.map((opt) => {
                const selected = sourceType === opt.value;
                return (
                  <motion.button
                    key={opt.value}
                    type="button"
                    onClick={() => setSourceType(opt.value)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`relative rounded-xl border px-3 py-2.5 text-left text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                      selected
                        ? "glow-border bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {selected && (
                      <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--accent)] text-[var(--on-accent)]">
                        <svg width="9" height="9" viewBox="0 0 24 24" fill="none">
                          <path d="M5 12l5 5L20 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </span>
                    )}
                    <div className="mb-1 flex h-4 w-4 items-center justify-center">{opt.icon}</div>
                    <div className="font-medium">{opt.label}</div>
                    <div className="mt-0.5 text-[11px] opacity-80">{opt.hint}</div>
                  </motion.button>
                );
              })}
            </div>
          </div>

          {sourceType === "description" && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <FieldLabel icon={<IconDoc />} noMargin>
                  Product description
                </FieldLabel>
                {onImproveDescription && (
                  <button
                    type="button"
                    onClick={handleImprove}
                    disabled={!sourceDescription.trim() || improvingDescription}
                    className="flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent-soft)]/80 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {improvingDescription ? (
                      <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-[var(--accent)]/30 border-t-[var(--accent)]" />
                    ) : (
                      <span>✨</span>
                    )}
                    Improve with AI
                  </button>
                )}
              </div>
              <Textarea
                rows={4}
                maxLength={DESCRIPTION_MAX}
                value={sourceDescription}
                onChange={(e) => setSourceDescription(e.target.value)}
                placeholder="Organic tulsi, ginger, and lemongrass tea sourced from Himalayan farms..."
                autoComplete="off"
              />
              <p className="mt-1 text-right text-[11px] text-[var(--muted)]">
                {sourceDescription.length} / {DESCRIPTION_MAX}
              </p>
            </div>
          )}

          {sourceType === "url" && (
            <div className="space-y-2.5">
              <FieldLabel icon={<IconGlobe />}>Website URL</FieldLabel>
              <Input
                value={sourceUrl}
                onChange={(e) => {
                  setSourceUrl(e.target.value);
                  if (urlStatus !== "idle") {
                    setUrlStatus("idle");
                    onSourceUrlRawTextChange(undefined);
                    setUrlSummary(null);
                  }
                }}
                placeholder="https://example.com/product"
                autoComplete="off"
              />
              <p className="text-[11px] text-[var(--muted)]">
                Paste a link — the AI fetches and reads the page automatically.
              </p>

              {urlStatus === "loading" && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-4 py-4">
                  <StagedProgress stages={URL_STAGES} currentIndex={urlStageIndex} />
                </div>
              )}

              {urlStatus === "error" && urlError && (
                <ErrorCard message={urlError} onRetry={() => runUrlAnalysis(sourceUrl.trim())} />
              )}

              {urlStatus === "done" && urlSummary && (
                <div className="rounded-xl border border-[var(--success)]/25 bg-[var(--success)]/[0.06] px-4 py-3">
                  <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--success)]">
                    <span>✓</span> Auto-filled from website
                  </p>
                  <p className="text-[12px] leading-snug text-[var(--foreground)]">{urlSummary}</p>
                  <p className="mt-1 text-[11px] text-[var(--muted)]">Edit any field above if needed.</p>
                </div>
              )}
            </div>
          )}

          {sourceType === "none" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <FieldLabel icon={<IconEdit />}>Ingredients</FieldLabel>
                <Textarea
                  rows={3}
                  value={manualIngredients}
                  onChange={(e) => setManualIngredients(e.target.value)}
                  placeholder="tulsi, ginger, lemongrass"
                  autoComplete="off"
                />
              </div>
              <div>
                <FieldLabel icon={<IconEdit />}>USP</FieldLabel>
                <Textarea
                  rows={3}
                  value={manualUsp}
                  onChange={(e) => setManualUsp(e.target.value)}
                  placeholder="Caffeine-free, Himalayan sourced"
                  autoComplete="off"
                />
              </div>
              {hasAnalyzedReference && !manualIngredients.trim() && !manualUsp.trim() && (
                <p className="col-span-2 text-[12px] text-[var(--muted)]">
                  No ingredients/USP entered — that&apos;s fine, your reference materials below are analyzed
                  ones will be used instead.
                </p>
              )}
            </div>
          )}

          <div className="border-t border-[var(--border)] pt-4">
            <ReferenceMaterialsPanel
              materials={referenceMaterials}
              uploadingIds={uploadingMaterialIds}
              onAddFiles={handleAddFiles}
              onAddUrl={onAddReferenceUrl}
              onRemove={onRemoveReferenceMaterial}
            />
          </div>

          <KnowledgeSourcesChecklist
            hasDescription={sourceType === "description" && sourceDescription.trim().length > 0}
            urlState={sourceType === "url" ? (urlStatus === "done" ? "active" : urlStatus === "loading" ? "pending" : "absent") : "absent"}
            referenceMaterials={referenceMaterials}
          />

          <div className="flex items-start gap-2.5 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 text-[12px] text-[var(--muted)]">
            <span className="mt-0.5">💡</span>
            <p>
              <span className="font-medium text-[var(--foreground)]">Tip:</span> the more detail you
              provide — description, website, or reference files — the more accurate the AI&apos;s
              understanding of your product will be.
            </p>
          </div>

          {error && (
            <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <p className="text-[12px] text-[var(--muted)]">
              Est. time <span className="text-[var(--foreground)]">~5s</span> · Next:{" "}
              <span className="text-[var(--foreground)]">AI Understanding</span>
            </p>
            <Button type="submit" disabled={!canSubmit} loading={loading}>
              Continue
              <IconArrow />
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function FieldLabel({
  icon,
  children,
  noMargin,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  noMargin?: boolean;
}) {
  return (
    <label className={`flex items-center gap-1.5 text-[13px] font-medium text-[var(--muted)] ${noMargin ? "" : "mb-1.5"}`}>
      <span className="text-[var(--accent-2)]">{icon}</span>
      {children}
    </label>
  );
}

function IconSparkle() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z"
        fill="currentColor"
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

function IconBox() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M21 8l-9-5-9 5 9 5 9-5z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M3 8v8l9 5 9-5V8M12 13v8" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M16 5.5a3 3 0 010 5.8M20 20c0-2.6-1.8-4.8-4-5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconTag() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M12.6 2.6l8.8 8.8a2 2 0 010 2.8l-6.8 6.8a2 2 0 01-2.8 0l-8.8-8.8V3h8.6z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="7.5" cy="7.5" r="1.5" fill="currentColor" />
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function IconDoc() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h9l5 5v15H6V2z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20h9M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
