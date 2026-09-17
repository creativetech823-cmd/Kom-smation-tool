export type SourceType = "url" | "description" | "none";

export type ContentType = "video" | "static";

export type VideoFormat =
  | "podcast"
  | "whiteboard"
  | "animation"
  | "video_ad"
  | "ugc_talking_head"
  | "explainer"
  | "cinematic"
  | "product_showcase"
  | "educational_video"
  | "social_media_reel"
  | "storytelling"
  | "testimonial"
  | "product_demo"
  | "custom";

export type StaticFormat =
  | "instagram_post"
  | "instagram_story"
  | "carousel"
  | "banner_ad"
  | "product_advertisement"
  | "infographic"
  | "quote_graphic"
  | "educational_graphic"
  | "promotional_creative"
  | "thumbnail"
  | "product_feature"
  | "custom";

export type ScriptTone =
  | "Professional"
  | "Casual"
  | "Conversational"
  | "Educational"
  | "Emotional"
  | "Bold"
  | "Funny"
  | "Premium"
  | "Persuasive"
  | "Storytelling";

export type ReferenceKind =
  | "pdf"
  | "docx"
  | "pptx"
  | "doc"
  | "ppt"
  | "txt"
  | "csv"
  | "xlsx"
  | "zip"
  | "image"
  | "video"
  | "audio"
  | "website"
  | "google_drive"
  | "youtube"
  | "dropbox"
  | "notion";

export type ReferenceAnalysis = "analyzed" | "coming_soon" | "not_supported" | "failed";

export type ReferenceMaterial = {
  id: string;
  kind: ReferenceKind;
  filename?: string;
  source_url?: string;
  stored_path?: string;
  mime_type?: string;
  size_bytes?: number;
  analysis: ReferenceAnalysis;
  extracted_text: string;
  truncated: boolean;
  note: string;
};

export type FetchUrlResult = {
  raw_text: string;
  title: string;
  char_count: number;
  truncated: boolean;
};

export type AutoFillSuggestion = {
  product_name: string;
  target_audience: string;
  source_description: string;
  product_category: string;
  brand: string;
  keywords: string[];
  key_benefits: string[];
  confidence: number;
};

export type ProductInput = {
  product_name: string;
  target_audience: string;
  source_type: SourceType;
  source_url?: string;
  source_description?: string;
  manual_ingredients?: string;
  manual_usp?: string;
  source_url_raw_text?: string;
  reference_materials?: ReferenceMaterial[];
};

export type StructuredProduct = {
  product_name: string;
  target_audience: string;
  ingredients: string[];
  usp: string;
  tone: string;
  key_benefits: string[];
  industry: string;
  pain_points: string[];
  marketing_angle: string;
  key_emotions: string[];
  keywords: string[];
  missing_fields: string[];
  confidence: number;
};

export type StorySituation = {
  id: string;
  title: string;
  description: string;
  emotion: string;
  persona: string;
  marketing_angle: string;
  category: string;
  difficulty: string;
  estimated_length: string;
  virality_score: number;
  recommended_angles: string[];
};

export type ScriptSection =
  | "hook"
  | "problem"
  | "science"
  | "story"
  | "product_intro"
  | "ingredients"
  | "benefits"
  | "objection_handling"
  | "cta";

export type ScriptRegenerateScope =
  | "full"
  | "hook"
  | "cta"
  | "science"
  | "story"
  | "product_explanation"
  | "emotional_tone"
  | "length"
  | "specific_scene";

export type ScriptLine = {
  text: string;
  on_screen_text?: string;
  visual_tags: string[];
  scene_label?: string;
  section?: ScriptSection;
  visual_direction?: string;
  camera_angle?: string;
  emotion?: string;
  lighting?: string;
  transition_note?: string;
  duration_seconds?: number;
  b_roll?: string[];
  sfx?: string;
  ai_image_prompt?: string;
  ai_video_prompt?: string;
};

