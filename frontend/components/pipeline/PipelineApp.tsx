"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { Button } from "@/components/ui/Button";
import { PipelineSubHeader } from "@/components/shell/PipelineSubHeader";
import { useToast } from "@/components/shell/ToastProvider";
import { useActiveProject } from "@/lib/project-context";
import { ACTIVE_TEMPLATE_KEY, type ActiveTemplateHint } from "@/lib/constants";
import { HookPickerModal } from "@/components/library/HookPickerModal";
import { ProductWorkspaceStep } from "@/components/steps/ProductWorkspaceStep";
import type { ActivityEntry } from "@/components/steps/AiUnderstandingPanel";
import { StorySituationStep } from "@/components/steps/StorySituationStep";
import { ScriptStep } from "@/components/steps/ScriptStep";
import { VisualConceptsSection } from "@/components/steps/VisualConceptsSection";
import { ComplianceStep } from "@/components/steps/ComplianceStep";
import { AssetsStep } from "@/components/steps/AssetsStep";
import { VoiceoverStep } from "@/components/steps/VoiceoverStep";
import { RenderStep } from "@/components/steps/RenderStep";
import {
  addReferenceUrl,
  ApiError,
  audioFileUrl,
  auditCompliance,
  createAsset,
  createProject,
  downloadVisualConcept,
  generateAlternatives,
  generateMotion,
  generateScript,
  generateStorySituations,
  planVisualConcepts,
  generateVoiceover,
  getScriptSuggestions,
  logHistoryEvent,
  motionFileUrl,
  regenerateScriptSection,
  regenerateVisualConcept,
  renderFileUrl,
  renderVideo,
  rewriteLine,
  runScriptCommand,
  savePipelineState,
  scoreVisualConcept,
  markHookUsed,
  sourceAsset,
  structureProduct,
  updateAsset,
  uploadReferenceMaterial,
} from "@/lib/api";
import type { ScriptVersion } from "@/components/ui/VersionHistoryPanel";
import type { ApplyPatch } from "@/components/ui/AiSuggestionsPanel";
import type { RegenerateOptions } from "@/components/steps/ScriptStep";
import {
  flattenScript,
  type ComplianceResult,
  type GeneratedScript,
  type Hook,
  type MotionGenerationResult,
  type ProductInput,
  type Project,
  type ReferenceKind,
  type ReferenceMaterial,
  type RenderResult,
  type RewriteDirective,
  type ScriptCommandSelection,
  type ScriptLanguage,
  type ScriptLine,
  type ScriptRegenerateScope,
  type SelectedAsset,
  type SmartScriptSuggestionsResult,
  type StorySituation,
  type StructuredProduct,
  type VisualConcept,
  type VisualConceptStyleParams,
  type VisualVariationStyle,
  type VoiceoverResult,
} from "@/lib/types";

const STEPS: Step[] = [
  { key: "product", label: "Product", sublabel: "Input & Understanding" },
  { key: "story", label: "Story", sublabel: "Discover Scenarios" },
  { key: "script", label: "Script", sublabel: "Generate Script" },
  { key: "compliance", label: "Compliance", sublabel: "Check Rules" },
  { key: "assets", label: "Assets", sublabel: "Create Assets" },
  { key: "voiceover", label: "Voiceover", sublabel: "Narrate" },
  { key: "render", label: "Render", sublabel: "Finalize" },
];
const STEP_KEYS = STEPS.map((s) => s.key);

const AUTOSAVE_DEBOUNCE_MS = 800;

function stageToIndex(stage: string | null | undefined): number {
  if (!stage) return 0;
  const idx = STEP_KEYS.indexOf(stage);
  return idx >= 0 ? idx : 0;
}

/** Everything that gets persisted for this project, restored on mount from
 * `project.pipeline_state` — deliberately excludes loading/error flags and
 * other ephemeral UI state (see PERSISTED_FIELDS in buildSnapshot below). */
type RestoredPipelineState = {
  stage: string | null;
  furthest: number | null;
  productInput: ProductInput | null;
  category: string | null;
  structured: StructuredProduct | null;
  referenceMaterials: ReferenceMaterial[] | null;
  sourceUrlRawText: string | undefined;
  situations: StorySituation[] | null;
  selectedSituation: StorySituation | null;
  selectedAngle: string | null;
  scriptLanguage: ScriptLanguage | null;
  targetDuration: string | null;
  script: GeneratedScript | null;
  scriptHistory: ScriptVersion[] | null;
  scriptHistoryIndex: number | null;
  visualConcepts: VisualConcept[] | null;
  visualAssetIdByConceptId: Record<string, string> | null;
  scriptAssetId: string | null;
  compliance: ComplianceResult | null;
  assets: Record<string, SelectedAsset | undefined> | null;
  motions: Record<string, MotionGenerationResult | undefined> | null;
  voiceovers: Record<string, VoiceoverResult | undefined> | null;
  renderResult: RenderResult | null;
  approved: boolean | null;
  selectedHookText: string | null;
};

function restorePipelineState(project: Project | null): RestoredPipelineState {
  const raw = (project?.pipeline_state ?? {}) as Record<string, unknown>;
  return {
    stage: project?.pipeline_stage ?? null,
    furthest: typeof raw.furthest === "number" ? raw.furthest : null,
    productInput: (raw.productInput as ProductInput | undefined) ?? null,
    category: typeof raw.category === "string" ? raw.category : null,
    structured: (raw.structured as StructuredProduct | undefined) ?? null,
    referenceMaterials: (raw.referenceMaterials as ReferenceMaterial[] | undefined) ?? null,
    sourceUrlRawText: raw.sourceUrlRawText as string | undefined,
    situations: (raw.situations as StorySituation[] | undefined) ?? null,
    selectedSituation: (raw.selectedSituation as StorySituation | undefined) ?? null,
    selectedAngle: (raw.selectedAngle as string | undefined) ?? null,
    scriptLanguage: (raw.scriptLanguage as ScriptLanguage | undefined) ?? null,
    targetDuration: typeof raw.targetDuration === "string" ? raw.targetDuration : null,
    script: (raw.script as GeneratedScript | undefined) ?? null,
    scriptHistory: (raw.scriptHistory as ScriptVersion[] | undefined) ?? null,
    scriptHistoryIndex: typeof raw.scriptHistoryIndex === "number" ? raw.scriptHistoryIndex : null,
    visualConcepts: (raw.visualConcepts as VisualConcept[] | undefined) ?? null,
    visualAssetIdByConceptId: (raw.visualAssetIdByConceptId as Record<string, string> | undefined) ?? null,
    scriptAssetId: (raw.scriptAssetId as string | undefined) ?? null,
    compliance: (raw.compliance as ComplianceResult | undefined) ?? null,
    assets: (raw.assets as Record<string, SelectedAsset | undefined> | undefined) ?? null,
    motions: (raw.motions as Record<string, MotionGenerationResult | undefined> | undefined) ?? null,
    voiceovers: (raw.voiceovers as Record<string, VoiceoverResult | undefined> | undefined) ?? null,
    renderResult: (raw.renderResult as RenderResult | undefined) ?? null,
    approved: typeof raw.approved === "boolean" ? raw.approved : null,
    selectedHookText: (raw.selectedHookText as string | undefined) ?? null,
  };
}

