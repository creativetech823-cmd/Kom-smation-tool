"use client";

import { useEffect, useRef, useState } from "react";
import type { RewriteDirective, ScriptLanguage } from "@/lib/types";

const CATEGORIES: { label: string; items: { directive: RewriteDirective; label: string }[] }[] = [
  {
    label: "Length",
    items: [
      { directive: "make_shorter", label: "Make Shorter" },
      { directive: "make_longer", label: "Make Longer" },
    ],
  },
  {
    label: "Emotion & Persuasion",
    items: [
      { directive: "make_emotional", label: "More Emotional" },
      { directive: "more_persuasive", label: "More Persuasive" },
      { directive: "fear_based", label: "Fear Based" },
      { directive: "more_scientific", label: "More Scientific" },
    ],
  },
  {
    label: "Style",
    items: [
      { directive: "more_cinematic", label: "More Cinematic" },
      { directive: "more_conversational", label: "More Conversational" },
      { directive: "simplify", label: "Simplify" },
      { directive: "professional_tone", label: "Professional Tone" },
      { directive: "funny", label: "Funny" },
    ],
  },
  {
    label: "Format",
    items: [
      { directive: "doctor_style", label: "Doctor Style" },
      { directive: "storytelling_style", label: "Storytelling Style" },
      { directive: "ugc_style", label: "UGC Style" },
      { directive: "podcast_style", label: "Podcast Style" },
      { directive: "meta_glasses_pov", label: "Meta Glasses POV" },
    ],
  },
  {
    label: "Other",
    items: [
      { directive: "improve", label: "Improve" },
      { directive: "make_viral", label: "Make Viral" },
      { directive: "increase_conversion", label: "Increase Conversion" },
      { directive: "rewrite", label: "Rewrite Sentence" },
      { directive: "rewrite", label: "Regenerate Only This Sentence" },
    ],
  },
];

const LANGUAGE_LABEL: Record<ScriptLanguage, string> = {
  english: "English",
  hindi: "हिंदी",
  hinglish: "Hinglish",
  marathi: "मराठी",
  gujarati: "ગુજરાતી",
  tamil: "தமிழ்",
  telugu: "తెలుగు",
  bengali: "বাংলা",
  kannada: "ಕನ್ನಡ",
  malayalam: "മലയാളം",
  custom: "Custom",
};
// "custom" is deliberately excluded — this quick per-line translate menu has
// no accompanying free-text field to name a custom language (see backend
// rewrite_service._LANGUAGE_NAME, same scope decision).
const ALL_LANGUAGES: ScriptLanguage[] = [
  "english",
  "hindi",
  "hinglish",
  "marathi",
  "gujarati",
  "tamil",
  "telugu",
  "bengali",
  "kannada",
  "malayalam",
];

export function AiRewriteMenu({
  onApplyDirective,
  onGenerateAlternatives,
  onSelectAlternative,
  onTranslate,
  currentLanguage,
  loading,
}: {
  onApplyDirective?: (directive: RewriteDirective) => void;
  onGenerateAlternatives?: () => Promise<string[]>;
  onSelectAlternative?: (text: string) => void;
  onTranslate?: (language: ScriptLanguage) => void;
  currentLanguage?: ScriptLanguage;
  loading?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"menu" | "alternatives" | "translate">("menu");
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [altLoading, setAltLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setView("menu");
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  async function handleGenerateAlternatives() {
    if (!onGenerateAlternatives) return;
    setView("alternatives");
    setAltLoading(true);
    try {
      const result = await onGenerateAlternatives();
      setAlternatives(result);
    } finally {
      setAltLoading(false);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="AI rewrite"
        disabled={loading}
        className="rounded p-0.5 text-[12px] hover:bg-[var(--foreground)]/[0.08] disabled:opacity-40"
      >
        {loading ? (
          <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-[var(--foreground)]/30 border-t-[var(--accent)]" />
        ) : (
          "✨"
        )}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-1.5 max-h-80 w-60 overflow-y-auto rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] shadow-[0_20px_40px_-20px_var(--shadow-color)]">
          {view === "menu" && (
            <>
              {CATEGORIES.map((cat) => (
                <div key={cat.label} className="border-b border-[var(--border)] last:border-b-0">
                  <p className="px-3 pt-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                    {cat.label}
                  </p>
                  {cat.items.map((item, i) => (
                    <button
                      key={`${item.directive}-${i}`}
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        onApplyDirective?.(item.directive);
                      }}
                      className="block w-full px-3 py-1.5 text-left text-[12px] text-[var(--foreground)] transition-colors hover:bg-[var(--foreground)]/[0.06]"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ))}
              {onGenerateAlternatives && (
                <button
                  type="button"
                  onClick={handleGenerateAlternatives}
                  className="block w-full border-b border-[var(--border)] px-3 py-2 text-left text-[12px] font-medium text-[var(--accent-2)] hover:bg-[var(--foreground)]/[0.06]"
                >
                  🎲 Generate 5 Alternatives
                </button>
              )}
              {onTranslate && (
                <button
                  type="button"
                  onClick={() => setView("translate")}
                  className="block w-full px-3 py-2 text-left text-[12px] font-medium text-[var(--accent-2)] hover:bg-[var(--foreground)]/[0.06]"
                >
                  🌐 Translate
                </button>
              )}
            </>
          )}

          {view === "alternatives" && (
            <div className="p-2">
              <button
                type="button"
                onClick={() => setView("menu")}
                className="mb-1.5 text-[11px] text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                ← Back
              </button>
              {altLoading ? (
                <div className="flex items-center gap-2 px-1 py-3 text-[12px] text-[var(--muted)]">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--foreground)]/30 border-t-[var(--accent)]" />
                  Generating…
                </div>
              ) : (
                <div className="space-y-1">
                  {alternatives.map((alt, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        setView("menu");
                        onSelectAlternative?.(alt);
                      }}
                      className="block w-full rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-left text-[11.5px] text-[var(--foreground)] hover:border-[var(--accent)]/40 hover:bg-[var(--foreground)]/[0.05]"
                    >
                      {alt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {view === "translate" && (
            <div className="p-2">
              <button
                type="button"
                onClick={() => setView("menu")}
                className="mb-1.5 text-[11px] text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                ← Back
              </button>
              <div className="space-y-1">
                {ALL_LANGUAGES.filter((l) => l !== currentLanguage).map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      setView("menu");
                      onTranslate?.(lang);
                    }}
                    className="block w-full rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-left text-[12px] text-[var(--foreground)] hover:border-[var(--accent)]/40 hover:bg-[var(--foreground)]/[0.05]"
                  >
                    {LANGUAGE_LABEL[lang]}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