export type RewriteDirective =
  | "improve"
  | "make_viral"
  | "make_emotional"
  | "increase_conversion"
  | "rewrite"
  | "make_shorter"
  | "make_longer"
  | "more_cinematic"
  | "more_conversational"
  | "more_scientific"
  | "more_persuasive"
  | "simplify"
  | "professional_tone"
  | "funny"
  | "fear_based"
  | "doctor_style"
  | "storytelling_style"
  | "ugc_style"
  | "podcast_style"
  | "meta_glasses_pov"
  | "translate";

export type ScriptLanguage =
  | "english"
  | "hindi"
  | "hinglish"
  | "marathi"
  | "gujarati"
  | "tamil"
  | "telugu"
  | "bengali"
  | "kannada"
  | "malayalam"
  | "custom";

/** One line of the Creative Breakdown — a deterministic readout of an
 * actual upstream creative decision (territory/premise/Creative Director
 * evaluation), never a fresh explanation generated for display. A value
 * containing "not available"/"not scored" means that pipeline stage didn't
 * run or didn't produce this piece for this particular script — render it
 * as an honest unavailable state, never substitute other copy. */
export type CreativeBreakdown = {
  hook_reason: string;
  territory_reason: string;
  human_insight: string;
  behavioral_tension: string;
  situation_reason: string;
  product_entry_reason: string;
  narrative_device_reason: string;
  payoff_reason: string;
  memorability_reason: string;
  visual_executability_reason: string;
  distinctiveness_reason: string;
  claims_avoided: string[];
  remaining_weaknesses: string[];
  /** False when one or more lines above are "not available" placeholders
   * because an upstream stage never ran for this script. */
  fully_grounded: boolean;
};

export type CreativeQualityDimension = {
  name: string;
  /** null = not scored (no Creative Director evaluation attached to this
   * script) — distinct from an actual 0, never coerced to a fake number. */
  score: number | null;
  evidence: string;
  source_creative_decision: string;
};

export type CreativeQualityAssessment = {
  dimensions: CreativeQualityDimension[];
  /** null = no evaluation attached to judge pass/fail from. */
  overall_passed: boolean | null;
};

export type GeneratedScript = {
  hook: ScriptLine;
  body: ScriptLine[];
  cta: ScriptLine;
  situation?: StorySituation;
  bgm_suggestion?: string;
  creative_angle?: string;
  script_language?: ScriptLanguage;
  custom_language?: string;
  target_duration?: string;
  estimated_duration_seconds?: number;
  content_type?: ContentType;
  format?: string;
  format_description?: string;
  tone?: string;
  /** Internal bookkeeping — which creative mechanism the model used (e.g.
   * "curiosity_gap"), so a later regenerate can be steered toward a
   * genuinely different one. Not surfaced in the UI. */
  creative_mechanism?: string;
  /** The specific human insight the story was built around, and which
   * creative_architecture.ARCHITECTURES key structured it — set on fresh
   * generations only; absent on narrow regenerations and older scripts. */
  human_insight?: string;
  creative_architecture?: string;
  /** Present only on a fresh generation whose creative pre-stage chain
   * (territory/premise/Creative Director evaluation) actually ran — absent
   * (undefined/null) on a regenerate_script_section() result, which has no
   * such chain to draw from. Never poll/regenerate for it; if absent, the
   * script itself is still complete and fully usable. */
  creative_breakdown?: CreativeBreakdown | null;
  creative_quality_assessment?: CreativeQualityAssessment | null;
};

export type ScriptSuggestionCategory =
  | "hook"
  | "opening_line"
  | "emotional_impact"
  | "clarity"
  | "flow"
  | "storytelling"
  | "product_integration"
  | "cta"
  | "repetition"
  | "length"
  | "natural_hinglish"
  | "brand_mention"
  | "audience_relevance"
  | "virality";

export type ScriptSuggestionCard = {
  id: string;
  category: ScriptSuggestionCategory;
  title: string;
  why: string;
  line_id: string | null;
  current_text: string | null;
  suggested_text: string | null;
  suggested_scope: ScriptRegenerateScope | null;
  instruction: string | null;
};

