"use client";

import { useEffect, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { VisualConceptCard } from "@/components/ui/VisualConceptCard";
import { EditVisualPromptModal } from "@/components/ui/EditVisualPromptModal";
import { Lightbox } from "@/components/ui/Lightbox";
import { ApiError, getVisualConceptDebugInfo, testVisualConceptImage, visualFileUrl } from "@/lib/api";
import type { VisualConcept, VisualConceptDebugInfo, VisualConceptStyleParams, VisualVariationStyle } from "@/lib/types";

const LOADING_STAGES = [
  "Preparing Prompt…",
  "Understanding Story…",
  "Generating Concept 1…",
  "Generating Concept 2…",
  "Generating Concept 3…",
  "Upscaling…",
  "Done",
];

export function VisualConceptsSection({
  concepts,
  loading,
  error,
  scoring,
  regenerating,
  downloading,
  onRegenerate,
  onGenerateVariation,
  onEditPrompt,
  onDownload,
  onToggleFavorite,
  onRetry,
}: {
  concepts: VisualConcept[];
  loading: boolean;
  error: string | null;
  scoring: Record<string, boolean>;
  regenerating: Record<string, boolean>;
  downloading: Record<string, boolean>;
  onRegenerate: (id: string, variationStyle?: VisualVariationStyle) => void;
  onGenerateVariation: (id: string, variationStyle: "generate_similar" | "different_angle") => void;
  onEditPrompt: (id: string, patch: { prompt: string; style_params: VisualConceptStyleParams }) => void;
  onDownload: (id: string, format: "png" | "jpeg" | "webp") => void;
  onToggleFavorite: (id: string) => void;
  onRetry: () => void;
}) {
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [testState, setTestState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [testImagePath, setTestImagePath] = useState<string | null>(null);
  const [testMeta, setTestMeta] = useState<{ used_model: string; elapsed_seconds: number } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<VisualConceptDebugInfo | null>(null);
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugLoading, setDebugLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [prevLoading, setPrevLoading] = useState(loading);
  if (loading !== prevLoading) {
    setPrevLoading(loading);
    if (loading) setLoadingStage(0);
  }

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setLoadingStage((s) => (s < LOADING_STAGES.length - 2 ? s + 1 : s));
    }, 2500);
    return () => clearInterval(interval);
  }, [loading]);

  const viewingConcept = concepts.find((c) => c.id === viewingId);
  const editingConcept = concepts.find((c) => c.id === editingId);

  async function handleTestImage() {
    setTestState("loading");
    setTestError(null);
    try {
      const result = await testVisualConceptImage();
      setTestImagePath(result.image_path);
      setTestMeta({ used_model: result.used_model, elapsed_seconds: result.elapsed_seconds });
      setTestState("success");
    } catch (e) {
      setTestError(e instanceof ApiError ? e.message : "Test generation failed.");
      setTestState("error");
    }
  }

  async function handleToggleDebug() {
    const next = !debugOpen;
    setDebugOpen(next);
    if (next && !debugInfo) {
      setDebugLoading(true);
      try {
        setDebugInfo(await getVisualConceptDebugInfo());
      } catch {
        // Debug panel is best-effort — a failed fetch just leaves it empty.
      } finally {
        setDebugLoading(false);
      }
    }
  }

  return (
    <Card glow>
      <CardHeader
        title="AI Visual Concepts"
        subtitle="3 premium storyboard stills generated from your script — hook, emotional turn, and transformation."
        icon={<IconImage />}
        right={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleToggleDebug}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] hover:bg-white/[0.06]"
              title="Config + connectivity diagnostics"
            >
              🔧 Debug Info
            </button>
            <button
              type="button"
              onClick={handleTestImage}
              disabled={testState === "loading"}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--foreground)] hover:bg-white/[0.06] disabled:opacity-50"
              title="Isolates whether a failure is in the image pipeline itself"
            >
              {testState === "loading" ? (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-[var(--accent)]" />
              ) : (
                "🧪"
              )}
              Test Image Generation
            </button>
          </div>
        }
      />
      <CardBody className="space-y-4">
        {debugOpen && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/50 px-3.5 py-3 text-[12px] sm:grid-cols-3">
            {debugLoading || !debugInfo ? (
              <p className="col-span-full text-[var(--muted)]">{debugLoading ? "Loading debug info…" : "Debug info unavailable."}</p>
            ) : (
              <>
                <DebugField label="API Key Loaded" value={debugInfo.api_key_loaded ? "YES" : "NO"} good={debugInfo.api_key_loaded} />
                <DebugField label="Model" value={debugInfo.model} />
                <DebugField label="API URL" value={debugInfo.api_url} />
                <DebugField label="Internet Access" value={debugInfo.internet_access ? "OK" : "UNREACHABLE"} good={debugInfo.internet_access} />
              </>
            )}
          </div>
        )}

        {testState !== "idle" && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/50 px-3.5 py-3">
            {testState === "loading" && <p className="text-[12px] text-[var(--muted)]">Generating test image…</p>}
            {testState === "success" && testImagePath && (
              <div className="flex items-center gap-3">
                <img src={visualFileUrl(testImagePath)} alt="Test render" className="h-20 w-20 rounded-lg object-cover" />
                <div>
                  <p className="text-[12px] text-[var(--success)]">
                    ✅ Test image generated successfully — the Gemini pipeline is working.
                  </p>
                  {testMeta && (
                    <p className="mt-0.5 text-[11px] text-[var(--muted)]">
                      Model: {testMeta.used_model} · Generation time: {testMeta.elapsed_seconds}s
                    </p>
                  )}
                </div>
              </div>
            )}
            {testState === "error" && <p className="text-[12px] text-[var(--danger)]">❌ Test failed: {testError}</p>}
          </div>
        )}

        {error && concepts.length === 0 && !loading ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-10 text-center">
            <p className="text-[13.5px] font-medium text-[var(--foreground)]">Failed to generate images.</p>
            <p className="max-w-md text-[12px] text-[var(--muted)]">Reason: {error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-[12.5px] font-medium text-white hover:brightness-110"
            >
              ↻ Retry
            </button>
          </div>
        ) : loading && concepts.length === 0 ? (
          <div className="space-y-3">
            <p className="flex items-center gap-2 text-[12.5px] text-[var(--muted)]">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/20 border-t-[var(--accent)]" />
              {LOADING_STAGES[loadingStage]}
            </p>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-shimmer aspect-[9/16] w-full rounded-2xl" />
              ))}
            </div>
          </div>
        ) : concepts.length > 0 ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {concepts.map((concept) => (
              <VisualConceptCard
                key={concept.id}
                concept={concept}
                regenerating={Boolean(regenerating[concept.id])}
                scoring={Boolean(scoring[concept.id])}
                downloading={Boolean(downloading[concept.id])}
                onView={() => setViewingId(concept.id)}
                onDownload={(format) => onDownload(concept.id, format)}
                onEditPrompt={() => setEditingId(concept.id)}
                onRegenerate={(variationStyle) => onRegenerate(concept.id, variationStyle)}
                onGenerateVariation={(variationStyle) => onGenerateVariation(concept.id, variationStyle)}
                onToggleFavorite={() => onToggleFavorite(concept.id)}
              />
            ))}
          </div>
        ) : null}
      </CardBody>

      {viewingConcept && (
        <Lightbox src={visualFileUrl(viewingConcept.image_path)} alt={viewingConcept.scene_title} onClose={() => setViewingId(null)} />
      )}

      {editingConcept && (
        <EditVisualPromptModal
          concept={editingConcept}
          loading={Boolean(regenerating[editingConcept.id])}
          onRegenerate={(patch) => {
            onEditPrompt(editingConcept.id, patch);
            setEditingId(null);
          }}
          onClose={() => setEditingId(null)}
        />
      )}
    </Card>
  );
}

function DebugField({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="min-w-0">
      <span className="text-[var(--muted)]">{label}: </span>
      <span
        className={
          good === undefined ? "text-[var(--foreground)]" : good ? "font-medium text-[var(--success)]" : "font-medium text-[var(--danger)]"
        }
      >
        {value}
      </span>
    </div>
  );
}

function IconImage() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
      <path d="M21 15l-5-5L5 21" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}
