"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type {
  GeneratedScript,
  ScriptCommandResult,
  ScriptCommandSelection,
  ScriptSuggestionCard,
  ScriptSuggestionCategory,
  SmartScriptSuggestionsResult,
} from "@/lib/types";
import { flattenScript } from "@/lib/types";
import { ApiError } from "@/lib/api";

export type ApplyPatch =
  | { kind: "line"; lineId: string; text: string; label: string }
  | { kind: "full"; script: GeneratedScript; label: string };

const CATEGORY_META: Record<ScriptSuggestionCategory, { icon: string; fallbackTitle: string }> = {
  hook: { icon: "🎯", fallbackTitle: "Stronger Hook" },
  opening_line: { icon: "✍️", fallbackTitle: "Opening Line" },
  emotional_impact: { icon: "❤️", fallbackTitle: "Emotional Impact" },
  clarity: { icon: "🔍", fallbackTitle: "Clarity" },
  flow: { icon: "🔗", fallbackTitle: "Flow" },
  storytelling: { icon: "📖", fallbackTitle: "Storytelling" },
  product_integration: { icon: "🏷️", fallbackTitle: "Product Integration" },
  cta: { icon: "📣", fallbackTitle: "CTA" },
  repetition: { icon: "🔁", fallbackTitle: "Repetition" },
  length: { icon: "⏱", fallbackTitle: "Length" },
  natural_hinglish: { icon: "🗣️", fallbackTitle: "Natural Hinglish" },
  brand_mention: { icon: "🏷️", fallbackTitle: "Brand Mention" },
  audience_relevance: { icon: "🎯", fallbackTitle: "Audience Relevance" },
  virality: { icon: "🚀", fallbackTitle: "Virality" },
};

type PendingCommand = { instruction: string; selection?: ScriptCommandSelection } | null;

