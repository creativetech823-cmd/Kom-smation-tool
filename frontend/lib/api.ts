import type {
  AutoFillSuggestion,
  AyushProduct,
  ComplianceResult,
  ProductAsset,
  ProductAssetType,
  ProductContext,
  ProductCreativeAngle,
  ProductImportResult,
  ProductReferenceScript,
  ContentAsset,
  ContentAssetType,
  ContentType,
  FetchUrlResult,
  GeneratedScript,
  HistoryEvent,
  HistoryEventType,
  Hook,
  HookListResult,
  MotionGenerationResult,
  ProductInput,
  Project,
  ReferenceMaterial,
  RenderLine,
  RenderResult,
  RewriteDirective,
  ScriptCommandResult,
  ScriptCommandSelection,
  ScriptLanguage,
  ScriptRegenerateScope,
  SelectedAsset,
  SmartScriptSuggestionsResult,
  StaticVisualResult,
  StorySituation,
  StructuredProduct,
  Template,
  TemplateKind,
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

async function patch<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
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

async function del(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail),
      res.status
    );
  }
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
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
  script_language?: ScriptLanguage;
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
  custom_language?: string;
  target_duration?: string;
  selected_hook_text?: string;
  content_type?: ContentType;
  format?: string;
  format_description?: string;
  tone?: string;
  avoid_repeating_hook?: string;
  avoid_repeating_mechanism?: string;
  product_context?: ProductContext;
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
  custom_language?: string;
  target_duration?: string;
  current_script: GeneratedScript;
  scope: ScriptRegenerateScope;
  custom_instruction?: string;
  target_word_count?: number;
  selected_hook_text?: string;
  content_type?: ContentType;
  format?: string;
  format_description?: string;
  tone?: string;
  target_scene_label?: string;
  product_context?: ProductContext;
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

export function getScriptSuggestions(payload: {
  script: GeneratedScript;
  structured_product?: StructuredProduct;
  target_duration?: string;
}) {
  return post<SmartScriptSuggestionsResult>("/pipeline/script-suggestions", payload);
}

export function runScriptCommand(payload: {
  structured_product: StructuredProduct;
  script: GeneratedScript;
  product_category?: string;
  creative_angle?: string;
  instruction: string;
  selection?: ScriptCommandSelection;
}) {
  return post<ScriptCommandResult>("/pipeline/script-command", payload);
}

export function auditCompliance(payload: {
  script_text: string;
  product_category: string;
  product_name: string;
  structured_product?: StructuredProduct;
}) {
  return post<ComplianceResult>("/pipeline/compliance-audit", payload);
}