function guessReferenceKindFromFilename(filename: string): ReferenceKind {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  const map: Record<string, ReferenceKind> = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".txt": "txt",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".zip": "zip",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".avi": "video",
    ".mkv": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".ogg": "audio",
    ".flac": "audio",
  };
  return map[ext] ?? "txt";
}

function updateScriptLine(s: GeneratedScript, lineId: string, patch: Partial<ScriptLine>): GeneratedScript {
  if (lineId === "hook") return { ...s, hook: { ...s.hook, ...patch } };
  if (lineId === "cta") return { ...s, cta: { ...s.cta, ...patch } };
  const match = lineId.match(/^body_(\d+)$/);
  if (match) {
    const idx = Number(match[1]);
    return { ...s, body: s.body.map((line, i) => (i === idx ? { ...line, ...patch } : line)) };
  }
  return s;
}

function changedLineIds(before: GeneratedScript, after: GeneratedScript): string[] {
  const beforeLines = flattenScript(before);
  const afterLines = flattenScript(after);
  const ids: string[] = [];
  for (const line of afterLines) {
    const match = beforeLines.find((l) => l.id === line.id);
    if (!match || match.text !== line.text) ids.push(line.id);
  }
  return ids;
}

const REGEN_SCOPE_LABEL: Record<ScriptRegenerateScope, string> = {
  full: "Full rewrite",
  hook: "Hook",
  cta: "CTA",
  science: "Science section",
  story: "Story section",
  product_explanation: "Product explanation",
  emotional_tone: "Emotional tone",
  length: "Made longer",
};

export type PipelineAppProps = {
  /** Null for a brand-new, not-yet-persisted session (rendered at `/`). */
  projectId: string | null;
  /** Already-fetched project (with `pipeline_state`) for a resumed session. */
  initialProject: Project | null;
};

