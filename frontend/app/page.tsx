"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { ToastHost, type ToastState, type ToastTone } from "@/components/ui/Toast";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { ProductWorkspaceStep } from "@/components/steps/ProductWorkspaceStep";
import type { ActivityEntry } from "@/components/steps/AiUnderstandingPanel";
import { StorySituationStep } from "@/components/steps/StorySituationStep";
import { ScriptStep } from "@/components/steps/ScriptStep";
import { ComplianceStep } from "@/components/steps/ComplianceStep";
import { AssetsStep } from "@/components/steps/AssetsStep";
import { VoiceoverStep } from "@/components/steps/VoiceoverStep";
import { RenderStep } from "@/components/steps/RenderStep";
import {
  addReferenceUrl,
  ApiError,
  audioFileUrl,
  auditCompliance,
  generateMotion,
  generateScript,
  generateStorySituations,
  generateVoiceover,
  motionFileUrl,
  regenerateScriptSection,
  renderFileUrl,
  renderVideo,
  rewriteLine,
  sourceAsset,
  structureProduct,
  uploadReferenceMaterial,
} from "@/lib/api";
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
  type ScriptRegenerateScope,
  type SelectedAsset,
  type StorySituation,
  type StructuredProduct,
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

function updateScriptLineText(s: GeneratedScript, lineId: string, text: string): GeneratedScript {
  if (lineId === "hook") return { ...s, hook: { ...s.hook, text } };
  if (lineId === "cta") return { ...s, cta: { ...s.cta, text } };
  const match = lineId.match(/^body_(\d+)$/);
  if (match) {
    const idx = Number(match[1]);
    return { ...s, body: s.body.map((line, i) => (i === idx ? { ...line, text } : line)) };
  }
  return s;
}

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
  const [targetDuration, setTargetDuration] = useState("");
  const [script, setScript] = useState<GeneratedScript | null>(null);
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
  const [rewriting, setRewriting] = useState<Record<string, RewriteDirective | undefined>>({});
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
        // Any previous assets/voiceovers/render are stale once the script changes.
        setAssets({});
        setVoiceovers({});
        setRenderResult(null);
        setApproved(false);
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

  async function handleRegenerateScope(scope: ScriptRegenerateScope) {
    if (!structured || !selectedSituation || !script) return;
    if (scope === "full") {
      await handleRegenerateScript();
      return;
    }
    setScriptRegenLoading(true);
    setGlobalError(null);
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
      });
      setScript(result);
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

  async function handleRewriteScriptLine(lineId: string, directive: RewriteDirective) {
    if (!script) return;
    const line = flattenScript(script).find((l) => l.id === lineId);
    if (!line) return;
    setRewriting((prev) => ({ ...prev, [lineId]: directive }));
    try {
      const result = await rewriteLine({ text: line.text, directive });
      setScript((prev) => (prev ? updateScriptLineText(prev, lineId, result.text) : prev));
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Rewrite failed for that line.", "danger");
    } finally {
      setRewriting((prev) => ({ ...prev, [lineId]: undefined }));
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
                  <ScriptStep
                    script={script}
                    situation={selectedSituation}
                    creativeAngle={selectedAngle ?? ""}
                    scriptLanguage={scriptLanguage}
                    onScriptLanguageChange={setScriptLanguage}
                    targetDuration={targetDuration}
                    onTargetDurationChange={setTargetDuration}
                    onRegenerateScope={handleRegenerateScope}
                    onContinue={handleRunCompliance}
                    onBack={() => goTo(1)}
                    regenerating={scriptRegenLoading}
                    continuing={complianceLoading}
                    onRewriteLine={handleRewriteScriptLine}
                    rewriting={rewriting}
                  />
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
