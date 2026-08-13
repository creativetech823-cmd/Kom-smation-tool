export type SourceType = "url" | "description" | "none";

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
  | "product_explanation"
  | "emotional_tone"
  | "length";

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

export type RewriteDirective = "improve" | "make_viral" | "make_emotional" | "increase_conversion" | "rewrite";

export type ScriptLanguage = "english" | "hindi" | "hinglish";

export type GeneratedScript = {
  hook: ScriptLine;
  body: ScriptLine[];
  cta: ScriptLine;
  situation?: StorySituation;
  bgm_suggestion?: string;
  creative_angle?: string;
  script_language?: ScriptLanguage;
  target_duration?: string;
};

export type ComplianceViolation = {
  phrase: string;
  reason: string;
  severity: "blocker" | "warning";
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
