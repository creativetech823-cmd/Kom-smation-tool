"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { DurationSelector } from "@/components/ui/DurationSelector";
import { RegenerateMenu } from "@/components/ui/RegenerateMenu";
import { DurationMeter } from "@/components/ui/DurationMeter";
import { VersionHistoryPanel, type ScriptVersion } from "@/components/ui/VersionHistoryPanel";
import { EditableLine } from "@/components/ui/EditableLine";
import { AiSuggestionsPanel, type ApplyPatch } from "@/components/ui/AiSuggestionsPanel";
import { angleAccent, angleEmoji } from "@/lib/creativeAngles";
import { renderBold } from "@/lib/renderBold";
import { durationStatus, estimateSeconds, targetSecondsFor, wordCount } from "@/lib/duration";
import { cn } from "@/lib/utils";
import {
  flattenScript,
  type FlatLine,
  type GeneratedScript,
  type RewriteDirective,
  type ScriptCommandResult,
  type ScriptCommandSelection,
  type ScriptRegenerateScope,
  type ScriptLanguage,
  type SmartScriptSuggestionsResult,
  type StorySituation,
} from "@/lib/types";

const ROLE_LABEL: Record<string, string> = { hook: "Hook", body: "Body", cta: "CTA" };
const ROLE_TONE: Record<string, "accent" | "success" | "neutral"> = { hook: "accent", body: "neutral", cta: "success" };
const ROLE_MARKER: Record<string, string> = { hook: "var(--accent)", body: "var(--border-strong)", cta: "var(--accent-2)" };
const SECTION_LABEL: Record<string, string> = {
  hook: "Hook",
  problem: "Problem",
  science: "Science",
  story: "Story",
  product_intro: "Product Intro",
  ingredients: "Ingredients",
  benefits: "Benefits",
  objection_handling: "Objection Handling",
  cta: "CTA",
};

const ONE_CLICK_ACTIONS: { label: string; scope: ScriptRegenerateScope; instruction: string }[] = [
  { label: "Add More Science", scope: "science", instruction: "Expand this section with more scientific/psychological depth and credibility." },
  { label: "Add More Emotion", scope: "emotional_tone", instruction: "" },
  { label: "Add More Storytelling", scope: "story", instruction: "Expand the narrative/emotional story beat with more depth." },
  { label: "Remove Repetition", scope: "full", instruction: "Find and remove any repetitive phrasing or repeated ideas across the script, tightening it." },
  { label: "Simplify", scope: "full", instruction: "Simplify the language throughout — shorter words, easier to follow, same meaning." },
  { label: "Improve Flow", scope: "full", instruction: "Improve the pacing and flow between beats so transitions feel smoother and more natural." },
  { label: "Improve CTA", scope: "cta", instruction: "Make the CTA noticeably stronger and more compelling." },
  { label: "Improve Hook", scope: "hook", instruction: "Make the hook noticeably stronger and more attention-grabbing." },
  { label: "Improve Ending", scope: "cta", instruction: "Make the ending land harder — a more memorable, resonant close." },
];

export type RegenerateOptions = { customInstruction?: string; targetWordCount?: number };

