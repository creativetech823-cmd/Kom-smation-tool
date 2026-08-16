"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { AiWorkingChecklist } from "@/components/ui/AiWorkingChecklist";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { DurationSelector } from "@/components/ui/DurationSelector";
import { angleAccent, angleEmoji } from "@/lib/creativeAngles";
import { cn } from "@/lib/utils";
import type { ScriptLanguage, StorySituation } from "@/lib/types";

type ViralityBucket = "" | "8+" | "6-8" | "<6";
type SelectingKey = { situationId: string; angle: string } | null;

const LOADING_STEPS = [
  { id: "profile", label: "Reading product profile" },
  { id: "personas", label: "Brainstorming personas" },
  { id: "virality", label: "Scoring virality" },
  { id: "finalize", label: "Finalizing story angles" },
];

const CATEGORY_ACCENTS = ["var(--accent)", "var(--accent-2)", "var(--success)", "var(--warning)"];
const VISIBLE_ANGLE_CAP = 5;
const CUSTOM_ANGLE_MAX = 300;

function categoryAccent(category: string): string {
  let hash = 0;
  for (let i = 0; i < category.length; i++) hash = (hash * 31 + category.charCodeAt(i)) >>> 0;
  return CATEGORY_ACCENTS[hash % CATEGORY_ACCENTS.length];
}

const gridVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, scale: 0.97, transition: { duration: 0.15 } },
};

function viralityTone(score: number): "success" | "warning" | "neutral" {
  if (score >= 8.5) return "success";
  if (score >= 6.5) return "warning";
  return "neutral";
}

function matchesBucket(score: number, bucket: ViralityBucket): boolean {
  if (bucket === "") return true;
  if (bucket === "8+") return score >= 8;
  if (bucket === "6-8") return score >= 6 && score < 8;
  return score < 6;
}

function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

