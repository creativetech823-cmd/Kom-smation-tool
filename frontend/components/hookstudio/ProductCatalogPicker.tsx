"use client";

import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { PRODUCT_CATEGORIES, CUSTOM_PRODUCT_ID } from "@/lib/productCatalog";

const SELECT_CLASS =
  "w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40";

export function ProductCatalogPicker({
  onSelect,
}: {
  onSelect: (productName: string, category: string) => void;
}) {
  const [categoryId, setCategoryId] = useState(PRODUCT_CATEGORIES[0].id);
  const [productId, setProductId] = useState("");

  const category = PRODUCT_CATEGORIES.find((c) => c.id === categoryId) ?? PRODUCT_CATEGORIES[0];

  function handleCategoryChange(nextCategoryId: string) {
    setCategoryId(nextCategoryId);
    setProductId("");
  }

  function handleProductChange(nextProductId: string) {
    setProductId(nextProductId);
    const nextCategory = PRODUCT_CATEGORIES.find((c) => c.id === categoryId) ?? category;
    const product = nextCategory.products.find((p) => p.id === nextProductId);
    if (!product) return;
    if (nextProductId === CUSTOM_PRODUCT_ID) {
      onSelect("", nextCategory.id === "other" ? "" : nextCategory.label);
      return;
    }
    onSelect(product.label, nextCategory.label);
  }

  return (
    <Card>
      <CardHeader title="What are you creating content for?" subtitle="Pick a product to quick-fill the details below, or choose Custom Product to enter your own." />
      <CardBody>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Category</label>
            <select value={categoryId} onChange={(e) => handleCategoryChange(e.target.value)} className={SELECT_CLASS}>
              {PRODUCT_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-[var(--muted)]">Product</label>
            <select value={productId} onChange={(e) => handleProductChange(e.target.value)} className={SELECT_CLASS}>
              <option value="" disabled>
                Select a product…
              </option>
              {category.products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