export type SmartScriptSuggestionsResult = {
  status: "strong" | "needs_work";
  headline: string;
  cards: ScriptSuggestionCard[];
  optional_ideas: string[];
};

export type ScriptCommandSelection = {
  line_id: string;
  selected_text: string;
};

export type ScriptCommandResult = {
  is_full_rewrite: boolean;
  title: string;
  why: string;
  line_id: string | null;
  current_text: string | null;
  suggested_text: string | null;
  full_script_after: GeneratedScript | null;
};

export type ComplianceViolation = {
  phrase: string;
  reason: string;
  severity: "blocker" | "warning";
  claim_type?: string;
  suggested_fix?: string;
};

export type ComplianceResult = {
  passed: boolean;
  violations: ComplianceViolation[];
  notes: string;
};

export type AssetCandidate = {
  source: string;
  url: string;
  thumbnail_url: string;
  width: number;
  height: number;
};

export type SelectedAsset = {
  line_id: string;
  tag_used: string;
  broadened: boolean;
  candidate: AssetCandidate | null;
  reasoning: string;
  provider_error?: boolean;
};

export type VoiceoverResult = {
  line_id: string;
  hindi_text: string;
  audio_path: string;
  duration_seconds: number;
};

export type MotionGenerationResult = {
  line_id: string;
  video_path: string;
  prompt_used: string;
};

export type RenderLine = {
  text: string;
  image_url: string;
  video_url?: string;
  audio_url?: string;
  min_duration_seconds?: number;
  section?: ScriptSection;
  scene_label?: string;
  on_screen_text?: string;
  visual_direction?: string;
  camera_angle?: string;
  emotion?: string;
  is_product_asset?: boolean;
};

export type RenderResult = {
  output_path: string;
  duration_seconds: number;
};

/** A single line of the flattened script, tagged with its role for asset/render bookkeeping. */
export type FlatLine = {
  id: string;
  role: "hook" | "body" | "cta";
  text: string;
  on_screen_text?: string;
  visual_tags: string[];
  scene_label?: string;
  section?: ScriptSection;
  visual_direction?: string;
  camera_angle?: string;
  emotion?: string;
  lighting?: string;
  transition_note?: string;
  duration_seconds?: number;
  b_roll?: string[];
  sfx?: string;
  ai_image_prompt?: string;
  ai_video_prompt?: string;
};

export function flattenScript(script: GeneratedScript): FlatLine[] {
  return [
    { id: "hook", role: "hook", ...script.hook },
    ...script.body.map((line, i) => ({
      id: `body_${i}`,
      role: "body" as const,
      ...line,
    })),
    { id: "cta", role: "cta", ...script.cta },
  ];
}

export type VisualSceneLabel =
  | "hook"
  | "emotional"
  | "transformation"
  | "product_shot"
  | "social_proof"
  | "testimonial"
  | "ugc"
  | "lifestyle";

export type VisualConceptStyleParams = {
  style: string;
  lighting: string;
  camera: string;
  mood: string;
  background: string;
  characters: string;
  composition: string;
  brand_colors: string;
  logo_placement: string;
  product_position: string;
  negative_prompt: string;
};

export type VisualConceptScores = {
  visual_impact: number;
  ad_quality: number;
  ctr_prediction: number;
  emotion_score: number;
  brand_match: number;
  photorealism: number;
  notes: string;
};

export type TestImageResult = {
  image_path: string;
  used_model: string;
  elapsed_seconds: number;
};

export type VisualConceptDebugInfo = {
  api_key_loaded: boolean;
  model: string;
  api_url: string;
  internet_access: boolean;
};

export type StaticVisualResult = {
  image_path: string;
  used_model: string;
  elapsed_seconds: number;
  seed: number | null;
};

export type StaticImageStatus = "pending" | "generating" | "completed" | "failed";

