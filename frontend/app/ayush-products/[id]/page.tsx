import { ProductDetailClient } from "./ProductDetailClient";

export default async function AyushProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProductDetailClient productId={id} />;
}
