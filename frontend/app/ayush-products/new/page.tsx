"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ApiError, createAyushProduct } from "@/lib/api";
import { PRODUCT_CATEGORIES } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/shell/ToastProvider";

function listField(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function NewAyushProductForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { showToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const categoryFromQuery = searchParams.get("category");
  const initialCategory =
    (categoryFromQuery && PRODUCT_CATEGORIES.some((c) => c.value === categoryFromQuery)
      ? categoryFromQuery
      : PRODUCT_CATEGORIES[0].value) ?? PRODUCT_CATEGORIES[0].value;

  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [category, setCategory] = useState(initialCategory);
  const [subcategory, setSubcategory] = useState("");
  const [brand, setBrand] = useState("");
  const [sku, setSku] = useState("");
  const [productUrl, setProductUrl] = useState("");
  const [landingPageUrl, setLandingPageUrl] = useState("");
  const [marketplaceUrls, setMarketplaceUrls] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [description, setDescription] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [primaryProblem, setPrimaryProblem] = useState("");
  const [positioning, setPositioning] = useState("");
  const [usp, setUsp] = useState("");
  const [neverSay, setNeverSay] = useState("");
  const [ingredients, setIngredients] = useState("");
  const [benefits, setBenefits] = useState("");
  const [usage, setUsage] = useState("");
  const [approvedClaims, setApprovedClaims] = useState("");
  const [prohibitedClaims, setProhibitedClaims] = useState("");
  const [secondaryTargetAudience, setSecondaryTargetAudience] = useState("");
  const [customerObjections, setCustomerObjections] = useState("");
  const [buyingTriggers, setBuyingTriggers] = useState("");
  const [awarenessLevel, setAwarenessLevel] = useState("");
  const [preferredTone, setPreferredTone] = useState("");
  const [ctaText, setCtaText] = useState("");
  const [brandPersonality, setBrandPersonality] = useState("");
  const [wordsToUse, setWordsToUse] = useState("");
  const [wordsToAvoid, setWordsToAvoid] = useState("");
  const [visualStyle, setVisualStyle] = useState("");
  const [visualExclusions, setVisualExclusions] = useState("");

  const canSubmit = name.trim().length > 0 && category.trim().length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      const product = await createAyushProduct({
        name: name.trim(),
        category,
        display_name: displayName.trim(),
        subcategory: subcategory.trim(),
        brand: brand.trim(),
        sku: sku.trim(),
        product_url: productUrl.trim() || undefined,
        landing_page_url: landingPageUrl.trim() || undefined,
        marketplace_urls: listField(marketplaceUrls),
        short_description: shortDescription.trim(),
        description: description.trim(),
        target_audience: targetAudience.trim(),
        primary_problem: primaryProblem.trim(),
        positioning: positioning.trim(),
        usp: usp.trim(),
        never_say: neverSay.trim(),
        ingredients: listField(ingredients),
        benefits: listField(benefits),
        usage: usage.trim(),
        approved_claims: listField(approvedClaims),
        prohibited_claims: listField(prohibitedClaims),
        secondary_target_audience: secondaryTargetAudience.trim(),
        customer_objections: listField(customerObjections),
        buying_triggers: listField(buyingTriggers),
        awareness_level: awarenessLevel.trim(),
        preferred_tone: preferredTone.trim(),
        cta_text: ctaText.trim(),
        brand_personality: brandPersonality.trim(),
        words_to_use: listField(wordsToUse),
        words_to_avoid: listField(wordsToAvoid),
        visual_style: visualStyle.trim(),
        visual_exclusions: visualExclusions.trim(),
      });
      showToast("Product created", "success");
      router.push(`/ayush-products/${product.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't create the product.");
    } finally {
      setSaving(false);
    }
  }

  const categoryLabel = PRODUCT_CATEGORIES.find((c) => c.value === category)?.label ?? category;

  return (
    <div className="mx-auto flex w-full max-w-[900px] flex-1 flex-col gap-6 px-6 py-10">
      <div>
        <Link href="/ayush-products" className="text-[12.5px] text-[var(--muted)] hover:text-[var(--foreground)]">
          ← AyushWellness Products
        </Link>
        <h1 className="mt-2 text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Add Product</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          Only Product Name and Category are required — everything else can be filled in or edited later.
          {categoryFromQuery && (
            <span className="ml-1 text-[var(--accent)]">Category preselected: {categoryLabel}.</span>
          )}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Card>
          <CardHeader title="Basic Product Information" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Product Name *</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Aayush Wellness Herbal Masala" />
              </div>
              <div>
                <Label>Category *</Label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3.5 py-2.5 text-[14px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
                >
                  {PRODUCT_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Display Name (optional)</Label>
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Shown in sidebar/lists if different from name"
                />
              </div>
              <div>
                <Label>Subcategory</Label>
                <Input value={subcategory} onChange={(e) => setSubcategory(e.target.value)} placeholder="e.g. Ziplock Big Pouches" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Brand</Label>
                <Input value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="AyushWellness" />
              </div>
              <div>
                <Label>SKU / Product Code</Label>
                <Input value={sku} onChange={(e) => setSku(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Short Description</Label>
              <Input value={shortDescription} onChange={(e) => setShortDescription(e.target.value)} placeholder="One-line summary" />
            </div>
            <div>
              <Label>Full Description</Label>
              <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Product Page / Website" />
          <CardBody className="space-y-4">
            <div>
              <Label>Product / Store URL</Label>
              <Input value={productUrl} onChange={(e) => setProductUrl(e.target.value)} placeholder="https://store.aayushwellness.com/products/..." />
            </div>
            <div>
              <Label>Landing Page URL</Label>
              <Input value={landingPageUrl} onChange={(e) => setLandingPageUrl(e.target.value)} placeholder="Campaign-specific landing page, if different" />
            </div>
            <div>
              <Label>Marketplace / Reference URLs (one per line)</Label>
              <Textarea rows={2} value={marketplaceUrls} onChange={(e) => setMarketplaceUrls(e.target.value)} placeholder="Amazon, Flipkart, etc." />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Product Positioning" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Target Audience</Label>
                <Input value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)} />
              </div>
              <div>
                <Label>Primary Problem Addressed</Label>
                <Input value={primaryProblem} onChange={(e) => setPrimaryProblem(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Positioning / Solution</Label>
              <Textarea rows={2} value={positioning} onChange={(e) => setPositioning(e.target.value)} placeholder="What makes this different, why choose it, core marketing message..." />
            </div>
            <div>
              <Label>USP</Label>
              <Textarea rows={2} value={usp} onChange={(e) => setUsp(e.target.value)} />
            </div>
            <div>
              <Label>Never Say (brand-voice guardrail, distinct from compliance claims)</Label>
              <Textarea rows={2} value={neverSay} onChange={(e) => setNeverSay(e.target.value)} placeholder="Things that should never be said about this product" />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Ingredients / Composition" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Key Ingredients (one per line)</Label>
                <Textarea rows={4} value={ingredients} onChange={(e) => setIngredients(e.target.value)} />
              </div>
              <div>
                <Label>Key Benefits (one per line)</Label>
                <Textarea rows={4} value={benefits} onChange={(e) => setBenefits(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>How to Use</Label>
              <Textarea rows={2} value={usage} onChange={(e) => setUsage(e.target.value)} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Claims" subtitle="Only Approved Claims may be used in generated ad copy — the Compliance system remains authoritative." />
          <CardBody className="space-y-4">
            <div>
              <Label>Approved Claims (one per line)</Label>
              <Textarea rows={3} value={approvedClaims} onChange={(e) => setApprovedClaims(e.target.value)} />
            </div>
            <div>
              <Label>Restricted / Prohibited Claims (one per line)</Label>
              <Textarea rows={3} value={prohibitedClaims} onChange={(e) => setProhibitedClaims(e.target.value)} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Target Customer" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Secondary Target Audience</Label>
                <Input value={secondaryTargetAudience} onChange={(e) => setSecondaryTargetAudience(e.target.value)} />
              </div>
              <div>
                <Label>Customer Awareness Level</Label>
                <Input value={awarenessLevel} onChange={(e) => setAwarenessLevel(e.target.value)} placeholder="e.g. Problem-aware, Solution-aware" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Customer Objections (one per line)</Label>
                <Textarea rows={3} value={customerObjections} onChange={(e) => setCustomerObjections(e.target.value)} />
              </div>
              <div>
                <Label>Buying Triggers (one per line)</Label>
                <Textarea rows={3} value={buyingTriggers} onChange={(e) => setBuyingTriggers(e.target.value)} />
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Brand / Creative Direction" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Preferred Tone</Label>
                <Input value={preferredTone} onChange={(e) => setPreferredTone(e.target.value)} placeholder="warm, trustworthy, energetic..." />
              </div>
              <div>
                <Label>CTA</Label>
                <Input value={ctaText} onChange={(e) => setCtaText(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Brand Personality</Label>
              <Input value={brandPersonality} onChange={(e) => setBrandPersonality(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Words / Phrases to Use (one per line)</Label>
                <Textarea rows={2} value={wordsToUse} onChange={(e) => setWordsToUse(e.target.value)} />
              </div>
              <div>
                <Label>Words / Phrases to Avoid (one per line)</Label>
                <Textarea rows={2} value={wordsToAvoid} onChange={(e) => setWordsToAvoid(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Preferred Visual Style</Label>
              <Textarea rows={2} value={visualStyle} onChange={(e) => setVisualStyle(e.target.value)} placeholder="Photography style, locations, persona..." />
            </div>
            <div>
              <Label>Visual Exclusions</Label>
              <Textarea rows={2} value={visualExclusions} onChange={(e) => setVisualExclusions(e.target.value)} placeholder="Things that should NOT appear visually" />
            </div>
          </CardBody>
        </Card>

        {error && (
          <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Link href="/ayush-products">
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </Link>
          <Button type="submit" disabled={!canSubmit} loading={saving}>
            Save Product
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function NewAyushProductPage() {
  return (
    <Suspense fallback={null}>
      <NewAyushProductForm />
    </Suspense>
  );
}