export type StaticImageState = {
  status: StaticImageStatus;
  imagePath: string | null;
  error: string | null;
};

export type VisualConceptStatus = "pending" | "generating" | "completed" | "failed";

export type VisualConcept = {
  id: string;
  scene_number: number;
  scene_title: string;
  scene_label: VisualSceneLabel;
  creative_angle: string;
  aspect_ratio: string;
  prompt: string;
  style_params: VisualConceptStyleParams;
  image_path: string;
  scores: VisualConceptScores | null;
  favorite: boolean;
  seed: number | null;
  resolution: string;
  generation_time_seconds: number;
  used_model: string;
  status: VisualConceptStatus;
  error: string | null;
};

export type VisualVariationStyle =
  | "photorealistic"
  | "luxury_product"
  | "studio_photography"
  | "commercial_advertisement"
  | "lifestyle"
  | "fashion"
  | "apple_style"
  | "nike_style"
  | "cinematic"
  | "moody"
  | "bollywood"
  | "documentary"
  | "meta_glasses_pov"
  | "ugc"
  | "instagram_ad"
  | "facebook_ad"
  | "luxury_cosmetic"
  | "minimal"
  | "hyper_realistic"
  | "generate_similar"
  | "different_angle";

// ---------------------------------------------------------------------------
// Library — Projects, Content Assets, Hooks, Templates, History
// ---------------------------------------------------------------------------

export type ProjectStatus = "active" | "archived";

export type Project = {
  id: string;
  name: string;
  description: string;
  product_category: string;
  status: ProjectStatus;
  pipeline_state: Record<string, unknown> | null;
  pipeline_stage: string | null;
  created_at: string;
  updated_at: string;
  asset_count: number;
};

export type ContentAssetType = "script" | "image" | "video" | "voiceover" | "render";

export type ContentAsset = {
  id: string;
  project_id: string | null;
  asset_type: ContentAssetType;
  title: string;
  product_name: string;
  file_path: string | null;
  thumbnail_path: string | null;
  content_json: Record<string, unknown> | null;
  source_hook_id: string | null;
  source_hook_text: string | null;
  model_used: string | null;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  project_name: string | null;
};

export type Hook = {
  id: string;
  text: string;
  category: string;
  platform: string;
  tone: string;
  usage_count: number;
  is_favorite: boolean;
  created_at: string;
  product_id: string | null;
};

export type HookListResult = {
  items: Hook[];
  total: number;
  page: number;
  page_size: number;
};

export type TemplateKind = "static" | "video";

export type Template = {
  id: string;
  name: string;
  kind: TemplateKind;
  category: string;
  description: string;
  thumbnail_key: string;
  is_official: boolean;
  config_json: Record<string, unknown> | null;
  is_favorite: boolean;
  created_at: string;
};

export type HistoryEventType =
  | "created_project"
  | "generated_script"
  | "generated_image"
  | "generated_video"
  | "generated_voiceover"
  | "used_template"
  | "used_hook"
  | "edited_script"
  | "exported_video"
  | "deleted_content"
  | "restored_content";

export type HistoryEvent = {
  id: string;
  event_type: HistoryEventType;
  summary: string;
  project_id: string | null;
  asset_id: string | null;
  created_at: string;
  project_name: string | null;
};

// ---------------------------------------------------------------------------
// AyushWellness Product Library
// ---------------------------------------------------------------------------

export type ProductCategory = "herbal_health" | "nutraceuticals" | string;

// REAL PRODUCT (genuine photography — eligible to become the primary/hero
// asset): product_image, product_packshot, product_lifestyle, ingredient_image
// REFERENCE MATERIAL (inspiration/context — never eligible to become
// primary): reference_image, advertisement, reference_video, other
export type ProductAssetType =
  | "product_image"
  | "product_packshot"
  | "product_lifestyle"
  | "ingredient_image"
  | "reference_image"
  | "advertisement"
  | "reference_video"
  | "other";

