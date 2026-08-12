export type SourceType = "url" | "description" | "none";

export type ProductInput = {
  product_name: string;
  target_audience: string;
  source_type: SourceType;
  source_url?: string;
  source_description?: string;
  manual_ingredients?: string;
  manual_usp?: string;
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
};

export type ScriptLine = {
  text: string;
  visual_tags: string[];
  scene_label?: string;
  visual_direction?: string;
  camera_angle?: string;
  emotion?: string;
  lighting?: string;
  transition_note?: string;
};

export type RewriteDirective = "improve" | "make_viral" | "make_emotional" | "increase_conversion" | "rewrite";

export type GeneratedScript = {
  hook: ScriptLine;
  body: ScriptLine[];
  cta: ScriptLine;
  situation?: StorySituation;
  bgm_suggestion?: string;
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
  visual_tags: string[];
  scene_label?: string;
  visual_direction?: string;
  camera_angle?: string;
  emotion?: string;
  lighting?: string;
  transition_note?: string;
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
