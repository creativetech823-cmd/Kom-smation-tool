import type {
  ComplianceResult,
  GeneratedScript,
  MotionGenerationResult,
  ProductInput,
  RenderLine,
  RenderResult,
  SelectedAsset,
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

export function structureProduct(input: ProductInput) {
  return post<StructuredProduct>("/pipeline/structure", input);
}

export function generateScript(payload: {
  structured_product: StructuredProduct;
  product_category: string;
  platform?: string;
  similar_past_winners?: string[];
  max_line_chars?: number;
}) {
  return post<GeneratedScript>("/pipeline/generate-script", payload);
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
