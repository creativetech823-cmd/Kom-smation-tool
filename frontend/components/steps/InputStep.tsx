"use client";

import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Field";
import type { ProductInput, SourceType } from "@/lib/types";

const SOURCE_OPTIONS: { value: SourceType; label: string; hint: string }[] = [
  { value: "description", label: "Description", hint: "Paste or type product details" },
  { value: "url", label: "Website URL", hint: "Not wired up yet (Stage 2)" },
  { value: "none", label: "Manual only", hint: "No source — enter ingredients + USP" },
];

export function InputStep({
  onSubmit,
  loading,
  error,
}: {
  onSubmit: (input: ProductInput, category: string) => void;
  loading: boolean;
  error: string | null;
}) {
  const [productName, setProductName] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [category, setCategory] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("description");
  const [sourceDescription, setSourceDescription] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [manualIngredients, setManualIngredients] = useState("");
  const [manualUsp, setManualUsp] = useState("");

  const canSubmit =
    productName.trim() &&
    targetAudience.trim() &&
    category.trim() &&
    (sourceType === "description"
      ? sourceDescription.trim()
      : sourceType === "url"
      ? sourceUrl.trim()
      : manualIngredients.trim() && manualUsp.trim());

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
        manual_ingredients: sourceType === "none" ? manualIngredients : undefined,
        manual_usp: sourceType === "none" ? manualUsp : undefined,
      },
      category
    );
  }

  return (
    <Card glow className="animate-fade-up">
      <CardHeader
        title="Stage 1 — Product Input"
        subtitle="Tell us about the product. This feeds the whole pipeline."
        icon={<IconSparkle />}
      />
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Product name</Label>
              <Input
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="GreenLeaf Herbal Tea"
              />
            </div>
            <div>
              <Label>Target audience</Label>
              <Input
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="Health-conscious millennials"
              />
            </div>
          </div>

          <div>
            <Label>Product category</Label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="beverages, supplements, finance..."
            />
            <p className="mt-1 text-[12px] text-[var(--muted)]">
              Used to select the right compliance rules in Stage 7.
            </p>
          </div>

          <div>
            <Label>Source</Label>
            <div className="grid grid-cols-3 gap-2">
              {SOURCE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSourceType(opt.value)}
                  className={`rounded-xl border px-3 py-2.5 text-left text-[13px] transition-colors ${
                    sourceType === opt.value
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <div className="font-medium">{opt.label}</div>
                  <div className="mt-0.5 text-[11px] opacity-80">{opt.hint}</div>
                </button>
              ))}
            </div>
          </div>

          {sourceType === "description" && (
            <div>
              <Label>Product description</Label>
              <Textarea
                rows={4}
                value={sourceDescription}
                onChange={(e) => setSourceDescription(e.target.value)}
                placeholder="Organic tulsi, ginger, and lemongrass tea sourced from Himalayan farms..."
              />
            </div>
          )}

          {sourceType === "url" && (
            <div>
              <Label>Website URL</Label>
              <Input
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://example.com/product"
              />
              <p className="mt-1 text-[12px] text-[var(--warning)]">
                Stage 2 (Jina Reader scraping) isn&apos;t wired up yet — this will fail on submit.
              </p>
            </div>
          )}

          {sourceType === "none" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Ingredients</Label>
                <Textarea
                  rows={3}
                  value={manualIngredients}
                  onChange={(e) => setManualIngredients(e.target.value)}
                  placeholder="tulsi, ginger, lemongrass"
                />
              </div>
              <div>
                <Label>USP</Label>
                <Textarea
                  rows={3}
                  value={manualUsp}
                  onChange={(e) => setManualUsp(e.target.value)}
                  placeholder="Caffeine-free, Himalayan sourced"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
              {error}
            </div>
          )}

          <div className="flex justify-end pt-1">
            <Button type="submit" disabled={!canSubmit} loading={loading}>
              Structure product data
              <IconArrow />
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
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
