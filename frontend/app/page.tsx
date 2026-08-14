"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { Button } from "@/components/ui/Button";
import { ToastHost, type ToastState, type ToastTone } from "@/components/ui/Toast";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
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
  downloadVisualConcept,
  generateAlternatives,
  generateMotion,
  generateScript,
  generateStorySituations,
  generateVisualConcepts,
  generateVoiceover,
  getScriptSuggestions,
  motionFileUrl,
  regenerateScriptSection,
  regenerateVisualConcept,
  renderFileUrl,
  renderVideo,
  rewriteLine,
  scoreVisualConcept,
  sourceAsset,
  structureProduct,
  uploadReferenceMaterial,
} from "@/lib/api";
import type { ScriptVersion } from "@/components/ui/VersionHistoryPanel";
import type { RegenerateOptions } from "@/components/steps/ScriptStep";
import {
  flattenScript,
  type ComplianceResult,
  type GeneratedScript,
  type MotionGenerationResult,
  type ProductInput,
  type ReferenceKind,
  type ReferenceMaterial,
  type RenderResult,
  type RewriteDirective,
  type ScriptLanguage,
  type ScriptLine,
  type ScriptRegenerateScope,
  type ScriptSuggestion,
  type SelectedAsset,
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

const DRAFT_KEY = "content-factory:draft:v1";

type Draft = {
  savedAt: string;
  stepIndex: number;
  furthest: number;
  productInput: ProductInput | null;
  category: string;
  structured: StructuredProduct | null;
  situations: StorySituation[];
  selectedSituation: StorySituation | null;
  selectedAngle: string | null;
  scriptLanguage: ScriptLanguage;
  targetDuration: string;
  script: GeneratedScript | null;
  compliance: ComplianceResult | null;
  referenceMaterials: ReferenceMaterial[];
  sourceUrlRawText: string | undefined;
};

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

export default function Home() {
  const [stepIndex, setStepIndex] = useState(0);
  const [furthest, setFurthest] = useState(0);

  const [productInput, setProductInput] = useState<ProductInput | null>(null);
  const [category, setCategory] = useState("");
  const [structured, setStructured] = useState<StructuredProduct | null>(null);
  const [referenceMaterials, setReferenceMaterials] = useState<ReferenceMaterial[]>([]);
  const [uploadingMaterialIds, setUploadingMaterialIds] = useState<Set<string>>(new Set());
  const [sourceUrlRawText, setSourceUrlRawText] = useState<string | undefined>(undefined);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [situations, setSituations] = useState<StorySituation[]>([]);
  const [selectedSituation, setSelectedSituation] = useState<StorySituation | null>(null);
  const [selectedAngle, setSelectedAngle] = useState<string | null>(null);
  const [scriptLanguage, setScriptLanguage] = useState<ScriptLanguage>("english");
  const [targetDuration, setTargetDuration] = useState("30s");
  const [script, setScript] = useState<GeneratedScript | null>(null);
  const [visualConcepts, setVisualConcepts] = useState<VisualConcept[]>([]);
  const [visualConceptsLoading, setVisualConceptsLoading] = useState(false);
  const [visualConceptsError, setVisualConceptsError] = useState<string | null>(null);
  const [visualConceptScoring, setVisualConceptScoring] = useState<Record<string, boolean>>({});
  const [visualConceptRegenLoading, setVisualConceptRegenLoading] = useState<Record<string, boolean>>({});
  const [visualConceptDownloading, setVisualConceptDownloading] = useState<Record<string, boolean>>({});
  const [compliance, setCompliance] = useState<ComplianceResult | null>(null);
  const [assets, setAssets] = useState<Record<string, SelectedAsset | undefined>>({});
  const [loadingAssetIds, setLoadingAssetIds] = useState<Set<string>>(new Set());
  const [motions, setMotions] = useState<Record<string, MotionGenerationResult | undefined>>({});
  const [loadingMotionIds, setLoadingMotionIds] = useState<Set<string>>(new Set());
  const [voiceovers, setVoiceovers] = useState<Record<string, VoiceoverResult | undefined>>({});
  const [loadingVoiceoverIds, setLoadingVoiceoverIds] = useState<Set<string>>(new Set());
  const [renderResult, setRenderResult] = useState<RenderResult | null>(null);
  const [approved, setApproved] = useState(false);

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
  const [scriptHistory, setScriptHistory] = useState<ScriptVersion[]>([]);
  const [scriptHistoryIndex, setScriptHistoryIndex] = useState(-1);
  const historyIndexRef = useRef(-1);
  const [recentlyChangedLineIds, setRecentlyChangedLineIds] = useState<Set<string>>(new Set());
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [assetsContinueLoading, setAssetsContinueLoading] = useState(false);
  const [voiceoverContinueLoading, setVoiceoverContinueLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [toast, setToast] = useState<ToastState>(null);
  const [draftAvailable, setDraftAvailable] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    // Deferred to after mount, not a lazy useState initializer: the server has no
    // access to localStorage, so reading it during the initial client render would
    // mismatch the server-rendered HTML and trigger a hydration error.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraftAvailable(window.localStorage.getItem(DRAFT_KEY) !== null);
  }, []);

  const showToast = useCallback((message: string, tone: ToastTone = "neutral") => {
    setToast({ message, tone });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2600);
  }, []);

  function goTo(i: number) {
    setStepIndex(i);
    setFurthest((f) => Math.max(f, i));
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

  function handleSaveDraft() {
    const draft: Draft = {
      savedAt: new Date().toISOString(),
      stepIndex,
      furthest,
      productInput,
      category,
      structured,
      situations,
      selectedSituation,
      selectedAngle,
      scriptLanguage,
      targetDuration,
      script,
      compliance,
      referenceMaterials,
      sourceUrlRawText,
    };
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    setDraftAvailable(true);
    showToast("Draft saved", "success");
  }

  function handleRestoreDraft() {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    try {
      const draft: Draft = JSON.parse(raw);
      setStepIndex(draft.stepIndex);
      setFurthest(draft.furthest);
      setProductInput(draft.productInput);
      setCategory(draft.category);
      setStructured(draft.structured);
      setSituations(draft.situations);
      setSelectedSituation(draft.selectedSituation);
      setSelectedAngle(draft.selectedAngle ?? null);
      setScriptLanguage(draft.scriptLanguage ?? "english");
      setTargetDuration(draft.targetDuration ?? "");
      setScript(draft.script);
      setCompliance(draft.compliance);
      setReferenceMaterials(draft.referenceMaterials ?? []);
      setSourceUrlRawText(draft.sourceUrlRawText);
      showToast("Draft restored — Assets/Voiceover/Render will need re-running", "success");
    } catch {
      showToast("Couldn't restore that draft.", "danger");
    }
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
      });
      setSituations((prev) => [...prev, ...more]);
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Couldn't generate more situations.");
    } finally {
      setSituationsGenMoreLoading(false);
    }
  }

  async function handleGenerateVisualConcepts(
    structuredProduct: StructuredProduct,
    generatedScript: GeneratedScript,
    situation: StorySituation,
    angle: string
  ) {
    setVisualConcepts([]);
    setVisualConceptsError(null);
    setVisualConceptsLoading(true);
    try {
      const concepts = await generateVisualConcepts({
        structured_product: structuredProduct,
        script: generatedScript,
        situation,
        creative_angle: angle,
        product_category: category,
      });
      setVisualConcepts(concepts);
      // Score each concept in the background — cards show a skeleton until each resolves.
      concepts.forEach((concept) => {
        setVisualConceptScoring((prev) => ({ ...prev, [concept.id]: true }));
        scoreVisualConcept({ concept })
          .then((scores) => {
            setVisualConcepts((prev) => prev.map((c) => (c.id === concept.id ? { ...c, scores } : c)));
          })
          .catch(() => {})
          .finally(() => {
            setVisualConceptScoring((prev) => ({ ...prev, [concept.id]: false }));
          });
      });
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Couldn't generate visual concepts.";
      setVisualConceptsError(message);
      showToast(message, "danger");
    } finally {
      setVisualConceptsLoading(false);
    }
  }

  function handleRetryVisualConcepts() {
    if (!structured || !script || !selectedSituation) return;
    void handleGenerateVisualConcepts(structured, script, selectedSituation, selectedAngle ?? "");
  }

  const runScriptGeneration = useCallback(
    async (situation: StorySituation, angle: string, setLoading: (v: boolean) => void) => {
      if (!structured) return;
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
        void handleGenerateVisualConcepts(structured, result, situation, angle);
      } catch (e) {
        setGlobalError(e instanceof ApiError ? e.message : "Script generation failed.");
      } finally {
        setLoading(false);
      }
    },
    [structured, category, scriptLanguage, targetDuration]
  );

  async function handleSelectAngle(situation: StorySituation, angle: string) {
    setSituationSelectingKey({ situationId: situation.id, angle });
    await runScriptGeneration(situation, angle, () => {});
    setSituationSelectingKey(null);
    goTo(2);
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

  async function handleFetchScriptSuggestions(): Promise<ScriptSuggestion[]> {
    if (!script) return [];
    try {
      const result = await getScriptSuggestions({ script, target_duration: targetDuration || script.target_duration });
      return result.suggestions;
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't get suggestions.", "danger");
      return [];
    }
  }

  function handleApplySuggestion(s: ScriptSuggestion) {
    if (!s.suggested_scope) return;
    void handleRegenerateScope(s.suggested_scope, { customInstruction: s.message });
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
    const editedConcept: VisualConcept = { ...concept, prompt: patch.prompt, style_params: patch.style_params };
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
    setVisualConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, favorite: !c.favorite } : c)));
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
    await runScriptGeneration(selectedSituation, selectedAngle, setScriptRegenLoading);
    goTo(2);
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

  const fetchVoiceoverForLine = useCallback(async (id: string, text: string) => {
    setLoadingVoiceoverIds((prev) => new Set(prev).add(id));
    try {
      const [result] = await generateVoiceover({ lines: [{ line_id: id, text }] });
      setVoiceovers((prev) => ({ ...prev, [id]: result }));
    } catch {
      setGlobalError("Voiceover generation failed for one line — try regenerating it.");
    } finally {
      setLoadingVoiceoverIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

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
    } catch (e) {
      setGlobalError(e instanceof ApiError ? e.message : "Render failed.");
    } finally {
      setRendering(false);
    }
  }

  const scriptLines = script ? flattenScript(script) : [];

  return (
    <div className="flex min-h-screen">
      <Sidebar onToast={(m) => showToast(m)} />

      <div className="flex min-h-screen flex-1 flex-col">
        <TopBar onSaveDraft={handleSaveDraft} draftAvailable={draftAvailable} onRestoreDraft={handleRestoreDraft} />

        <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-8 px-6 py-10 lg:px-10 xl:px-12">
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
                      onEditLine={handleEditLine}
                      onEditLineField={handleEditLineField}
                      onEditWholeScript={handleEditWholeScript}
                      onApplyDirective={handleApplyDirectiveToLine}
                      onGenerateAlternatives={handleGenerateAlternativesForLine}
                      onSelectAlternative={handleSelectAlternativeForLine}
                      onTranslateLine={handleTranslateLine}
                      lineLoading={lineLoading}
                      recentlyChangedLineIds={recentlyChangedLineIds}
                      onFetchSuggestions={handleFetchScriptSuggestions}
                      onApplySuggestion={handleApplySuggestion}
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
      </div>

      <ToastHost toast={toast} />
    </div>
  );
}