export function AiSuggestionsPanel({
  open,
  onClose,
  script,
  onAnalyze,
  onRunCommand,
  onApply,
  pendingCommand,
  onConsumePendingCommand,
}: {
  open: boolean;
  onClose: () => void;
  script: GeneratedScript;
  onAnalyze: () => Promise<SmartScriptSuggestionsResult>;
  onRunCommand: (instruction: string, selection?: ScriptCommandSelection) => Promise<ScriptCommandResult>;
  onApply: (patch: ApplyPatch) => void;
  /** Set by an external trigger (e.g. "✨ Improve selection" in the whole-script
   * editor) to skip the analysis view and jump straight into a running command. */
  pendingCommand?: PendingCommand;
  onConsumePendingCommand?: () => void;
}) {
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<SmartScriptSuggestionsResult | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);

  const [instruction, setInstruction] = useState("");
  const [commandLoading, setCommandLoading] = useState(false);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScriptCommandResult | null>(null);
  const [previewSelection, setPreviewSelection] = useState<ScriptCommandSelection | undefined>(undefined);
  const [applyingPreview, setApplyingPreview] = useState(false);

  const ranForRef = useRef<GeneratedScript | null>(null);

  async function runAnalysis() {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      setResult(await onAnalyze());
    } catch (e) {
      setAnalyzeError(e instanceof ApiError ? e.message : "Couldn't analyze this script right now.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function runCommand(text: string, selection?: ScriptCommandSelection) {
    setCommandLoading(true);
    setCommandError(null);
    setPreview(null);
    setPreviewSelection(selection);
    try {
      const commandResult = await onRunCommand(text, selection);
      setPreview(commandResult);
    } catch (e) {
      setCommandError(e instanceof ApiError ? e.message : "Couldn't process that instruction.");
    } finally {
      setCommandLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    if (pendingCommand) {
      setInstruction(pendingCommand.instruction);
      void runCommand(pendingCommand.instruction, pendingCommand.selection);
      onConsumePendingCommand?.();
      return;
    }
    if (ranForRef.current !== script) {
      ranForRef.current = script;
      void runAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleClose() {
    setPreview(null);
    setCommandError(null);
    setInstruction("");
    onClose();
  }

  function handleApplyCard(card: ScriptSuggestionCard) {
    if (card.line_id && card.suggested_text) {
      setApplyingId(card.id);
      onApply({ kind: "line", lineId: card.line_id, text: card.suggested_text, label: `AI Suggestion: ${card.title}` });
      setResult((prev) => (prev ? { ...prev, cards: prev.cards.filter((c) => c.id !== card.id) } : prev));
      setApplyingId(null);
    } else if (card.suggested_scope) {
      onApply({ kind: "full", script, label: `AI Suggestion: ${card.title}` });
    }
  }

  function handleApplyPreview() {
    if (!preview) return;
    setApplyingPreview(true);
    if (preview.is_full_rewrite && preview.full_script_after) {
      onApply({ kind: "full", script: preview.full_script_after, label: `AI: ${preview.title}` });
    } else if (preview.line_id && preview.suggested_text) {
      onApply({ kind: "line", lineId: preview.line_id, text: preview.suggested_text, label: `AI: ${preview.title}` });
    }
    setApplyingPreview(false);
    setPreview(null);
    setInstruction("");
  }

  function handleTryAnother() {
    void runCommand(instruction, previewSelection);
  }

  function handleSubmitInstruction() {
    const text = instruction.trim();
    if (!text) return;
    void runCommand(text, undefined);
  }

  function handleDismissPreview() {
    setPreview(null);
    setCommandError(null);
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={handleClose}
            className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[1px]"
          />
          <motion.aside
            key="panel"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[420px] flex-col border-l border-[var(--border-strong)] bg-[var(--surface)] shadow-[-20px_0_60px_-20px_var(--shadow-color)]"
          >
            <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3.5">
              <div className="min-w-0">
                <h3 className="flex items-center gap-1.5 text-[14px] font-semibold text-[var(--foreground)]">
                  💡 AI Suggestions
                </h3>
                <p className="mt-0.5 text-[12px] text-[var(--muted)]">
                  Make this script sharper, clearer and more engaging.
                </p>
              </div>
              <button
                type="button"
                onClick={handleClose}
                aria-label="Close AI Suggestions"
                className="shrink-0 rounded-lg p-1 text-[15px] text-[var(--muted)] hover:bg-[var(--foreground)]/[0.06] hover:text-[var(--foreground)]"
              >
                ✕
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              {commandLoading || preview || commandError ? (
                <CommandPanel
                  loading={commandLoading}
                  error={commandError}
                  result={preview}
                  applying={applyingPreview}
                  isSelectionEdit={Boolean(previewSelection)}
                  onApply={handleApplyPreview}
                  onTryAnother={handleTryAnother}
                  onDismiss={handleDismissPreview}
                />
              ) : (
                <SuggestionsList
                  analyzing={analyzing}
                  error={analyzeError}
                  result={result}
                  applyingId={applyingId}
                  onApply={handleApplyCard}
                  onRetry={runAnalysis}
                />
              )}
            </div>

            <div className="border-t border-[var(--border)] px-4 py-3.5">
              <p className="mb-1.5 text-[11.5px] font-medium text-[var(--muted)]">Tell AI what you want to change</p>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    handleSubmitInstruction();
                  }
                }}
                rows={2}
                placeholder='e.g. "mention Ayush Wellness naturally" or "make the hook more emotional"'
                className="w-full resize-none rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-2 text-[12.5px] text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
              />
              <button
                type="button"
                disabled={!instruction.trim() || commandLoading}
                onClick={handleSubmitInstruction}
                className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {commandLoading ? (
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" />
                ) : (
                  "✨"
                )}
                Improve
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SuggestionsList({
  analyzing,
  error,
  result,
  applyingId,
  onApply,
  onRetry,
}: {
  analyzing: boolean;
  error: string | null;
  result: SmartScriptSuggestionsResult | null;
  applyingId: string | null;
  onApply: (card: ScriptSuggestionCard) => void;
  onRetry: () => void;
}) {
  if (analyzing) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--foreground)]/20 border-t-[var(--accent)]" />
        <p className="text-[12.5px] text-[var(--muted)]">Analyzing your script...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3.5 py-3 text-center">
        <p className="text-[12.5px] text-[var(--foreground)]">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--on-accent)] hover:brightness-110"
        >
          ↻ Retry
        </button>
      </div>
    );
  }

  if (!result) return null;

  const isStrong = result.status === "strong";

  return (
    <div className="space-y-3">
      <div
        className={`rounded-xl border px-3.5 py-2.5 text-[12.5px] ${
          isStrong
            ? "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--foreground)]"
            : "border-[var(--accent)]/25 bg-[var(--accent-soft)] text-[var(--foreground)]"
        }`}
      >
        {isStrong ? "✓ " : ""}
        {result.headline || (isStrong ? "Your script is ready to go." : `Found ${result.cards.length} opportunities to improve.`)}
      </div>

      {result.cards.map((card) => (
        <SuggestionCardView key={card.id} card={card} applying={applyingId === card.id} onApply={() => onApply(card)} />
      ))}

      {isStrong && result.optional_ideas.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">Optional polish ideas</p>
          <div className="flex flex-wrap gap-1.5">
            {result.optional_ideas.map((idea, i) => (
              <span
                key={i}
                className="rounded-full border border-[var(--border)] bg-[var(--foreground)]/[0.03] px-2.5 py-1 text-[11.5px] text-[var(--muted)]"
              >
                {idea}
              </span>
            ))}
          </div>
        </div>
      )}

      {isStrong && result.cards.length === 0 && result.optional_ideas.length === 0 && (
        <p className="py-4 text-center text-[12.5px] text-[var(--muted)]">Your script is ready to go.</p>
      )}
    </div>
  );
}

