"use client";

// Shared scene-image generation orchestration — the "generate structured
// scenes -> image prompts -> images, shown scene by scene" machinery used by
// both the Content Pipeline's Assets step (PipelineApp.tsx) and Hook Studio.
// Extracted so both consumers reuse the exact same logic instead of forking
// it; each caller keeps owning its own persistence (autosave/restore) and
// just seeds this hook's initial state from whatever it restored.

import { useCallback, useRef, useState } from "react";
import {
  ApiError,
  createAsset,
  downloadVisualConcept,
  generateStaticVisual,
  logHistoryEvent,
  planVisualConcepts,
  regenerateVisualConcept,
  scoreVisualConcept,
  updateAsset,
} from "@/lib/api";
import { staticAspectRatio } from "@/lib/contentFormats";
import type { ToastTone } from "@/components/ui/Toast";
import {
  flattenScript,
  type GeneratedScript,
  type StaticImageState,
  type StorySituation,
  type StructuredProduct,
  type VisualConcept,
  type VisualConceptStyleParams,
  type VisualVariationStyle,
} from "@/lib/types";

export type SceneVisualsContext = {
  structuredProduct: StructuredProduct;
  script: GeneratedScript;
  situation: StorySituation;
  angle: string;
};

export function useSceneVisuals({
  projectId,
  productCategory,
  productName,
  format,
  showToast,
  initialVisualConcepts,
  initialStaticImages,
  initialVisualAssetIdByConceptId,
}: {
  projectId: string | null;
  productCategory: string;
  productName: string;
  format: string;
  showToast: (message: string, tone?: ToastTone) => void;
  initialVisualConcepts?: VisualConcept[];
  initialStaticImages?: Record<string, StaticImageState>;
  initialVisualAssetIdByConceptId?: Record<string, string>;
}) {
  const [visualConcepts, setVisualConcepts] = useState<VisualConcept[]>(() => initialVisualConcepts ?? []);
  const [staticImages, setStaticImages] = useState<Record<string, StaticImageState>>(
    () => initialStaticImages ?? {}
  );
  const [visualConceptsLoading, setVisualConceptsLoading] = useState(false);
  const [visualConceptsError, setVisualConceptsError] = useState<string | null>(null);
  const [visualConceptScoring, setVisualConceptScoring] = useState<Record<string, boolean>>({});
  const [visualConceptRegenLoading, setVisualConceptRegenLoading] = useState<Record<string, boolean>>({});
  const [visualConceptDownloading, setVisualConceptDownloading] = useState<Record<string, boolean>>({});
  const [visualAssetIdByConceptId, setVisualAssetIdByConceptId] = useState<Record<string, string>>(
    () => initialVisualAssetIdByConceptId ?? {}
  );

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
          project_id: projectId ?? undefined,
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
              project_id: projectId ?? undefined,
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
    [projectId]
  );

  const generateVisualConcepts = useCallback(
    async (
      structuredProduct: StructuredProduct,
      generatedScript: GeneratedScript,
      situation: StorySituation,
      angle: string
    ) => {
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
          product_category: productCategory,
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
    },
    [productCategory, showToast, renderOneVisualConcept]
  );

  const retryVisualConcepts = useCallback(
    (ctx: SceneVisualsContext | null) => {
      if (!ctx) return;
      void generateVisualConcepts(ctx.structuredProduct, ctx.script, ctx.situation, ctx.angle);
    },
    [generateVisualConcepts]
  );

  const retryOneVisualConcept = useCallback(
    (id: string, ctx: SceneVisualsContext | null) => {
      if (!ctx) return;
      const concept = visualConcepts.find((c) => c.id === id);
      if (!concept) return;
      void renderOneVisualConcept(concept, ctx.structuredProduct, ctx.script, ctx.situation, ctx.angle);
    },
    [visualConcepts, renderOneVisualConcept]
  );

  const handleRegenerateVisualConcept = useCallback(
    async (id: string, variationStyle: VisualVariationStyle | undefined, ctx: SceneVisualsContext | null) => {
      if (!ctx) return;
      const concept = visualConcepts.find((c) => c.id === id);
      if (!concept) return;
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
      try {
        const result = await regenerateVisualConcept({
          structured_product: ctx.structuredProduct,
          script: ctx.script,
          situation: ctx.situation,
          creative_angle: ctx.angle,
          concept,
          variation_style: variationStyle,
        });
        setVisualConcepts((prev) => prev.map((c) => (c.id === id ? result : c)));
        setVisualAssetIdByConceptId((prevIds) => {
          const regenAssetId = prevIds[id];
          if (regenAssetId) {
            void updateAsset(regenAssetId, {
              file_path: result.image_path,
              content_json: result as unknown as Record<string, unknown>,
            }).catch(() => {});
          }
          return prevIds;
        });
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
    },
    [visualConcepts, showToast]
  );

  const handleGenerateVisualVariation = useCallback(
    async (id: string, variationStyle: VisualVariationStyle, ctx: SceneVisualsContext | null) => {
      if (!ctx) return;
      const concept = visualConcepts.find((c) => c.id === id);
      if (!concept) return;
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
      try {
        const result = await regenerateVisualConcept({
          structured_product: ctx.structuredProduct,
          script: ctx.script,
          situation: ctx.situation,
          creative_angle: ctx.angle,
          concept,
          variation_style: variationStyle,
          as_new_variation: true,
        });
        setVisualConcepts((prev) => [...prev, result]);
        createAsset({
          project_id: projectId ?? undefined,
          asset_type: "image",
          title: result.scene_title,
          product_name: ctx.structuredProduct.product_name,
          file_path: result.image_path,
          model_used: result.used_model,
          content_json: result as unknown as Record<string, unknown>,
        })
          .then((asset) => {
            setVisualAssetIdByConceptId((prev) => ({ ...prev, [result.id]: asset.id }));
            void logHistoryEvent({
              event_type: "generated_image",
              summary: `Generated image variation — ${result.scene_title}`,
              project_id: projectId ?? undefined,
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
    },
    [visualConcepts, projectId, showToast]
  );

  const handleEditVisualConceptPrompt = useCallback(
    async (
      id: string,
      patch: { prompt: string; style_params: VisualConceptStyleParams },
      ctx: SceneVisualsContext | null
    ) => {
      if (!ctx) return;
      const concept = visualConcepts.find((c) => c.id === id);
      if (!concept) return;
      const editedConcept: VisualConcept = { ...concept, prompt: patch.prompt, style_params: patch.style_params };
      setVisualConcepts((prev) => prev.map((c) => (c.id === id ? editedConcept : c)));
      setVisualConceptRegenLoading((prev) => ({ ...prev, [id]: true }));
      try {
        const result = await regenerateVisualConcept({
          structured_product: ctx.structuredProduct,
          script: ctx.script,
          situation: ctx.situation,
          creative_angle: ctx.angle,
          concept: editedConcept,
          is_manual_edit: true,
        });
        setVisualConcepts((prev) => prev.map((c) => (c.id === id ? result : c)));
        setVisualAssetIdByConceptId((prevIds) => {
          const editAssetId = prevIds[id];
          if (editAssetId) {
            void updateAsset(editAssetId, {
              file_path: result.image_path,
              content_json: result as unknown as Record<string, unknown>,
            }).catch(() => {});
          }
          return prevIds;
        });
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
    },
    [visualConcepts, showToast]
  );

  const handleDownloadVisualConcept = useCallback(
    async (id: string, downloadFormat: "png" | "jpeg" | "webp") => {
      const concept = visualConcepts.find((c) => c.id === id);
      if (!concept) return;
      setVisualConceptDownloading((prev) => ({ ...prev, [id]: true }));
      try {
        const blob = await downloadVisualConcept({ concept, format: downloadFormat });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${concept.scene_title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-4k.${downloadFormat}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Download failed.", "danger");
      } finally {
        setVisualConceptDownloading((prev) => ({ ...prev, [id]: false }));
      }
    },
    [visualConcepts, showToast]
  );

  const handleToggleFavoriteVisualConcept = useCallback(
    (id: string) => {
      const concept = visualConcepts.find((c) => c.id === id);
      setVisualConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, favorite: !c.favorite } : c)));
      const favAssetId = visualAssetIdByConceptId[id];
      if (favAssetId) {
        void updateAsset(favAssetId, { is_favorite: !(concept?.favorite ?? false) }).catch(() => {});
      }
    },
    [visualConcepts, visualAssetIdByConceptId]
  );

  const generateOneStaticImage = useCallback(
    async (lineId: string, prompt: string, aspectRatio: string) => {
      setStaticImages((prev) => ({ ...prev, [lineId]: { status: "generating", imagePath: null, error: null } }));
      try {
        const result = await generateStaticVisual({ prompt, aspect_ratio: aspectRatio });
        setStaticImages((prev) => ({
          ...prev,
          [lineId]: { status: "completed", imagePath: result.image_path, error: null },
        }));
        createAsset({
          project_id: projectId ?? undefined,
          asset_type: "image",
          title: `Static visual — ${lineId}`,
          product_name: productName,
          file_path: result.image_path,
          model_used: result.used_model,
        })
          .then((asset) => {
            void logHistoryEvent({
              event_type: "generated_image",
              summary: "Generated static creative image",
              project_id: projectId ?? undefined,
              asset_id: asset.id,
            }).catch(() => {});
          })
          .catch(() => {});
      } catch (e) {
        const message = e instanceof ApiError ? e.message : "Couldn't generate that image.";
        setStaticImages((prev) => ({ ...prev, [lineId]: { status: "failed", imagePath: null, error: message } }));
      }
    },
    [projectId, productName]
  );

  // Static creative's equivalent of generateVisualConcepts — one image per
  // body/hook/cta block that carries an ai_image_prompt, rendered directly
  // (no scene-planning pass needed, the prompts already exist).
  const generateStaticVisuals = useCallback(
    (generatedScript: GeneratedScript, scriptFormat: string) => {
      const lines = flattenScript(generatedScript).filter((l) => l.ai_image_prompt);
      setStaticImages(
        Object.fromEntries(lines.map((l) => [l.id, { status: "pending" as const, imagePath: null, error: null }]))
      );
      const aspectRatio = staticAspectRatio(scriptFormat);
      lines.forEach((l) => {
        void generateOneStaticImage(l.id, l.ai_image_prompt ?? "", aspectRatio);
      });
    },
    [generateOneStaticImage]
  );

  const retryStaticImage = useCallback(
    (lineId: string, prompt: string) => {
      void generateOneStaticImage(lineId, prompt, staticAspectRatio(format));
    },
    [generateOneStaticImage, format]
  );

  return {
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
    regenerateVisualConcept: handleRegenerateVisualConcept,
    generateVisualVariation: handleGenerateVisualVariation,
    editVisualConceptPrompt: handleEditVisualConceptPrompt,
    downloadVisualConcept: handleDownloadVisualConcept,
    toggleFavoriteVisualConcept: handleToggleFavoriteVisualConcept,
    generateStaticVisuals,
    retryStaticImage,
  };
}
