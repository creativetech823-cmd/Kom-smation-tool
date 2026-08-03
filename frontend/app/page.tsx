"use client";

import { useCallback, useState } from "react";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { InputStep } from "@/components/steps/InputStep";
import { StructureStep } from "@/components/steps/StructureStep";
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
  generateVoiceover,
  motionFileUrl,
  renderFileUrl,
  renderVideo,
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
  type SelectedAsset,
  type StructuredProduct,
  type VoiceoverResult,
} from "@/lib/types";

const STEPS: Step[] = [
  { key: "input", label: "Input" },
  { key: "structure", label: "Structure" },
  { key: "script", label: "Script" },
  { key: "compliance", label: "Compliance" },
  { key: "assets", label: "Assets" },
  { key: "voiceover", label: "Voiceover" },
  { key: "render", label: "Render" },
];

export default function Home() {
  const [stepIndex, setStepIndex] = useState(0);
  const [furthest, setFurthest] = useState(0);

  const [productInput, setProductInput] = useState<ProductInput | null>(null);
  const [category, setCategory] = useState("");
  const [structured, setStructured] = useState<StructuredProduct | null>(null);
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
  const [scriptLoading, setScriptLoading] = useState(false);
  const [scriptRegenLoading, setScriptRegenLoading] = useState(false);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [assetsContinueLoading, setAssetsContinueLoading] = useState(false);
  const [voiceoverContinueLoading, setVoiceoverContinueLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  function goTo(i: number) {
    setStepIndex(i);
    setFurthest((f) => Math.max(f, i));
  }

  async function handleInputSubmit(input: ProductInput, cat: string) {
    setInputLoading(true);
    setInputError(null);
    try {
      const result = await structureProduct(input);
      setProductInput(input);
      setCategory(cat);
      setStructured(result);
      goTo(1);
    } catch (e) {
      setInputError(e instanceof ApiError ? e.message : "Something went wrong structuring the product.");
    } finally {
      setInputLoading(false);
    }
  }

  const runScriptGeneration = useCallback(
    async (setLoading: (v: boolean) => void) => {
      if (!structured) return;
      setLoading(true);
      setGlobalError(null);
      try {
        const result = await generateScript({
          structured_product: structured,
          product_category: category,
        });
        setScript(result);
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

  async function handleGenerateScript() {
    await runScriptGeneration(setScriptLoading);
    goTo(2);
  }

  async function handleRegenerateScript() {
    await runScriptGeneration(setScriptRegenLoading);
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
    await runScriptGeneration(setScriptRegenLoading);
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
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] text-white shadow-lg shadow-[var(--accent)]/20">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2l1.8 5.6L19 9.5l-5.2 1.9L12 17l-1.8-5.6L5 9.5l5.2-1.9L12 2z" fill="white" />
            </svg>
          </div>
          <div>
            <h1 className="text-[16px] font-semibold tracking-tight">Content Factory</h1>
            <p className="text-[12px] text-[var(--muted)]">Human-in-the-loop pipeline review</p>
          </div>
        </div>
        <div className="overflow-x-auto pb-1">
          <Stepper steps={STEPS} activeIndex={stepIndex} furthestIndex={furthest} />
        </div>
      </header>

      {globalError && (
        <div className="rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-3 text-[13px] text-[var(--danger)]">
          {globalError}
        </div>
      )}

      <main>
        {stepIndex === 0 && (
          <InputStep onSubmit={handleInputSubmit} loading={inputLoading} error={inputError} />
        )}

        {stepIndex === 1 && structured && (
          <StructureStep
            data={structured}
            onContinue={handleGenerateScript}
            onBack={() => goTo(0)}
            loading={scriptLoading}
          />
        )}

        {stepIndex === 2 && script && (
          <ScriptStep
            script={script}
            onRegenerate={handleRegenerateScript}
            onContinue={handleRunCompliance}
            onBack={() => goTo(1)}
            regenerating={scriptRegenLoading}
            continuing={complianceLoading}
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
      </main>
    </div>
  );
}