export function sourceAsset(payload: {
  line_id: string;
  visual_tags: string[];
  exclude_urls?: string[];
  section?: string;
  product_context?: ProductContext;
}) {
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

export function generateStaticVisual(payload: { prompt: string; aspect_ratio?: string }) {
  return post<StaticVisualResult>("/pipeline/static-visual/generate", payload);
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

export function planVisualConcepts(payload: {
  structured_product: StructuredProduct;
  script: GeneratedScript;
  situation: StorySituation;
  creative_angle?: string;
  product_category?: string;
}) {
  return post<{ concepts: VisualConcept[] }>("/pipeline/visual-concepts/plan", payload).then((r) => r.concepts);
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

// ---------------------------------------------------------------------------
// Library — Projects, Content Assets, Hooks, Templates, History
// ---------------------------------------------------------------------------

export function listProjects(params: { status?: string } = {}) {
  return get<Project[]>(`/library/projects${buildQuery(params)}`);
}

export function createProject(payload: { name: string; description?: string; product_category?: string }) {
  return post<Project>("/library/projects", payload);
}

export function getProject(id: string) {
  return get<Project>(`/library/projects/${id}`);
}

export function updateProject(
  id: string,
  payload: Partial<{ name: string; description: string; product_category: string; status: string }>
) {
  return patch<Project>(`/library/projects/${id}`, payload);
}

export function deleteProject(id: string) {
  return del(`/library/projects/${id}`);
}

export function savePipelineState(
  id: string,
  payload: { pipeline_state: Record<string, unknown>; pipeline_stage: string; name?: string; product_category?: string }
) {
  return patch<Project>(`/library/projects/${id}/state`, payload);
}

export function listAssets(
  params: {
    asset_type?: ContentAssetType;
    project_id?: string;
    favorite?: boolean;
    q?: string;
    sort?: "recent" | "oldest";
  } = {}
) {
  return get<ContentAsset[]>(`/library/assets${buildQuery(params)}`);
}

export function createAsset(payload: {
  project_id?: string;
  asset_type: ContentAssetType;
  title?: string;
  product_name?: string;
  file_path?: string;
  thumbnail_path?: string;
  content_json?: Record<string, unknown>;
  source_hook_id?: string;
  source_hook_text?: string;
  model_used?: string;
  is_favorite?: boolean;
}) {
  return post<ContentAsset>("/library/assets", payload);
}

export function getAsset(id: string) {
  return get<ContentAsset>(`/library/assets/${id}`);
}

export function updateAsset(
  id: string,
  payload: Partial<{
    title: string;
    project_id: string;
    file_path: string;
    thumbnail_path: string;
    content_json: Record<string, unknown>;
    is_favorite: boolean;
  }>
) {
  return patch<ContentAsset>(`/library/assets/${id}`, payload);
}

export function deleteAsset(id: string) {
  return del(`/library/assets/${id}`);
}

export function listHooks(
  params: {
    q?: string;
    category?: string;
    platform?: string;
    tone?: string;
    favorite?: boolean;
    product_id?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return get<HookListResult>(`/library/hooks${buildQuery(params)}`);
}

export function createHook(payload: { text: string; category?: string; platform?: string; tone?: string; product_id?: string }) {
  return post<Hook>("/library/hooks", payload);
}

export function getHook(id: string) {
  return get<Hook>(`/library/hooks/${id}`);
}

export function toggleHookFavorite(id: string, is_favorite: boolean) {
  return patch<Hook>(`/library/hooks/${id}`, { is_favorite });
}

export function updateHook(
  id: string,
  payload: Partial<Pick<Hook, "text" | "category" | "platform" | "tone" | "is_favorite">>
) {
  return patch<Hook>(`/library/hooks/${id}`, payload);
}

export function markHookUsed(id: string) {
  return post<Hook>(`/library/hooks/${id}/use`, {});
}

export function listTemplates(
  params: { kind?: TemplateKind; category?: string; mine?: boolean; favorite?: boolean } = {}
) {
  return get<Template[]>(`/library/templates${buildQuery(params)}`);
}

export function getTemplate(id: string) {
  return get<Template>(`/library/templates/${id}`);
}

export function createTemplate(payload: {
  name?: string;
  kind?: TemplateKind;
  category?: string;
  description?: string;
  thumbnail_key?: string;
  config_json?: Record<string, unknown>;
}) {
  return post<Template>("/library/templates", payload);
}

export function duplicateTemplate(templateId: string) {
  return post<Template>("/library/templates", { duplicate_from: templateId });
}

export function updateTemplate(
  id: string,
  payload: Partial<{
    name: string;
    description: string;
    category: string;
    config_json: Record<string, unknown>;
    is_favorite: boolean;
  }>
) {
  return patch<Template>(`/library/templates/${id}`, payload);
}

export function deleteTemplate(id: string) {
  return del(`/library/templates/${id}`);
}

export function listHistory(params: { project_id?: string; limit?: number } = {}) {
  return get<HistoryEvent[]>(`/library/history${buildQuery(params)}`);
}

export function logHistoryEvent(payload: {
  event_type: HistoryEventType;
  summary?: string;
  project_id?: string;
  asset_id?: string;
}) {
  return post<HistoryEvent>("/library/history", payload);
}

// ---------------------------------------------------------------------------
// AyushWellness Product Library
// ---------------------------------------------------------------------------

export type ProductCreatePayload = Partial<Omit<AyushProduct, "id" | "slug" | "status" | "primary_asset" | "asset_count" | "created_at" | "updated_at">> & {
  name: string;
  category: string;
};

export function listAyushProducts(params: { category?: string; status?: string; q?: string } = {}) {
  return get<AyushProduct[]>(`/product-library/products${buildQuery(params)}`);
}

export function createAyushProduct(payload: ProductCreatePayload) {
  return post<AyushProduct>("/product-library/products", payload);
}

export function getAyushProduct(id: string) {
  return get<AyushProduct>(`/product-library/products/${id}`);
}

export function updateAyushProduct(id: string, payload: Partial<ProductCreatePayload> & { status?: string }) {
  return patch<AyushProduct>(`/product-library/products/${id}`, payload);
}

export function archiveAyushProduct(id: string) {
  return post<AyushProduct>(`/product-library/products/${id}/archive`, {});
}

export function restoreAyushProduct(id: string) {
  return post<AyushProduct>(`/product-library/products/${id}/restore`, {});
}

export function getAyushProductContext(id: string) {
  return get<ProductContext>(`/product-library/products/${id}/context`);
}

export function importProductFromUrl(url: string) {
  return post<ProductImportResult>("/product-library/import-url", { url });
}

export function importProductAssetFromUrl(
  productId: string,
  payload: { asset_type: ProductAssetType; source_url: string; title?: string }
) {
  return post<ProductAsset>(`/product-library/products/${productId}/assets/import-url`, payload);
}

export function listProductAssets(productId: string, params: { asset_type?: string; include_inactive?: boolean } = {}) {
  return get<ProductAsset[]>(`/product-library/products/${productId}/assets${buildQuery(params)}`);
}

export function uploadProductAsset(
  productId: string,
  file: File,
  meta: {
    asset_type: ProductAssetType;
    title?: string;
    description?: string;
    reference_state?: string;
    learning_notes?: string;
    style_notes?: string;
  }
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("asset_type", meta.asset_type);
  if (meta.title) formData.append("title", meta.title);
  if (meta.description) formData.append("description", meta.description);
  if (meta.reference_state) formData.append("reference_state", meta.reference_state);
  if (meta.learning_notes) formData.append("learning_notes", meta.learning_notes);
  if (meta.style_notes) formData.append("style_notes", meta.style_notes);
  return postMultipart<ProductAsset>(`/product-library/products/${productId}/assets`, formData);
}

export function linkProductAsset(
  productId: string,
  payload: {
    asset_type: ProductAssetType;
    source_url: string;
    title?: string;
    description?: string;
    tags?: string[];
    reference_state?: string;
    learning_notes?: string;
    style_notes?: string;
  }
) {
  return post<ProductAsset>(`/product-library/products/${productId}/assets/link`, payload);
}

export function updateProductAsset(
  assetId: string,
  payload: Partial<{
    asset_type: ProductAssetType;
    title: string;
    description: string;
    tags: string[];
    reference_state: string;
    sort_order: number;
    is_primary: boolean;
    is_active: boolean;
    source_url: string;
    learning_notes: string;
    style_notes: string;
  }>
) {
  return patch<ProductAsset>(`/product-library/assets/${assetId}`, payload);
}

export function deactivateProductAsset(assetId: string) {
  return del(`/product-library/assets/${assetId}`);
}

export function createProductReferenceScript(
  productId: string,
  payload: { title?: string; script_text: string; format?: string; notes?: string; is_approved?: boolean }
) {
  return post<ProductReferenceScript>(`/product-library/products/${productId}/reference-scripts`, payload);
}

export function listProductReferenceScripts(productId: string, approvedOnly = false) {
  return get<ProductReferenceScript[]>(
    `/product-library/products/${productId}/reference-scripts${buildQuery({ approved_only: approvedOnly })}`
  );
}

export function updateProductReferenceScript(
  scriptId: string,
  payload: Partial<{ title: string; script_text: string; format: string; notes: string; is_approved: boolean }>
) {
  return patch<ProductReferenceScript>(`/product-library/reference-scripts/${scriptId}`, payload);
}

export function deleteProductReferenceScript(scriptId: string) {
  return del(`/product-library/reference-scripts/${scriptId}`);
}

export function productUploadFileUrl(relativePath: string): string {
  return `${API_BASE}/product-uploads/${relativePath}`;
}

export function createProductCreativeAngle(
  productId: string,
  payload: {
    name: string;
    description?: string;
    target_audience?: string;
    emotional_direction?: string;
    approved_messaging?: string;
    restricted_messaging?: string;
    visual_direction?: string;
    cta_direction?: string;
  }
) {
  return post<ProductCreativeAngle>(`/product-library/products/${productId}/creative-angles`, payload);
}

export function listProductCreativeAngles(productId: string) {
  return get<ProductCreativeAngle[]>(`/product-library/products/${productId}/creative-angles`);
}

export function updateProductCreativeAngle(
  angleId: string,
  payload: Partial<{
    name: string;
    description: string;
    target_audience: string;
    emotional_direction: string;
    approved_messaging: string;
    restricted_messaging: string;
    visual_direction: string;
    cta_direction: string;
    sort_order: number;
  }>
) {
  return patch<ProductCreativeAngle>(`/product-library/creative-angles/${angleId}`, payload);
}

export function deleteProductCreativeAngle(angleId: string) {
  return del(`/product-library/creative-angles/${angleId}`);
}
