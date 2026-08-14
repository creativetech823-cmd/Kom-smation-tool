import type {
  AutoFillSuggestion,
  ComplianceResult,
  FetchUrlResult,
  GeneratedScript,
  MotionGenerationResult,
  ProductInput,
  ReferenceMaterial,
  RenderLine,
  RenderResult,
  RewriteDirective,
  ScriptLanguage,
  ScriptRegenerateScope,
  ScriptSuggestion,
  SelectedAsset,
  StorySituation,
  StructuredProduct,
  TestImageResult,
  VisualConcept,
  VisualConceptDebugInfo,
  VisualConceptScores,
  VisualVariationStyle,
  VoiceoverResult,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function get<TResponse>(path: string): Promise<TResponse> {
  const res = await fetch(`${API_BASE}${path}`);

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail),
      res.status
    );
  }

  return res.json() as Promise<TResponse>;
}

async function post<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail),
      res.status
    );
  }

  return res.json() as Promise<TResponse>;
}

async function postMultipart<TResponse>(path: string, formData: FormData): Promise<TResponse> {
  // No Content-Type header — the browser sets it (with the multipart boundary) itself.
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail),
      res.status
    );
  }

  return res.json() as Promise<TResponse>;
}

async function postBlob(path: string, body: unknown): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail),
      res.status
    );
  }

  return res.blob();
}

export function structureProduct(input: ProductInput) {
  return post<StructuredProduct>("/pipeline/structure", input);
}

export function fetchUrlContent(payload: { url: string }) {
  return post<FetchUrlResult>("/pipeline/fetch-url", payload);
}

export function autofillProduct(payload: { raw_text: string; source_url?: string }) {
  return post<AutoFillSuggestion>("/pipeline/autofill-product", payload);
}

export function uploadReferenceMaterial(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return postMultipart<ReferenceMaterial>("/pipeline/reference-materials/upload", formData);
}

export function addReferenceUrl(payload: { url: string }) {
  return post<ReferenceMaterial>("/pipeline/reference-materials/url", payload);
}

export function referenceFileUrl(storedPath: string): string {
  const filename = storedPath.split(/[\\/]/).pop();
  return `${API_BASE}/reference-uploads/${filename}`;
}

export function generateStorySituations(payload: {
  structured_product: StructuredProduct;
  product_category: string;
  count?: number;
  exclude_titles?: string[];
}) {
  return post<{ situations: StorySituation[] }>("/pipeline/story-situations", payload).then(
    (r) => r.situations
  );
}

export function generateScript(payload: {
  structured_product: StructuredProduct;
  selected_situation: StorySituation;
  product_category: string;
  platform?: string;
  similar_past_winners?: string[];
  max_line_chars?: number;
  creative_angle?: string;
  script_language?: ScriptLanguage;
  target_duration?: string;
}) {
  return post<GeneratedScript>("/pipeline/generate-script", payload);
}

export function regenerateScriptSection(payload: {
  structured_product: StructuredProduct;
  selected_situation: StorySituation;
  product_category: string;
  platform?: string;
  max_line_chars?: number;
  creative_angle?: string;
  script_language?: ScriptLanguage;
  target_duration?: string;
  current_script: GeneratedScript;
  scope: ScriptRegenerateScope;
  custom_instruction?: string;
  target_word_count?: number;
}) {
  return post<GeneratedScript>("/pipeline/regenerate-script-section", payload);
}

export function rewriteLine(payload: {
  text: string;
  directive: RewriteDirective;
  max_chars?: number;
  target_language?: ScriptLanguage;
}) {
  return post<{ text: string }>("/pipeline/rewrite-line", payload);
}

export function generateAlternatives(payload: { text: string; directive: RewriteDirective; max_chars?: number }) {
  return post<{ alternatives: string[] }>("/pipeline/generate-alternatives", payload);
}

export function getScriptSuggestions(payload: { script: GeneratedScript; target_duration?: string }) {
  return post<{ suggestions: ScriptSuggestion[] }>("/pipeline/script-suggestions", payload);
}

export function auditCompliance(payload: {
  script_text: string;
  product_category: string;
  product_name: string;
}) {
  return post<ComplianceResult>("/pipeline/compliance-audit", payload);
}

export function sourceAsset(payload: { line_id: string; visual_tags: string[] }) {
  return post<SelectedAsset>("/pipeline/source-asset", payload);
}

export function renderVideo(payload: {
  product_name: string;
  lines: RenderLine[];
  seconds_per_line?: number;
}) {
  return post<RenderResult>("/pipeline/render", payload);
}

export function renderFileUrl(outputPath: string): string {
  const filename = outputPath.split(/[\\/]/).pop();
  return `${API_BASE}/renders/${filename}`;
}

export function generateVoiceover(payload: { lines: { line_id: string; text: string }[] }) {
  return post<VoiceoverResult[]>("/pipeline/voiceover", payload);
}

export function audioFileUrl(audioPath: string): string {
  const filename = audioPath.split(/[\\/]/).pop();
  return `${API_BASE}/audio/${filename}`;
}

export function generateMotion(payload: { line_id: string; image_url: string; visual_tags: string[] }) {
  return post<MotionGenerationResult>("/pipeline/generate-motion", payload);
}

export function motionFileUrl(videoPath: string): string {
  const filename = videoPath.split(/[\\/]/).pop();
  return `${API_BASE}/motion/${filename}`;
}

export function visualFileUrl(imagePath: string): string {
  const filename = imagePath.split(/[\\/]/).pop();
  return `${API_BASE}/visuals/${filename}`;
}

export function generateVisualConcepts(payload: {
  structured_product: StructuredProduct;
  script: GeneratedScript;
  situation: StorySituation;
  creative_angle?: string;
  product_category?: string;
}) {
  return post<{ concepts: VisualConcept[] }>("/pipeline/visual-concepts", payload).then((r) => r.concepts);
}

export function regenerateVisualConcept(payload: {
  structured_product: StructuredProduct;
  script: GeneratedScript;
  situation: StorySituation;
  creative_angle?: string;
  concept: VisualConcept;
  variation_style?: VisualVariationStyle;
  as_new_variation?: boolean;
  is_manual_edit?: boolean;
}) {
  return post<VisualConcept>("/pipeline/visual-concepts/regenerate", payload);
}

export function scoreVisualConcept(payload: { concept: VisualConcept }) {
  return post<VisualConceptScores>("/pipeline/visual-concepts/score", payload);
}

export function testVisualConceptImage() {
  return post<TestImageResult>("/pipeline/visual-concepts/test", {});
}

export function getVisualConceptDebugInfo() {
  return get<VisualConceptDebugInfo>("/pipeline/visual-concepts/debug");
}

export function downloadVisualConcept(payload: { concept: VisualConcept; format?: "png" | "jpeg" | "webp" }) {
  return postBlob("/pipeline/visual-concepts/download", payload);
}
