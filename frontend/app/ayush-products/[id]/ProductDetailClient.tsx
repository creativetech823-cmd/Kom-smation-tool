"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  archiveAyushProduct,
  createHook,
  createProductCreativeAngle,
  createProductReferenceScript,
  deactivateProductAsset,
  deleteProductCreativeAngle,
  deleteProductReferenceScript,
  getAyushProduct,
  linkProductAsset,
  listHooks,
  listProductAssets,
  listProductCreativeAngles,
  listProductReferenceScripts,
  productUploadFileUrl,
  restoreAyushProduct,
  updateAyushProduct,
  updateProductAsset,
  updateProductReferenceScript,
  uploadProductAsset,
} from "@/lib/api";
import type { AyushProduct, Hook, ProductAsset, ProductAssetType, ProductCreativeAngle, ProductReferenceScript } from "@/lib/types";
import { PRODUCT_CATEGORIES } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Label, Textarea } from "@/components/ui/Field";
import { EmptyState } from "@/components/library/EmptyState";
import { useToast } from "@/components/shell/ToastProvider";

const TABS = ["Overview", "Product Knowledge", "Claims", "Assets", "Reference Scripts", "Creative Angles", "Hooks"] as const;
type Tab = (typeof TABS)[number];

const ASSET_TYPES: { value: ProductAssetType; label: string }[] = [
  { value: "product_packshot", label: "Product Packshot" },
  { value: "product_image", label: "Product Image" },
  { value: "product_lifestyle", label: "Product Lifestyle" },
  { value: "ingredient_image", label: "Ingredient Image" },
  { value: "advertisement", label: "Advertisement" },
  { value: "reference_video", label: "Reference Video" },
  { value: "other", label: "Other" },
];

function listField(value: string): string[] {
  return value.split("\n").map((l) => l.trim()).filter(Boolean);
}
function toLines(items: string[]): string {
  return (items || []).join("\n");
}

