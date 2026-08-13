"""Curated "Creative Angle" (execution style) catalog — the HOW a story is
told, distinct from a StorySituation's marketing_angle (the WHY/strategy).

Deduplicated from a much larger brainstormed list that mixed category names
and example items together. Kept as plain labels (not ids) — every other
filterable field on StorySituation is a plain string, and labels avoid a
frontend id->label resolution step a typo could silently break.
"""

CREATIVE_ANGLES: list[dict[str, str]] = [
    {"label": "Emotional Conversation", "emoji": "\U0001F5E3️", "category": "Emotional & Family"},
    {"label": "Heartbreaking", "emoji": "\U0001F494", "category": "Emotional & Family"},
    {"label": "Father-Son", "emoji": "\U0001F468‍\U0001F466", "category": "Emotional & Family"},
    {"label": "Mother's Perspective", "emoji": "\U0001F469‍\U0001F467", "category": "Emotional & Family"},
    {"label": "Friendship", "emoji": "\U0001F91D", "category": "Emotional & Family"},
    {"label": "Fear / Scary", "emoji": "\U0001F480", "category": "Fear & Awareness"},
    {"label": "Cancer Awareness", "emoji": "\U0001F397️", "category": "Fear & Awareness"},
    {"label": "Hospital / Emergency", "emoji": "\U0001F6A8", "category": "Fear & Awareness"},
    {"label": "Doctor Explains", "emoji": "\U0001FA7A", "category": "Educational & Expert"},
    {"label": "Expert Advice", "emoji": "\U0001F393", "category": "Educational & Expert"},
    {"label": "Customer Testimonial", "emoji": "\U0001F5E8️", "category": "Testimonial"},
    {"label": "Doctor Testimonial", "emoji": "\U0001FA7A", "category": "Testimonial"},
    {"label": "Celebrity Testimonial", "emoji": "\U0001F31F", "category": "Testimonial"},
    {"label": "UGC / Selfie Style", "emoji": "\U0001F4F1", "category": "UGC & Personal"},
    {"label": "Day in My Life / GRWM", "emoji": "☀️", "category": "UGC & Personal"},
    {"label": "Cinematic Storytelling", "emoji": "\U0001F3AC", "category": "Storytelling"},
    {"label": "Viral Trend Style", "emoji": "\U0001F525", "category": "Social / Viral"},
    {"label": "POV / First Person", "emoji": "\U0001F441️", "category": "POV & Camera"},
    {"label": "Meta Glasses POV", "emoji": "\U0001F453", "category": "POV & Camera"},
    {"label": "Documentary", "emoji": "\U0001F4D6", "category": "Documentary"},
    {"label": "Before vs After", "emoji": "\U0001F504", "category": "Sales"},
    {"label": "Product Demo", "emoji": "\U0001F3AF", "category": "Sales"},
    {"label": "Comedy / Satire", "emoji": "\U0001F602", "category": "Comedy"},
    {"label": "Motivation / Transformation", "emoji": "\U0001F680", "category": "Motivation"},
    {"label": "Interview / Podcast", "emoji": "\U0001F399️", "category": "Interview & Talk"},
    {"label": "Social Experiment / Challenge", "emoji": "\U0001F9EA", "category": "Social Experiment"},
]

_DEFAULT_FALLBACK_LABELS = ["Emotional Conversation", "UGC / Selfie Style", "Documentary"]

_NORMALIZED_LOOKUP: dict[str, str] = {entry["label"].strip().lower(): entry["label"] for entry in CREATIVE_ANGLES}


def catalog_prompt_block() -> str:
    """The vocabulary listing injected into the story-situations system prompt."""
    return "\n".join(f"- {entry['label']} ({entry['category']})" for entry in CREATIVE_ANGLES)


def valid_angle_labels(candidates: list[str]) -> list[str]:
    """Drop anything not in the known catalog (case/whitespace-insensitive),
    de-duplicating while preserving order. Falls back to a small generic
    subset if nothing survives, so a situation is never left with zero angles."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in candidates:
        canonical = _NORMALIZED_LOOKUP.get(raw.strip().lower())
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result or list(_DEFAULT_FALLBACK_LABELS)
