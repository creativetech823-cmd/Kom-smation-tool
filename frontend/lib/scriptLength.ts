import { targetSecondsFor } from "./duration";

/** Named script-length levels, each backed by one of the backend's curated
 * duration buckets (see backend app/services/script_length.py) — so
 * stepping a level sends a real target_word_count grounded in that bucket's
 * tuned word range, not an arbitrary percentage nudge. */
export type ScriptLengthLevel = {
  key: string;
  label: string;
  /** Duration bucket string understood by the backend (target_duration). */
  bucket: string;
  rangeLabel: string;
  /** Representative target word count for a length-adjustment regenerate — video. */
  targetWordCount: number;
  /** Same level, but scaled for static ad copy (headline/body/cta), which
   * runs far shorter than a spoken video script at the same "size". */
  staticTargetWordCount: number;
};

export const SCRIPT_LENGTH_LEVELS: ScriptLengthLevel[] = [
  { key: "very_short", label: "Very Short", bucket: "15s", rangeLabel: "≈ 10–15s", targetWordCount: 27, staticTargetWordCount: 9 },
  { key: "short", label: "Short", bucket: "20s", rangeLabel: "≈ 15–25s", targetWordCount: 52, staticTargetWordCount: 16 },
  { key: "medium", label: "Medium", bucket: "30s", rangeLabel: "≈ 25–40s", targetWordCount: 85, staticTargetWordCount: 26 },
  { key: "long", label: "Long", bucket: "45s", rangeLabel: "≈ 40–60s", targetWordCount: 127, staticTargetWordCount: 41 },
  { key: "very_long", label: "Very Long", bucket: "90s", rangeLabel: "≈ 60–90s", targetWordCount: 195, staticTargetWordCount: 62 },
];

/** Finds the level whose bucket is closest (in seconds) to the given bucket
 * string, so the stepper reflects whatever target_duration is currently set
 * even if it doesn't exactly match one of the four named levels. */
export function scriptLengthIndexForBucket(bucket: string): number {
  const seconds = targetSecondsFor(bucket);
  let bestIndex = 0;
  let bestDiff = Infinity;
  SCRIPT_LENGTH_LEVELS.forEach((level, i) => {
    const diff = Math.abs(targetSecondsFor(level.bucket) - seconds);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestIndex = i;
    }
  });
  return bestIndex;
}