export function ProductDetailClient({ productId }: { productId: string }) {
  const { showToast } = useToast();
  const [product, setProduct] = useState<AyushProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("Overview");

  const refresh = useCallback(() => {
    setLoading(true);
    return getAyushProduct(productId)
      .then(setProduct)
      .catch(() => showToast("Couldn't load this product.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleArchiveToggle() {
    if (!product) return;
    try {
      const updated = product.status === "archived" ? await restoreAyushProduct(product.id) : await archiveAyushProduct(product.id);
      setProduct(updated);
      showToast(updated.status === "archived" ? "Product archived" : "Product restored", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't update product.", "danger");
    }
  }

  if (loading && !product) {
    return (
      <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col gap-6 px-6 py-10">
        <p className="text-[13px] text-[var(--muted)]">Loading product…</p>
      </div>
    );
  }
  if (!product) {
    return (
      <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col gap-6 px-6 py-10">
        <EmptyState title="Product not found" message="This product may have been deleted." />
      </div>
    );
  }

  const categoryLabel = PRODUCT_CATEGORIES.find((c) => c.value === product.category)?.label ?? product.category;

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10">
      <Link href="/ayush-products" className="text-[12.5px] text-[var(--muted)] hover:text-[var(--foreground)]">
        ← AyushWellness Products
      </Link>

      <Card>
        <CardBody className="flex flex-wrap items-start justify-between gap-4 pt-6">
          <div className="flex items-start gap-4">
            <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-[var(--surface-2)]">
              {product.primary_asset?.file_path ? (
                <img src={productUploadFileUrl(product.primary_asset.file_path)} alt={product.name} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-[10px] text-[var(--muted)]">No image</div>
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[19px] font-semibold tracking-tight text-[var(--foreground)]">{product.name}</h1>
                {product.status === "archived" && <Badge tone="warning">Archived</Badge>}
              </div>
              <span className="mt-1 inline-block rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent)]">
                {categoryLabel}
              </span>
              {product.product_url && (
                <a
                  href={product.product_url}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-2 text-[11.5px] text-[var(--accent)] hover:underline"
                >
                  View product page ↗
                </a>
              )}
              {product.short_description && (
                <p className="mt-1 max-w-lg text-[13px] text-[var(--muted)]">{product.short_description}</p>
              )}
            </div>
          </div>
          <Button size="sm" variant="secondary" onClick={handleArchiveToggle}>
            {product.status === "archived" ? "Restore" : "Archive"}
          </Button>
        </CardBody>
      </Card>

      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
              tab === t
                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab product={product} onSaved={setProduct} />}
      {tab === "Product Knowledge" && <KnowledgeTab product={product} onSaved={setProduct} />}
      {tab === "Claims" && <ClaimsTab product={product} onSaved={setProduct} />}
      {tab === "Assets" && <AssetsTab productId={product.id} onPrimaryChanged={() => void refresh()} />}
      {tab === "Reference Scripts" && <ReferenceScriptsTab productId={product.id} />}
      {tab === "Creative Angles" && <CreativeAnglesTab productId={product.id} />}
      {tab === "Hooks" && <HooksTab productId={product.id} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

function OverviewTab({ product, onSaved }: { product: AyushProduct; onSaved: (p: AyushProduct) => void }) {
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    display_name: product.display_name,
    subcategory: product.subcategory,
    brand: product.brand,
    sku: product.sku,
    short_description: product.short_description,
    description: product.description,
    target_audience: product.target_audience,
    primary_problem: product.primary_problem,
    positioning: product.positioning,
    usp: product.usp,
    never_say: product.never_say,
    preferred_tone: product.preferred_tone,
    cta_text: product.cta_text,
  });

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateAyushProduct(product.id, form);
      onSaved(updated);
      setEditing(false);
      showToast("Saved", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't save changes.", "danger");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Product Information"
        right={
          editing ? (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} loading={saving}>
                Save
              </Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
              Edit Product
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {editing ? (
          <>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Display Name">
                <Input value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} />
              </Field>
              <Field label="Subcategory">
                <Input value={form.subcategory} onChange={(e) => setForm((f) => ({ ...f, subcategory: e.target.value }))} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Brand">
                <Input value={form.brand} onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))} />
              </Field>
              <Field label="SKU / Product Code">
                <Input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} />
              </Field>
            </div>
            <Field label="Short Description">
              <Input value={form.short_description} onChange={(e) => setForm((f) => ({ ...f, short_description: e.target.value }))} />
            </Field>
            <Field label="Description">
              <Textarea rows={3} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Target Audience">
                <Input value={form.target_audience} onChange={(e) => setForm((f) => ({ ...f, target_audience: e.target.value }))} />
              </Field>
              <Field label="Primary Problem">
                <Input value={form.primary_problem} onChange={(e) => setForm((f) => ({ ...f, primary_problem: e.target.value }))} />
              </Field>
            </div>
            <Field label="Positioning / Solution">
              <Input value={form.positioning} onChange={(e) => setForm((f) => ({ ...f, positioning: e.target.value }))} />
            </Field>
            <Field label="USP">
              <Textarea rows={2} value={form.usp} onChange={(e) => setForm((f) => ({ ...f, usp: e.target.value }))} />
            </Field>
            <Field label="Never Say (brand-voice guardrail)">
              <Textarea rows={2} value={form.never_say} onChange={(e) => setForm((f) => ({ ...f, never_say: e.target.value }))} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Preferred Tone">
                <Input value={form.preferred_tone} onChange={(e) => setForm((f) => ({ ...f, preferred_tone: e.target.value }))} />
              </Field>
              <Field label="CTA">
                <Input value={form.cta_text} onChange={(e) => setForm((f) => ({ ...f, cta_text: e.target.value }))} />
              </Field>
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <ReadRow label="Display Name" value={product.display_name} />
              <ReadRow label="Subcategory" value={product.subcategory} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <ReadRow label="Brand" value={product.brand} />
              <ReadRow label="SKU" value={product.sku} />
            </div>
            <ReadRow label="Description" value={product.description} />
            <div className="grid grid-cols-2 gap-4">
              <ReadRow label="Target Audience" value={product.target_audience} />
              <ReadRow label="Primary Problem" value={product.primary_problem} />
            </div>
            <ReadRow label="Positioning / Solution" value={product.positioning} />
            <ReadRow label="USP" value={product.usp} />
            <ReadRow label="Never Say" value={product.never_say} />
            <div className="grid grid-cols-2 gap-4">
              <ReadRow label="Preferred Tone" value={product.preferred_tone} />
              <ReadRow label="CTA" value={product.cta_text} />
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Product Knowledge
// ---------------------------------------------------------------------------

function KnowledgeTab({ product, onSaved }: { product: AyushProduct; onSaved: (p: AyushProduct) => void }) {
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    ingredients: toLines(product.ingredients),
    benefits: toLines(product.benefits),
    usage: product.usage,
    how_it_works: product.how_it_works,
    who_is_it_for: product.who_is_it_for,
    cautions: product.cautions,
    secondary_target_audience: product.secondary_target_audience,
    awareness_level: product.awareness_level,
    customer_objections: toLines(product.customer_objections),
    buying_triggers: toLines(product.buying_triggers),
    brand_personality: product.brand_personality,
    words_to_use: toLines(product.words_to_use),
    words_to_avoid: toLines(product.words_to_avoid),
    visual_style: product.visual_style,
    visual_exclusions: product.visual_exclusions,
  });

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateAyushProduct(product.id, {
        ...form,
        ingredients: listField(form.ingredients),
        benefits: listField(form.benefits),
        customer_objections: listField(form.customer_objections),
        buying_triggers: listField(form.buying_triggers),
        words_to_use: listField(form.words_to_use),
        words_to_avoid: listField(form.words_to_avoid),
      });
      onSaved(updated);
      setEditing(false);
      showToast("Saved", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't save changes.", "danger");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Product Knowledge"
        right={
          editing ? (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} loading={saving}>
                Save
              </Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {editing ? (
          <>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Key Ingredients (one per line)">
                <Textarea rows={4} value={form.ingredients} onChange={(e) => setForm((f) => ({ ...f, ingredients: e.target.value }))} />
              </Field>
              <Field label="Key Benefits (one per line)">
                <Textarea rows={4} value={form.benefits} onChange={(e) => setForm((f) => ({ ...f, benefits: e.target.value }))} />
              </Field>
            </div>
            <Field label="How to Use">
              <Textarea rows={2} value={form.usage} onChange={(e) => setForm((f) => ({ ...f, usage: e.target.value }))} />
            </Field>
            <Field label="How does it work?">
              <Textarea rows={2} value={form.how_it_works} onChange={(e) => setForm((f) => ({ ...f, how_it_works: e.target.value }))} />
            </Field>
            <Field label="Who is it for?">
              <Textarea rows={2} value={form.who_is_it_for} onChange={(e) => setForm((f) => ({ ...f, who_is_it_for: e.target.value }))} />
            </Field>
            <Field label="Important cautions">
              <Textarea rows={2} value={form.cautions} onChange={(e) => setForm((f) => ({ ...f, cautions: e.target.value }))} />
            </Field>

            <div className="border-t border-[var(--border)] pt-4">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">Target Customer</p>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Secondary Target Audience">
                  <Input value={form.secondary_target_audience} onChange={(e) => setForm((f) => ({ ...f, secondary_target_audience: e.target.value }))} />
                </Field>
                <Field label="Awareness Level">
                  <Input value={form.awareness_level} onChange={(e) => setForm((f) => ({ ...f, awareness_level: e.target.value }))} />
                </Field>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <Field label="Customer Objections (one per line)">
                  <Textarea rows={3} value={form.customer_objections} onChange={(e) => setForm((f) => ({ ...f, customer_objections: e.target.value }))} />
                </Field>
                <Field label="Buying Triggers (one per line)">
                  <Textarea rows={3} value={form.buying_triggers} onChange={(e) => setForm((f) => ({ ...f, buying_triggers: e.target.value }))} />
                </Field>
              </div>
            </div>

            <div className="border-t border-[var(--border)] pt-4">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">Brand / Creative Direction</p>
              <Field label="Brand Personality">
                <Input value={form.brand_personality} onChange={(e) => setForm((f) => ({ ...f, brand_personality: e.target.value }))} />
              </Field>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <Field label="Words to Use (one per line)">
                  <Textarea rows={2} value={form.words_to_use} onChange={(e) => setForm((f) => ({ ...f, words_to_use: e.target.value }))} />
                </Field>
                <Field label="Words to Avoid (one per line)">
                  <Textarea rows={2} value={form.words_to_avoid} onChange={(e) => setForm((f) => ({ ...f, words_to_avoid: e.target.value }))} />
                </Field>
              </div>
              <Field label="Preferred Visual Style">
                <Textarea rows={2} value={form.visual_style} onChange={(e) => setForm((f) => ({ ...f, visual_style: e.target.value }))} />
              </Field>
              <Field label="Visual Exclusions">
                <Textarea rows={2} value={form.visual_exclusions} onChange={(e) => setForm((f) => ({ ...f, visual_exclusions: e.target.value }))} />
              </Field>
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <TagListRow label="Key Ingredients" items={product.ingredients} />
              <TagListRow label="Key Benefits" items={product.benefits} />
            </div>
            <ReadRow label="How to Use" value={product.usage} />
            <ReadRow label="How does it work?" value={product.how_it_works} />
            <ReadRow label="Who is it for?" value={product.who_is_it_for} />
            <ReadRow label="Important cautions" value={product.cautions} />

            <div className="border-t border-[var(--border)] pt-4">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">Target Customer</p>
              <div className="grid grid-cols-2 gap-4">
                <ReadRow label="Secondary Target Audience" value={product.secondary_target_audience} />
                <ReadRow label="Awareness Level" value={product.awareness_level} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <TagListRow label="Customer Objections" items={product.customer_objections} />
                <TagListRow label="Buying Triggers" items={product.buying_triggers} />
              </div>
            </div>

            <div className="border-t border-[var(--border)] pt-4">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">Brand / Creative Direction</p>
              <ReadRow label="Brand Personality" value={product.brand_personality} />
              <div className="mt-4 grid grid-cols-2 gap-4">
                <TagListRow label="Words to Use" items={product.words_to_use} tone="success" />
                <TagListRow label="Words to Avoid" items={product.words_to_avoid} tone="danger" />
              </div>
              <ReadRow label="Preferred Visual Style" value={product.visual_style} />
              <ReadRow label="Visual Exclusions" value={product.visual_exclusions} />
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Claims
// ---------------------------------------------------------------------------

function ClaimsTab({ product, onSaved }: { product: AyushProduct; onSaved: (p: AyushProduct) => void }) {
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    approved_claims: toLines(product.approved_claims),
    prohibited_claims: toLines(product.prohibited_claims),
    mandatory_wording: product.mandatory_wording,
  });

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateAyushProduct(product.id, {
        ...form,
        approved_claims: listField(form.approved_claims),
        prohibited_claims: listField(form.prohibited_claims),
      });
      onSaved(updated);
      setEditing(false);
      showToast("Saved", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't save changes.", "danger");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Claims"
        subtitle="Script generation is only allowed to use Approved Claims — Restricted claims are passed as an explicit denylist."
        right={
          editing ? (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} loading={saving}>
                Save
              </Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {editing ? (
          <>
            <Field label="Approved Claims (one per line)">
              <Textarea rows={4} value={form.approved_claims} onChange={(e) => setForm((f) => ({ ...f, approved_claims: e.target.value }))} />
            </Field>
            <Field label="Restricted / Avoid Claims (one per line)">
              <Textarea rows={4} value={form.prohibited_claims} onChange={(e) => setForm((f) => ({ ...f, prohibited_claims: e.target.value }))} />
            </Field>
            <Field label="Mandatory wording">
              <Textarea rows={2} value={form.mandatory_wording} onChange={(e) => setForm((f) => ({ ...f, mandatory_wording: e.target.value }))} />
            </Field>
          </>
        ) : (
          <>
            <TagListRow label="Approved Claims" items={product.approved_claims} tone="success" />
            <TagListRow label="Restricted / Avoid Claims" items={product.prohibited_claims} tone="danger" />
            <ReadRow label="Mandatory wording" value={product.mandatory_wording} />
          </>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Assets
// ---------------------------------------------------------------------------

const REFERENCE_TYPES: ProductAssetType[] = ["advertisement", "reference_video"];

function AssetsTab({ productId, onPrimaryChanged }: { productId: string; onPrimaryChanged: () => void }) {
  const { showToast } = useToast();
  const [assets, setAssets] = useState<ProductAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [assetType, setAssetType] = useState<ProductAssetType>("product_packshot");
  const [title, setTitle] = useState("");
  const [linkMode, setLinkMode] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [learningNotes, setLearningNotes] = useState("");
  const [styleNotes, setStyleNotes] = useState("");
  const [linking, setLinking] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isReferenceType = REFERENCE_TYPES.includes(assetType);

  const refresh = useCallback(() => {
    setLoading(true);
    listProductAssets(productId)
      .then(setAssets)
      .catch(() => showToast("Couldn't load assets.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  function resetForm() {
    setTitle("");
    setSourceUrl("");
    setLearningNotes("");
    setStyleNotes("");
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadProductAsset(productId, file, {
        asset_type: assetType,
        title: title.trim(),
        learning_notes: learningNotes.trim(),
        style_notes: styleNotes.trim(),
      });
      resetForm();
      showToast("Asset uploaded", "success");
      await refresh();
      onPrimaryChanged();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Upload failed.", "danger");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleLinkReference() {
    if (!sourceUrl.trim()) return;
    setLinking(true);
    try {
      await linkProductAsset(productId, {
        asset_type: assetType,
        source_url: sourceUrl.trim(),
        title: title.trim(),
        learning_notes: learningNotes.trim(),
        style_notes: styleNotes.trim(),
      });
      resetForm();
      showToast("Reference added", "success");
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't add that reference.", "danger");
    } finally {
      setLinking(false);
    }
  }

  async function handleSetPrimary(assetId: string) {
    try {
      await updateProductAsset(assetId, { is_primary: true });
      await refresh();
      onPrimaryChanged();
    } catch {
      showToast("Couldn't set primary asset.", "danger");
    }
  }

  async function handleDeactivate(assetId: string) {
    try {
      await deactivateProductAsset(assetId);
      await refresh();
      onPrimaryChanged();
    } catch {
      showToast("Couldn't remove asset.", "danger");
    }
  }

  return (
    <Card>
      <CardHeader
        title="Assets"
        subtitle="Real product images, packshots, lifestyle photos, reference ads, and reference videos."
      />
      <CardBody className="space-y-5">
        <div className="flex flex-col gap-2.5 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <Label>Asset Type</Label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value as ProductAssetType)}
                className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
              >
                {ASSET_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[160px]">
              <Label>Title (optional)</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Front packshot" />
            </div>
            {!linkMode && (
              <Button size="sm" variant="secondary" onClick={() => fileInputRef.current?.click()} loading={uploading}>
                + Add Asset
              </Button>
            )}
            {isReferenceType && (
              <button
                type="button"
                onClick={() => setLinkMode((v) => !v)}
                className="rounded-xl border border-[var(--border-strong)] px-3 py-2 text-[12.5px] text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                {linkMode ? "Upload file instead" : "Or paste a reference URL"}
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/mp4,video/quicktime,video/webm"
              hidden
              onChange={handleFileSelected}
            />
          </div>

          {isReferenceType && (
            <div className="grid gap-2 sm:grid-cols-2">
              {linkMode && (
                <div className="sm:col-span-2">
                  <Label>Reference URL</Label>
                  <Input
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://... (competitor ad, YouTube link, etc.)"
                  />
                </div>
              )}
              <div>
                <Label>What should AI learn from this?</Label>
                <Textarea
                  value={learningNotes}
                  onChange={(e) => setLearningNotes(e.target.value)}
                  rows={2}
                  placeholder="Strong hook-first structure, quick product reveal…"
                />
              </div>
              <div>
                <Label>Style notes (hook / visual / editing / CTA)</Label>
                <Textarea
                  value={styleNotes}
                  onChange={(e) => setStyleNotes(e.target.value)}
                  rows={2}
                  placeholder="Fast cuts, bold captions, direct CTA at the end…"
                />
              </div>
              {linkMode && (
                <div className="sm:col-span-2 flex justify-end">
                  <Button size="sm" onClick={handleLinkReference} loading={linking} disabled={!sourceUrl.trim()}>
                    Add Reference
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        {loading ? (
          <p className="text-[13px] text-[var(--muted)]">Loading…</p>
        ) : assets.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)]">No assets yet — upload the real product packshot to get started.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {assets.map((asset) => (
              <div key={asset.id} className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-2)]">
                <div className="relative aspect-square w-full bg-black/20">
                  {asset.file_path ? (
                    asset.asset_type === "reference_video" || asset.file_path.match(/\.(mp4|mov|webm)$/i) ? (
                      <video src={productUploadFileUrl(asset.file_path)} className="h-full w-full object-cover" muted controls />
                    ) : (
                      <img src={productUploadFileUrl(asset.file_path)} alt={asset.title} className="h-full w-full object-cover" />
                    )
                  ) : asset.source_url ? (
                    <a
                      href={asset.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex h-full w-full flex-col items-center justify-center gap-1.5 p-3 text-center text-[var(--accent)] hover:bg-[var(--accent-soft)]"
                    >
                      <IconExternalLink />
                      <span className="text-[11.5px] font-medium">View reference ↗</span>
                    </a>
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-[11px] text-[var(--muted)]">
                      No preview
                    </div>
                  )}
                  {asset.is_primary && (
                    <span className="absolute left-1.5 top-1.5 rounded-full bg-[var(--accent)] px-2 py-0.5 text-[10px] font-semibold text-[var(--on-accent)]">
                      Primary
                    </span>
                  )}
                </div>
                <div className="p-2">
                  <p className="truncate text-[12px] font-medium text-[var(--foreground)]">{asset.title || ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</p>
                  <p className="text-[10.5px] text-[var(--muted)]">{ASSET_TYPES.find((t) => t.value === asset.asset_type)?.label}</p>
                  {asset.learning_notes && (
                    <p className="mt-1 line-clamp-2 text-[10.5px] text-[var(--muted)]" title={asset.learning_notes}>
                      Learn: {asset.learning_notes}
                    </p>
                  )}
                  <div className="mt-2 flex gap-1.5">
                    {!asset.is_primary && asset.file_path && (
                      <button
                        type="button"
                        onClick={() => handleSetPrimary(asset.id)}
                        className="rounded-lg border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--muted)] hover:text-[var(--foreground)]"
                      >
                        Set Primary
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeactivate(asset.id)}
                      className="rounded-lg border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--danger)] hover:bg-[var(--danger)]/10"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Reference Scripts
// ---------------------------------------------------------------------------

function ReferenceScriptsTab({ productId }: { productId: string }) {
  const { showToast } = useToast();
  const [scripts, setScripts] = useState<ProductReferenceScript[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newText, setNewText] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    listProductReferenceScripts(productId)
      .then(setScripts)
      .catch(() => showToast("Couldn't load reference scripts.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleAdd() {
    if (!newText.trim()) return;
    setSaving(true);
    try {
      await createProductReferenceScript(productId, { title: newTitle.trim(), script_text: newText.trim() });
      setNewTitle("");
      setNewText("");
      setAdding(false);
      await refresh();
      showToast("Reference script added", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't add script.", "danger");
    } finally {
      setSaving(false);
    }
  }

  async function toggleApproved(script: ProductReferenceScript) {
    try {
      await updateProductReferenceScript(script.id, { is_approved: !script.is_approved });
      await refresh();
    } catch {
      showToast("Couldn't update script.", "danger");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteProductReferenceScript(id);
      await refresh();
    } catch {
      showToast("Couldn't delete script.", "danger");
    }
  }

  return (
    <Card>
      <CardHeader
        title="Reference Scripts"
        subtitle="Previous advertising for this product — used as a style/strategy reference, never copied verbatim. Only Approved scripts reach Script generation."
        right={
          !adding && (
            <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
              + Add Reference Script
            </Button>
          )
        }
      />
      <CardBody className="space-y-4">
        {adding && (
          <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
            <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Title (optional)" />
            <Textarea rows={4} value={newText} onChange={(e) => setNewText(e.target.value)} placeholder="Paste the previous script text…" />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleAdd} loading={saving} disabled={!newText.trim()}>
                Save
              </Button>
            </div>
          </div>
        )}
        {loading ? (
          <p className="text-[13px] text-[var(--muted)]">Loading…</p>
        ) : scripts.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)]">No reference scripts yet.</p>
        ) : (
          <div className="space-y-2">
            {scripts.map((s) => (
              <div key={s.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-[13px] font-medium text-[var(--foreground)]">{s.title || "Untitled"}</p>
                  <div className="flex items-center gap-2">
                    <Badge tone={s.is_approved ? "success" : "neutral"}>{s.is_approved ? "Approved" : "Draft"}</Badge>
                    <button
                      type="button"
                      onClick={() => toggleApproved(s)}
                      className="rounded-lg border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--muted)] hover:text-[var(--foreground)]"
                    >
                      {s.is_approved ? "Unapprove" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(s.id)}
                      className="rounded-lg border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--danger)] hover:bg-[var(--danger)]/10"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="whitespace-pre-wrap text-[12.5px] text-[var(--muted)]">{s.script_text}</p>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Creative Angles
// ---------------------------------------------------------------------------

const EMPTY_ANGLE_FORM = {
  name: "",
  description: "",
  target_audience: "",
  emotional_direction: "",
  approved_messaging: "",
  restricted_messaging: "",
  visual_direction: "",
  cta_direction: "",
};

function CreativeAnglesTab({ productId }: { productId: string }) {
  const { showToast } = useToast();
  const [angles, setAngles] = useState<ProductCreativeAngle[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(EMPTY_ANGLE_FORM);

  const refresh = useCallback(() => {
    setLoading(true);
    listProductCreativeAngles(productId)
      .then(setAngles)
      .catch(() => showToast("Couldn't load creative angles.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleCreate() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await createProductCreativeAngle(productId, form);
      setForm(EMPTY_ANGLE_FORM);
      setAdding(false);
      showToast("Creative angle added", "success");
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't save that angle.", "danger");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteProductCreativeAngle(id);
      await refresh();
    } catch {
      showToast("Couldn't delete that angle.", "danger");
    }
  }

  return (
    <Card>
      <CardHeader
        title="Creative Angles"
        subtitle="Structured advertising angles this product can be approached from — targeting, messaging, and visual direction per angle."
      />
      <CardBody className="space-y-4">
        {!adding ? (
          <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
            + Add Creative Angle
          </Button>
        ) : (
          <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Angle name *</Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Tobacco-free alternative" />
              </div>
              <div className="sm:col-span-2">
                <Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>Target audience</Label>
                <Textarea value={form.target_audience} onChange={(e) => setForm({ ...form, target_audience: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>Emotional direction</Label>
                <Textarea value={form.emotional_direction} onChange={(e) => setForm({ ...form, emotional_direction: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>Approved messaging</Label>
                <Textarea value={form.approved_messaging} onChange={(e) => setForm({ ...form, approved_messaging: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>Restricted messaging</Label>
                <Textarea value={form.restricted_messaging} onChange={(e) => setForm({ ...form, restricted_messaging: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>Visual direction</Label>
                <Textarea value={form.visual_direction} onChange={(e) => setForm({ ...form, visual_direction: e.target.value })} rows={2} />
              </div>
              <div>
                <Label>CTA direction</Label>
                <Textarea value={form.cta_direction} onChange={(e) => setForm({ ...form, cta_direction: e.target.value })} rows={2} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="secondary" onClick={() => { setAdding(false); setForm(EMPTY_ANGLE_FORM); }}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleCreate} loading={saving} disabled={!form.name.trim()}>
                Save Angle
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-[13px] text-[var(--muted)]">Loading…</p>
        ) : angles.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)]">Not added yet.</p>
        ) : (
          <div className="space-y-3">
            {angles.map((a) => (
              <div key={a.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-[13.5px] font-semibold text-[var(--foreground)]">{a.name}</p>
                    {a.description && <p className="mt-0.5 text-[12.5px] text-[var(--muted)]">{a.description}</p>}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(a.id)}
                    className="shrink-0 rounded-lg border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--danger)] hover:bg-[var(--danger)]/10"
                  >
                    Delete
                  </button>
                </div>
                <div className="mt-2 grid gap-2 text-[12px] sm:grid-cols-2">
                  {a.target_audience && <p><span className="text-[var(--muted)]">Audience: </span>{a.target_audience}</p>}
                  {a.emotional_direction && <p><span className="text-[var(--muted)]">Emotion: </span>{a.emotional_direction}</p>}
                  {a.approved_messaging && <p><span className="text-[var(--muted)]">Approved: </span>{a.approved_messaging}</p>}
                  {a.restricted_messaging && <p><span className="text-[var(--muted)]">Restricted: </span>{a.restricted_messaging}</p>}
                  {a.visual_direction && <p><span className="text-[var(--muted)]">Visual: </span>{a.visual_direction}</p>}
                  {a.cta_direction && <p><span className="text-[var(--muted)]">CTA: </span>{a.cta_direction}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Hooks (product-specific — reuses the global Hook Studio table)
// ---------------------------------------------------------------------------

function HooksTab({ productId }: { productId: string }) {
  const { showToast } = useToast();
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [tone, setTone] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    listHooks({ product_id: productId, page_size: 50 })
      .then((r) => setHooks(r.items))
      .catch(() => showToast("Couldn't load hooks.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleCreate() {
    if (!text.trim()) return;
    setSaving(true);
    try {
      await createHook({ text: text.trim(), tone: tone.trim(), product_id: productId });
      setText("");
      setTone("");
      showToast("Hook added", "success");
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't save that hook.", "danger");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Hooks"
        subtitle="Product-specific hooks — captured here and available product-wide in Hook Studio."
      />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-end gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
          <div className="flex-1 min-w-[220px]">
            <Label>Hook text</Label>
            <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Still reaching for tobacco out of habit, not choice?" />
          </div>
          <div className="min-w-[140px]">
            <Label>Tone (optional)</Label>
            <Input value={tone} onChange={(e) => setTone(e.target.value)} placeholder="empathetic" />
          </div>
          <Button size="sm" onClick={handleCreate} loading={saving} disabled={!text.trim()}>
            + Add Hook
          </Button>
        </div>

        {loading ? (
          <p className="text-[13px] text-[var(--muted)]">Loading…</p>
        ) : hooks.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)]">Not added yet.</p>
        ) : (
          <div className="space-y-2">
            {hooks.map((h) => (
              <div key={h.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
                <p className="text-[13px] text-[var(--foreground)]">{h.text}</p>
                {h.tone && <Badge>{h.tone}</Badge>}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function IconExternalLink() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M18 13v6a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h6M14 3h7v7M21 3l-9 9"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Small shared display helpers
// ---------------------------------------------------------------------------

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function ReadRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">{label}</p>
      <p className="mt-0.5 whitespace-pre-wrap text-[13px] text-[var(--foreground)]">{value || "—"}</p>
    </div>
  );
}

function TagListRow({ label, items, tone = "neutral" }: { label: string; items: string[]; tone?: "neutral" | "success" | "danger" }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">{label}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-[13px] text-[var(--muted)]">—</p>
      ) : (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <Badge key={i} tone={tone}>
              {item}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
