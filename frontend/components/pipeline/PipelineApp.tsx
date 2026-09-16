"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { PipelineSubHeader } from "@/components/shell/PipelineSubHeader";
import { useToast } from "@/components/shell/ToastProvider";
import { useActiveProject } from "@/lib/project-context";
import { ACTIVE_TEMPLATE_KEY, type ActiveTemplateHint } from "@/lib/constants";
import { useSceneVisuals, type SceneVisualsContext } from "@/lib/useSceneVisuals";
import { useAyushProducts } from "@/lib/useAyushProducts";
import { HookPickerModal } from "@/components/library/HookPickerModal";
import { HookBanner } from "@/components/pipeline/HookBanner";
import { ProductWorkspaceStep } from "@/components/steps/ProductWorkspaceStep";
import type { ActivityEntry } from "@/components/steps/AiUnderstandingPanel";
import { StorySituationStep } from "@/components/steps/StorySituationStep";
import { ContentTypeStep } from "@/components/steps/ContentTypeStep";
import { FormatStep } from "@/components/steps/FormatStep";
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
  generateAlternatives,
  generateMotion,
  generateScript,
  generateStorySituations,
  generateVoiceover,
  getAyushProductContext,
  getScriptSuggestions,
  logHistoryEvent,
  motionFileUrl,
  productUploadFileUrl,
  regenerateScriptSection,
  renderFileUrl,
  renderVideo,
  rewriteLine,
  runScriptCommand,
  savePipelineState,
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
  PRODUCT_CATEGORIES,
  type AyushProduct,
  type ComplianceResult,
  type ContentType,
  type GeneratedScript,
  type Hook,
  type MotionGenerationResult,
  type ProductContext,
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
  type StaticImageState,
  type StorySituation,
  type StructuredProduct,
  type VisualConcept,
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
  contentType: ContentType | null;
  selectedFormat: string | null;
  formatDescription: string | null;
  scriptTone: string | null;
  scriptLanguage: ScriptLanguage | null;
  targetDuration: string | null;
  script: GeneratedScript | null;
  scriptHistory: ScriptVersion[] | null;
  scriptHistoryIndex: number | null;
  visualConcepts: VisualConcept[] | null;
  visualAssetIdByConceptId: Record<string, string> | null;
  staticImages: Record<string, StaticImageState> | null;
  scriptAssetId: string | null;
  compliance: ComplianceResult | null;
  assets: Record<string, SelectedAsset | undefined> | null;
  motions: Record<string, MotionGenerationResult | undefined> | null;
  voiceovers: Record<string, VoiceoverResult | undefined> | null;
  renderResult: RenderResult | null;
  approved: boolean | null;
  selectedHookText: string | null;
  productLibraryContext: ProductContext | null;
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
    contentType: (raw.contentType as ContentType | undefined) ?? null,
    selectedFormat: typeof raw.selectedFormat === "string" ? raw.selectedFormat : null,
    formatDescription: typeof raw.formatDescription === "string" ? raw.formatDescription : null,
    scriptTone: typeof raw.scriptTone === "string" ? raw.scriptTone : null,
    scriptLanguage: (raw.scriptLanguage as ScriptLanguage | undefined) ?? null,
    targetDuration: typeof raw.targetDuration === "string" ? raw.targetDuration : null,
    script: (raw.script as GeneratedScript | undefined) ?? null,
    scriptHistory: (raw.scriptHistory as ScriptVersion[] | undefined) ?? null,
    scriptHistoryIndex: typeof raw.scriptHistoryIndex === "number" ? raw.scriptHistoryIndex : null,
    visualConcepts: (raw.visualConcepts as VisualConcept[] | undefined) ?? null,
    visualAssetIdByConceptId: (raw.visualAssetIdByConceptId as Record<string, string> | undefined) ?? null,
    staticImages: (raw.staticImages as Record<string, StaticImageState> | undefined) ?? null,
    scriptAssetId: (raw.scriptAssetId as string | undefined) ?? null,
    compliance: (raw.compliance as ComplianceResult | undefined) ?? null,
    assets: (raw.assets as Record<string, SelectedAsset | undefined> | undefined) ?? null,
    motions: (raw.motions as Record<string, MotionGenerationResult | undefined> | undefined) ?? null,
    voiceovers: (raw.voiceovers as Record<string, VoiceoverResult | undefined> | undefined) ?? null,
    renderResult: (raw.renderResult as RenderResult | undefined) ?? null,
    approved: typeof raw.approved === "boolean" ? raw.approved : null,
    selectedHookText: (raw.selectedHookText as string | undefined) ?? null,
    productLibraryContext: (raw.productLibraryContext as ProductContext | undefined) ?? null,
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
  specific_scene: "Scene regenerated",
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
  // Set only when the user picked a Product Library product instead of the
  // manual Product flow — threaded into Script generation / Asset Sourcing
  // as approved product knowledge. `structured` above is still populated
  // (mapped from this context) so every existing downstream reader keeps
  // working unchanged; this is purely additive.
  const [productLibraryContext, setProductLibraryContext] = useState<ProductContext | null>(
    () => restored.productLibraryContext
  );
  const [productSourceMode, setProductSourceMode] = useState<"manual" | "library">(() =>
    restored.productLibraryContext ? "library" : "manual"
  );
  // Shared with Sidebar.tsx's AyushWellness category tree — same fetch,
  // same loading/failed/retry semantics, so the two can never disagree about
  // which products exist. Only fetches while this mode is actually selected
  // (and re-fetches each time the user switches back into it), rather than
  // once-ever-per-mount, so a product created/restored elsewhere is picked
  // up without needing a full page reload.
  const { products: ayushProducts, failed: ayushProductsFailed, refresh: retryAyushProducts } = useAyushProducts({
    enabled: productSourceMode === "library",
  });
  const [referenceMaterials, setReferenceMaterials] = useState<ReferenceMaterial[]>(() => restored.referenceMaterials ?? []);
  const [uploadingMaterialIds, setUploadingMaterialIds] = useState<Set<string>>(new Set());
  const [sourceUrlRawText, setSourceUrlRawText] = useState<string | undefined>(() => restored.sourceUrlRawText);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [situations, setSituations] = useState<StorySituation[]>(() => restored.situations ?? []);
  const [selectedSituation, setSelectedSituation] = useState<StorySituation | null>(() => restored.selectedSituation);
  const [selectedAngle, setSelectedAngle] = useState<string | null>(() => restored.selectedAngle);
  const [contentType, setContentType] = useState<ContentType>(() => restored.contentType ?? "video");
  const [selectedFormat, setSelectedFormat] = useState(() => restored.selectedFormat ?? "");
  const [formatDescription, setFormatDescription] = useState(() => restored.formatDescription ?? "");
  const [scriptTone, setScriptTone] = useState(() => restored.scriptTone ?? "");
  // Sub-flow shown in place of the situation grid between picking an angle and
  // actually generating — never persisted (a refresh mid-selection just drops
  // back to the situation grid, same as situationSelectingKey today).
  const [scriptSetupPhase, setScriptSetupPhase] = useState<"content_type" | "format" | null>(null);
  const [pendingAngleSelection, setPendingAngleSelection] = useState<{ situation: StorySituation; angle: string } | null>(
    null
  );
  const [scriptLanguage, setScriptLanguage] = useState<ScriptLanguage>(() => restored.scriptLanguage ?? "hinglish");
  const [targetDuration, setTargetDuration] = useState(() => restored.targetDuration ?? "30s");
  const [script, setScript] = useState<GeneratedScript | null>(() => restored.script);
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
  const [scriptRegenLoading, setScriptRegenLoading] = useState(false);
  const [formatGenerating, setFormatGenerating] = useState(false);
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
  const [selectedHookText, setSelectedHookText] = useState(() => restored.selectedHookText ?? "");
  const [hookPickerOpen, setHookPickerOpen] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<ActiveTemplateHint | null>(null);

  const sceneVisuals = useSceneVisuals({
    projectId: activeProjectId,
    productCategory: category,
    productName: structured?.product_name ?? "",
    format: selectedFormat,
    showToast,
    initialVisualConcepts: restored.visualConcepts ?? undefined,
    initialStaticImages: restored.staticImages ?? undefined,
    initialVisualAssetIdByConceptId: restored.visualAssetIdByConceptId ?? undefined,
  });
  const {
    visualConcepts,
    setVisualConcepts,
    staticImages,
    setStaticImages,
    visualConceptsLoading,
    visualConceptsError,
    visualConceptScoring,
    visualConceptRegenLoading,
    visualConceptDownloading,
    visualAssetIdByConceptId,
    renderOneVisualConcept,
    generateVisualConcepts: handleGenerateVisualConcepts,
    retryVisualConcepts,
    retryOneVisualConcept,
    regenerateVisualConcept: handleRegenerateVisualConcept,
    generateVisualVariation: handleGenerateVisualVariation,
    editVisualConceptPrompt: handleEditVisualConceptPrompt,
    downloadVisualConcept: handleDownloadVisualConcept,
    toggleFavoriteVisualConcept: handleToggleFavoriteVisualConcept,
    generateStaticVisuals: handleGenerateStaticVisuals,
    retryStaticImage: handleRetryStaticImage,
  } = sceneVisuals;

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
      contentType,
      selectedFormat,
      formatDescription,
      scriptTone,
      scriptLanguage,
      targetDuration,
      script,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      staticImages,
      scriptAssetId,
      compliance,
      assets,
      motions,
      voiceovers,
      renderResult,
      approved,
      selectedHookText,
      furthest,
      productLibraryContext,
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
      contentType,
      selectedFormat,
      formatDescription,
      scriptTone,
      scriptLanguage,
      targetDuration,
      script,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      staticImages,
      scriptAssetId,
      compliance,
      assets,
      motions,
      voiceovers,
      renderResult,
      approved,
      selectedHookText,
      furthest,
      productLibraryContext,
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

  // The very first save creates the project AND does a one-time
  // router.replace from the project-less "/" route into the persistent
  // "/pipeline/[projectId]/..." layout — a real remount, unlike navigation
  // between sibling stages once inside that layout (see
  // PipelineProjectClient's comment). If that first save is still sitting in
  // its normal debounce window when a long-running generation call (e.g.
  // story situations, which can take 15s+) is kicked off, the remount tears
  // down the component instance holding that in-flight request; when it
  // resolves, setState + goTo() fire against a dead instance and the result
  // is silently lost — the next screen renders from the pre-generation
  // snapshot with no error and no visible sign anything went wrong. Firing
  // the first save immediately (no debounce) the moment there's something
  // worth saving closes that window: project creation is a couple of fast
  // REST calls, reliably finishing well before any subsequent generation
  // step, so the remount is done and settled before it could race anything.
  useEffect(() => {
    if (!projectIdRef.current && !creatingProjectRef.current && (structured || productInput)) {
      void flushSave();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structured, productInput]);

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

  async function handleSelectAyushProduct(product: AyushProduct) {
    setInputLoading(true);
    setInputError(null);
    try {
      const context = await getAyushProductContext(product.id);
      setProductLibraryContext(context);
      setCategory(context.category);
      // Real, approved product knowledge — map directly into StructuredProduct
      // so every existing downstream reader (Story/Script/Compliance) keeps
      // working unchanged. No AI structuring call needed: this data is
      // already ground truth, not something to re-derive.
      setStructured({
        product_name: context.name,
        target_audience: context.target_audience,
        ingredients: context.ingredients,
        usp: context.usp,
        tone: context.preferred_tone,
        key_benefits: context.benefits,
        industry: context.category,
        pain_points: [],
        marketing_angle: context.positioning,
        key_emotions: [],
        keywords: [],
        missing_fields: [],
        confidence: 1,
      });
      setProductInput({
        product_name: context.name,
        target_audience: context.target_audience,
        source_type: "none",
        manual_ingredients: context.ingredients.join(", "),
        manual_usp: context.usp,
      } as ProductInput);
    } catch (e) {
      setInputError(e instanceof ApiError ? e.message : "Couldn't load that product's knowledge.");
    } finally {
      setInputLoading(false);
    }
  }

  function handleClearAyushProduct() {
    setProductLibraryContext(null);
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

  const sceneContext: SceneVisualsContext | null =
    structured && script && selectedSituation
      ? { structuredProduct: structured, script, situation: selectedSituation, angle: selectedAngle ?? "" }
      : null;

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
    async (
      situation: StorySituation,
      angle: string,
      setLoading: (v: boolean) => void,
      overrides?: { format?: string; formatDescription?: string; tone?: string }
    ): Promise<boolean> => {
      if (!structured) return false;
      const formatValue = overrides?.format ?? selectedFormat;
      const formatDescriptionValue = overrides?.formatDescription ?? formatDescription;
      const toneValue = overrides?.tone ?? scriptTone;
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
          content_type: contentType,
          format: formatValue,
          format_description: formatDescriptionValue,
          tone: toneValue,
          avoid_repeating_hook: script?.hook.text || undefined,
          avoid_repeating_mechanism: script?.creative_mechanism || undefined,
          product_context: productLibraryContext ?? undefined,
        });
        setScript(result);
        setSelectedSituation(situation);
        setSelectedAngle(angle);
        if (overrides) {
          setSelectedFormat(formatValue);
          setFormatDescription(formatDescriptionValue);
          setScriptTone(toneValue);
        }
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
        if (contentType === "video") {
          setStaticImages({});
          void handleGenerateVisualConcepts(structured, result, situation, angle);
        } else {
          setVisualConcepts([]);
          handleGenerateStaticVisuals(result, formatValue);
        }
        return true;
      } catch (e) {
        setGlobalError(e instanceof ApiError ? e.message : "Script generation failed.");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [
      structured,
      category,
      scriptLanguage,
      targetDuration,
      selectedHookText,
      activeProjectId,
      contentType,
      selectedFormat,
      formatDescription,
      scriptTone,
      script,
      productLibraryContext,
    ]
  );

  function handleSelectAngle(situation: StorySituation, angle: string) {
    // Don't generate yet — surface Content Type -> Format -> Configure first;
    // runScriptGeneration only fires once the user finishes that sub-flow
    // (see handleGenerateFromFormat below).
    setPendingAngleSelection({ situation, angle });
    setScriptSetupPhase("content_type");
  }

  function handleSelectContentType(type: ContentType) {
    setContentType(type);
    setScriptSetupPhase("format");
  }

  function handleContentTypeBack() {
    setScriptSetupPhase(null);
    setPendingAngleSelection(null);
  }

  function handleFormatBack() {
    setScriptSetupPhase("content_type");
  }

  async function handleGenerateFromFormat(selection: { format: string; formatDescription: string; tone: string }) {
    if (!pendingAngleSelection) return;
    const { situation, angle } = pendingAngleSelection;
    const ok = await runScriptGeneration(situation, angle, setFormatGenerating, selection);
    // Stay on the format step (with the error already surfaced via
    // globalError) if generation failed — never navigate to Script without a
    // real script.
    if (ok) {
      setScriptSetupPhase(null);
      setPendingAngleSelection(null);
      goTo(2);
    }
  }

  async function handleRegenerateScript() {
    if (!selectedSituation || !selectedAngle) return;
    await runScriptGeneration(selectedSituation, selectedAngle, setScriptRegenLoading);
  }

  function handleChangeFormatFromScript() {
    if (!selectedSituation || !selectedAngle) return;
    setPendingAngleSelection({ situation: selectedSituation, angle: selectedAngle });
    setScriptSetupPhase("format");
    goTo(1);
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
        content_type: contentType,
        format: selectedFormat,
        format_description: formatDescription,
        tone: options?.tone ?? scriptTone,
        target_scene_label: options?.targetSceneLabel,
        product_context: productLibraryContext ?? undefined,
      });
      setScript(result);
      if (options?.tone) setScriptTone(options.tone);
      const label = options?.targetSceneLabel
        ? `AI: Regenerated "${options.targetSceneLabel}"`
        : options?.tone
          ? `AI: Tone → ${options.tone}`
          : options?.targetWordCount
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
        structured_product: structured ?? undefined,
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

  const fetchAssetForLine = useCallback(async (id: string, tags: string[], excludeUrls: string[] = [], section?: string) => {
    // The backend rejects an empty visual_tags list with a 422 before ever
    // touching Pexels/Pixabay — catching that here avoids a guaranteed-to-fail
    // request and, more importantly, avoids it landing in the generic catch
    // below and rendering identically to a genuine "found nothing" result.
    if (tags.length === 0) {
      setAssets((prev) => ({
        ...prev,
        [id]: {
          line_id: id,
          tag_used: "",
          broadened: false,
          candidate: null,
          reasoning: "No visual search terms were generated for this line.",
        },
      }));
      return;
    }
    setLoadingAssetIds((prev) => new Set(prev).add(id));
    try {
      const result = await sourceAsset({
        line_id: id,
        visual_tags: tags,
        exclude_urls: excludeUrls,
        section,
        product_context: productLibraryContext ?? undefined,
      });
      setAssets((prev) => ({ ...prev, [id]: result }));
    } catch (e) {
      setAssets((prev) => ({
        ...prev,
        [id]: {
          line_id: id,
          tag_used: tags[0] ?? "",
          broadened: false,
          candidate: null,
          reasoning: e instanceof ApiError ? `Request failed (HTTP ${e.status}).` : "Request failed.",
        },
      }));
    } finally {
      setLoadingAssetIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, [productLibraryContext]);

  async function handleEnterAssetsStep() {
    if (!script) return;
    goTo(4);
    const lines = flattenScript(script);
    await Promise.all(lines.map((l) => fetchAssetForLine(l.id, l.visual_tags, [], l.section ?? undefined)));
  }

  async function handleRegenerateAssetLine(id: string) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === id);
    if (!line) return;
    // Steer away from images already used on the script's OTHER lines —
    // by regenerate time every other line has already resolved, so this is
    // the one place the pipeline actually knows prior selections.
    const excludeUrls = Object.entries(assets)
      .filter(([lineId]) => lineId !== id)
      .map(([, a]) => a?.candidate?.url)
      .filter((url): url is string => Boolean(url));
    await fetchAssetForLine(id, line.visual_tags, excludeUrls, line.section ?? undefined);
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
        const asset = assets[l.id]?.candidate ?? null;
        return {
          text: l.text,
          image_url: asset?.url ?? "",
          video_url: motion ? motionFileUrl(motion.video_path) : undefined,
          audio_url: vo ? audioFileUrl(vo.audio_path) : undefined,
          min_duration_seconds: vo ? vo.duration_seconds + 0.5 : undefined,
          section: l.section,
          scene_label: l.scene_label,
          on_screen_text: l.on_screen_text,
          visual_direction: l.visual_direction,
          camera_angle: l.camera_angle,
          emotion: l.emotion,
          is_product_asset: asset?.source === "product_library",
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
                {stepIndex === 0 && selectedHookText && (
                  <HookBanner
                    text={selectedHookText}
                    onChangeText={setSelectedHookText}
                    onChooseHook={() => setHookPickerOpen(true)}
                  />
                )}

                {stepIndex === 0 && (
                  <Card>
                    <CardBody className="space-y-3 pt-5">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]/70">
                        Product Source
                      </p>
                      <div className="flex gap-1.5">
                        {(["manual", "library"] as const).map((mode) => (
                          <button
                            key={mode}
                            type="button"
                            onClick={() => setProductSourceMode(mode)}
                            className={`rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
                              productSourceMode === mode
                                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                                : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
                            }`}
                          >
                            {mode === "manual" ? "Manual Product" : "AyushWellness Product"}
                          </button>
                        ))}
                      </div>

                      {productSourceMode === "library" &&
                        (productLibraryContext ? (
                          <div className="flex items-center gap-3 rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-4 py-3">
                            {productLibraryContext.primary_asset_url && (
                              <img
                                src={productUploadFileUrl(
                                  productLibraryContext.primary_asset_url.replace(/^\/product-uploads\//, "")
                                )}
                                alt={productLibraryContext.name}
                                className="h-12 w-12 shrink-0 rounded-lg object-cover"
                              />
                            )}
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-[13px] font-medium text-[var(--foreground)]">
                                {productLibraryContext.name}
                              </p>
                              <p className="text-[11.5px] text-[var(--muted)]">
                                {PRODUCT_CATEGORIES.find((c) => c.value === productLibraryContext.category)?.label ??
                                  productLibraryContext.category}
                              </p>
                            </div>
                            <Button size="sm" variant="ghost" onClick={handleClearAyushProduct}>
                              Change
                            </Button>
                          </div>
                        ) : ayushProducts === null && ayushProductsFailed ? (
                          <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3.5 py-2.5">
                            <p className="text-[13px] text-[var(--danger)]">Couldn&apos;t load AyushWellness products.</p>
                            <button
                              type="button"
                              onClick={retryAyushProducts}
                              className="text-[12.5px] font-medium text-[var(--accent)] hover:underline"
                            >
                              Retry
                            </button>
                          </div>
                        ) : (
                          <select
                            defaultValue=""
                            onChange={(e) => {
                              const p = ayushProducts?.find((p) => p.id === e.target.value);
                              if (p) void handleSelectAyushProduct(p);
                            }}
                            className="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3.5 py-2.5 text-[14px] text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
                          >
                            <option value="" disabled>
                              {ayushProducts === null ? "Loading products…" : "Select a product…"}
                            </option>
                            {PRODUCT_CATEGORIES.map((cat) => {
                              const inCategory = (ayushProducts ?? []).filter((p) => p.category === cat.value);
                              if (inCategory.length === 0) return null;
                              return (
                                <optgroup key={cat.value} label={cat.label}>
                                  {inCategory.map((p) => (
                                    <option key={p.id} value={p.id}>
                                      {p.name}
                                    </option>
                                  ))}
                                </optgroup>
                              );
                            })}
                          </select>
                        ))}
                    </CardBody>
                  </Card>
                )}

                {stepIndex === 0 && productSourceMode === "library" && productLibraryContext ? (
                  <Card>
                    <CardBody className="flex items-center justify-between gap-3 pt-5">
                      <p className="text-[13px] text-[var(--muted)]">
                        Using <span className="font-medium text-[var(--foreground)]">{productLibraryContext.name}</span>
                        &apos;s approved product knowledge. Ready to discover story scenarios.
                      </p>
                      <Button onClick={handleGenerateSituations} loading={situationsLoading}>
                        Continue to Story →
                      </Button>
                    </CardBody>
                  </Card>
                ) : stepIndex === 0 ? (
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
                ) : null}

                {stepIndex === 1 && scriptSetupPhase === null && selectedHookText && (
                  <HookBanner
                    text={selectedHookText}
                    onChangeText={setSelectedHookText}
                    onChooseHook={() => setHookPickerOpen(true)}
                  />
                )}

                {stepIndex === 1 && scriptSetupPhase === null && (
                  <StorySituationStep
                    situations={situations}
                    loading={situationsLoading}
                    generatingMore={situationsGenMoreLoading}
                    selectingKey={null}
                    onSelectAngle={handleSelectAngle}
                    onGenerateMore={handleGenerateMoreSituations}
                    onBack={() => goTo(0)}
                    scriptLanguage={scriptLanguage}
                    onScriptLanguageChange={setScriptLanguage}
                    targetDuration={targetDuration}
                    onTargetDurationChange={setTargetDuration}
                  />
                )}

                {stepIndex === 1 && scriptSetupPhase === "content_type" && pendingAngleSelection && (
                  <ContentTypeStep
                    situation={pendingAngleSelection.situation}
                    angle={pendingAngleSelection.angle}
                    onSelect={handleSelectContentType}
                    onBack={handleContentTypeBack}
                  />
                )}

                {stepIndex === 1 && scriptSetupPhase === "format" && pendingAngleSelection && (
                  <FormatStep
                    situation={pendingAngleSelection.situation}
                    angle={pendingAngleSelection.angle}
                    contentType={contentType}
                    targetDuration={targetDuration}
                    onTargetDurationChange={setTargetDuration}
                    onBack={handleFormatBack}
                    onGenerate={handleGenerateFromFormat}
                    generating={formatGenerating}
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
                      onChangeFormat={handleChangeFormatFromScript}
                      staticImages={staticImages}
                      onGenerateStaticImage={handleRetryStaticImage}
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

                    {(script.content_type ?? "video") === "video" && (
                      <VisualConceptsSection
                        concepts={visualConcepts}
                        loading={visualConceptsLoading}
                        error={visualConceptsError}
                        scoring={visualConceptScoring}
                        regenerating={visualConceptRegenLoading}
                        downloading={visualConceptDownloading}
                        onRegenerate={(id, variationStyle) => handleRegenerateVisualConcept(id, variationStyle, sceneContext)}
                        onGenerateVariation={(id, variationStyle) => handleGenerateVisualVariation(id, variationStyle, sceneContext)}
                        onEditPrompt={(id, patch) => handleEditVisualConceptPrompt(id, patch, sceneContext)}
                        onDownload={handleDownloadVisualConcept}
                        onToggleFavorite={handleToggleFavoriteVisualConcept}
                        onRetry={() => retryVisualConcepts(sceneContext)}
                        onRetryOne={(id) => retryOneVisualConcept(id, sceneContext)}
                      />
                    )}

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
                    <p className="text-[14px] font-medium text-[var(--foreground)]">Select a story angle to continue</p>
                    <p className="max-w-sm text-[12.5px] text-[var(--muted)]">
                      No script has been generated for this project yet — pick a story and angle first.
                    </p>
                    <Button variant="secondary" onClick={() => goTo(1)}>
                      ← Back to Story
                    </Button>
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

                {stepIndex === 5 && script && (script.content_type ?? "video") === "static" && (
                  <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-6 py-14 text-center">
                    <p className="text-[14px] font-medium text-[var(--foreground)]">Voiceover isn&#39;t applicable</p>
                    <p className="max-w-sm text-[12.5px] text-[var(--muted)]">
                      This is static creative — there&#39;s no spoken line to narrate, so this stage is skipped.
                    </p>
                    <div className="flex gap-2 pt-1">
                      <Button variant="ghost" onClick={() => goTo(4)}>
                        ← Back
                      </Button>
                      <Button onClick={handleEnterRenderStep}>Continue to Render →</Button>
                    </div>
                  </div>
                )}

                {stepIndex === 5 && script && (script.content_type ?? "video") !== "static" && (
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
