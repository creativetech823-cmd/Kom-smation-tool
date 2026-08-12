"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { AiWorkingChecklist } from "@/components/ui/AiWorkingChecklist";
import { cn } from "@/lib/utils";
import type { StorySituation } from "@/lib/types";

type ViralityBucket = "" | "8+" | "6-8" | "<6";

const LOADING_STEPS = [
  { id: "profile", label: "Reading product profile" },
  { id: "personas", label: "Brainstorming personas" },
  { id: "virality", label: "Scoring virality" },
  { id: "finalize", label: "Finalizing story angles" },
];

const CATEGORY_ACCENTS = ["var(--accent)", "var(--accent-2)", "var(--success)", "var(--warning)"];

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
  selectingId,
  onSelect,
  onGenerateMore,
  onBack,
}: {
  situations: StorySituation[];
  loading: boolean;
  generatingMore: boolean;
  selectingId: string | null;
  onSelect: (situation: StorySituation) => void;
  onGenerateMore: () => void;
  onBack: () => void;
}) {
  const [search, setSearch] = useState("");
  const [emotion, setEmotion] = useState("");
  const [persona, setPersona] = useState("");
  const [angle, setAngle] = useState("");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [length, setLength] = useState("");
  const [virality, setVirality] = useState<ViralityBucket>("");

  const options = useMemo(() => {
    const uniq = (values: string[]) => Array.from(new Set(values.filter(Boolean))).sort();
    return {
      emotion: uniq(situations.map((s) => s.emotion)),
      persona: uniq(situations.map((s) => s.persona)),
      angle: uniq(situations.map((s) => s.marketing_angle)),
      category: uniq(situations.map((s) => s.category)),
      difficulty: uniq(situations.map((s) => s.difficulty)),
      length: uniq(situations.map((s) => s.estimated_length)),
    };
  }, [situations]);

  const filtersActive =
    search.trim() !== "" ||
    emotion !== "" ||
    persona !== "" ||
    angle !== "" ||
    category !== "" ||
    difficulty !== "" ||
    length !== "" ||
    virality !== "";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return situations.filter((s) => {
      if (
        q &&
        !`${s.title} ${s.description} ${s.emotion} ${s.persona} ${s.marketing_angle} ${s.category}`
          .toLowerCase()
          .includes(q)
      )
        return false;
      if (emotion && s.emotion !== emotion) return false;
      if (persona && s.persona !== persona) return false;
      if (angle && s.marketing_angle !== angle) return false;
      if (category && s.category !== category) return false;
      if (difficulty && s.difficulty !== difficulty) return false;
      if (length && s.estimated_length !== length) return false;
      if (!matchesBucket(s.virality_score, virality)) return false;
      return true;
    });
  }, [situations, search, emotion, persona, angle, category, difficulty, length, virality]);

  function clearFilters() {
    setSearch("");
    setEmotion("");
    setPersona("");
    setAngle("");
    setCategory("");
    setDifficulty("");
    setLength("");
    setVirality("");
  }

  const anySelecting = selectingId !== null;

  return (
    <Card glow>
      <CardHeader
        title="Choose Your Story"
        subtitle="AI-generated marketing angles. Pick one to generate the full cinematic script."
        icon={<IconCompass />}
      />
      <CardBody className="space-y-5">
        {!loading && situations.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search doctor, mother, gym, fear..."
              className="!w-auto min-w-[200px] flex-1 !py-1.5 !text-[13px]"
            />
            <FilterSelect label="Emotion" value={emotion} onChange={setEmotion} options={options.emotion} />
            <FilterSelect label="Persona" value={persona} onChange={setPersona} options={options.persona} />
            <FilterSelect label="Angle" value={angle} onChange={setAngle} options={options.angle} />
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
                    const isSelecting = selectingId === s.id;
                    const isDisabled = anySelecting && !isSelecting;
                    return (
                      <motion.div
                        key={s.id}
                        layout
                        variants={cardVariants}
                        exit="exit"
                        role="button"
                        tabIndex={0}
                        onClick={() => !anySelecting && onSelect(s)}
                        onKeyDown={(e) => {
                          if ((e.key === "Enter" || e.key === " ") && !anySelecting) {
                            e.preventDefault();
                            onSelect(s);
                          }
                        }}
                        className={cn(
                          "relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 p-4 backdrop-blur-xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
                          isSelecting
                            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                            : "cursor-pointer hover:border-[var(--accent)]/50 hover:bg-white/[0.02]",
                          isDisabled && "pointer-events-none opacity-50"
                        )}
                      >
                        <span
                          className="absolute inset-x-0 top-0 h-[3px]"
                          style={{ background: categoryAccent(s.category) }}
                        />

                        <div className="mb-2.5 flex items-center justify-between gap-2">
                          <Badge tone="accent">{s.category}</Badge>
                          <Badge tone={viralityTone(s.virality_score)}>
                            ⚡ {s.virality_score.toFixed(1)}/10
                          </Badge>
                        </div>

                        <h3 className="text-[15px] font-semibold leading-snug text-[var(--foreground)]">
                          {s.title}
                        </h3>
                        <p className="mt-1 line-clamp-3 text-[13px] leading-snug text-[var(--muted)]">
                          {s.description}
                        </p>

                        <div className="mt-3 flex flex-wrap gap-1.5">
                          <Chip>🎭 {s.emotion}</Chip>
                          <Chip>👤 {s.persona}</Chip>
                          <Chip>🎯 {s.marketing_angle}</Chip>
                        </div>

                        <div className="mt-3.5 flex items-center justify-between">
                          <div className="flex gap-1.5">
                            <Badge tone="neutral">{cap(s.difficulty)}</Badge>
                            <Badge tone="neutral">{s.estimated_length}</Badge>
                          </div>
                          <span className="text-[12px] font-medium text-[var(--accent-2)]">Select →</span>
                        </div>

                        {isSelecting && (
                          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-2xl bg-[var(--surface)]/90 px-4 text-center backdrop-blur-sm">
                            <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-[var(--accent)]" />
                            <p className="text-[12px] text-[var(--foreground)]">
                              Directing your script for &ldquo;{s.title}&rdquo;...
                            </p>
                          </div>
                        )}
                      </motion.div>
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

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-[var(--border)] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-[var(--muted)]">
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
