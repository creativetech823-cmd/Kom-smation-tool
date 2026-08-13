// Display metadata for Creative Angles (execution styles — the HOW a story
// is told, distinct from a situation's marketing_angle, the WHY/strategy).
// Mirrors backend/app/services/creative_angles.py by hand, same convention
// used everywhere else in this codebase (no shared codegen). Any label not
// in this map — including arbitrary custom angles — falls back to a
// hash-derived emoji/color so nothing ever renders unstyled.

export const CREATIVE_ANGLE_EMOJI: Record<string, string> = {
  "Emotional Conversation": "\u{1F5E3}\u{FE0F}",
  "Heartbreaking": "\u{1F494}",
  "Father-Son": "\u{1F468}\u{200D}\u{1F466}",
  "Mother's Perspective": "\u{1F469}\u{200D}\u{1F467}",
  "Friendship": "\u{1F91D}",
  "Fear / Scary": "\u{1F480}",
  "Cancer Awareness": "\u{1F397}\u{FE0F}",
  "Hospital / Emergency": "\u{1F6A8}",
  "Doctor Explains": "\u{1FA7A}",
  "Expert Advice": "\u{1F393}",
  "Customer Testimonial": "\u{1F5E8}\u{FE0F}",
  "Doctor Testimonial": "\u{1FA7A}",
  "Celebrity Testimonial": "\u{1F31F}",
  "UGC / Selfie Style": "\u{1F4F1}",
  "Day in My Life / GRWM": "\u{2600}\u{FE0F}",
  "Cinematic Storytelling": "\u{1F3AC}",
  "Viral Trend Style": "\u{1F525}",
  "POV / First Person": "\u{1F441}\u{FE0F}",
  "Meta Glasses POV": "\u{1F453}",
  "Documentary": "\u{1F4D6}",
  "Before vs After": "\u{1F504}",
  "Product Demo": "\u{1F3AF}",
  "Comedy / Satire": "\u{1F602}",
  "Motivation / Transformation": "\u{1F680}",
  "Interview / Podcast": "\u{1F399}\u{FE0F}",
  "Social Experiment / Challenge": "\u{1F9EA}",
};

const FALLBACK_EMOJI = ["\u{1F3A5}", "\u{1F3AC}", "\u{2728}", "\u{1F3AF}", "\u{1F4A1}"];
const ANGLE_ACCENTS = ["var(--accent)", "var(--accent-2)", "var(--indigo)", "var(--magenta)", "var(--success)", "var(--warning)"];

function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  return hash;
}

export function angleEmoji(label: string): string {
  return CREATIVE_ANGLE_EMOJI[label] ?? FALLBACK_EMOJI[hashString(label) % FALLBACK_EMOJI.length];
}

export function angleAccent(label: string): string {
  return ANGLE_ACCENTS[hashString(label) % ANGLE_ACCENTS.length];
}
