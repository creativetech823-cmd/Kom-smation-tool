"use client";

// Hook Studio — a lightweight, dedicated Hook -> Script -> Images workspace.
// Deliberately NOT the 7-stage Content Pipeline: no Story-situation AI call,
// no Compliance/Voiceover/Render stages, no stepper chrome. Reuses the same
// steps/services the pipeline uses (ProductWorkspaceStep, ContentTypeStep,
// FormatStep, ScriptStep, useSceneVisuals) so script/scene/image generation
// behaves identically to the main pipeline — see PipelineApp.tsx for the
// full-pipeline equivalent of most of the wiring below.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { PipelineSubHeader, type SaveStatus } from "@/components/shell/PipelineSubHeader";
import { useToast } from "@/components/shell/ToastProvider";
import { useSceneVisuals, type SceneVisualsContext } from "@/lib/useSceneVisuals";
import { HookPickerModal } from "@/components/library/HookPickerModal";
import { HookBanner } from "@/components/pipeline/HookBanner";
import { ProductCatalogPicker } from "@/components/hookstudio/ProductCatalogPicker";
import { ProductWorkspaceStep } from "@/components/steps/ProductWorkspaceStep";
import type { ActivityEntry } from "@/components/steps/AiUnderstandingPanel";
import { ContentTypeStep } from "@/components/steps/ContentTypeStep";
import { FormatStep } from "@/components/steps/FormatStep";
import { ScriptStep, type RegenerateOptions } from "@/components/steps/ScriptStep";
import { VisualConceptsSection } from "@/components/steps/VisualConceptsSection";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import type { ScriptVersion } from "@/components/ui/VersionHistoryPanel";
import type { ApplyPatch } from "@/components/ui/AiSuggestionsPanel";
import {
  addReferenceUrl,
  ApiError,
  createAsset,
  generateAlternatives,
  generateScript,
  getScriptSuggestions,
  logHistoryEvent,
  markHookUsed,
  regenerateScriptSection,
  rewriteLine,
  runScriptCommand,
  savePipelineState,
  structureProduct,
  updateAsset,
  uploadReferenceMaterial,
} from "@/lib/api";
import {
  flattenScript,
  type ContentType,
  type GeneratedScript,
  type Hook,
  type ProductInput,
  type Project,
  type ReferenceKind,
  type ReferenceMaterial,
  type RewriteDirective,
  type ScriptCommandSelection,
  type ScriptLanguage,
  type ScriptLine,
  type ScriptRegenerateScope,
  type SmartScriptSuggestionsResult,
  type StorySituation,
  type StructuredProduct,
} from "@/lib/types";

const AUTOSAVE_DEBOUNCE_MS = 800;

const HOOK_STUDIO_LANGUAGE_OPTIONS: { value: ScriptLanguage; label: string }[] = [
  { value: "english", label: "English" },
  { value: "hindi", label: "हिंदी" },
  { value: "hinglish", label: "Hinglish" },
  { value: "marathi", label: "मराठी" },
  { value: "gujarati", label: "ગુજરાતી" },
  { value: "tamil", label: "தமிழ்" },
  { value: "telugu", label: "తెలుగు" },
  { value: "bengali", label: "বাংলা" },
  { value: "kannada", label: "ಕನ್ನಡ" },
  { value: "malayalam", label: "മലയാളം" },
  { value: "custom", label: "Custom" },
];

type Phase = "product" | "content_type" | "format" | "script";

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