function SuggestionCardView({
  card,
  applying,
  onApply,
}: {
  card: ScriptSuggestionCard;
  applying: boolean;
  onApply: () => void;
}) {
  const meta = CATEGORY_META[card.category] ?? { icon: "💡", fallbackTitle: "Suggestion" };
  const canApply = Boolean((card.line_id && card.suggested_text) || card.suggested_scope);

  return (
    <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-3">
      <p className="text-[12.5px] font-semibold text-[var(--foreground)]">
        {meta.icon} {card.title || meta.fallbackTitle}
      </p>

      {card.current_text && (
        <div>
          <p className="text-[10.5px] font-medium uppercase tracking-wide text-[var(--muted)]">Current</p>
          <p className="text-[12.5px] text-[var(--muted)] line-through decoration-[var(--danger)]/40">{card.current_text}</p>
        </div>
      )}

      {card.suggested_text && (
        <div>
          <p className="text-[10.5px] font-medium uppercase tracking-wide text-[var(--muted)]">Suggestion</p>
          <p className="text-[13px] text-[var(--foreground)]">{card.suggested_text}</p>
        </div>
      )}

      {card.why && <p className="text-[11.5px] italic text-[var(--muted)]">{card.why}</p>}

      {canApply && (
        <button
          type="button"
          disabled={applying}
          onClick={onApply}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-2.5 py-1 text-[11.5px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:opacity-50"
        >
          {applying && <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-[var(--on-accent)]/30 border-t-[var(--on-accent)]" />}
          Apply
        </button>
      )}
    </div>
  );
}

function CommandPanel({
  loading,
  error,
  result,
  applying,
  isSelectionEdit,
  onApply,
  onTryAnother,
  onDismiss,
}: {
  loading: boolean;
  error: string | null;
  result: ScriptCommandResult | null;
  applying: boolean;
  isSelectionEdit: boolean;
  onApply: () => void;
  onTryAnother: () => void;
  onDismiss: () => void;
}) {
  if (loading) {
    return (
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--foreground)]/20 border-t-[var(--accent)]" />
        <p className="text-[12.5px] text-[var(--muted)]">Thinking...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-3.5 py-3 text-center">
        <p className="text-[12.5px] text-[var(--foreground)]">{error}</p>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Back to suggestions
        </button>
      </div>
    );
  }

  if (!result) return null;

  if (result.is_full_rewrite && result.full_script_after) {
    return <FullRewritePreview result={result} applying={applying} onApply={onApply} onDismiss={onDismiss} />;
  }

  return (
    <div className="space-y-3">
      <button type="button" onClick={onDismiss} className="text-[11.5px] text-[var(--muted)] hover:text-[var(--foreground)]">
        ← Back to suggestions
      </button>
      <div className="space-y-2 rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-3.5 py-3">
        <p className="text-[12.5px] font-semibold text-[var(--foreground)]">✍️ {result.title}</p>
        {result.current_text && (
          <div>
            <p className="text-[10.5px] font-medium uppercase tracking-wide text-[var(--muted)]">
              {isSelectionEdit ? "Before" : "Current"}
            </p>
            <p className="text-[12.5px] text-[var(--muted)] line-through decoration-[var(--danger)]/40">{result.current_text}</p>
          </div>
        )}
        {result.suggested_text && (
          <div>
            <p className="text-[10.5px] font-medium uppercase tracking-wide text-[var(--muted)]">
              {isSelectionEdit ? "After" : "Suggestion"}
            </p>
            <p className="text-[13px] text-[var(--foreground)]">{result.suggested_text}</p>
          </div>
        )}
        {result.why && <p className="text-[11.5px] italic text-[var(--muted)]">{result.why}</p>}
        <div className="flex gap-1.5 pt-1">
          <button
            type="button"
            disabled={applying}
            onClick={onApply}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:opacity-50"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={onTryAnother}
            className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]"
          >
            Try Another
          </button>
        </div>
      </div>
    </div>
  );
}

function FullRewritePreview({
  result,
  applying,
  onApply,
  onDismiss,
}: {
  result: ScriptCommandResult;
  applying: boolean;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const after = result.full_script_after;
  if (!after) return null;
  const afterLines = flattenScript(after);

  return (
    <div className="space-y-3">
      <button type="button" onClick={onDismiss} className="text-[11.5px] text-[var(--muted)] hover:text-[var(--foreground)]">
        ← Back to suggestions
      </button>
      <div className="rounded-xl border border-[var(--accent)]/25 bg-[var(--accent-soft)] px-3.5 py-3">
        <p className="text-[12.5px] font-semibold text-[var(--foreground)]">📝 {result.title}</p>
        {result.why && <p className="mt-1 text-[11.5px] italic text-[var(--muted)]">{result.why}</p>}
      </div>

      <div>
        <p className="mb-1.5 text-[10.5px] font-medium uppercase tracking-wide text-[var(--muted)]">AI Version</p>
        <div className="max-h-64 space-y-1.5 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5">
          {afterLines.map((line) => (
            <p key={line.id} className="text-[12.5px] leading-relaxed text-[var(--foreground)]">
              {line.text}
            </p>
          ))}
        </div>
      </div>

      <div className="flex gap-1.5">
        <button
          type="button"
          disabled={applying}
          onClick={onApply}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--on-accent)] hover:brightness-110 disabled:opacity-50"
        >
          Use AI Version
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]"
        >
          Keep Original
        </button>
      </div>
    </div>
  );
}
