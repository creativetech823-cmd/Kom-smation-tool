"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { ToastHost, type ToastState, type ToastTone } from "@/components/ui/Toast";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { ProductWorkspaceStep } from "@/components/steps/ProductWorkspaceStep";
import { StorySituationStep } from "@/components/steps/StorySituationStep";
import { ScriptStep } from "@/components/steps/ScriptStep";
import { ComplianceStep } from "@/components/steps/ComplianceStep";
import { AssetsStep } from "@/components/steps/AssetsStep";
import { VoiceoverStep } from "@/components/steps/VoiceoverStep";
import { RenderStep } from "@/components/steps/RenderStep";
import {
  ApiError,
  audioFileUrl,
  auditCompliance,
  generateMotion,
  generateScript,
  generateStorySituations,
  generateVoiceover,
  motionFileUrl,
  renderFileUrl,
  renderVideo,
  rewriteLine,
  sourceAsset,
  structureProduct,
} from "@/lib/api";
import {
  flattenScript,
  type ComplianceResult,
  type GeneratedScript,
  type MotionGenerationResult,
  type ProductInput,
  type RenderResult,
  type RewriteDirective,
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
  script: GeneratedScript | null;
  compliance: ComplianceResult | null;
};

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
  const [situations, setSituations] = useState<StorySituation[]>([]);
  const [selectedSituation, setSelectedSituation] = useState<StorySituation | null>(null);
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
  const [situationSelectingId, setSituationSelectingId] = useState<string | null>(null);
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
      script,
      compliance,
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
      setScript(draft.script);
      setCompliance(draft.compliance);
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
    async (situation: StorySituation, setLoading: (v: boolean) => void) => {
      if (!structured) return;
      setLoading(true);
      setGlobalError(null);
      try {
        const result = await generateScript({
          structured_product: structured,
          selected_situation: situation,
          product_category: category,
        });
        setScript(result);
        setSelectedSituation(situation);
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
    [structured, category]
  );

  async function handleSelectSituation(situation: StorySituation) {
    setSituationSelectingId(situation.id);
    await runScriptGeneration(situation, () => {});
    setSituationSelectingId(null);
    goTo(2);
  }

  async function handleRegenerateScript() {
    if (!selectedSituation) return;
    await runScriptGeneration(selectedSituation, setScriptRegenLoading);
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
    if (!selectedSituation) return;
    await runScriptGeneration(selectedSituation, setScriptRegenLoading);
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
                  />
                )}

                {stepIndex === 1 && (
                  <StorySituationStep
                    situations={situations}
                    loading={situationsLoading}
                    generatingMore={situationsGenMoreLoading}
                    selectingId={situationSelectingId}
                    onSelect={handleSelectSituation}
                    onGenerateMore={handleGenerateMoreSituations}
                    onBack={() => goTo(0)}
                  />
                )}

                {stepIndex === 2 && script && selectedSituation && (
                  <ScriptStep
                    script={script}
                    situation={selectedSituation}
                    onRegenerate={handleRegenerateScript}
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
