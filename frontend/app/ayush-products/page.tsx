"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, listAyushProducts, productUploadFileUrl } from "@/lib/api";
import { PRODUCT_CATEGORIES, type AyushProduct } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { EmptyState } from "@/components/library/EmptyState";
import { useToast } from "@/components/shell/ToastProvider";

export default function AyushProductsPage() {
  const { showToast } = useToast();
  const [products, setProducts] = useState<AyushProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    listAyushProducts({ q: search || undefined })
      .then(setProducts)
      .catch((e) => showToast(e instanceof ApiError ? e.message : "Couldn't load AyushWellness products.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">AyushWellness Products</h1>
          <p className="mt-1 text-[13px] text-[var(--muted)]">
            Real product knowledge and assets the Content Pipeline can draw on for authentic, on-brand creative.
          </p>
        </div>
        <Link href="/ayush-products/new">
          <Button>+ Add Product</Button>
        </Link>
      </div>

      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search products…"
        className="max-w-sm"
      />

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading…</p>
      ) : products.length === 0 ? (
        <EmptyState
          title="No products yet"
          message="Add your first AyushWellness product — its knowledge and real assets will be available throughout the Content Pipeline."
          actionLabel="+ Add Product"
          onAction={() => (window.location.href = "/ayush-products/new")}
        />
      ) : (
        <div className="flex flex-col gap-8">
          {PRODUCT_CATEGORIES.map((cat) => {
            const inCategory = products.filter((p) => p.category === cat.value);
            if (inCategory.length === 0) return null;
            return (
              <div key={cat.value} className="flex flex-col gap-3">
                <div>
                  <h2 className="text-[15px] font-semibold text-[var(--foreground)]">{cat.label}</h2>
                  <p className="text-[12.5px] text-[var(--muted)]">{cat.description}</p>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {inCategory.map((p) => (
                    <ProductCard key={p.id} product={p} />
                  ))}
                </div>
              </div>
            );
          })}
          {(() => {
            const known = new Set(PRODUCT_CATEGORIES.map((c) => c.value));
            const other = products.filter((p) => !known.has(p.category));
            if (other.length === 0) return null;
            return (
              <div className="flex flex-col gap-3">
                <h2 className="text-[15px] font-semibold text-[var(--foreground)]">Other</h2>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {other.map((p) => (
                    <ProductCard key={p.id} product={p} />
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function ProductCard({ product }: { product: AyushProduct }) {
  return (
    <Link href={`/ayush-products/${product.id}`}>
      <Card className="group h-full transition-colors hover:border-[var(--accent)]/40">
        <CardBody className="flex flex-col gap-3 pt-6">
          <div className="aspect-square w-full overflow-hidden rounded-xl bg-[var(--surface-2)]">
            {product.primary_asset?.file_path ? (
              <img
                src={productUploadFileUrl(product.primary_asset.file_path)}
                alt={product.name}
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-[12px] text-[var(--muted)]">
                No image yet
              </div>
            )}
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-[var(--foreground)]">{product.name}</h3>
            {product.short_description && (
              <p className="mt-0.5 line-clamp-2 text-[12.5px] text-[var(--muted)]">{product.short_description}</p>
            )}
          </div>
          <p className="text-[11.5px] text-[var(--muted)]">
            {product.asset_count} asset{product.asset_count === 1 ? "" : "s"}
          </p>
        </CardBody>
      </Card>
    </Link>
  );
}