export function StorySituationStep({
  situations,
  loading,
  generatingMore,
  selectingKey,
  onSelectAngle,
  onGenerateMore,
  onBack,
  scriptLanguage,
  onScriptLanguageChange,
  targetDuration,
  onTargetDurationChange,
}: {
  situations: StorySituation[];
  loading: boolean;
  generatingMore: boolean;
  selectingKey: SelectingKey;
  onSelectAngle: (situation: StorySituation, angle: string) => void;
  onGenerateMore: () => void;
  onBack: () => void;
  scriptLanguage: ScriptLanguage;
  onScriptLanguageChange: (language: ScriptLanguage) => void;
  targetDuration: string;
  onTargetDurationChange: (duration: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [emotion, setEmotion] = useState("");
  const [persona, setPersona] = useState("");
  const [marketingAngle, setMarketingAngle] = useState("");
  const [creativeAngle, setCreativeAngle] = useState("");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [length, setLength] = useState("");
  const [virality, setVirality] = useState<ViralityBucket>("");

  const options = useMemo(() => {
    const uniq = (values: string[]) => Array.from(new Set(values.filter(Boolean))).sort();
    return {
      emotion: uniq(situations.map((s) => s.emotion)),
      persona: uniq(situations.map((s) => s.persona)),
      marketingAngle: uniq(situations.map((s) => s.marketing_angle)),
      creativeAngle: uniq(situations.flatMap((s) => s.recommended_angles)),
      category: uniq(situations.map((s) => s.category)),
      difficulty: uniq(situations.map((s) => s.difficulty)),
      length: uniq(situations.map((s) => s.estimated_length)),
    };
  }, [situations]);

  const filtersActive =
    search.trim() !== "" ||
    emotion !== "" ||
    persona !== "" ||
    marketingAngle !== "" ||
    creativeAngle !== "" ||
    category !== "" ||
    difficulty !== "" ||
    length !== "" ||
    virality !== "";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return situations.filter((s) => {
      if (
        q &&
        !`${s.title} ${s.description} ${s.emotion} ${s.persona} ${s.marketing_angle} ${s.category} ${s.recommended_angles.join(
          " "
        )}`
          .toLowerCase()
          .includes(q)
      )
        return false;
      if (emotion && s.emotion !== emotion) return false;
      if (persona && s.persona !== persona) return false;
      if (marketingAngle && s.marketing_angle !== marketingAngle) return false;
      if (creativeAngle && !s.recommended_angles.includes(creativeAngle)) return false;
      if (category && s.category !== category) return false;
      if (difficulty && s.difficulty !== difficulty) return false;
      if (length && s.estimated_length !== length) return false;
      if (!matchesBucket(s.virality_score, virality)) return false;
      return true;
    });
  }, [situations, search, emotion, persona, marketingAngle, creativeAngle, category, difficulty, length, virality]);

  function clearFilters() {
    setSearch("");
    setEmotion("");
    setPersona("");
    setMarketingAngle("");
    setCreativeAngle("");
    setCategory("");
    setDifficulty("");
    setLength("");
    setVirality("");
  }

  const anySelecting = selectingKey !== null;

  return (
    <Card glow>
      <CardHeader
        title="Choose Your Story"
        subtitle="Pick a story situation, then pick how it's told — the same story can become dozens of different scripts."
        icon={<IconCompass />}
      />
      <CardBody className="space-y-5">
        {!loading && situations.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-3.5 py-2.5">
            <p className="text-[12px] font-medium text-[var(--muted)]">
              Script language + duration — applies when you pick an angle below
            </p>
            <div className="flex items-center gap-2">
              <LanguageSelector value={scriptLanguage} onChange={onScriptLanguageChange} disabled={anySelecting} />
              <DurationSelector value={targetDuration} onChange={onTargetDurationChange} disabled={anySelecting} />
            </div>
          </div>
        )}

        {!loading && situations.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search doctor, mother, gym, fear, UGC, meta..."
              className="!w-auto min-w-[200px] flex-1 !py-1.5 !text-[13px]"
            />
            <FilterSelect label="Emotion" value={emotion} onChange={setEmotion} options={options.emotion} />
            <FilterSelect label="Persona" value={persona} onChange={setPersona} options={options.persona} />
            <FilterSelect
              label="Creative Angle"
              value={creativeAngle}
              onChange={setCreativeAngle}
              options={options.creativeAngle}
            />
            <FilterSelect
              label="Marketing Angle"
              value={marketingAngle}
              onChange={setMarketingAngle}
              options={options.marketingAngle}
            />
            <FilterSelect label="Category" value={category} onChange={setCategory} options={options.category} />
            <FilterSelect
              label="Difficulty"
              value={difficulty}
              onChange={setDifficulty}
              options={options.difficulty}
            />
            <FilterSelect label="Length" value={length} onChange={setLength} options={options.length} />
            <FilterSelect
              label="Virality"
              value={virality}
              onChange={(v) => setVirality(v as ViralityBucket)}
              options={["8+", "6-8", "<6"]}
            />
            {filtersActive && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </div>
        )}

        {loading && situations.length === 0 && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)]/40 px-4 py-6">
            <AiWorkingChecklist steps={LOADING_STEPS} active={loading} />
          </div>
        )}

        {!loading && situations.length > 0 && (
          <>
            {filtered.length === 0 ? (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-6 text-center text-[13px] text-[var(--muted)]">
                No situations match your filters.
              </div>
            ) : (
              <motion.div
                variants={gridVariants}
                initial="hidden"
                animate="show"
                className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
              >
                <AnimatePresence>
                  {filtered.map((s) => {
                    const isCardActive = selectingKey?.situationId === s.id;
                    const activeAngle = isCardActive ? selectingKey!.angle : null;
                    const isDisabled = anySelecting && !isCardActive;
                    return (
                      <SituationCard
                        key={s.id}
                        situation={s}
                        isCardActive={isCardActive}
                        isDisabled={isDisabled}
                        activeAngle={activeAngle}
                        onSelectAngle={onSelectAngle}
                      />
                    );
                  })}
                </AnimatePresence>
              </motion.div>
            )}

            <div className="flex justify-center pt-1">
              <Button
                variant="secondary"
                onClick={onGenerateMore}
                loading={generatingMore}
                disabled={anySelecting}
              >
                <IconRefresh /> Generate More Situations
              </Button>
            </div>
          </>
        )}

        <div className="flex justify-between pt-2">
          <Button variant="ghost" onClick={onBack} disabled={anySelecting}>
            ← Back
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function SituationCard({
  situation,
  isCardActive,
  isDisabled,
  activeAngle,
  onSelectAngle,
}: {
  situation: StorySituation;
  isCardActive: boolean;
  isDisabled: boolean;
  activeAngle: string | null;
  onSelectAngle: (situation: StorySituation, angle: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [customOpen, setCustomOpen] = useState(false);
  const [customText, setCustomText] = useState("");

  const angles = situation.recommended_angles;
  const visibleAngles = expanded ? angles : angles.slice(0, VISIBLE_ANGLE_CAP);
  const hiddenCount = angles.length - visibleAngles.length;
  const isCustomActive = isCardActive && activeAngle !== null && !angles.includes(activeAngle);

  function handleCustomSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!customText.trim() || isDisabled) return;
    onSelectAngle(situation, customText.trim());
  }

  return (
    <motion.div
      layout
      variants={cardVariants}
      exit="exit"
      className={cn(
        "relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors",
        isCardActive ? "border-[var(--accent)] bg-[var(--accent-soft)]" : "hover:border-[var(--accent)]/40",
        isDisabled && "pointer-events-none opacity-50"
      )}
    >
      <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: categoryAccent(situation.category) }} />

      <div className="mb-2.5 flex items-center justify-between gap-2">
        <Badge tone="accent">{situation.category}</Badge>
        <Badge tone={viralityTone(situation.virality_score)}>⚡ {situation.virality_score.toFixed(1)}/10</Badge>
      </div>

      <h3 className="text-[15px] font-semibold leading-snug text-[var(--foreground)]">{situation.title}</h3>
      <p className="mt-1 line-clamp-3 text-[13px] leading-snug text-[var(--muted)]">{situation.description}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip>🎭 {situation.emotion}</Chip>
        <Chip>👤 {situation.persona}</Chip>
        <Chip>🎯 {situation.marketing_angle}</Chip>
      </div>

      <div className="mt-3 flex gap-1.5">
        <Badge tone="neutral">{cap(situation.difficulty)}</Badge>
        <Badge tone="neutral">{situation.estimated_length}</Badge>
      </div>

      <div className="mt-3.5 border-t border-[var(--border)] pt-3">
        <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
          <span>⭐</span> AI Recommended Angles
        </p>
        <div className="flex flex-wrap gap-1.5">
          {visibleAngles.map((angle) => {
            const chipActive = activeAngle === angle;
            const accent = angleAccent(angle);
            return (
              <button
                key={angle}
                type="button"
                disabled={isDisabled}
                onClick={() => onSelectAngle(situation, angle)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] disabled:cursor-not-allowed",
                  chipActive ? "scale-105 border-transparent text-white" : "border-[var(--border-strong)] bg-[var(--foreground)]/[0.03] hover:border-current"
                )}
                style={chipActive ? { background: accent } : { color: accent }}
              >
                {chipActive ? (
                  <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-[var(--on-accent)]/40 border-t-[var(--on-accent)]" />
                ) : (
                  <span>{angleEmoji(angle)}</span>
                )}
                {angle}
              </button>
            );
          })}
          {hiddenCount > 0 && !expanded && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="rounded-full border border-dashed border-[var(--border-strong)] px-2.5 py-1 text-[11px] text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              +{hiddenCount} more
            </button>
          )}
          {!customOpen && (
            <button
              type="button"
              disabled={isDisabled}
              onClick={() => setCustomOpen(true)}
              className="inline-flex items-center gap-1 rounded-full border border-dashed border-[var(--accent)]/40 px-2.5 py-1 text-[11px] font-medium text-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              ➕ Custom Angle
            </button>
          )}
        </div>

        {customOpen && (
          <form onSubmit={handleCustomSubmit} className="mt-2 flex gap-1.5">
            <input
              autoFocus
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              maxLength={CUSTOM_ANGLE_MAX}
              placeholder='e.g. "Generate like a Netflix documentary"'
              disabled={isDisabled}
              className="h-8 flex-1 rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 text-[12px] text-[var(--foreground)] outline-none focus:border-[var(--accent)] disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!customText.trim() || isDisabled}
              className="flex h-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] px-3 text-[12px] font-medium text-[var(--on-accent)] disabled:opacity-40"
            >
              {isCustomActive ? (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--on-accent)]/40 border-t-[var(--on-accent)]" />
              ) : (
                "Generate"
              )}
            </button>
          </form>
        )}
      </div>
    </motion.div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--border)] bg-[var(--foreground)]/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]">
      {children}
    </span>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-[var(--border-strong)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12px] text-[var(--foreground)] outline-none transition-colors focus:border-[var(--accent)]"
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function IconCompass() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M16 8l-2.5 5.5L8 16l2.5-5.5L16 8z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 4v6h6M20 20v-6h-6M4.5 15a8 8 0 0014.9 2.3M19.5 9A8 8 0 004.6 6.7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