export function ScriptStep({
  script,
  situation,
  creativeAngle,
  scriptLanguage,
  onScriptLanguageChange,
  targetDuration,
  onTargetDurationChange,
  onRegenerateScope,
  onBack,
  regenerating,
  onEditLine,
  onEditLineField,
  onEditWholeScript,
  onApplyDirective,
  onGenerateAlternatives,
  onSelectAlternative,
  onTranslateLine,
  lineLoading,
  recentlyChangedLineIds,
  onAnalyzeScript,
  onRunScriptCommand,
  onApplyPatch,
  onEditTitle,
  history,
  historyIndex,
  onUndo,
  onRedo,
  onRestoreVersion,
  selectedHookText,
  onChooseHook,
}: {
  script: GeneratedScript;
  situation: StorySituation;
  creativeAngle?: string;
  scriptLanguage?: ScriptLanguage;
  onScriptLanguageChange?: (language: ScriptLanguage) => void;
  targetDuration?: string;
  onTargetDurationChange?: (duration: string) => void;
  onRegenerateScope: (scope: ScriptRegenerateScope, options?: RegenerateOptions) => void;
  onBack: () => void;
  regenerating: boolean;
  onEditLine: (lineId: string, text: string) => void;
  onEditLineField: (lineId: string, field: string, value: string | string[]) => void;
  onEditWholeScript: (texts: string[]) => void;
  onApplyDirective: (lineId: string, directive: RewriteDirective) => void;
  onGenerateAlternatives: (lineId: string) => Promise<string[]>;
  onSelectAlternative: (lineId: string, text: string) => void;
  onTranslateLine: (lineId: string, language: ScriptLanguage) => void;
  lineLoading: Record<string, boolean>;
  recentlyChangedLineIds: Set<string>;
  onAnalyzeScript: () => Promise<SmartScriptSuggestionsResult>;
  onRunScriptCommand: (instruction: string, selection?: ScriptCommandSelection) => Promise<ScriptCommandResult>;
  onApplyPatch: (patch: ApplyPatch) => void;
  onEditTitle?: (title: string) => void;
  history: ScriptVersion[];
  historyIndex: number;
  onUndo: () => void;
  onRedo: () => void;
  onRestoreVersion: (index: number) => void;
  selectedHookText?: string;
  onChooseHook?: () => void;
}) {
  const lines = flattenScript(script);
  const [view, setView] = useState<"shotlist" | "sheet">("shotlist");
  const [sectionEditing, setSectionEditing] = useState<string | null>(null);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [pendingCommand, setPendingCommand] = useState<{ instruction: string; selection?: ScriptCommandSelection } | null>(
    null
  );
  const [wholeScriptEditing, setWholeScriptEditing] = useState(false);

  const bucket = targetDuration || script.target_duration || "30s";
  const targetSeconds = targetSecondsFor(bucket);
  const estimated = script.estimated_duration_seconds || estimateSeconds(lines);
  const status = durationStatus(estimated, targetSeconds);
  const currentWords = wordCount(lines);

  const grouped = useMemo(() => {
    const groups: { section: string; lines: FlatLine[] }[] = [];
    for (const line of lines) {
      const key = line.section ?? "other";
      const last = groups[groups.length - 1];
      if (last && last.section === key) last.lines.push(line);
      else groups.push({ section: key, lines: [line] });
    }
    return groups;
  }, [lines]);

  function handleImproveSelection(lineId: string, selectedText: string) {
    setPendingCommand({ instruction: "", selection: { line_id: lineId, selected_text: selectedText } });
    setSuggestionsOpen(true);
  }

  function handleLengthPct(pct: number) {
    const target = Math.max(15, Math.round(currentWords * (1 + pct / 100)));
    onRegenerateScope("full", { targetWordCount: target });
  }

  return (
    <Card glow>
      <CardHeader
        title="Cinematic Script"
        subtitle="Full cinematic script for your chosen story — plus literal search tags for Stage 8."
        icon={<IconPen />}
        right={<RegenerateMenu onSelect={(scope) => onRegenerateScope(scope)} loading={regenerating} />}
      />
      <CardBody className="space-y-4">
        <div className="flex items-start justify-between gap-3 rounded-xl border border-[var(--accent)]/20 bg-[var(--accent-soft)] px-4 py-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Badge tone="accent">{situation.category}</Badge>
              <span className="text-[13px] font-semibold text-[var(--foreground)]">{situation.title}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Chip>🎭 {situation.emotion}</Chip>
              <Chip>👤 {situation.persona}</Chip>
              {creativeAngle && (
                <span
                  className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium text-white"
                  style={{ background: angleAccent(creativeAngle), borderColor: "transparent" }}
                >
                  {angleEmoji(creativeAngle)} {creativeAngle}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onBack}
            className="shrink-0 whitespace-nowrap text-[12px] font-medium text-[var(--accent-2)] hover:underline"
          >
            Different angle
          </button>
        </div>

        {onChooseHook && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <p className="shrink-0 text-[12px] font-medium text-[var(--muted)]">Hook</p>
              {selectedHookText ? (
                <span className="truncate text-[12.5px] text-[var(--foreground)]">&ldquo;{selectedHookText}&rdquo;</span>
              ) : (
                <span className="text-[12.5px] text-[var(--muted)]">No hook selected — AI writes its own opening.</span>
              )}
            </div>
            <Button variant="secondary" size="sm" onClick={onChooseHook}>
              Choose Hook
            </Button>
          </div>
        )}

        {onScriptLanguageChange && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[12px] font-medium text-[var(--muted)]">Language</p>
              <LanguageSelector value={scriptLanguage ?? "english"} onChange={onScriptLanguageChange} />
              {onTargetDurationChange && (
                <>
                  <p className="ml-1 text-[12px] font-medium text-[var(--muted)]">Duration</p>
                  <DurationSelector value={bucket} onChange={onTargetDurationChange} />
                </>
              )}
              <span className="text-[11px] text-[var(--muted)]">— change, then Regenerate</span>
            </div>
            <div className="inline-flex items-center gap-1 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] p-1">
              {(["shotlist", "sheet"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors ${
                    view === v ? "bg-[var(--accent)] text-[var(--on-accent)]" : "text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {v === "shotlist" ? "Shot List" : "Script Sheet"}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Duration meter + length controls */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
          <DurationMeter estimatedSeconds={estimated} targetSeconds={targetSeconds} status={status} />
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={() => handleLengthPct(-40)} className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]">
              − 40%
            </button>
            <button type="button" onClick={() => handleLengthPct(-20)} className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]">
              − 20%
            </button>
            <button type="button" onClick={() => handleLengthPct(20)} className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]">
              + 20%
            </button>
            <button type="button" onClick={() => handleLengthPct(40)} className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]">
              + 40%
            </button>
          </div>
        </div>

        {status === "bad" && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-4 py-2.5">
            <p className="text-[12.5px] text-[var(--foreground)]">
              ⚠️ Script is ~{estimated}s — target is {targetSeconds}s.
            </p>
            <button
              type="button"
              onClick={() => onRegenerateScope("full", { targetWordCount: Math.round((targetSeconds / 60) * 165) })}
              className="shrink-0 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--on-accent)] hover:brightness-110"
            >
              Auto-balance
            </button>
          </div>
        )}

        {/* One-click actions */}
        <div className="flex flex-wrap gap-1.5">
          {ONE_CLICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              type="button"
              onClick={() => onRegenerateScope(action.scope, { customInstruction: action.instruction })}
              className="rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1 text-[11px] font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)]/50 hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]"
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* Suggestions + history toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button variant="secondary" size="sm" onClick={() => setSuggestionsOpen(true)}>
            💡 AI Suggestions
          </Button>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setWholeScriptEditing((o) => !o)}
              className={`rounded-lg border px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
                wholeScriptEditing
                  ? "border-[var(--accent)]/50 bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06]"
              }`}
            >
              📝 Edit Whole Script
            </button>
            <button
              type="button"
              disabled={historyIndex <= 0}
              onClick={onUndo}
              className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
            >
              ↶ Undo
            </button>
            <button
              type="button"
              disabled={historyIndex >= history.length - 1}
              onClick={onRedo}
              className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12px] font-medium text-[var(--foreground)] hover:bg-[var(--foreground)]/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
            >
              ↷ Redo
            </button>
            <VersionHistoryPanel entries={history} currentIndex={historyIndex} onRestore={onRestoreVersion} />
          </div>
        </div>

        {wholeScriptEditing && (
          <WholeScriptEditor
            title={situation.title}
            lines={lines}
            onSaveTitle={onEditTitle}
            onSave={(texts) => {
              onEditWholeScript(texts);
              setWholeScriptEditing(false);
            }}
            onClose={() => setWholeScriptEditing(false)}
            onImproveSelection={handleImproveSelection}
          />
        )}

        <AiSuggestionsPanel
          open={suggestionsOpen}
          onClose={() => setSuggestionsOpen(false)}
          script={script}
          onAnalyze={onAnalyzeScript}
          onRunCommand={onRunScriptCommand}
          onApply={onApplyPatch}
          pendingCommand={pendingCommand}
          onConsumePendingCommand={() => setPendingCommand(null)}
        />

        <p className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
          <span>🎙</span> Voiceover for every line happens in Stage 9, after Compliance and Assets are locked in.
        </p>

        {view === "shotlist" ? (
          <div className="space-y-5">
            {grouped.map((group, gi) => (
              <div key={gi}>
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                    {SECTION_LABEL[group.section] ?? group.section}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSectionEditing((cur) => (cur === group.section ? null : group.section))}
                    className="text-[11px] font-medium text-[var(--accent-2)] hover:underline"
                  >
                    {sectionEditing === group.section ? "Done" : "✏️ Edit section"}
                  </button>
                </div>
                <div className="relative">
                  <div className="pointer-events-none absolute bottom-2 left-[15px] top-2 w-px bg-[var(--border-strong)]" />
                  <div className="space-y-3">
                    {group.lines.map((line) => (
                      <TimelineNode
                        key={line.id}
                        line={line}
                        defaultExpanded={line.role === "hook"}
                        forceEditing={sectionEditing === group.section}
                        onEditLine={(text) => onEditLine(line.id, text)}
                        onEditField={(field, value) => onEditLineField(line.id, field, value)}
                        onApplyDirective={(directive) => onApplyDirective(line.id, directive)}
                        onGenerateAlternatives={() => onGenerateAlternatives(line.id)}
                        onSelectAlternative={(text) => onSelectAlternative(line.id, text)}
                        onTranslate={(language) => onTranslateLine(line.id, language)}
                        currentLanguage={scriptLanguage}
                        aiLoading={Boolean(lineLoading[line.id])}
                        glow={recentlyChangedLineIds.has(line.id)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <ScriptSheet
            title={situation.title}
            lines={lines}
            onEditLine={onEditLine}
            onApplyDirective={onApplyDirective}
            onGenerateAlternatives={onGenerateAlternatives}
            onSelectAlternative={onSelectAlternative}
            onTranslateLine={onTranslateLine}
            currentLanguage={scriptLanguage}
            lineLoading={lineLoading}
            recentlyChangedLineIds={recentlyChangedLineIds}
          />
        )}

        {script.bgm_suggestion && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3.5">
            <p className="text-[13px] text-[var(--foreground)]">
              <span className="mr-1.5">🎵</span>
              <span className="font-medium">Background music:</span> {script.bgm_suggestion}
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function WholeScriptEditor({
  title,
  lines,
  onSaveTitle,
  onSave,
  onClose,
  onImproveSelection,
}: {
  title: string;
  lines: FlatLine[];
  onSaveTitle?: (title: string) => void;
  onSave: (texts: string[]) => void;
  onClose: () => void;
  onImproveSelection: (lineId: string, selectedText: string) => void;
}) {
  const [titleDraft, setTitleDraft] = useState(title);
  const [draftMap, setDraftMap] = useState<Record<string, string>>(() =>
    Object.fromEntries(lines.map((l) => [l.id, l.text]))
  );
  const signature = lines.map((l) => `${l.id}:${l.text}`).join("|");
  const prevSignatureRef = useRef(signature);

  useEffect(() => {
    if (prevSignatureRef.current !== signature) {
      prevSignatureRef.current = signature;
      setDraftMap(Object.fromEntries(lines.map((l) => [l.id, l.text])));
    }
  }, [signature, lines]);

  useEffect(() => {
    setTitleDraft(title);
  }, [title]);

  function setLineDraft(id: string, value: string) {
    setDraftMap((prev) => ({ ...prev, [id]: value }));
  }

  function handleSave() {
    onSaveTitle?.(titleDraft.trim());
    onSave(lines.map((l) => draftMap[l.id] ?? l.text));
  }

  const hookLine = lines.find((l) => l.role === "hook");
  const bodyLines = lines.filter((l) => l.role === "body");
  const ctaLine = lines.find((l) => l.role === "cta");

  return (
    <div className="space-y-3.5 rounded-xl border border-[var(--accent)]/30 bg-[var(--surface-2)] p-3.5">
      <p className="text-[12px] text-[var(--muted)]">
        Edit any field directly, or select text within a field and click ✨ Improve selection.
      </p>

      {onSaveTitle && (
        <div>
          <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Title
          </label>
          <input
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[14px] font-medium text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
          />
        </div>
      )}

      {hookLine && (
        <EditorField
          label="Hook"
          value={draftMap[hookLine.id] ?? hookLine.text}
          onChange={(v) => setLineDraft(hookLine.id, v)}
          onImproveSelection={(sel) => onImproveSelection(hookLine.id, sel)}
        />
      )}

      {bodyLines.length > 0 && (
        <div className="space-y-2.5">
          <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--muted)]">Body</p>
          <div className="space-y-2.5 border-l border-[var(--border)] pl-3">
            {bodyLines.map((line, i) => (
              <EditorField
                key={line.id}
                label={line.scene_label || `Line ${i + 1}`}
                value={draftMap[line.id] ?? line.text}
                onChange={(v) => setLineDraft(line.id, v)}
                onImproveSelection={(sel) => onImproveSelection(line.id, sel)}
              />
            ))}
          </div>
        </div>
      )}

      {ctaLine && (
        <EditorField
          label="CTA"
          value={draftMap[ctaLine.id] ?? ctaLine.text}
          onChange={(v) => setLineDraft(ctaLine.id, v)}
          onImproveSelection={(sel) => onImproveSelection(ctaLine.id, sel)}
        />
      )}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={handleSave}
          className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--on-accent)] hover:brightness-110"
        >
          Save Changes
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-[var(--border-strong)] px-3 py-1.5 text-[12px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function EditorField({
  label,
  value,
  onChange,
  onImproveSelection,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onImproveSelection?: (selectedText: string) => void;
}) {
  const [selection, setSelection] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleSelect() {
    const el = ref.current;
    if (!el) return;
    setSelection(el.value.slice(el.selectionStart, el.selectionEnd));
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <label className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</label>
        {onImproveSelection && selection.trim().length > 1 && (
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              onImproveSelection(selection);
              setSelection("");
            }}
            className="text-[11px] font-medium text-[var(--accent-2)] hover:underline"
          >
            ✨ Improve selection
          </button>
        )}
      </div>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onSelect={handleSelect}
        onBlur={() => setTimeout(() => setSelection(""), 150)}
        rows={2}
        className="w-full resize-y rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[13px] leading-relaxed text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
      />
    </div>
  );
}

function ScriptSheet({
  title,
  lines,
  onEditLine,
  onApplyDirective,
  onGenerateAlternatives,
  onSelectAlternative,
  onTranslateLine,
  currentLanguage,
  lineLoading,
  recentlyChangedLineIds,
}: {
  title: string;
  lines: FlatLine[];
  onEditLine: (lineId: string, text: string) => void;
  onApplyDirective: (lineId: string, directive: RewriteDirective) => void;
  onGenerateAlternatives: (lineId: string) => Promise<string[]>;
  onSelectAlternative: (lineId: string, text: string) => void;
  onTranslateLine: (lineId: string, language: ScriptLanguage) => void;
  currentLanguage?: ScriptLanguage;
  lineLoading: Record<string, boolean>;
  recentlyChangedLineIds: Set<string>;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)]/50 px-6 py-8 sm:px-10">
      <h2 className="mb-6 text-center text-[19px] font-bold tracking-tight text-[var(--foreground)]">{title}</h2>
      <div className="mx-auto max-w-[640px] space-y-4">
        {lines.map((line) => (
          <EditableLine
            key={line.id}
            text={line.text}
            onSave={(text) => onEditLine(line.id, text)}
            renderText={renderBold}
            textClassName={
              line.role === "hook" || line.role === "cta"
                ? "text-[15px] font-semibold leading-relaxed text-[var(--foreground)]"
                : "text-[15px] leading-relaxed text-[var(--foreground)]/90"
            }
            onApplyDirective={(d) => onApplyDirective(line.id, d)}
            onGenerateAlternatives={() => onGenerateAlternatives(line.id)}
            onSelectAlternative={(text) => onSelectAlternative(line.id, text)}
            onTranslate={(lang) => onTranslateLine(line.id, lang)}
            currentLanguage={currentLanguage}
            aiLoading={Boolean(lineLoading[line.id])}
            glow={recentlyChangedLineIds.has(line.id)}
          />
        ))}
      </div>
    </div>
  );
}

function InlineField({
  value,
  placeholder,
  onSave,
  className,
}: {
  value: string;
  placeholder?: string;
  onSave: (v: string) => void;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          setEditing(false);
          if (draft !== value) onSave(draft);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            setEditing(false);
            if (draft !== value) onSave(draft);
          }
          if (e.key === "Escape") {
            setDraft(value);
            setEditing(false);
          }
        }}
        className={cn("rounded border border-[var(--accent)]/40 bg-[var(--surface)] px-1.5 py-0.5 text-inherit", className)}
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      title="Click to edit"
      className={cn("cursor-text rounded px-0.5 text-left hover:bg-[var(--foreground)]/[0.06]", className)}
    >
      {value || <span className="italic text-[var(--muted)]">{placeholder ?? "—"}</span>}
    </button>
  );
}

