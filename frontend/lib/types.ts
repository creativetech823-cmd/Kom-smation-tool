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
  missing_fields: string[];
  confidence: number;
};

export type ScriptLine = {
  text: string;
  visual_tags: string[];
};

export type GeneratedScript = {
  hook: ScriptLine;
  body: ScriptLine[];
  cta: ScriptLine;
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
};

export function flattenScript(script: GeneratedScript): FlatLine[] {
  return [
    { id: "hook", role: "hook", text: script.hook.text, visual_tags: script.hook.visual_tags },
    ...script.body.map((line, i) => ({
      id: `body_${i}`,
      role: "body" as const,
      text: line.text,
      visual_tags: line.visual_tags,
    })),
    { id: "cta", role: "cta", text: script.cta.text, visual_tags: script.cta.visual_tags },
  ];
}
