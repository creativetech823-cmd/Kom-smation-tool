import type { FlatLine } from "./types";

/** Matches backend `script_length.WPM` — keep in sync. */
export const WPM = 165;

export function wordCount(lines: FlatLine[]): number {
  return lines.reduce((sum, l) => sum + l.text.trim().split(/\s+/).filter(Boolean).length, 0);
}

export function estimateSeconds(lines: FlatLine[]): number {
  const words = wordCount(lines);
  return Math.round(((words / WPM) * 60 + Number.EPSILON) * 10) / 10;
}

export function targetSecondsFor(bucket: string): number {
  const match = bucket.match(/\d+/);
  return match ? Number(match[0]) : 30;
}

export type DurationStatus = "good" | "warn" | "bad";

export function durationStatus(estimated: number, targetSeconds: number): DurationStatus {
  if (targetSeconds <= 0) return "good";
  const ratio = Math.abs(estimated - targetSeconds) / targetSeconds;
  if (ratio <= 0.15) return "good";
  if (ratio <= 0.3) return "warn";
  return "bad";
}
