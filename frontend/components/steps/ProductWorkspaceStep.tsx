"use client";

import { InputStep } from "./InputStep";
import { AiUnderstandingPanel, type ActivityEntry } from "./AiUnderstandingPanel";
import type { ProductInput, ReferenceMaterial, StructuredProduct } from "@/lib/types";

export function ProductWorkspaceStep({
  onSubmit,
  inputLoading,
  inputError,
  structured,
  onImproveDescription,
  improvingDescription,
  onContinue,
  continueLoading,
  referenceMaterials,
  uploadingMaterialIds,
  onAddReferenceFiles,
  onAddReferenceUrl,
  onRemoveReferenceMaterial,
  sourceUrlRawText,
  onSourceUrlRawTextChange,
  activityLog,
  onActivity,
}: {
  onSubmit: (input: ProductInput, category: string) => void;
  inputLoading: boolean;
  inputError: string | null;
  structured: StructuredProduct | null;
  onImproveDescription: (text: string) => Promise<string>;
  improvingDescription: boolean;
  onContinue: () => void;
  continueLoading: boolean;
  referenceMaterials: ReferenceMaterial[];
  uploadingMaterialIds: Set<string>;
  onAddReferenceFiles: (files: FileList | File[]) => void;
  onAddReferenceUrl: (url: string) => void;
  onRemoveReferenceMaterial: (id: string) => void;
  sourceUrlRawText: string | undefined;
  onSourceUrlRawTextChange: (text: string | undefined) => void;
  activityLog: ActivityEntry[];
  onActivity: (label: string, tone?: "info" | "success" | "error") => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
      <InputStep
        onSubmit={onSubmit}
        loading={inputLoading}
        error={inputError}
        onImproveDescription={onImproveDescription}
        improvingDescription={improvingDescription}
        referenceMaterials={referenceMaterials}
        uploadingMaterialIds={uploadingMaterialIds}
        onAddReferenceFiles={onAddReferenceFiles}
        onAddReferenceUrl={onAddReferenceUrl}
        onRemoveReferenceMaterial={onRemoveReferenceMaterial}
        sourceUrlRawText={sourceUrlRawText}
        onSourceUrlRawTextChange={onSourceUrlRawTextChange}
        onActivity={onActivity}
      />
      <AiUnderstandingPanel
        data={structured}
        loading={inputLoading}
        onContinue={onContinue}
        continueLoading={continueLoading}
        activityLog={activityLog}
      />
    </div>
  );
}