export type ProductAsset = {
  id: string;
  product_id: string;
  asset_type: ProductAssetType;
  file_path: string | null;
  thumbnail_path: string | null;
  title: string;
  description: string;
  tags: string[];
  reference_state: string | null;
  source_url: string | null;
  learning_notes: string;
  style_notes: string;
  sort_order: number;
  is_primary: boolean;
  is_active: boolean;
  // Backend-authoritative classification — real product photography vs
  // reference/inspiration material. Always trust this over re-deriving the
  // same distinction from asset_type in the frontend.
  is_real_product_asset: boolean;
  created_at: string;
  updated_at: string;
};

export type AyushProduct = {
  id: string;
  name: string;
  slug: string;
  category: ProductCategory;
  status: "active" | "archived";
  short_description: string;
  description: string;
  product_url: string | null;
  price: string | null;

  display_name: string;
  subcategory: string;
  brand: string;
  sku: string;
  marketplace_urls: string[];
  landing_page_url: string | null;

  target_audience: string;
  primary_problem: string;
  positioning: string;
  usp: string;
  ingredients: string[];
  benefits: string[];
  usage: string;
  how_it_works: string;
  who_is_it_for: string;
  cautions: string;

  approved_claims: string[];
  prohibited_claims: string[];
  mandatory_wording: string;
  never_say: string;

  secondary_target_audience: string;
  customer_objections: string[];
  buying_triggers: string[];
  awareness_level: string;

  pain_points: string[];
  emotional_triggers: string[];
  advertising_angles: string[];
  preferred_tone: string;
  preferred_language: string;
  cta_text: string;
  winning_hooks: string[];
  creative_notes: string;
  brand_personality: string;
  words_to_use: string[];
  words_to_avoid: string[];
  visual_style: string;
  visual_exclusions: string;

  primary_asset: ProductAsset | null;
  asset_count: number;

  created_at: string;
  updated_at: string;

  // Duplicate-prevention signals — only meaningful right after POST /products.
  is_existing?: boolean;
  possible_duplicate?: { id: string; name: string } | null;
};

export type ProductReferenceScript = {
  id: string;
  product_id: string;
  title: string;
  script_text: string;
  format: string | null;
  notes: string;
  is_approved: boolean;
  created_at: string;
  updated_at: string;
};

export type ProductCreativeAngle = {
  id: string;
  product_id: string;
  name: string;
  description: string;
  target_audience: string;
  emotional_direction: string;
  approved_messaging: string;
  restricted_messaging: string;
  visual_direction: string;
  cta_direction: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type ProductContext = {
  product_id: string;
  name: string;
  category: string;
  short_description: string;
  usp: string;
  target_audience: string;
  primary_problem: string;
  positioning: string;
  ingredients: string[];
  benefits: string[];
  approved_claims: string[];
  prohibited_claims: string[];
  mandatory_wording: string;
  preferred_tone: string;
  preferred_language: string;
  cta_text: string;
  winning_hooks: string[];
  reference_script_excerpts: string[];
  primary_asset_url: string | null;
  never_say: string;
  preferred_visual_style: string;
  visual_exclusions: string;
  words_to_use: string[];
  words_to_avoid: string[];
  creative_angles: string[];
  approved_hooks: string[];
  has_real_product_asset: boolean;
};

export type ProductImportImageCandidate = {
  url: string;
  alt: string;
};

export type ProductImportResult = {
  source_url: string;
  name: string;
  short_description: string;
  description: string;
  price: string | null;
  brand: string;
  ingredients: string[];
  benefits: string[];
  usage: string;
  variants: string[];
  images: ProductImportImageCandidate[];
  confidence: number;
  warnings: string[];
};

export const PRODUCT_CATEGORIES: { value: ProductCategory; label: string; description: string }[] = [
  { value: "herbal_health", label: "Herbal Health Solutions", description: "Herbal health products, tobacco-free alternatives, etc." },
  { value: "nutraceuticals", label: "Nutraceutical Products", description: "Supplements, vitamins, wellness products, etc." },
];
