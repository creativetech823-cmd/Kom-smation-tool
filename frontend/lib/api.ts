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
  SelectedAsset,
  StorySituation,
  StructuredProduct,
  VoiceoverResult,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
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
}) {
  return post<GeneratedScript>("/pipeline/regenerate-script-section", payload);
}

export function rewriteLine(payload: { text: string; directive: RewriteDirective; max_chars?: number }) {
  return post<{ text: string }>("/pipeline/rewrite-line", payload);
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