function InlineTagsField({ values, onSave, emoji }: { values: string[]; onSave: (v: string[]) => void; emoji: string }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(values.join(", "));

  function commit() {
    setEditing(false);
    onSave(
      draft
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    );
  }

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") {
            setDraft(values.join(", "));
            setEditing(false);
          }
        }}
        placeholder="comma, separated, tags"
        className="w-full rounded border border-[var(--accent)]/40 bg-[var(--surface)] px-1.5 py-0.5 text-[11px] text-[var(--foreground)]"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => {
        setDraft(values.join(", "));
        setEditing(true);
      }}
      title="Click to edit"
      className="flex flex-wrap gap-1.5"
    >
      {values.length ? (
        values.map((tag) => (
          <span key={tag} className="rounded-full border border-[var(--border)] bg-[var(--foreground)]/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]">
            {emoji} {tag}
          </span>
        ))
      ) : (
        <span className="text-[11px] italic text-[var(--muted)]">{emoji} add tags…</span>
      )}
    </button>
  );
}

function TimelineNode({
  line,
  defaultExpanded,
  forceEditing,
  onEditLine,
  onEditField,
  onApplyDirective,
  onGenerateAlternatives,
  onSelectAlternative,
  onTranslate,
  currentLanguage,
  aiLoading,
  glow,
}: {
  line: FlatLine;
  defaultExpanded: boolean;
  forceEditing: boolean;
  onEditLine: (text: string) => void;
  onEditField: (field: string, value: string | string[]) => void;
  onApplyDirective: (directive: RewriteDirective) => void;
  onGenerateAlternatives: () => Promise<string[]>;
  onSelectAlternative: (text: string) => void;
  onTranslate: (language: ScriptLanguage) => void;
  currentLanguage?: ScriptLanguage;
  aiLoading: boolean;
  glow: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded || forceEditing);

  return (
    <div className="relative flex gap-4">
      <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center">
        <span
          className="h-4 w-4 rounded-full border-2 bg-[var(--surface)]"
          style={{ borderColor: ROLE_MARKER[line.role] }}
        />
      </div>

      <div className={cn("min-w-0 flex-1 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-2)]", glow && "animate-glow")}>
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center gap-2 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <Badge tone={ROLE_TONE[line.role]}>{line.scene_label || ROLE_LABEL[line.role]}</Badge>
          {line.camera_angle && <MetaChip>📷 {line.camera_angle}</MetaChip>}
          {line.emotion && <MetaChip>🎭 {line.emotion}</MetaChip>}
          {typeof line.duration_seconds === "number" && <MetaChip>⏱ {line.duration_seconds}s</MetaChip>}
          {!expanded && (
            <span className="ml-1 flex-1 truncate text-[13px] text-[var(--muted)]">{renderBold(line.text)}</span>
          )}
          <IconChevron expanded={expanded} className="ml-auto shrink-0" />
        </button>

        <AnimatePresence initial={false}>
          {(expanded || forceEditing) && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="space-y-2.5 px-4 pb-4">
                <EditableLine
                  text={line.text}
                  onSave={onEditLine}
                  renderText={renderBold}
                  textClassName="text-[15px] leading-snug text-[var(--foreground)]"
                  onApplyDirective={onApplyDirective}
                  onGenerateAlternatives={onGenerateAlternatives}
                  onSelectAlternative={onSelectAlternative}
                  onTranslate={onTranslate}
                  currentLanguage={currentLanguage}
                  aiLoading={aiLoading}
                />

                {line.on_screen_text && (
                  <div className="flex items-center gap-1.5 text-[12.5px]">
                    <span className="text-[var(--muted)]">On-screen:</span>
                    <InlineField value={line.on_screen_text} onSave={(v) => onEditField("on_screen_text", v)} className="text-[var(--accent-2)]" />
                  </div>
                )}

                <div className="flex items-center gap-1.5 text-[13px] italic leading-snug text-[var(--muted)]">
                  <InlineField
                    value={line.visual_direction ?? ""}
                    placeholder="camera direction…"
                    onSave={(v) => onEditField("visual_direction", v)}
                  />
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <InlineTagsField values={line.visual_tags} onSave={(v) => onEditField("visual_tags", v)} emoji="🎞" />
                  <InlineTagsField values={line.b_roll ?? []} onSave={(v) => onEditField("b_roll", v)} emoji="🎬" />
                </div>

                <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
                  <span className="flex items-center gap-1">
                    📷 <InlineField value={line.camera_angle ?? ""} placeholder="shot type…" onSave={(v) => onEditField("camera_angle", v)} />
                  </span>
                  <span className="flex items-center gap-1">
                    🔊 <InlineField value={line.sfx ?? ""} placeholder="sfx…" onSave={(v) => onEditField("sfx", v)} />
                  </span>
                  {line.lighting && <MetaChip>💡 {line.lighting}</MetaChip>}
                </div>

                {line.transition_note && (
                  <p className="text-[12px] text-[var(--muted)]">↳ {line.transition_note}</p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--accent)]/25 bg-[var(--foreground)]/[0.04] px-2.5 py-0.5 text-[11px] text-[var(--foreground)]">
      {children}
    </span>
  );
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--border-strong)] bg-[var(--foreground)]/[0.04] px-2.5 py-0.5 text-[11px] text-[var(--muted)]">
      {children}
    </span>
  );
}

function IconChevron({ expanded, className }: { expanded: boolean; className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      style={{ transform: expanded ? "rotate(180deg)" : undefined, transition: "transform .2s" }}
    >
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPen() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20h9M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

