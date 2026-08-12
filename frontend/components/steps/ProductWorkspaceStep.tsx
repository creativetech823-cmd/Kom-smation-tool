"use client";

import { InputStep } from "./InputStep";
import { AiUnderstandingPanel } from "./AiUnderstandingPanel";
import type { ProductInput, StructuredProduct } from "@/lib/types";

export function ProductWorkspaceStep({
  onSubmit,
  inputLoading,
  inputError,
  structured,
  onImproveDescription,
  improvingDescription,
  onContinue,
  continueLoading,
}: {
  onSubmit: (input: ProductInput, category: string) => void;
  inputLoading: boolean;
  inputError: string | null;
  structured: StructuredProduct | null;
  onImproveDescription: (text: string) => Promise<string>;
  improvingDescription: boolean;
  onContinue: () => void;
  continueLoading: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
      <InputStep
        onSubmit={onSubmit}
        loading={inputLoading}
        error={inputError}
        onImproveDescription={onImproveDescription}
        improvingDescription={improvingDescription}
      />
      <AiUnderstandingPanel
        data={structured}
        loading={inputLoading}
        onContinue={onContinue}
        continueLoading={continueLoading}
      />
    </div>
  );
}
