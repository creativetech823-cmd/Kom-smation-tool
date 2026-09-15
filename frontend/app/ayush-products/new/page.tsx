"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ApiError, createAyushProduct, importProductAssetFromUrl, importProductFromUrl } from "@/lib/api";
import { PRODUCT_CATEGORIES, type ProductImportImageCandidate } from "@/lib/types";
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

function joinField(values: string[]): string {
  return values.join("\n");
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

  // --- Product URL import (Part 3/4 — minimal-input-first flow) ---
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [imported, setImported] = useState(false);
  const [imageCandidates, setImageCandidates] = useState<ProductImportImageCandidate[]>([]);
  const [selectedImageUrls, setSelectedImageUrls] = useState<Set<string>>(new Set());
  const [skipImagesForNow, setSkipImagesForNow] = useState(false);
  const [additionalOpen, setAdditionalOpen] = useState(false);

  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [category, setCategory] = useState(initialCategory);
  const [subcategory, setSubcategory] = useState("");
  const [brand, setBrand] = useState("");
  const [sku, setSku] = useState("");
  const [price, setPrice] = useState("");
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
  const hasImagePlan = imageCandidates.length === 0 || selectedImageUrls.size > 0 || skipImagesForNow;

  async function handleImport() {
    const url = importUrl.trim();
    if (!url) return;
    setImporting(true);
    setImportError(null);
    setImportWarnings([]);
    try {
      const result = await importProductFromUrl(url);
      setProductUrl(url);
      if (result.name) setName(result.name);
      if (result.short_description) setShortDescription(result.short_description);
      if (result.description) setDescription(result.description);
      if (result.brand) setBrand(result.brand);
      if (result.price) setPrice(result.price);
      if (result.ingredients.length > 0) setIngredients(joinField(result.ingredients));
      if (result.benefits.length > 0) setBenefits(joinField(result.benefits));
      if (result.usage) setUsage(result.usage);
      setImageCandidates(result.images);
      // All fetched candidates are already relevance/quality-filtered by the
      // importer (title-overlap + size floor) — select every one by default
      // so a real save actually persists the full set the user sees, not
      // just the first. The checkbox grid below still lets them deselect
      // anything that isn't actually the product before saving.
      setSelectedImageUrls(new Set(result.images.map((img) => img.url)));
      setImportWarnings(result.warnings);
      setImported(true);
      showToast("Product page fetched — review the details below", "success");
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : "Couldn't fetch that product page.");
    } finally {
      setImporting(false);
    }
  }

  function toggleImage(url: string) {
    setSelectedImageUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

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
        price: price.trim() || undefined,
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

      // Real product images the user picked from the URL import — fetched
      // server-side and stored as genuine assets (not just linked URLs), so
      // one of them can become the product's primary/hero asset. Imported
      // ONE AT A TIME, in the user's selection order (already best-first,
      // per the importer's own relevance ranking) — importing them
      // concurrently let a network race decide which one landed first in
      // the DB and silently became primary, regardless of which image the
      // user actually meant as the hero shot.
      const chosen = imageCandidates.filter((img) => selectedImageUrls.has(img.url));
      let failedCount = 0;
      for (const img of chosen) {
        try {
          await importProductAssetFromUrl(product.id, {
            asset_type: "product_image",
            source_url: img.url,
            title: img.alt || product.name,
          });
        } catch {
          failedCount += 1;
        }
      }
      if (failedCount > 0) {
        showToast(
          `Product created, but ${failedCount} of ${chosen.length} image${chosen.length > 1 ? "s" : ""} couldn't be imported — add ${failedCount > 1 ? "them" : "it"} from the product page.`,
          "danger"
        );
      }

      if (product.is_existing) {
        showToast("A product with this URL already exists — opening it instead of creating a duplicate", "success");
      } else if (product.possible_duplicate) {
        showToast(`Product created. Note: "${product.possible_duplicate.name}" already exists in this category too.`, "success");
      } else {
        showToast("Product created", "success");
      }
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
          Paste a product URL to fetch the basics automatically, or fill in Product Name and Category manually —
          everything else can be added or edited later.
          {categoryFromQuery && (
            <span className="ml-1 text-[var(--accent)]">Category preselected: {categoryLabel}.</span>
          )}
        </p>
      </div>

      <Card glow={!imported}>
        <CardHeader
          title="Import from Product URL"
          subtitle="We'll read the public page and pre-fill what it clearly states — nothing is invented, and you review everything before saving."
        />
        <CardBody className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="https://store.aayushwellness.com/products/..."
              className="flex-1"
            />
            <Button type="button" onClick={handleImport} loading={importing} disabled={!importUrl.trim()}>
              Fetch Product
            </Button>
          </div>
          {importError && <p className="text-[12.5px] text-[var(--danger)]">{importError}</p>}
          {importWarnings.map((w, i) => (
            <p key={i} className="text-[12.5px] text-[var(--warning)]">
              {w}
            </p>
          ))}
          {imported && (
            <p className="text-[12.5px] text-[var(--accent)]">
              ✓ Fetched — review the fields below (name, description, ingredients, benefits, images) and correct
              anything before saving.
            </p>
          )}
        </CardBody>
      </Card>

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
                <Label>Brand</Label>
                <Input value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="AyushWellness" />
              </div>
              <div>
                <Label>Product / Store URL</Label>
                <Input value={productUrl} onChange={(e) => setProductUrl(e.target.value)} placeholder="https://store.aayushwellness.com/products/..." />
              </div>
            </div>
            <div>
              <Label>Price</Label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="₹499" />
            </div>
            <div>
              <Label>Short Description {imported && !shortDescription && "*"}</Label>
              <Input value={shortDescription} onChange={(e) => setShortDescription(e.target.value)} placeholder="One-line summary" />
            </div>
            <div>
              <Label>Full Description</Label>
              <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Product Images"
            subtitle={
              imageCandidates.length > 0
                ? "All fetched product photos are selected by default and will be saved as real product assets — used by the Assets/Render pipeline in place of stock imagery for product shots. Click any photo to leave it out."
                : "Fetch a product URL above to find images, or add them later from the product page."
            }
            right={
              imageCandidates.length > 1 ? (
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => setSelectedImageUrls(new Set(imageCandidates.map((img) => img.url)))}
                    className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1 text-[11.5px] text-[var(--muted)] hover:text-[var(--foreground)]"
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedImageUrls(new Set())}
                    className="rounded-lg border border-[var(--border-strong)] px-2.5 py-1 text-[11.5px] text-[var(--muted)] hover:text-[var(--foreground)]"
                  >
                    Select none
                  </button>
                </div>
              ) : undefined
            }
          />
          <CardBody className="space-y-3">
            {imageCandidates.length > 0 ? (
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
                {imageCandidates.map((img) => {
                  const selected = selectedImageUrls.has(img.url);
                  return (
                    <button
                      type="button"
                      key={img.url}
                      onClick={() => toggleImage(img.url)}
                      className={`relative overflow-hidden rounded-xl border-2 transition-colors ${
                        selected ? "border-[var(--accent)]" : "border-transparent hover:border-[var(--border-strong)]"
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.url} alt={img.alt} className="aspect-square w-full bg-black/20 object-cover" />
                      {selected && (
                        <span className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--accent)] text-[11px] font-bold text-[var(--on-accent)]">
                          ✓
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <label className="flex items-center gap-2 text-[12.5px] text-[var(--muted)]">
                <input type="checkbox" checked={skipImagesForNow} onChange={(e) => setSkipImagesForNow(e.target.checked)} />
                I&apos;ll add product images later
              </label>
            )}
          </CardBody>
        </Card>

        <details
          className="group rounded-2xl border border-[var(--border)] bg-[var(--surface)]/60 open:bg-[var(--surface)]"
          open={additionalOpen}
          onToggle={(e) => setAdditionalOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer list-none px-5 py-4 text-[13.5px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]">
            <span className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
            Additional Product Knowledge <span className="font-normal text-[var(--muted)]">— optional, improves AI script/video quality</span>
          </summary>

          <div className="flex flex-col gap-5 px-5 pb-5">
            <Card>
              <CardHeader title="Product Page / Website" />
              <CardBody className="space-y-4">
                <div>
                  <Label>Display Name (optional)</Label>
                  <Input
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Shown in sidebar/lists if different from name"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Subcategory</Label>
                    <Input value={subcategory} onChange={(e) => setSubcategory(e.target.value)} placeholder="e.g. Ziplock Big Pouches" />
                  </div>
                  <div>
                    <Label>SKU / Product Code</Label>
                    <Input value={sku} onChange={(e) => setSku(e.target.value)} />
                  </div>
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
          </div>
        </details>

        {error && (
          <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
            {error}
          </div>
        )}

        {!hasImagePlan && (
          <p className="text-[12px] text-[var(--muted)]">
            Tip: pick at least one product image above, or check &quot;I&apos;ll add product images later&quot; — you can
            still save without it.
          </p>
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