export function HookStudioApp({ projectId, initialProject }: { projectId: string; initialProject: Project }) {
  const router = useRouter();
  const { showToast } = useToast();

  const raw = (initialProject.pipeline_state ?? {}) as Record<string, unknown>;
  const [restored] = useState(() => ({
    selectedHookText: typeof raw.selectedHookText === "string" ? raw.selectedHookText : "",
    phase: (raw.phase as Phase | undefined) ?? "product",
    productInput: (raw.productInput as ProductInput | undefined) ?? null,
    category: typeof raw.category === "string" ? raw.category : "",
    structured: (raw.structured as StructuredProduct | undefined) ?? null,
    referenceMaterials: (raw.referenceMaterials as ReferenceMaterial[] | undefined) ?? [],
    sourceUrlRawText: raw.sourceUrlRawText as string | undefined,
    contentType: (raw.contentType as ContentType | undefined) ?? "video",
    selectedFormat: typeof raw.selectedFormat === "string" ? raw.selectedFormat : "",
    formatDescription: typeof raw.formatDescription === "string" ? raw.formatDescription : "",
    scriptTone: typeof raw.scriptTone === "string" ? raw.scriptTone : "",
    scriptLanguage: (raw.scriptLanguage as ScriptLanguage | undefined) ?? "hinglish",
    customLanguage: typeof raw.customLanguage === "string" ? raw.customLanguage : "",
    targetDuration: typeof raw.targetDuration === "string" ? raw.targetDuration : "30s",
    script: (raw.script as GeneratedScript | undefined) ?? null,
    scriptAssetId: (raw.scriptAssetId as string | undefined) ?? null,
    scriptHistory: (raw.scriptHistory as ScriptVersion[] | undefined) ?? [],
    scriptHistoryIndex: typeof raw.scriptHistoryIndex === "number" ? raw.scriptHistoryIndex : -1,
    visualConcepts: raw.visualConcepts as ReturnType<typeof useSceneVisuals>["visualConcepts"] | undefined,
    visualAssetIdByConceptId: raw.visualAssetIdByConceptId as Record<string, string> | undefined,
    staticImages: raw.staticImages as ReturnType<typeof useSceneVisuals>["staticImages"] | undefined,
  }));

  const [selectedHookText, setSelectedHookText] = useState(restored.selectedHookText);
  const [hookPickerOpen, setHookPickerOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>(restored.phase);

  const [catalogSelection, setCatalogSelection] = useState<{ productName: string; category: string }>({
    productName: restored.productInput?.product_name ?? "",
    category: restored.category ?? "",
  });

  const [productInput, setProductInput] = useState<ProductInput | null>(restored.productInput);
  const [category, setCategory] = useState(restored.category);
  const [structured, setStructured] = useState<StructuredProduct | null>(restored.structured);
  const [referenceMaterials, setReferenceMaterials] = useState<ReferenceMaterial[]>(restored.referenceMaterials);
  const [uploadingMaterialIds, setUploadingMaterialIds] = useState<Set<string>>(new Set());
  const [sourceUrlRawText, setSourceUrlRawText] = useState<string | undefined>(restored.sourceUrlRawText);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [inputLoading, setInputLoading] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  const [improvingDescription, setImprovingDescription] = useState(false);

  const [contentType, setContentType] = useState<ContentType>(restored.contentType);
  const [selectedFormat, setSelectedFormat] = useState(restored.selectedFormat);
  const [formatDescription, setFormatDescription] = useState(restored.formatDescription);
  const [scriptTone, setScriptTone] = useState(restored.scriptTone);
  const [scriptLanguage, setScriptLanguage] = useState<ScriptLanguage>(restored.scriptLanguage);
  const [customLanguage, setCustomLanguage] = useState(restored.customLanguage);
  const [targetDuration, setTargetDuration] = useState(restored.targetDuration);
  const [formatGenerating, setFormatGenerating] = useState(false);

  const [script, setScript] = useState<GeneratedScript | null>(restored.script);
  const [scriptAssetId, setScriptAssetId] = useState<string | null>(restored.scriptAssetId);
  const [scriptHistory, setScriptHistory] = useState<ScriptVersion[]>(restored.scriptHistory);
  const [scriptHistoryIndex, setScriptHistoryIndex] = useState(restored.scriptHistoryIndex);
  const historyIndexRef = useRef(restored.scriptHistoryIndex);
  const [lineLoading, setLineLoading] = useState<Record<string, boolean>>({});
  const [recentlyChangedLineIds, setRecentlyChangedLineIds] = useState<Set<string>>(new Set());
  const [scriptRegenLoading, setScriptRegenLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");

  const sceneVisuals = useSceneVisuals({
    projectId,
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
    generateVisualConcepts,
    retryVisualConcepts,
    retryOneVisualConcept,
    regenerateVisualConcept,
    generateVisualVariation,
    editVisualConceptPrompt,
    downloadVisualConcept,
    toggleFavoriteVisualConcept,
    generateStaticVisuals,
    retryStaticImage,
  } = sceneVisuals;

  // The lightweight placeholder "creative brief" ScriptGenerationInput/ScriptStep
  // require in place of a real AI-generated Story Situation — see the Context
  // section of the plan for why this is safe (the mandatory hook line + full
  // product context are injected into the prompt separately regardless).
  const situation: StorySituation | null = structured
    ? {
        id: "hook-studio",
        title: structured.product_name || "Hook-Driven Script",
        description: `A hook-driven script for ${
          structured.product_name || "this product"
        }, opening with the selected hook and building naturally around it.`,
        emotion: "Direct",
        persona: structured.target_audience || "General audience",
        marketing_angle: structured.usp || structured.key_benefits[0] || "",
        category: "Hook-Driven",
        difficulty: "easy",
        estimated_length: targetDuration || "30s",
        virality_score: 0,
        recommended_angles: [],
      }
    : null;

  const sceneContext: SceneVisualsContext | null =
    structured && script && situation ? { structuredProduct: structured, script, situation, angle: "" } : null;

  // Resume in-flight generations after a refresh — same rationale as
  // PipelineApp.tsx's equivalent effect: a restored concept whose last known
  // status is "pending"/"generating" never got a completed image persisted
  // (the reload/tab-close killed its request). Re-fire just that one image,
  // not the other two, and only once per mount.
  const resumedVisualConceptsRef = useRef(false);
  useEffect(() => {
    if (resumedVisualConceptsRef.current) return;
    resumedVisualConceptsRef.current = true;
    if (!structured || !script || !situation || visualConcepts.length === 0) return;
    visualConcepts
      .filter((c) => c.status === "pending" || c.status === "generating")
      .forEach((c) => {
        void renderOneVisualConcept(c, structured, script, situation, "");
      });
    // Deliberately mount-only — see resumedVisualConceptsRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
  // Autosave — same debounced-signature pattern as PipelineApp.tsx, minus
  // project auto-creation (the project already exists by the time this
  // component mounts) and, crucially, minus setActiveProject — a Hook
  // Studio session must never become the thing "/" tries to resume into.
  // ---------------------------------------------------------------------

  const lastSavedSignatureRef = useRef<string>("");
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const buildSnapshot = useCallback(
    (): Record<string, unknown> => ({
      selectedHookText,
      phase,
      productInput,
      category,
      structured,
      referenceMaterials,
      sourceUrlRawText,
      contentType,
      selectedFormat,
      formatDescription,
      scriptTone,
      scriptLanguage,
      customLanguage,
      targetDuration,
      script,
      scriptAssetId,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      staticImages,
    }),
    [
      selectedHookText,
      phase,
      productInput,
      category,
      structured,
      referenceMaterials,
      sourceUrlRawText,
      contentType,
      selectedFormat,
      formatDescription,
      scriptTone,
      scriptLanguage,
      customLanguage,
      targetDuration,
      script,
      scriptAssetId,
      scriptHistory,
      scriptHistoryIndex,
      visualConcepts,
      visualAssetIdByConceptId,
      staticImages,
    ]
  );

  async function flushSave() {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const signature = JSON.stringify(buildSnapshot());
    if (signature === lastSavedSignatureRef.current) return;
    setSaveStatus("saving");
    try {
      await savePipelineState(projectId, {
        pipeline_state: buildSnapshot(),
        pipeline_stage: "hook_studio",
        name: structured?.product_name || undefined,
        product_category: category || undefined,
      });
      lastSavedSignatureRef.current = signature;
      setSaveStatus("saved");
    } catch {
      setSaveStatus("error");
    }
  }

  useEffect(() => {
    const signature = JSON.stringify(buildSnapshot());
    if (signature === lastSavedSignatureRef.current) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void flushSave();
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildSnapshot]);

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
  }, [buildSnapshot]);

  // ---------------------------------------------------------------------
  // Product phase
  // ---------------------------------------------------------------------

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
      setReferenceMaterials((prev) => prev.map((m) => (m.id === tempId ? { ...m, analysis: "failed", note: message } : m)));
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
      pushActivity(result.analysis === "analyzed" ? `Understood ${url} ✓` : `Couldn't read ${url}`, result.analysis === "analyzed" ? "success" : "error");
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't fetch that link.";
      setReferenceMaterials((prev) => prev.map((m) => (m.id === tempId ? { ...m, analysis: "failed", note: message } : m)));
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

  function handleContinueFromProduct() {
    if (!structured) return;
    setPhase("content_type");
  }

  function handleCatalogSelect(productName: string, categoryLabel: string) {
    setCatalogSelection({ productName, category: categoryLabel });
  }

  // ---------------------------------------------------------------------
  // Content type / Format phases
  // ---------------------------------------------------------------------

  function handleSelectContentType(type: ContentType) {
    setContentType(type);
    setPhase("format");
  }

  function handleContentTypeBack() {
    setPhase("product");
  }

  function handleFormatBack() {
    setPhase("content_type");
  }

  async function handleGenerateFromFormat(selection: { format: string; formatDescription: string; tone: string }) {
    if (!structured || !situation) return;
    setFormatGenerating(true);
    setGlobalError(null);
    try {
      const result = await generateScript({
        structured_product: structured,
        selected_situation: situation,
        product_category: category,
        creative_angle: "",
        script_language: scriptLanguage,
        custom_language: scriptLanguage === "custom" ? customLanguage : undefined,
        target_duration: targetDuration,
        selected_hook_text: selectedHookText || undefined,
        content_type: contentType,
        format: selection.format,
        format_description: selection.formatDescription,
        tone: selection.tone,
      });
      setScript(result);
      setSelectedFormat(selection.format);
      setFormatDescription(selection.formatDescription);
      setScriptTone(selection.tone);
      resetScriptHistory(result, "Generated");
      setScriptAssetId(null);
      createAsset({
        project_id: projectId,
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
            summary: `Generated script — ${structured.product_name}`,
            project_id: projectId,
            asset_id: asset.id,
          }).catch(() => {});
        })
        .catch(() => {});
      if (contentType === "video") {
        setStaticImages({});
        void generateVisualConcepts(structured, result, situation, "");
      } else {
        setVisualConcepts([]);
        generateStaticVisuals(result, selection.format);
      }
      setPhase("script");
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Script generation failed.");
    } finally {
      setFormatGenerating(false);
    }
  }

  function handleChangeFormat() {
    setPhase("format");
  }

  // ---------------------------------------------------------------------
  // Script phase
  // ---------------------------------------------------------------------

  async function handleRegenerateScope(scope: ScriptRegenerateScope, options?: RegenerateOptions) {
    if (!structured || !situation || !script) return;
    if (scope === "full" && !options?.customInstruction && !options?.targetWordCount) {
      setScriptRegenLoading(true);
      setGlobalError(null);
      try {
        const result = await generateScript({
          structured_product: structured,
          selected_situation: situation,
          product_category: category,
          creative_angle: "",
          script_language: scriptLanguage,
          custom_language: scriptLanguage === "custom" ? customLanguage : undefined,
          target_duration: targetDuration,
          selected_hook_text: selectedHookText || undefined,
          content_type: contentType,
          format: selectedFormat,
          format_description: formatDescription,
          tone: scriptTone,
        });
        setScript(result);
        resetScriptHistory(result, "Regenerated");
        setStaticImages({});
        setVisualConcepts([]);
        if (contentType === "video") void generateVisualConcepts(structured, result, situation, "");
        else generateStaticVisuals(result, selectedFormat);
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Couldn't regenerate the script.", "danger");
      } finally {
        setScriptRegenLoading(false);
      }
      return;
    }
    setScriptRegenLoading(true);
    setGlobalError(null);
    const before = script;
    try {
      const result = await regenerateScriptSection({
        structured_product: structured,
        selected_situation: situation,
        product_category: category,
        creative_angle: "",
        script_language: scriptLanguage,
        custom_language: scriptLanguage === "custom" ? customLanguage : undefined,
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
      if (scriptAssetId) {
        void updateAsset(scriptAssetId, { content_json: result as unknown as Record<string, unknown> }).catch(() => {});
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
      creative_angle: "",
      instruction,
      selection,
    });
  }

  function handleApplyPatch(patch: ApplyPatch) {
    if (!script) return;
    let next: GeneratedScript;
    if (patch.kind === "full") {
      next = patch.script;
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

  function handleSelectHook(hook: Hook) {
    setSelectedHookText(hook.text);
    setHookPickerOpen(false);
    void markHookUsed(hook.id).catch(() => {});
    void logHistoryEvent({ event_type: "used_hook", summary: `Used hook — "${hook.text}"`, project_id: projectId }).catch(() => {});
    showToast("Hook selected — used on the next script generation", "success");
  }

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => router.push("/hooks")}
          className="text-[12.5px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Hooks Library
        </button>
        <PipelineSubHeader saveStatus={saveStatus} />
      </div>

      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Hook Studio</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">Create a high-quality script from your selected hook.</p>
      </div>

      <HookPickerModal open={hookPickerOpen} onClose={() => setHookPickerOpen(false)} onSelect={handleSelectHook} />

      {selectedHookText && (
        <HookBanner text={selectedHookText} onChangeText={setSelectedHookText} onChooseHook={() => setHookPickerOpen(true)} />
      )}

      {globalError && (
        <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
          {globalError}
        </div>
      )}

      {phase === "product" && (
        <div className="space-y-6">
          <ProductCatalogPicker onSelect={handleCatalogSelect} />
          <ProductWorkspaceStep
            key={`${catalogSelection.category}::${catalogSelection.productName}`}
            onSubmit={handleInputSubmit}
            inputLoading={inputLoading}
            inputError={inputError}
            structured={structured}
            onImproveDescription={handleImproveDescription}
            improvingDescription={improvingDescription}
            onContinue={handleContinueFromProduct}
            continueLoading={false}
            referenceMaterials={referenceMaterials}
            uploadingMaterialIds={uploadingMaterialIds}
            onAddReferenceFiles={handleAddReferenceFiles}
            onAddReferenceUrl={handleAddReferenceUrl}
            onRemoveReferenceMaterial={handleRemoveReferenceMaterial}
            sourceUrlRawText={sourceUrlRawText}
            onSourceUrlRawTextChange={setSourceUrlRawText}
            activityLog={activityLog}
            onActivity={pushActivity}
            initialProductName={catalogSelection.productName}
            initialCategory={catalogSelection.category}
            continueLabel="Continue"
          />
        </div>
      )}

      {phase === "content_type" && situation && (
        <ContentTypeStep situation={situation} angle="" onSelect={handleSelectContentType} onBack={handleContentTypeBack} />
      )}

      {phase === "format" && situation && (
        <div className="space-y-4">
          <FormatStep
            situation={situation}
            angle=""
            contentType={contentType}
            targetDuration={targetDuration}
            onTargetDurationChange={setTargetDuration}
            onBack={handleFormatBack}
            onGenerate={handleGenerateFromFormat}
            generating={formatGenerating}
          />
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="mb-2 text-[12px] font-medium text-[var(--muted)]">Script Language</p>
            <LanguageSelector value={scriptLanguage} onChange={setScriptLanguage} options={HOOK_STUDIO_LANGUAGE_OPTIONS} />
            {scriptLanguage === "custom" && (
              <input
                value={customLanguage}
                onChange={(e) => setCustomLanguage(e.target.value)}
                placeholder="Name the language (e.g. Punjabi, Odia)"
                className="mt-2.5 w-full max-w-xs rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-2 text-[13px] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
              />
            )}
          </div>
        </div>
      )}

      {phase === "script" && script && situation && (
        <div className="space-y-6">
          <ScriptStep
            script={script}
            situation={situation}
            creativeAngle=""
            scriptLanguage={scriptLanguage}
            onScriptLanguageChange={setScriptLanguage}
            targetDuration={targetDuration}
            onTargetDurationChange={setTargetDuration}
            onRegenerateScope={handleRegenerateScope}
            onBack={handleChangeFormat}
            regenerating={scriptRegenLoading}
            selectedHookText={selectedHookText}
            onChooseHook={() => setHookPickerOpen(true)}
            onChangeFormat={handleChangeFormat}
            staticImages={staticImages}
            onGenerateStaticImage={retryStaticImage}
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
            history={scriptHistory}
            historyIndex={scriptHistoryIndex}
            onUndo={handleUndoScript}
            onRedo={handleRedoScript}
            onRestoreVersion={handleRestoreScriptVersion}
            showsPipelineStages={false}
          />

          {(script.content_type ?? "video") === "video" && (
            <VisualConceptsSection
              concepts={visualConcepts}
              loading={visualConceptsLoading}
              error={visualConceptsError}
              scoring={visualConceptScoring}
              regenerating={visualConceptRegenLoading}
              downloading={visualConceptDownloading}
              onRegenerate={(id, variationStyle) => regenerateVisualConcept(id, variationStyle, sceneContext)}
              onGenerateVariation={(id, variationStyle) => generateVisualVariation(id, variationStyle, sceneContext)}
              onEditPrompt={(id, patch) => editVisualConceptPrompt(id, patch, sceneContext)}
              onDownload={downloadVisualConcept}
              onToggleFavorite={toggleFavoriteVisualConcept}
              onRetry={() => retryVisualConcepts(sceneContext)}
              onRetryOne={(id) => retryOneVisualConcept(id, sceneContext)}
            />
          )}
        </div>
      )}
    </div>
  );
}