export function PipelineApp({ projectId: projectIdProp, initialProject }: PipelineAppProps) {
  const router = useRouter();
  // Read reactively (not just once) — this component now lives in a layout
  // that stays mounted while the [stage] segment changes underneath it, so
  // this is how stage navigation is actually observed (see goTo below).
  const params = useParams();
  const liveStage = typeof params.stage === "string" ? params.stage : null;
  const [restored] = useState(() => restorePipelineState(initialProject));

  const [stepIndex, setStepIndex] = useState(() => stageToIndex(liveStage ?? restored.stage));
  const [furthest, setFurthest] = useState(() => restored.furthest ?? stageToIndex(liveStage ?? restored.stage));

  const [productInput, setProductInput] = useState<ProductInput | null>(() => restored.productInput);
  const [category, setCategory] = useState(() => restored.category ?? "");
  const [structured, setStructured] = useState<StructuredProduct | null>(() => restored.structured);
  const [referenceMaterials, setReferenceMaterials] = useState<ReferenceMaterial[]>(() => restored.referenceMaterials ?? []);
  const [uploadingMaterialIds, setUploadingMaterialIds] = useState<Set<string>>(new Set());
  const [sourceUrlRawText, setSourceUrlRawText] = useState<string | undefined>(() => restored.sourceUrlRawText);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [situations, setSituations] = useState<StorySituation[]>(() => restored.situations ?? []);
  const [selectedSituation, setSelectedSituation] = useState<StorySituation | null>(() => restored.selectedSituation);
  const [selectedAngle, setSelectedAngle] = useState<string | null>(() => restored.selectedAngle);
  const [scriptLanguage, setScriptLanguage] = useState<ScriptLanguage>(() => restored.scriptLanguage ?? "hinglish");
  const [targetDuration, setTargetDuration] = useState(() => restored.targetDuration ?? "30s");
  const [script, setScript] = useState<GeneratedScript | null>(() => restored.script);
  const [visualConcepts, setVisualConcepts] = useState<VisualConcept[]>(() => restored.visualConcepts ?? []);
  const [visualConceptsLoading, setVisualConceptsLoading] = useState(false);
  const [visualConceptsError, setVisualConceptsError] = useState<string | null>(null);
  const [visualConceptScoring, setVisualConceptScoring] = useState<Record<string, boolean>>({});
  const [visualConceptRegenLoading, setVisualConceptRegenLoading] = useState<Record<string, boolean>>({});
  const [visualConceptDownloading, setVisualConceptDownloading] = useState<Record<string, boolean>>({});
  const [compliance, setCompliance] = useState<ComplianceResult | null>(() => restored.compliance);
  const [assets, setAssets] = useState<Record<string, SelectedAsset | undefined>>(() => restored.assets ?? {});
  const [loadingAssetIds, setLoadingAssetIds] = useState<Set<string>>(new Set());
  const [motions, setMotions] = useState<Record<string, MotionGenerationResult | undefined>>(() => restored.motions ?? {});
  const [loadingMotionIds, setLoadingMotionIds] = useState<Set<string>>(new Set());
  const [voiceovers, setVoiceovers] = useState<Record<string, VoiceoverResult | undefined>>(() => restored.voiceovers ?? {});
  const [loadingVoiceoverIds, setLoadingVoiceoverIds] = useState<Set<string>>(new Set());
  const [renderResult, setRenderResult] = useState<RenderResult | null>(() => restored.renderResult);
  const [approved, setApproved] = useState(() => restored.approved ?? false);

  const [inputLoading, setInputLoading] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  const [improvingDescription, setImprovingDescription] = useState(false);
  const [situationsLoading, setSituationsLoading] = useState(false);
  const [situationsGenMoreLoading, setSituationsGenMoreLoading] = useState(false);
  const [situationSelectingKey, setSituationSelectingKey] = useState<{ situationId: string; angle: string } | null>(
    null
  );
  const [scriptRegenLoading, setScriptRegenLoading] = useState(false);
  const [lineLoading, setLineLoading] = useState<Record<string, boolean>>({});
  const [scriptHistory, setScriptHistory] = useState<ScriptVersion[]>(() => restored.scriptHistory ?? []);
  const [scriptHistoryIndex, setScriptHistoryIndex] = useState(() => restored.scriptHistoryIndex ?? -1);
  const historyIndexRef = useRef(restored.scriptHistoryIndex ?? -1);
  const [recentlyChangedLineIds, setRecentlyChangedLineIds] = useState<Set<string>>(new Set());
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [assetsContinueLoading, setAssetsContinueLoading] = useState(false);
  const [voiceoverContinueLoading, setVoiceoverContinueLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const { showToast } = useToast();
  const { activeProjectId, setActiveProject } = useActiveProject();

  const [scriptAssetId, setScriptAssetId] = useState<string | null>(() => restored.scriptAssetId);
  const [visualAssetIdByConceptId, setVisualAssetIdByConceptId] = useState<Record<string, string>>(
    () => restored.visualAssetIdByConceptId ?? {}
  );
  const [selectedHookText, setSelectedHookText] = useState(() => restored.selectedHookText ?? "");
  const [hookPickerOpen, setHookPickerOpen] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<ActiveTemplateHint | null>(null);

  const projectIdRef = useRef<string | null>(projectIdProp);
  const creatingProjectRef = useRef(false);
  const lastSavedSignatureRef = useRef<string>("");
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Deferred to after mount, not a lazy useState initializer: the server has no
    // access to localStorage, so reading it during the initial client render would
    // mismatch the server-rendered HTML and trigger a hydration error.
    const rawTemplate = window.localStorage.getItem(ACTIVE_TEMPLATE_KEY);
    if (rawTemplate) {
      try {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setActiveTemplate(JSON.parse(rawTemplate));
      } catch {
        // ignore malformed value
      }
    }
  }, []);

  // Keep stepIndex in sync with the URL's [stage] segment — covers browser
  // back/forward, direct URL entry, and this component's own router.push
  // calls (see goTo below) once Next.js re-renders with the new param.
  useEffect(() => {
    if (!liveStage) return;
    const idx = stageToIndex(liveStage);
    setStepIndex((prev) => (prev === idx ? prev : idx));
  }, [liveStage]);

  function handleClearActiveTemplate() {
    setActiveTemplate(null);
    window.localStorage.removeItem(ACTIVE_TEMPLATE_KEY);
  }

  function goTo(i: number) {
    setFurthest((f) => Math.max(f, i));
    if (projectIdRef.current) {
      router.push(`/pipeline/${projectIdRef.current}/${STEPS[i].key}`);
    } else {
      setStepIndex(i);
    }
  }

  const pushActivity = useCallback((label: string, tone: "info" | "success" | "error" = "info") => {
    setActivityLog((prev) => [{ id: crypto.randomUUID(), label, tone, ts: Date.now() }, ...prev].slice(0, 8));
  }, []);

  function resetScriptHistory(next: GeneratedScript, label: string) {
    historyIndexRef.current = 0;
    setScriptHistory([{ script: next, label, ts: Date.now() }]);
    setScriptHistoryIndex(0);
    setRecentlyChangedLineIds(new Set());
    setLineLoading({});
  }

  function pushScriptHistory(next: GeneratedScript, label: string) {
    setScriptHistory((prev) => {
      const truncated = prev.slice(0, historyIndexRef.current + 1);
      const combined = [...truncated, { script: next, label, ts: Date.now() }];
      const capped = combined.length > 30 ? combined.slice(combined.length - 30) : combined;
      historyIndexRef.current = capped.length - 1;
      setScriptHistoryIndex(capped.length - 1);
      return capped;
    });
  }

  function markLinesChanged(ids: string[]) {
    if (ids.length === 0) return;
    setRecentlyChangedLineIds((prev) => new Set([...prev, ...ids]));
    setTimeout(() => {
      setRecentlyChangedLineIds((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.delete(id));
        return next;
      });
    }, 4000);
  }

  // ---------------------------------------------------------------------
  // Autosave — debounced, always the full current snapshot. Excludes
  // loading/error flags and other ephemeral UI state on purpose.
  // ---------------------------------------------------------------------

  const buildSnapshot = useCallback(
    (): Record<string, unknown> => ({
      productInput,
      category,
      structured,
      referenceMaterials,
      sourceUrlRawText,
      situations,
      selectedSituation,
      selectedAngle,
      scriptLanguage,
      targetDuration,
      script,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      scriptAssetId,
      compliance,
      assets,
      motions,
      voiceovers,
      renderResult,
      approved,
      selectedHookText,
      furthest,
    }),
    [
      productInput,
      category,
      structured,
      referenceMaterials,
      sourceUrlRawText,
      situations,
      selectedSituation,
      selectedAngle,
      scriptLanguage,
      targetDuration,
      script,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      scriptAssetId,
      compliance,
      assets,
      motions,
      voiceovers,
      renderResult,
      approved,
      selectedHookText,
      furthest,
    ]
  );

  function computeSignature(): string {
    return JSON.stringify(buildSnapshot()) + "|" + STEPS[stepIndex].key;
  }

  async function flushSave() {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const signature = computeSignature();
    if (signature === lastSavedSignatureRef.current) return;
    // Nothing meaningful yet on a brand-new session — don't create a project
    // just because the user glanced at the page.
    if (!projectIdRef.current && !productInput && !structured) return;
    if (creatingProjectRef.current) return;

    setSaveStatus("saving");
    try {
      const stageKey = STEPS[stepIndex].key;
      const isFirstSave = !projectIdRef.current;
      if (isFirstSave) {
        creatingProjectRef.current = true;
        const created = await createProject({
          name: structured?.product_name || productInput?.product_name || "Untitled Project",
          product_category: category || undefined,
        });
        projectIdRef.current = created.id;
        creatingProjectRef.current = false;
      }
      await savePipelineState(projectIdRef.current as string, {
        pipeline_state: buildSnapshot(),
        pipeline_stage: stageKey,
        name: structured?.product_name || undefined,
        product_category: category || undefined,
      });
      lastSavedSignatureRef.current = signature;
      setActiveProject(projectIdRef.current, structured?.product_name || productInput?.product_name || null);
      setSaveStatus("saved");
      if (isFirstSave) {
        // The project didn't exist when this URL was rendered — move onto
        // its real URL now so a refresh from here on resolves through the
        // normal restore path instead of starting fresh again.
        router.replace(`/pipeline/${projectIdRef.current}/${stageKey}`);
      }
    } catch {
      creatingProjectRef.current = false;
      setSaveStatus("error");
    }
  }

  useEffect(() => {
    const signature = computeSignature();
    if (signature === lastSavedSignatureRef.current) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void flushSave();
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildSnapshot, stepIndex]);

  useEffect(() => {
    function handleFlushOnHide() {
      if (document.visibilityState === "hidden") void flushSave();
    }
    window.addEventListener("visibilitychange", handleFlushOnHide);
    window.addEventListener("pagehide", handleFlushOnHide);
    return () => {
      window.removeEventListener("visibilitychange", handleFlushOnHide);
      window.removeEventListener("pagehide", handleFlushOnHide);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildSnapshot, stepIndex]);

  async function uploadOneReferenceFile(file: File) {
    const tempId = `temp-${crypto.randomUUID()}`;
    const placeholder: ReferenceMaterial = {
      id: tempId,
      kind: guessReferenceKindFromFilename(file.name),
      filename: file.name,
      analysis: "failed",
      extracted_text: "",
      truncated: false,
      note: "",
    };
    setReferenceMaterials((prev) => [...prev, placeholder]);
    setUploadingMaterialIds((prev) => new Set(prev).add(tempId));
    pushActivity(`Reading ${file.name}...`);
    try {
      const result = await uploadReferenceMaterial(file);
      setReferenceMaterials((prev) => prev.map((m) => (m.id === tempId ? { ...result, id: tempId } : m)));
      pushActivity(
        result.analysis === "analyzed" ? `Understood ${file.name} ✓` : `${file.name} attached — ${result.note || result.analysis}`,
        result.analysis === "analyzed" ? "success" : "info"
      );
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Upload failed.";
      setReferenceMaterials((prev) =>
        prev.map((m) => (m.id === tempId ? { ...m, analysis: "failed", note: message } : m))
      );
      pushActivity(`Couldn't read ${file.name}`, "error");
    } finally {
      setUploadingMaterialIds((prev) => {
        const next = new Set(prev);
        next.delete(tempId);
        return next;
      });
    }
  }

  async function handleAddReferenceFiles(files: FileList | File[]) {
    const fileArray = Array.from(files);
    // Batch concurrent uploads so a big drop doesn't overload the backend instance.
    for (let i = 0; i < fileArray.length; i += 3) {
      const batch = fileArray.slice(i, i + 3);
      await Promise.all(batch.map(uploadOneReferenceFile));
    }
  }

  async function handleAddReferenceUrl(url: string) {
    const tempId = `temp-${crypto.randomUUID()}`;
    const placeholder: ReferenceMaterial = {
      id: tempId,
      kind: "website",
      source_url: url,
      analysis: "failed",
      extracted_text: "",
      truncated: false,
      note: "",
    };
    setReferenceMaterials((prev) => [...prev, placeholder]);
    setUploadingMaterialIds((prev) => new Set(prev).add(tempId));
    pushActivity(`Fetching ${url}...`);
    try {
      const result = await addReferenceUrl({ url });
      setReferenceMaterials((prev) => prev.map((m) => (m.id === tempId ? { ...result, id: tempId } : m)));
      pushActivity(
        result.analysis === "analyzed" ? `Understood ${url} ✓` : `Couldn't read ${url}`,
        result.analysis === "analyzed" ? "success" : "error"
      );
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't fetch that link.";
      setReferenceMaterials((prev) =>
        prev.map((m) => (m.id === tempId ? { ...m, analysis: "failed", note: message } : m))
      );
      pushActivity(`Couldn't fetch ${url}`, "error");
    } finally {
      setUploadingMaterialIds((prev) => {
        const next = new Set(prev);
        next.delete(tempId);
        return next;
      });
    }
  }

  function handleRemoveReferenceMaterial(id: string) {
    setReferenceMaterials((prev) => prev.filter((m) => m.id !== id));
  }

  async function handleInputSubmit(input: ProductInput, cat: string) {
    setInputLoading(true);
    setInputError(null);
    try {
      const result = await structureProduct(input);
      setProductInput(input);
      setCategory(cat);
      setStructured(result);
    } catch (e) {
      setInputError(e instanceof ApiError ? e.message : "Something went wrong structuring the product.");
    } finally {
      setInputLoading(false);
    }
  }

  async function handleImproveDescription(text: string): Promise<string> {
    setImprovingDescription(true);
    try {
      const result = await rewriteLine({ text, directive: "improve" });
      return result.text;
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't improve the description.", "danger");
      return text;
    } finally {
      setImprovingDescription(false);
    }
  }

  async function handleGenerateSituations() {
    if (!structured) return;
    setSituationsLoading(true);
    setGlobalError(null);
    try {
      const result = await generateStorySituations({
        structured_product: structured,
        product_category: category,
        script_language: scriptLanguage,
      });
      setSituations(result);
      goTo(1);
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Story situation generation failed.");
    } finally {
      setSituationsLoading(false);
    }
  }

  async function handleGenerateMoreSituations() {
    if (!structured) return;
    setSituationsGenMoreLoading(true);
    setGlobalError(null);
    try {
      const more = await generateStorySituations({
        structured_product: structured,
        product_category: category,
        exclude_titles: situations.map((s) => s.title),
        script_language: scriptLanguage,
      });
      setSituations((prev) => [...prev, ...more]);
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Couldn't generate more situations.");
    } finally {
      setSituationsGenMoreLoading(false);
    }
  }

  // Guards against firing two renders for the same concept at once — the
  // resume-after-refresh effect and a fresh plan could otherwise race.
  const renderingConceptIdsRef = useRef<Set<string>>(new Set());

  const renderOneVisualConcept = useCallback(
    async (
      concept: VisualConcept,
      structuredProduct: StructuredProduct,
      generatedScript: GeneratedScript,
      situation: StorySituation,
      angle: string
    ) => {
      if (renderingConceptIdsRef.current.has(concept.id)) return;
      renderingConceptIdsRef.current.add(concept.id);
      setVisualConcepts((prev) => prev.map((c) => (c.id === concept.id ? { ...c, status: "generating", error: null } : c)));
      try {
        const result = await regenerateVisualConcept({
          structured_product: structuredProduct,
          script: generatedScript,
          situation,
          creative_angle: angle,
          concept,
        });
        const completed: VisualConcept = { ...result, status: "completed", error: null };
        setVisualConcepts((prev) => prev.map((c) => (c.id === concept.id ? completed : c)));
        createAsset({
          project_id: activeProjectId ?? undefined,
          asset_type: "image",
          title: completed.scene_title,
          product_name: structuredProduct.product_name,
          file_path: completed.image_path,
          model_used: completed.used_model,
          content_json: completed as unknown as Record<string, unknown>,
        })
          .then((asset) => {
            setVisualAssetIdByConceptId((prev) => ({ ...prev, [completed.id]: asset.id }));
            void logHistoryEvent({
              event_type: "generated_image",
              summary: `Generated image — ${completed.scene_title}`,
              project_id: activeProjectId ?? undefined,
              asset_id: asset.id,
            }).catch(() => {});
          })
          .catch(() => {});
        setVisualConceptScoring((prev) => ({ ...prev, [completed.id]: true }));
        scoreVisualConcept({ concept: completed })
          .then((scores) => {
            setVisualConcepts((prev) => prev.map((c) => (c.id === completed.id ? { ...c, scores } : c)));
          })
          .catch(() => {})
          .finally(() => {
            setVisualConceptScoring((prev) => ({ ...prev, [completed.id]: false }));
          });
      } catch (e) {
        const message = e instanceof ApiError ? e.message : "Couldn't generate that image.";
        setVisualConcepts((prev) => prev.map((c) => (c.id === concept.id ? { ...c, status: "failed", error: message } : c)));
      } finally {
        renderingConceptIdsRef.current.delete(concept.id);
      }
    },
    [activeProjectId]
  );

  async function handleGenerateVisualConcepts(
    structuredProduct: StructuredProduct,
    generatedScript: GeneratedScript,
    situation: StorySituation,
    angle: string
  ) {
    setVisualConcepts([]);
    setVisualConceptsError(null);
    setVisualConceptsLoading(true);
    let planned: VisualConcept[];
    try {
      planned = await planVisualConcepts({
        structured_product: structuredProduct,
        script: generatedScript,
        situation,
        creative_angle: angle,
        product_category: category,
      });
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't plan visual concepts.";
      setVisualConceptsError(message);
      showToast(message, "danger");
      setVisualConceptsLoading(false);
      return;
    }
    // The 3 concepts are known immediately — show all 3 cards right away
    // (each "pending"), then let each image stream in independently rather
    // than making the user wait for all 3 before seeing anything.
    setVisualConcepts(planned);
    setVisualConceptsLoading(false);
    planned.forEach((concept) => {
      void renderOneVisualConcept(concept, structuredProduct, generatedScript, situation, angle);
    });
  }

  function handleRetryVisualConcepts() {
    if (!structured || !script || !selectedSituation) return;
    void handleGenerateVisualConcepts(structured, script, selectedSituation, selectedAngle ?? "");
  }

  function handleRetryOneVisualConcept(id: string) {
    if (!structured || !script || !selectedSituation) return;
    const concept = visualConcepts.find((c) => c.id === id);
    if (!concept) return;
    void renderOneVisualConcept(concept, structured, script, selectedSituation, selectedAngle ?? "");
  }

  // Resume in-flight generations after a refresh — a restored concept whose
  // last known status is "pending"/"generating" never got a completed image
  // persisted, so its own request is gone (the reload killed it). Re-fire
  // just that one image, not the other two, and only once per mount.
  const resumedVisualConceptsRef = useRef(false);
  useEffect(() => {
    if (resumedVisualConceptsRef.current) return;
    resumedVisualConceptsRef.current = true;
    if (!structured || !script || !selectedSituation || visualConcepts.length === 0) return;
    visualConcepts
      .filter((c) => c.status === "pending" || c.status === "generating")
      .forEach((c) => {
        void renderOneVisualConcept(c, structured, script, selectedSituation, selectedAngle ?? "");
      });
    // Deliberately mount-only — see resumedVisualConceptsRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runScriptGeneration = useCallback(
    async (situation: StorySituation, angle: string, setLoading: (v: boolean) => void): Promise<boolean> => {
      if (!structured) return false;
      setLoading(true);
      setGlobalError(null);
      try {
        const result = await generateScript({
          structured_product: structured,
          selected_situation: situation,
          product_category: category,
          creative_angle: angle,
          script_language: scriptLanguage,
          target_duration: targetDuration,
          selected_hook_text: selectedHookText || undefined,
        });
        setScript(result);
        setSelectedSituation(situation);
        setSelectedAngle(angle);
        resetScriptHistory(result, "Generated");
        // Any previous assets/voiceovers/render are stale once the script changes.
        setAssets({});
        setVoiceovers({});
        setRenderResult(null);
        setApproved(false);
        setScriptAssetId(null);
        createAsset({
          project_id: activeProjectId ?? undefined,
          asset_type: "script",
          title: situation.title,
          product_name: structured.product_name,
          content_json: result as unknown as Record<string, unknown>,
          source_hook_text: selectedHookText || undefined,
        })
          .then((asset) => {
            setScriptAssetId(asset.id);
            void logHistoryEvent({
              event_type: "generated_script",
              summary: `Generated script — ${situation.title}`,
              project_id: activeProjectId ?? undefined,
              asset_id: asset.id,
            }).catch(() => {});
          })
          .catch(() => {});
        void handleGenerateVisualConcepts(structured, result, situation, angle);
        return true;
      } catch (e) {
        setGlobalError(e instanceof ApiError ? e.message : "Script generation failed.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [structured, category, scriptLanguage, targetDuration, selectedHookText, activeProjectId]
  );

  async function handleSelectAngle(situation: StorySituation, angle: string) {
    setSituationSelectingKey({ situationId: situation.id, angle });
    const ok = await runScriptGeneration(situation, angle, () => {});
    setSituationSelectingKey(null);
    // Stay on Story (with the error already surfaced via globalError) if
    // generation failed — never navigate to Script without a real script.
    if (ok) goTo(2);
  }

  async function handleRegenerateScript() {
    if (!selectedSituation || !selectedAngle) return;
    await runScriptGeneration(selectedSituation, selectedAngle, setScriptRegenLoading);
  }

  async function handleRegenerateScope(scope: ScriptRegenerateScope, options?: RegenerateOptions) {
    if (!structured || !selectedSituation || !script) return;
    if (scope === "full" && !options?.customInstruction && !options?.targetWordCount) {
      await handleRegenerateScript();
      return;
    }
    setScriptRegenLoading(true);
    setGlobalError(null);
    const before = script;
    try {
      const result = await regenerateScriptSection({
        structured_product: structured,
        selected_situation: selectedSituation,
        product_category: category,
        creative_angle: selectedAngle ?? "",
        script_language: scriptLanguage,
        target_duration: targetDuration,
        current_script: script,
        scope,
        custom_instruction: options?.customInstruction,
        target_word_count: options?.targetWordCount,
        selected_hook_text: scope === "full" ? selectedHookText || undefined : undefined,
      });
      setScript(result);
      const label = options?.targetWordCount
        ? `Length adjust — ~${options.targetWordCount}w`
        : `AI: ${REGEN_SCOPE_LABEL[scope] ?? scope}`;
      pushScriptHistory(result, label);
      markLinesChanged(changedLineIds(before, result));
      // Any previous assets/voiceovers/render are stale once the script changes.
      setAssets({});
      setVoiceovers({});
      setRenderResult(null);
      setApproved(false);
      if (scriptAssetId) {
        void updateAsset(scriptAssetId, { content_json: result as unknown as Record<string, unknown> }).catch(
          () => {}
        );
      }
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't regenerate that part of the script.", "danger");
    } finally {
      setScriptRegenLoading(false);
    }
  }

  function handleEditLine(lineId: string, text: string) {
    if (!script) return;
    const next = updateScriptLine(script, lineId, { text });
    setScript(next);
    pushScriptHistory(next, "Manual edit");
  }

  function handleEditWholeScript(texts: string[]) {
    if (!script) return;
    const ids = flattenScript(script).map((l) => l.id);
    let next = script;
    ids.forEach((id, i) => {
      if (texts[i] !== undefined) next = updateScriptLine(next, id, { text: texts[i] });
    });
    setScript(next);
    pushScriptHistory(next, "Manual edit — whole script");
  }

  function handleEditLineField(lineId: string, field: string, value: string | string[]) {
    if (!script) return;
    const next = updateScriptLine(script, lineId, { [field]: value } as Partial<ScriptLine>);
    setScript(next);
    pushScriptHistory(next, `Manual edit — ${field.replace(/_/g, " ")}`);
  }

  async function handleApplyDirectiveToLine(lineId: string, directive: RewriteDirective) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === lineId);
    if (!line) return;
    setLineLoading((prev) => ({ ...prev, [lineId]: true }));
    try {
      const result = await rewriteLine({ text: line.text, directive });
      const next = updateScriptLine(script, lineId, { text: result.text });
      setScript(next);
      pushScriptHistory(next, `AI: ${directive.replace(/_/g, " ")}`);
      markLinesChanged([lineId]);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Rewrite failed for that line.", "danger");
    } finally {
      setLineLoading((prev) => ({ ...prev, [lineId]: false }));
    }
  }

  async function handleGenerateAlternativesForLine(lineId: string): Promise<string[]> {
    if (!script) return [];
    const line = flattenScript(script).find((l) => l.id === lineId);
    if (!line) return [];
    try {
      const result = await generateAlternatives({ text: line.text, directive: "rewrite" });
      return result.alternatives;
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't generate alternatives.", "danger");
      return [];
    }
  }

  function handleSelectAlternativeForLine(lineId: string, text: string) {
    if (!script) return;
    const next = updateScriptLine(script, lineId, { text });
    setScript(next);
    pushScriptHistory(next, "AI: Selected alternative");
    markLinesChanged([lineId]);
  }

  async function handleTranslateLine(lineId: string, language: ScriptLanguage) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === lineId);
    if (!line) return;
    setLineLoading((prev) => ({ ...prev, [lineId]: true }));
    try {
      const result = await rewriteLine({ text: line.text, directive: "translate", target_language: language });
      const next = updateScriptLine(script, lineId, { text: result.text });
      setScript(next);
      pushScriptHistory(next, `AI: Translated to ${language}`);
      markLinesChanged([lineId]);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Translation failed.", "danger");
    } finally {
      setLineLoading((prev) => ({ ...prev, [lineId]: false }));
    }
  }

  async function handleAnalyzeScript(): Promise<SmartScriptSuggestionsResult> {
    if (!script) return { status: "strong", headline: "", cards: [], optional_ideas: [] };
    return getScriptSuggestions({
      script,
      structured_product: structured ?? undefined,
      target_duration: targetDuration || script.target_duration,
    });
  }

  async function handleRunScriptCommand(instruction: string, selection?: ScriptCommandSelection) {
    if (!structured || !script) throw new Error("Script isn't ready yet.");
    return runScriptCommand({
      structured_product: structured,
      script,
      product_category: category,
      creative_angle: selectedAngle ?? "",
      instruction,
      selection,
    });
  }

  function handleApplyPatch(patch: ApplyPatch) {
    if (!script) return;
    let next: GeneratedScript;
    if (patch.kind === "full") {
      next = patch.script;
      setAssets({});
      setVoiceovers({});
      setRenderResult(null);
      setApproved(false);
      if (scriptAssetId) {
        void updateAsset(scriptAssetId, { content_json: next as unknown as Record<string, unknown> }).catch(() => {});
      }
    } else {
      next = updateScriptLine(script, patch.lineId, { text: patch.text });
    }
    setScript(next);
    pushScriptHistory(next, patch.label);
    markLinesChanged(patch.kind === "full" ? changedLineIds(script, next) : [patch.lineId]);
    showToast("Change applied", "success");
  }

  function handleEditSituationTitle(title: string) {
    if (!title || !selectedSituation) return;
    setSelectedSituation((prev) => (prev ? { ...prev, title } : prev));
  }

  function handleUndoScript() {
    const i = historyIndexRef.current;
    if (i <= 0) return;
    const newIndex = i - 1;
    historyIndexRef.current = newIndex;
    setScriptHistoryIndex(newIndex);
    setScript(scriptHistory[newIndex].script);
  }

  function handleRedoScript() {
    const i = historyIndexRef.current;
    if (i >= scriptHistory.length - 1) return;
    const newIndex = i + 1;
    historyIndexRef.current = newIndex;
    setScriptHistoryIndex(newIndex);
    setScript(scriptHistory[newIndex].script);
  }

  function handleRestoreScriptVersion(index: number) {
    historyIndexRef.current = index;
    setScriptHistoryIndex(index);
    setScript(scriptHistory[index].script);
  }

  async function handleRegenerateVisualConcept(id: string, variationStyle?: VisualVariationStyle) {
    if (!structured || !script || !selectedSituation) return;
    const concept = visualConcepts.find((c) => c.id === id);
    if (!concept) return;
    setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const result = await regenerateVisualConcept({
        structured_product: structured,
        script,
        situation: selectedSituation,
        creative_angle: selectedAngle ?? "",
        concept,
        variation_style: variationStyle,
      });
      setVisualConcepts((prev) => prev.map((c) => (c.id === id ? result : c)));
      const regenAssetId = visualAssetIdByConceptId[id];
      if (regenAssetId) {
        void updateAsset(regenAssetId, {
          file_path: result.image_path,
          content_json: result as unknown as Record<string, unknown>,
        }).catch(() => {});
      }
      setVisualConceptScoring((prev) => ({ ...prev, [id]: true }));
      scoreVisualConcept({ concept: result })
        .then((scores) => setVisualConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, scores } : c))))
        .catch(() => {})
        .finally(() => setVisualConceptScoring((prev) => ({ ...prev, [id]: false })));
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't regenerate that image.", "danger");
    } finally {
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleGenerateVisualVariation(id: string, variationStyle: VisualVariationStyle) {
    if (!structured || !script || !selectedSituation) return;
    const concept = visualConcepts.find((c) => c.id === id);
    if (!concept) return;
    setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const result = await regenerateVisualConcept({
        structured_product: structured,
        script,
        situation: selectedSituation,
        creative_angle: selectedAngle ?? "",
        concept,
        variation_style: variationStyle,
        as_new_variation: true,
      });
      setVisualConcepts((prev) => [...prev, result]);
      createAsset({
        project_id: activeProjectId ?? undefined,
        asset_type: "image",
        title: result.scene_title,
        product_name: structured.product_name,
        file_path: result.image_path,
        model_used: result.used_model,
        content_json: result as unknown as Record<string, unknown>,
      })
        .then((asset) => {
          setVisualAssetIdByConceptId((prev) => ({ ...prev, [result.id]: asset.id }));
          void logHistoryEvent({
            event_type: "generated_image",
            summary: `Generated image variation — ${result.scene_title}`,
            project_id: activeProjectId ?? undefined,
            asset_id: asset.id,
          }).catch(() => {});
        })
        .catch(() => {});
      setVisualConceptScoring((prev) => ({ ...prev, [result.id]: true }));
      scoreVisualConcept({ concept: result })
        .then((scores) => setVisualConcepts((prev) => prev.map((c) => (c.id === result.id ? { ...c, scores } : c))))
        .catch(() => {})
        .finally(() => setVisualConceptScoring((prev) => ({ ...prev, [result.id]: false })));
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't generate a variation.", "danger");
    } finally {
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleEditVisualConceptPrompt(
    id: string,
    patch: { prompt: string; style_params: VisualConceptStyleParams }
  ) {
    if (!structured || !script || !selectedSituation) return;
    const concept = visualConcepts.find((c) => c.id === id);
    if (!concept) return;
    const editedConcept: VisualConcept = {
      ...concept,
      prompt: patch.prompt,
      style_params: patch.style_params,
    };
    setVisualConcepts((prev) => prev.map((c) => (c.id === id ? editedConcept : c)));
    setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const result = await regenerateVisualConcept({
        structured_product: structured,
        script,
        situation: selectedSituation,
        creative_angle: selectedAngle ?? "",
        concept: editedConcept,
        is_manual_edit: true,
      });
      setVisualConcepts((prev) => prev.map((c) => (c.id === id ? result : c)));
      const editAssetId = visualAssetIdByConceptId[id];
      if (editAssetId) {
        void updateAsset(editAssetId, {
          file_path: result.image_path,
          content_json: result as unknown as Record<string, unknown>,
        }).catch(() => {});
      }
      setVisualConceptScoring((prev) => ({ ...prev, [id]: true }));
      scoreVisualConcept({ concept: result })
        .then((scores) => setVisualConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, scores } : c))))
        .catch(() => {})
        .finally(() => setVisualConceptScoring((prev) => ({ ...prev, [id]: false })));
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't regenerate with those changes.", "danger");
    } finally {
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleDownloadVisualConcept(id: string, format: "png" | "jpeg" | "webp") {
    const concept = visualConcepts.find((c) => c.id === id);
    if (!concept) return;
    setVisualConceptDownloading((prev) => ({ ...prev, [id]: true }));
    try {
      const blob = await downloadVisualConcept({ concept, format });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${concept.scene_title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-4k.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Download failed.", "danger");
    } finally {
      setVisualConceptDownloading((prev) => ({ ...prev, [id]: false }));
    }
  }

  function handleToggleFavoriteVisualConcept(id: string) {
    const concept = visualConcepts.find((c) => c.id === id);
    setVisualConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, favorite: !c.favorite } : c)));
    const favAssetId = visualAssetIdByConceptId[id];
    if (favAssetId) {
      void updateAsset(favAssetId, { is_favorite: !(concept?.favorite ?? false) }).catch(() => {});
    }
  }

  async function handleRunCompliance() {
    if (!script || !productInput) return;
    setComplianceLoading(true);
    setGlobalError(null);
    try {
      const fullText = flattenScript(script)
        .map((l) => l.text)
        .join("\n");
      const result = await auditCompliance({
        script_text: fullText,
        product_category: category,
        product_name: productInput.product_name,
      });
      setCompliance(result);
      goTo(3);
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Compliance audit failed.");
    } finally {
      setComplianceLoading(false);
    }
  }

  async function handleRegenerateFromCompliance() {
    if (!selectedSituation || !selectedAngle) return;
    const ok = await runScriptGeneration(selectedSituation, selectedAngle, setScriptRegenLoading);
    if (ok) goTo(2);
  }

  const fetchAssetForLine = useCallback(async (id: string, tags: string[]) => {
    setLoadingAssetIds((prev) => new Set(prev).add(id));
    try {
      const result = await sourceAsset({ line_id: id, visual_tags: tags });
      setAssets((prev) => ({ ...prev, [id]: result }));
    } catch {
      setAssets((prev) => ({
        ...prev,
        [id]: { line_id: id, tag_used: tags[0] ?? "", broadened: false, candidate: null, reasoning: "Request failed." },
      }));
    } finally {
      setLoadingAssetIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

  async function handleEnterAssetsStep() {
    if (!script) return;
    goTo(4);
    const lines = flattenScript(script);
    await Promise.all(lines.map((l) => fetchAssetForLine(l.id, l.visual_tags)));
  }

  async function handleRegenerateAssetLine(id: string) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === id);
    if (!line) return;
    await fetchAssetForLine(id, line.visual_tags);
  }

  async function handleGenerateMotion(id: string) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === id);
    const asset = assets[id];
    if (!line || !asset?.candidate) return;

    setLoadingMotionIds((prev) => new Set(prev).add(id));
    try {
      const result = await generateMotion({
        line_id: id,
        image_url: asset.candidate.url,
        visual_tags: line.visual_tags,
      });
      setMotions((prev) => ({ ...prev, [id]: result }));
      createAsset({
        project_id: activeProjectId ?? undefined,
        asset_type: "video",
        title: line.text.slice(0, 60),
        product_name: structured?.product_name ?? "",
        file_path: result.video_path,
        content_json: result as unknown as Record<string, unknown>,
      })
        .then((newAsset) => {
          void logHistoryEvent({
            event_type: "generated_video",
            summary: "Generated video clip",
            project_id: activeProjectId ?? undefined,
            asset_id: newAsset.id,
          }).catch(() => {});
        })
        .catch(() => {});
    } catch (e) {
      setGlobalError(
        e instanceof ApiError ? e.message : "Motion generation failed for this line — the image will stay static."
      );
    } finally {
      setLoadingMotionIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  const fetchVoiceoverForLine = useCallback(
    async (id: string, text: string) => {
      setLoadingVoiceoverIds((prev) => new Set(prev).add(id));
      try {
        const [result] = await generateVoiceover({ lines: [{ line_id: id, text }] });
        setVoiceovers((prev) => ({ ...prev, [id]: result }));
        createAsset({
          project_id: activeProjectId ?? undefined,
          asset_type: "voiceover",
          title: text.slice(0, 60),
          product_name: structured?.product_name ?? "",
          file_path: result.audio_path,
          content_json: result as unknown as Record<string, unknown>,
        })
          .then((asset) => {
            void logHistoryEvent({
              event_type: "generated_voiceover",
              summary: "Generated voiceover",
              project_id: activeProjectId ?? undefined,
              asset_id: asset.id,
            }).catch(() => {});
          })
          .catch(() => {});
      } catch {
        setGlobalError("Voiceover generation failed for one line — try regenerating it.");
      } finally {
        setLoadingVoiceoverIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [activeProjectId, structured]
  );

  async function handleEnterVoiceoverStep() {
    if (!script) return;
    setAssetsContinueLoading(true);
    goTo(5);
    setAssetsContinueLoading(false);
    const lines = flattenScript(script);
    await Promise.all(lines.map((l) => fetchVoiceoverForLine(l.id, l.text)));
  }

  async function handleRegenerateVoiceoverLine(id: string) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === id);
    if (!line) return;
    await fetchVoiceoverForLine(id, line.text);
  }

  async function handleEnterRenderStep() {
    setVoiceoverContinueLoading(true);
    goTo(6);
    setVoiceoverContinueLoading(false);
  }

  async function handleRender() {
    if (!script || !productInput) return;
    setRendering(true);
    setGlobalError(null);
    try {
      const lines = flattenScript(script).map((l) => {
        const vo = voiceovers[l.id];
        const motion = motions[l.id];
        return {
          text: l.text,
          image_url: assets[l.id]?.candidate?.url ?? "",
          video_url: motion ? motionFileUrl(motion.video_path) : undefined,
          audio_url: vo ? audioFileUrl(vo.audio_path) : undefined,
          min_duration_seconds: vo ? vo.duration_seconds + 0.5 : undefined,
        };
      });
      const result = await renderVideo({
        product_name: productInput.product_name,
        lines,
      });
      setRenderResult(result);
      setApproved(false);
      createAsset({
        project_id: activeProjectId ?? undefined,
        asset_type: "render",
        title: productInput.product_name,
        product_name: productInput.product_name,
        file_path: result.output_path,
        content_json: result as unknown as Record<string, unknown>,
      })
        .then((asset) => {
          void logHistoryEvent({
            event_type: "exported_video",
            summary: `Exported final render — ${productInput.product_name}`,
            project_id: activeProjectId ?? undefined,
            asset_id: asset.id,
          }).catch(() => {});
        })
        .catch(() => {});
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Render failed.");
    } finally {
      setRendering(false);
    }
  }

  function handleSelectHook(hook: Hook) {
    setSelectedHookText(hook.text);
    setHookPickerOpen(false);
    void markHookUsed(hook.id).catch(() => {});
    void logHistoryEvent({
      event_type: "used_hook",
      summary: `Used hook — "${hook.text}"`,
      project_id: activeProjectId ?? undefined,
    }).catch(() => {});
    showToast("Hook selected — used on the next script generation", "success");
  }

  const scriptLines = script ? flattenScript(script) : [];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-8 px-6 py-10 lg:px-10 xl:px-12">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {activeTemplate ? (
          <div className="flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-1.5 text-[12px] font-medium text-[var(--accent)]">
            <span>Using template: {activeTemplate.name}</span>
            <button type="button" onClick={handleClearActiveTemplate} className="text-[var(--accent)]/70 hover:text-[var(--accent)]">
              ✕
            </button>
          </div>
        ) : (
          <span />
        )}
        <PipelineSubHeader saveStatus={saveStatus} />
      </div>

      <HookPickerModal open={hookPickerOpen} onClose={() => setHookPickerOpen(false)} onSelect={handleSelectHook} />

      <div className="overflow-x-auto pb-1">
        <Stepper steps={STEPS} activeIndex={stepIndex} furthestIndex={furthest} onSelect={goTo} />
      </div>

          {globalError && (
            <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
              {globalError}
            </div>
          )}

          <main>
            <AnimatePresence mode="wait">
              <motion.div
                key={STEPS[stepIndex].key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {stepIndex === 0 && (
                  <ProductWorkspaceStep
                    onSubmit={handleInputSubmit}
                    inputLoading={inputLoading}
                    inputError={inputError}
                    structured={structured}
                    onImproveDescription={handleImproveDescription}
                    improvingDescription={improvingDescription}
                    onContinue={handleGenerateSituations}
                    continueLoading={situationsLoading}
                    referenceMaterials={referenceMaterials}
                    uploadingMaterialIds={uploadingMaterialIds}
                    onAddReferenceFiles={handleAddReferenceFiles}
                    onAddReferenceUrl={handleAddReferenceUrl}
                    onRemoveReferenceMaterial={handleRemoveReferenceMaterial}
                    sourceUrlRawText={sourceUrlRawText}
                    onSourceUrlRawTextChange={setSourceUrlRawText}
                    activityLog={activityLog}
                    onActivity={pushActivity}
                  />
                )}

                {stepIndex === 1 && (
                  <StorySituationStep
                    situations={situations}
                    loading={situationsLoading}
                    generatingMore={situationsGenMoreLoading}
                    selectingKey={situationSelectingKey}
                    onSelectAngle={handleSelectAngle}
                    onGenerateMore={handleGenerateMoreSituations}
                    onBack={() => goTo(0)}
                    scriptLanguage={scriptLanguage}
                    onScriptLanguageChange={setScriptLanguage}
                    targetDuration={targetDuration}
                    onTargetDurationChange={setTargetDuration}
                  />
                )}

                {stepIndex === 2 && script && selectedSituation && (
                  <div className="space-y-6">
                    <ScriptStep
                      script={script}
                      situation={selectedSituation}
                      creativeAngle={selectedAngle ?? ""}
                      scriptLanguage={scriptLanguage}
                      onScriptLanguageChange={setScriptLanguage}
                      targetDuration={targetDuration}
                      onTargetDurationChange={setTargetDuration}
                      onRegenerateScope={handleRegenerateScope}
                      onBack={() => goTo(1)}
                      regenerating={scriptRegenLoading}
                      selectedHookText={selectedHookText}
                      onChooseHook={() => setHookPickerOpen(true)}
                      onEditLine={handleEditLine}
                      onEditLineField={handleEditLineField}
                      onEditWholeScript={handleEditWholeScript}
                      onApplyDirective={handleApplyDirectiveToLine}
                      onGenerateAlternatives={handleGenerateAlternativesForLine}
                      onSelectAlternative={handleSelectAlternativeForLine}
                      onTranslateLine={handleTranslateLine}
                      lineLoading={lineLoading}
                      recentlyChangedLineIds={recentlyChangedLineIds}
                      onAnalyzeScript={handleAnalyzeScript}
                      onRunScriptCommand={handleRunScriptCommand}
                      onApplyPatch={handleApplyPatch}
                      onEditTitle={handleEditSituationTitle}
                      history={scriptHistory}
                      historyIndex={scriptHistoryIndex}
                      onUndo={handleUndoScript}
                      onRedo={handleRedoScript}
                      onRestoreVersion={handleRestoreScriptVersion}
                    />

                    <VisualConceptsSection
                      concepts={visualConcepts}
                      loading={visualConceptsLoading}
                      error={visualConceptsError}
                      scoring={visualConceptScoring}
                      regenerating={visualConceptRegenLoading}
                      downloading={visualConceptDownloading}
                      onRegenerate={handleRegenerateVisualConcept}
                      onGenerateVariation={handleGenerateVisualVariation}
                      onEditPrompt={handleEditVisualConceptPrompt}
                      onDownload={handleDownloadVisualConcept}
                      onToggleFavorite={handleToggleFavoriteVisualConcept}
                      onRetry={handleRetryVisualConcepts}
                      onRetryOne={handleRetryOneVisualConcept}
                    />

                    <div className="flex justify-between pt-2">
                      <Button variant="ghost" onClick={() => goTo(1)}>
                        ← Back
                      </Button>
                      <Button onClick={handleRunCompliance} loading={complianceLoading}>
                        Run compliance audit →
                      </Button>
                    </div>
                  </div>
                )}

                {stepIndex === 2 && (!script || !selectedSituation) && (
                  <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-6 py-14 text-center">
                    {situationSelectingKey ? (
                      <>
                        <span className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--foreground)]/20 border-t-[var(--accent)]" />
                        <p className="text-[13.5px] text-[var(--foreground)]">Writing your script…</p>
                      </>
                    ) : (
                      <>
                        <p className="text-[14px] font-medium text-[var(--foreground)]">Select a story angle to continue</p>
                        <p className="max-w-sm text-[12.5px] text-[var(--muted)]">
                          No script has been generated for this project yet — pick a story and angle first.
                        </p>
                        <Button variant="secondary" onClick={() => goTo(1)}>
                          ← Back to Story
                        </Button>
                      </>
                    )}
                  </div>
                )}

                {stepIndex === 3 && compliance && (
                  <ComplianceStep
                    result={compliance}
                    onContinue={handleEnterAssetsStep}
                    onBack={() => goTo(2)}
                    onRegenerateScript={handleRegenerateFromCompliance}
                    regenerating={scriptRegenLoading}
                    continuing={false}
                  />
                )}

                {stepIndex === 4 && script && (
                  <AssetsStep
                    lines={scriptLines}
                    assets={assets}
                    loadingIds={loadingAssetIds}
                    onRegenerateLine={handleRegenerateAssetLine}
                    motions={motions}
                    loadingMotionIds={loadingMotionIds}
                    onGenerateMotion={handleGenerateMotion}
                    onContinue={handleEnterVoiceoverStep}
                    onBack={() => goTo(3)}
                    continuing={assetsContinueLoading}
                  />
                )}

                {stepIndex === 5 && script && (
                  <VoiceoverStep
                    lines={scriptLines}
                    voiceovers={voiceovers}
                    loadingIds={loadingVoiceoverIds}
                    onRegenerateLine={handleRegenerateVoiceoverLine}
                    onContinue={handleEnterRenderStep}
                    onBack={() => goTo(4)}
                    continuing={voiceoverContinueLoading}
                  />
                )}

                {stepIndex === 6 && (
                  <RenderStep
                    rendering={rendering}
                    renderResult={renderResult}
                    videoUrl={renderResult ? renderFileUrl(renderResult.output_path) : null}
                    approved={approved}
                    onRender={handleRender}
                    onApprove={() => setApproved(true)}
                    onBack={() => goTo(5)}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </main>
    </div>
  );
}
