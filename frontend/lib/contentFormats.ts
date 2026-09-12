// Display metadata for Content Type / Format selection — mirrors
// backend/app/services/content_formats.py by hand, same convention used
// throughout this codebase (no shared codegen; see creativeAngles.ts).

export type FormatOption = { value: string; label: string; emoji: string; hint: string };

export const VIDEO_FORMATS: FormatOption[] = [
  { value: "podcast", label: "Podcast", emoji: "\u{1F399}\u{FE0F}", hint: "Host + guest conversation" },
  { value: "whiteboard", label: "Whiteboard", emoji: "\u{1F58A}\u{FE0F}", hint: "Drawn explainer, scene by scene" },
  { value: "animation", label: "Animation", emoji: "\u{1F3A8}", hint: "Animated scenes with voiceover" },
  { value: "video_ad", label: "Video Ad", emoji: "\u{1F3AC}", hint: "Classic hook-problem-solution ad" },
  { value: "ugc_talking_head", label: "UGC / Talking Head", emoji: "\u{1F4F1}", hint: "One person, direct to camera" },
  { value: "explainer", label: "Explainer", emoji: "\u{1F4A1}", hint: "Teach one idea, step by step" },
  { value: "cinematic", label: "Cinematic", emoji: "\u{1F3A5}", hint: "Film-like visuals, sparse voiceover" },
  { value: "product_showcase", label: "Product Showcase", emoji: "\u{1F3AF}", hint: "Feature-by-feature demo" },
  { value: "educational_video", label: "Educational Video", emoji: "\u{1F393}", hint: "Genuinely teaches something" },
  { value: "social_media_reel", label: "Social Media Reel", emoji: "\u{26A1}", hint: "Fast cuts, native short-form" },
  { value: "storytelling", label: "Storytelling", emoji: "\u{1F4D6}", hint: "Full narrative arc" },
  { value: "testimonial", label: "Testimonial", emoji: "\u{1F5E3}\u{FE0F}", hint: "Real-customer voice" },
  { value: "product_demo", label: "Product Demo", emoji: "\u{1F4E6}", hint: "Step-by-step walkthrough" },
  { value: "custom", label: "Custom", emoji: "\u{2728}", hint: "Describe your own format" },
];

export const STATIC_FORMATS: FormatOption[] = [
  { value: "instagram_post", label: "Instagram Post", emoji: "\u{1F5BC}\u{FE0F}", hint: "Feed post, 1:1" },
  { value: "instagram_story", label: "Instagram Story", emoji: "\u{1F4F2}", hint: "Full-bleed vertical, glanced fast" },
  { value: "carousel", label: "Carousel", emoji: "\u{1F501}", hint: "Multi-slide swipe set" },
  { value: "banner_ad", label: "Banner Ad", emoji: "\u{1FA84}", hint: "Small, split-second impact" },
  { value: "product_advertisement", label: "Product Advertisement", emoji: "\u{1F6CD}\u{FE0F}", hint: "Product front and center" },
  { value: "infographic", label: "Infographic", emoji: "\u{1F4CA}", hint: "Data points / steps at a glance" },
  { value: "quote_graphic", label: "Quote / Text Graphic", emoji: "\u{1F4AC}", hint: "One quotable line" },
  { value: "educational_graphic", label: "Educational Graphic", emoji: "\u{1F4DA}", hint: "Teach, then a soft CTA" },
  { value: "promotional_creative", label: "Promotional Creative", emoji: "\u{1F4E3}", hint: "Offer-led, urgency-driven" },
  { value: "thumbnail", label: "Thumbnail", emoji: "\u{1F5BC}\u{FE0F}", hint: "Bold, click-winning, minimal text" },
  { value: "product_feature", label: "Product Feature", emoji: "\u{1F50D}", hint: "Spotlight one feature" },
  { value: "custom", label: "Custom", emoji: "\u{2728}", hint: "Describe your own format" },
];

export const TONE_OPTIONS: { value: string; label: string }[] = [
  { value: "Professional", label: "Professional" },
  { value: "Casual", label: "Casual" },
  { value: "Conversational", label: "Conversational" },
  { value: "Educational", label: "Educational" },
  { value: "Emotional", label: "Emotional" },
  { value: "Bold", label: "Bold" },
  { value: "Funny", label: "Funny" },
  { value: "Premium", label: "Premium" },
  { value: "Persuasive", label: "Persuasive" },
  { value: "Storytelling", label: "Storytelling" },
];

export function formatLabel(contentType: "video" | "static", value: string): string {
  const list = contentType === "static" ? STATIC_FORMATS : VIDEO_FORMATS;
  return list.find((f) => f.value === value)?.label ?? value;
}

const STATIC_ASPECT_RATIOS: Record<string, string> = {
  instagram_post: "1:1",
  instagram_story: "9:16",
  carousel: "1:1",
  banner_ad: "16:9",
  product_advertisement: "4:5",
  infographic: "4:5",
  quote_graphic: "1:1",
  educational_graphic: "4:5",
  promotional_creative: "4:5",
  thumbnail: "16:9",
  product_feature: "4:5",
};

export function staticAspectRatio(format: string): string {
  return STATIC_ASPECT_RATIOS[format] ?? "1:1";
}
