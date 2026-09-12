// Quick-fill catalog for Hook Studio's "What are you creating content for?"
// picker. Hand-authored, same convention as contentFormats.ts/creativeAngles.ts.
//
// Deliberately carries ONLY product_name + category — no benefits/USPs/claims.
// Real product detail always comes from the existing structure/reference-analysis
// flow (POST /pipeline/structure), never invented here — see the "don't invent
// product claims" rule this catalog must respect.

export type CatalogProduct = { id: string; label: string };
export type CatalogCategory = { id: string; label: string; products: CatalogProduct[] };

export const CUSTOM_PRODUCT_ID = "custom";

function withCustom(products: { id: string; label: string }[]): CatalogProduct[] {
  return [...products, { id: CUSTOM_PRODUCT_ID, label: "Custom Product" }];
}

export const PRODUCT_CATEGORIES: CatalogCategory[] = [
  {
    id: "ayurveda_wellness",
    label: "Ayurveda / Wellness",
    products: withCustom([
      { id: "ayush_herbal_pan_masala", label: "Ayush Herbal Pan Masala" },
      { id: "ayurvedic_wellness", label: "Ayurvedic Wellness" },
      { id: "herbal_products", label: "Herbal Products" },
      { id: "ayurvedic_supplements", label: "Ayurvedic Supplements" },
      { id: "herbal_tea", label: "Herbal Tea" },
      { id: "natural_remedies", label: "Natural Remedies" },
    ]),
  },
  {
    id: "skincare",
    label: "Skincare",
    products: withCustom([
      { id: "ayush_skin_care", label: "Ayush Skin Care" },
      { id: "herbal_skincare", label: "Herbal Skincare" },
      { id: "ayurvedic_skincare", label: "Ayurvedic Skincare" },
      { id: "face_care", label: "Face Care" },
      { id: "hair_care", label: "Hair Care" },
      { id: "beauty_personal_care", label: "Beauty & Personal Care" },
    ]),
  },
  {
    id: "healthcare",
    label: "Healthcare",
    products: withCustom([
      { id: "general_healthcare", label: "General Healthcare" },
      { id: "preventive_wellness", label: "Preventive Wellness" },
      { id: "health_education", label: "Health Education" },
      { id: "nutrition", label: "Nutrition" },
      { id: "fitness_wellness", label: "Fitness & Wellness" },
    ]),
  },
  {
    id: "food_beverage",
    label: "Food & Beverage",
    products: withCustom([
      { id: "herbal_drinks", label: "Herbal Drinks" },
      { id: "tea", label: "Tea" },
      { id: "healthy_foods", label: "Healthy Foods" },
      { id: "beverages", label: "Beverages" },
      { id: "nutritional_products", label: "Nutritional Products" },
    ]),
  },
  {
    id: "lifestyle",
    label: "Lifestyle",
    products: withCustom([
      { id: "personal_care", label: "Personal Care" },
      { id: "fitness", label: "Fitness" },
      { id: "mental_wellness", label: "Mental Wellness" },
      { id: "healthy_lifestyle", label: "Healthy Lifestyle" },
      { id: "daily_wellness", label: "Daily Wellness" },
    ]),
  },
  {
    id: "other",
    label: "Other",
    products: [
      { id: "custom_product", label: "Custom Product" },
      { id: CUSTOM_PRODUCT_ID, label: "Custom Category" },
    ],
  },
];
