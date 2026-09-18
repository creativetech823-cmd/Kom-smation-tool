"""Post-generation creative quality gate — Stage 6's cheap, mostly-local
second opinion on its own output, separate from Stage 7's compliance audit
(compliance_service.py checks legal/claim risk on a user-triggered pass;
this checks creative genericness automatically, inline, right after
generation).

Layer 1 (deterministic, free, always runs): banned-phrase/cliche detection,
structural sanity (missing hook/cta, empty body, duplicate lines), and a
product-relevance keyword proxy. BANNED_PHRASES here is the single source of
truth — script_service.py's system prompt is built FROM this list rather
than keeping a second hand-written copy in sync.

Layer 2 (one small LLM call, JSON mode, only when Layer 1 found nothing and
the caller opts in): the semantic checks a regex genuinely cannot make —
hook payoff, feature-dumping, audience relevance, CTA fit, claim safety.
Kept deliberately small and separate from the full script-writing prompt so
it stays cheap.

Callers (script_service.py) turn the returned issue codes into ONE targeted
rewrite instruction via rewrite_reason() and do at most one rewrite pass —
this module never calls back into script generation itself.
"""

import json
import logging
import re

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("script_quality")

# Canonical banned-phrase list — substring match, case-insensitive. Also the
# source script_service._banned_phrases_prose() renders into the generation
# system prompt, so the writer and the checker never drift apart.
BANNED_PHRASES: list[str] = [
    "game changer",
    "game-changer",
    "revolutionary",
    "revolutionize",
    "transform your",
    "unlock the power",
    "elevate your",
    "unleash",
    "seamlessly",
    "journey to a better you",
    "say goodbye to",
    "say hello to",
    "in today's fast-paced world",
    "in today's busy world",
    "in today's world",
    "here's the thing",
    "but wait",
    "you won't believe",
    "did you know",
    "here's why",
    "everyone wants",
    "now you can",
    "looking for the best",
    "it's time to",
    "ultimate solution",
    "perfect solution",
    "amazing product",
    "incredible product",
    "best ever",
    "must-have",
    "must have",
    "don't miss out",
    # Hinglish equivalents of the same AI-cliche patterns above — a
    # transliterated cliche is still a cliche, just missed by an
    # English-only list otherwise.
    "potential unlock",
    "apna potential",
    "apni potential",
    "unlock karo",
    "zindagi badal",
    "life badal do",
    # Generic-opener patterns (AHM Creative DNA §2/§5) — an ad that could be
    # for any product/brand in this category, not this one specifically.
    "every mother wants",
    "we all know health is important",
    "your child's health matters",
    "take care of your family",
    "health is wealth",
    "because your health matters",
    "in today's fast paced life",
]

# Patterns that need a wildcard, not a plain substring.
_BANNED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\btake your .{1,40} to the next level\b", re.IGNORECASE),
]

# Filmable-format fix (2026-09-18 task) — "AI-copy quality" signal stems: a
# script that leans on Hinglish abstraction/explanation phrasing instead of
# showing behavior. Deliberately NOT added to BANNED_PHRASES: a single
# occurrence of any of these is fine (some are ordinary words — "familiar",
# "ritual" — that show up in perfectly natural lines), this is a DENSITY
# signal, not a hard filter. Only a script genuinely DOMINATED by them (see
# _detect_explanatory_language_overuse) is flagged.
_EXPLANATORY_LANGUAGE_SIGNALS: list[str] = [
    "aadat",
    "ye sirf",
    "yeh sirf",
    "iska matlab",
    "yahi",
    "ab samajh",
    "choice badal",
    "habit ko support",
    "familiar",
    "refreshing",
    "ritual",
    "direction",
]


def _detect_explanatory_language_overuse(texts: list[str]) -> bool:
    """True when the script is DOMINATED by explanatory/abstract phrasing
    rather than shown behavior — at least 2 lines match AND at least 40% of
    all non-empty lines match. Both thresholds exist so a short script
    (few lines) still needs genuine repetition, not one unlucky line, and a
    long script needs a real proportion, not just an absolute count."""
    non_empty = [t for t in texts if t.strip()]
    if not non_empty:
        return False
    matched = sum(1 for t in non_empty if any(sig in t.lower() for sig in _EXPLANATORY_LANGUAGE_SIGNALS))
    return matched >= 2 and (matched / len(non_empty)) >= 0.4


# Filmable hard-gate fix (2026-09-18 task, follow-up to the filmable-format
# prompt/schema task) — a script can pass every other check (no banned
# phrases, real scene labels, real dialogue) while still being fundamentally
# an explanation dressed as scenes, because those checks judge TEXT content,
# never whether the body actually carries physical/visual behavior anywhere.
# This check is deliberately structural, not a second abstract-language
# denylist: it trusts the SAME action/reaction/visual_direction fields the
# generation prompt now fills with concrete physical behavior — their
# PRESENCE across the body is the evidence, using the structured fields as
# the PRIMARY signal (exactly as specified) rather than keyword-matching
# "physical behavior" across Hindi/Hinglish/English text, which a fixed verb
# list could never reliably do across languages.
#
# This also implicitly covers "creative mechanism named only in dialogue/
# explanation, never dramatized" without a second detector: a mechanism
# that's actually dramatized necessarily shows up as action/reaction/
# visual_direction content somewhere in the body — a mechanism that's only
# explained in a line of dialogue does not. Reuses the existing creative-
# mechanism metadata's downstream effect rather than inventing a separate
# mechanism-specific architecture.
_FILMABILITY_MIN_CONCRETE_RATIO = 0.4
_FILMABILITY_MIN_SUBSTANTIVE_LINES = 2


def _video_body_is_filmable(body: list) -> bool:
    """True (filmable, no issue) when the body has enough structural
    evidence of physical/visual storytelling. Fails OPEN — returns True —
    for a body too short to judge meaningfully (fewer than 2 substantive
    lines); this is about DOMINANCE of explanation across the body as a
    whole, never a per-line requirement, so a script that's mostly action/
    visual with a couple of plain dialogue-only lines is expected to pass,
    and so is a script with sparse dialogue but strong visual/action
    coverage — evaluating the body as a whole is the point, not counting
    every field on every line."""
    lines = [b for b in body if isinstance(b, dict)]
    substantive = [b for b in lines if (b.get("text") or "").strip() or (b.get("visual_direction") or "").strip()]
    if len(substantive) < _FILMABILITY_MIN_SUBSTANTIVE_LINES:
        return True
    concrete = sum(
        1 for b in substantive
        if (b.get("action") or "").strip() or (b.get("reaction") or "").strip() or (b.get("visual_direction") or "").strip()
    )
    return (concrete / len(substantive)) >= _FILMABILITY_MIN_CONCRETE_RATIO


# The 17 canonical creative-mechanism labels — single source of truth. The
# generation prompt's CREATIVE MECHANISM step is rendered FROM this list
# (script_service._creative_mechanisms_prose()), and every self-reported
# value is normalized against it before a GeneratedScript is ever returned,
# so an unknown/off-list value the model happens to produce (e.g. the free
# word "transformation" instead of the canonical "before_after") can never
# leak into avoid_repeating_mechanism or stored state.
CREATIVE_MECHANISMS: list[str] = [
    "pattern_interrupt",
    "curiosity_gap",
    "contrarian_insight",
    "confession",
    "pov",
    "social_observation",
    "mini_story",
    "before_after",
    "problem_insight",
    "demonstration",
    "comparison",
    "testimonial_style",
    "dialogue",
    "challenge",
    "myth_busting",
    "emotional_story",
    "question",
]
_CREATIVE_MECHANISM_SET = set(CREATIVE_MECHANISMS)

# Safe fallback when a returned value can't be mapped to anything canonical.
DEFAULT_MECHANISM = "curiosity_gap"

# Deterministic synonym/near-miss -> canonical mapping for values the model
# sometimes reaches for that aren't on the list but have an obvious match.
# Checked after exact-match normalization fails, before the keyword-contains
# fallback below.
_MECHANISM_SYNONYMS: dict[str, str] = {
    "transformation": "before_after",
    "transformation_story": "before_after",
    "emotional_transformation": "emotional_story",
    "relatable_moment": "social_observation",
    "relatable": "social_observation",
    "story": "mini_story",
    "storytelling": "mini_story",
    "narrative": "mini_story",
    "insight": "problem_insight",
    "curiosity": "curiosity_gap",
    "contrarian": "contrarian_insight",
    "myth_bust": "myth_busting",
    "ugc": "testimonial_style",
    "point_of_view": "pov",
    "first_person": "pov",
}

# Last-resort keyword-contains fallback — order matters, first match wins.
_MECHANISM_KEYWORDS: list[tuple[str, str]] = [
    ("transform", "before_after"),
    ("before", "before_after"),
    ("after", "before_after"),
    ("emotion", "emotional_story"),
    ("confess", "confession"),
    ("contrari", "contrarian_insight"),
    ("myth", "myth_busting"),
    ("challenge", "challenge"),
    ("compar", "comparison"),
    ("demo", "demonstration"),
    ("testimonial", "testimonial_style"),
    ("dialog", "dialogue"),
    ("social", "social_observation"),
    ("relatable", "social_observation"),
    ("pov", "pov"),
    ("first_person", "pov"),
    ("problem", "problem_insight"),
    ("insight", "problem_insight"),
    ("pattern", "pattern_interrupt"),
    ("interrupt", "pattern_interrupt"),
    ("stor", "mini_story"),  # story, storytelling, narrative-ish
    ("curio", "curiosity_gap"),
    ("question", "question"),
]


def normalize_creative_mechanism(raw: str) -> str:
    """Maps whatever the model self-reported to a guaranteed-canonical
    label from CREATIVE_MECHANISMS. Purely deterministic (no LLM call):
    exact match (case/whitespace-insensitive) -> known synonym -> keyword
    heuristic -> DEFAULT_MECHANISM. Always returns a value in
    CREATIVE_MECHANISM_SET, never the raw input verbatim if it's off-list."""
    if not raw or not isinstance(raw, str):
        return DEFAULT_MECHANISM

    cleaned = re.sub(r"[\s-]+", "_", raw.strip().lower()).strip("_")
    if cleaned in _CREATIVE_MECHANISM_SET:
        return cleaned
    if cleaned in _MECHANISM_SYNONYMS:
        return _MECHANISM_SYNONYMS[cleaned]
    for keyword, mechanism in _MECHANISM_KEYWORDS:
        if keyword in cleaned:
            return mechanism
    return DEFAULT_MECHANISM

# Loose signals of an ungrounded factual claim — deliberately broad (some
# false positives are fine; the cost of missing a real one is higher). Not
# cross-referenced against the given product data by default (see
# claim_grounded_in_product_data) — an unmatched hit routes to a rewrite
# that's told to keep the claim only if genuinely supported.
#
# Split into two groups: "authority" phrases that are almost never
# legitimate in a self-written ad script (clinical/medical/regulatory
# language, guarantees), and "outcome" claims — a specific, quantified, or
# absolute result. A bare ingredient name or a soft verb ("helps", "supports",
# "designed for") is never enough on its own to trigger this; it takes an
# actual timeframe, percentage, or absolute-outcome word.
_CLAIM_PATTERNS: list[re.Pattern] = [
    # Authority / regulatory / guarantee language
    re.compile(r"\bclinically\s+proven\b", re.IGNORECASE),
    re.compile(r"\bdoctor[s]?\s+recommend", re.IGNORECASE),
    re.compile(r"\bfda\s+approved\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\b", re.IGNORECASE),
    re.compile(r"\bstudies show\b", re.IGNORECASE),
    re.compile(r"\bproven to\b", re.IGNORECASE),
    re.compile(r"\baward[- ]winning\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+out of\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b100%\s*effective\b", re.IGNORECASE),
    re.compile(r"\bresults?\s+guaranteed\b", re.IGNORECASE),
    # Quantified efficacy: a percentage, or a specific timeframe attached to
    # a result ("in 2 weeks", "within 7 days") — the exact shape of the
    # reported "fades dark spots in 2 weeks" failure.
    re.compile(r"\d+\s?%"),
    re.compile(r"\b(in|within)\s+(just\s+)?\d+\s*(day|days|week|weeks|month|months)\b", re.IGNORECASE),
    # Absolute/definitive outcome or medical-treatment verbs — these claim a
    # complete, guaranteed, or medical result, not a supported/contributes-to
    # framing. Deliberately excludes soft verbs (helps, supports, aids,
    # designed for, formulated with) which are never flagged on their own.
    re.compile(r"\bcures?\b", re.IGNORECASE),
    re.compile(r"\bcure\s+for\b", re.IGNORECASE),
    re.compile(r"\bheals?\b", re.IGNORECASE),
    re.compile(r"\bprevents?\b", re.IGNORECASE),
    re.compile(r"\beliminates?\b", re.IGNORECASE),
    re.compile(r"\breverses?\b", re.IGNORECASE),
    re.compile(r"\berases?\b", re.IGNORECASE),
    re.compile(r"\bremoves?\s+(pigmentation|dark\s+spots?|wrinkles?|acne|scars?|blemish(es)?)\b", re.IGNORECASE),
    re.compile(r"\bworks?\s+instantly\b", re.IGNORECASE),
    re.compile(r"\binstant(ly)?\s+results?\b", re.IGNORECASE),
    # Wellness/performance-specific outcome claims — a multiplier or a
    # hormone/medical-outcome claim, not a soft "helps"/"supports" framing.
    re.compile(r"\b(doubles?|triples?|2x|3x)\s+(your\s+)?(stamina|energy|strength|endurance)\b", re.IGNORECASE),
    re.compile(r"\b(boosts?|increases?)\s+testosterone\b", re.IGNORECASE),
    re.compile(r"\bpermanently\s+(removes?|eliminates?|cures?|fixes?)\b", re.IGNORECASE),
    re.compile(r"\bremoves?\s+fatigue\b", re.IGNORECASE),
]


def _block_texts(data: dict) -> list[str]:
    texts: list[str] = []
    hook = data.get("hook")
    if isinstance(hook, dict):
        texts.append(str(hook.get("text") or ""))
    for line in data.get("body") or []:
        if isinstance(line, dict):
            texts.append(str(line.get("text") or ""))
    cta = data.get("cta")
    if isinstance(cta, dict):
        texts.append(str(cta.get("text") or ""))
    return texts


def _significant_tokens(*phrases: str) -> set[str]:
    tokens: set[str] = set()
    for phrase in phrases:
        for word in re.findall(r"[A-Za-z]{4,}", phrase or ""):
            tokens.add(word.lower())
    return tokens


# Deterministic safety net for AHM Creative DNA §8 ("do not overfit to
# Herbal Masala") — the insight/hook/outline prompts already carry an
# explicit instruction not to default to these terms, but a model can still
# drift, so this catches it after the fact for any product whose category
# genuinely has nothing to do with tobacco/gutka.
_CATEGORY_OVERFIT_TERMS = [
    "gutka", "gutkha", "tobacco", "paan masala", "pan masala", "pan shop", "paan shop",
    "supari", "quitting addiction", "quit smoking", "chewing tobacco",
]
_TOBACCO_CATEGORY_SIGNALS = ("tobacco", "gutka", "gutkha", "pan masala", "paan masala", "supari")


def category_overfit_terms_present(text: str, product_category: str, brief_text: str = "") -> list[str]:
    """Returns which banned surface-content terms appear in `text`, but only
    when this product genuinely ISN'T tobacco/gutka-related — checked
    against `product_category` AND `brief_text` (product name/target
    audience/USP/benefits), not the category string alone. A product can be
    stored under a generic category label (e.g. the Product Library's
    "herbal_health") while its actual given audience/brief genuinely is
    gutka/tobacco habit-replacement — in that case this must NOT strip the
    correct content back out."""
    category_low = (product_category or "").lower()
    brief_low = (brief_text or "").lower()
    if any(sig in category_low for sig in _TOBACCO_CATEGORY_SIGNALS) or any(
        sig in brief_low for sig in _TOBACCO_CATEGORY_SIGNALS
    ):
        return []
    low = text.lower()
    return [term for term in _CATEGORY_OVERFIT_TERMS if term in low]


# Ingredient-dumping (AHM Creative DNA §6): a line that just lists product
# ingredients/features joined by commas/"and", with no surrounding sentence
# connecting them to a story beat — "Contains Amlaki, Elderberry, Echinacea
# and many natural ingredients" — the exact failure pattern named in the brief.
_INGREDIENT_DUMP_PATTERN = re.compile(
    r"\b(contains?|ingredients?|made with|formulated with|packed with)\b"
    r"[^.!?]{0,15}([A-Za-z][A-Za-z\s]{1,20},\s*){2,}[A-Za-z][A-Za-z\s]{1,20}\b(and|&)\b",
    re.IGNORECASE,
)


# Per-ingredient benefit-attachment signals — when each ingredient in a list
# is immediately followed by its own reason ("Mulethi for natural
# sweetness, Amla for freshness..."), that is the "name it, then its
# one-line benefit" pattern the generation prompt's own _VOICE_STRUCTURE_GUIDE
# explicitly recommends — NOT the bare "contains X, Y, Z" dump this check
# exists to catch. Only a list where ingredients genuinely outnumber
# attached benefit phrases counts as a real dump.
_BENEFIT_ATTACHMENT_SIGNALS = re.compile(
    r"\bfor\b|\bke liye\b|\bjo\b|\bhelps?\b|\bsupports?\b|\bkarta hai\b|\bkarti hai\b|\bfor\b", re.IGNORECASE
)


def _has_ingredient_dump(text: str, given_ingredients: list[str]) -> bool:
    if _INGREDIENT_DUMP_PATTERN.search(text):
        return True
    if len(given_ingredients) < 3:
        return False
    # Or: 3+ of the ACTUAL given ingredient names crammed into one short
    # (<20 word) span, with fewer attached benefit phrases than ingredients
    # (i.e. at least one ingredient has no reason attached — a real dump,
    # not the recommended "ingredient -> one-line benefit" parallel pattern).
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = sentence.split()
        if len(words) > 20:
            continue
        hits = sum(1 for ing in given_ingredients if ing.lower() in sentence.lower())
        if hits < 3:
            continue
        benefit_signals = len(_BENEFIT_ATTACHMENT_SIGNALS.findall(sentence))
        if benefit_signals < hits:
            return True
    return False


def claim_grounded_in_product_data(payload) -> bool:
    """True if the SUPPLIED product data itself already contains
    claim-shaped language (a timeframe, a percentage, or one of the
    absolute-outcome words) — i.e. the user/reference extraction actually
    gave us that specific claim, so the script repeating it isn't invented.
    Coarse (doesn't match the exact same claim, just that claim-shaped
    language exists somewhere in the given data) but keeps this a cheap,
    deterministic check rather than a second LLM call."""
    p = getattr(payload, "structured_product", None)
    if p is None:
        return False
    source = " ".join([p.usp or ""] + list(p.key_benefits or []))
    return any(pattern.search(source) for pattern in _CLAIM_PATTERNS)


def text_issues(text: str) -> list[str]:
    """Free-text-only checks (banned phrases + claim patterns) — no
    structural or product-relevance checks, since those need the full
    script/payload. Shared by the whole-script gate and the narrow-scope
    (single-block) gate so the same rules apply everywhere."""
    issues: list[str] = []
    low = text.lower()
    if any(phrase in low for phrase in BANNED_PHRASES) or any(p.search(text) for p in _BANNED_PATTERNS):
        issues.append("generic_language")
    if any(p.search(text) for p in _CLAIM_PATTERNS):
        issues.append("unsupported_claim")
    return issues


def deterministic_issues(data: dict, payload) -> list[str]:
    """Free, regex/keyword-only checks over the WHOLE script. No API call.
    Returns issue codes — empty list means Layer 1 found nothing (caller
    may still run Layer 2)."""
    texts = _block_texts(data)
    combined = " ".join(texts)
    combined_low = combined.lower()
    content_type = getattr(payload, "content_type", "video")

    issues = text_issues(combined)
    if "unsupported_claim" in issues and claim_grounded_in_product_data(payload):
        issues = [i for i in issues if i != "unsupported_claim"]

    if _detect_explanatory_language_overuse(texts):
        issues.append("explanatory_language_overuse")

    # Video-only structural checks — several static formats (thumbnail,
    # quote_graphic) legitimately ship an empty body or empty cta.
    if content_type != "static":
        hook_text = (data.get("hook") or {}).get("text", "") if isinstance(data.get("hook"), dict) else ""
        cta_text = (data.get("cta") or {}).get("text", "") if isinstance(data.get("cta"), dict) else ""
        if not hook_text.strip():
            issues.append("missing_hook")
        if not cta_text.strip():
            issues.append("missing_cta")
        body = data.get("body") or []
        if not body:
            issues.append("empty_body")
        elif not _video_body_is_filmable(body):
            issues.append("not_filmable_video")

    non_empty = [t.strip() for t in texts if t.strip()]
    if len(non_empty) != len(set(non_empty)) and len(non_empty) > 1:
        issues.append("duplicate_lines")

    product_category = getattr(payload, "product_category", "")
    p = getattr(payload, "structured_product", None)
    brief_text = " ".join(
        [
            getattr(p, "target_audience", "") or "",
            getattr(p, "usp", "") or "",
            " ".join(getattr(p, "key_benefits", []) or []),
        ]
    ) if p is not None else ""
    if category_overfit_terms_present(combined, product_category, brief_text):
        issues.append("category_overfit")

    if p is not None:
        tokens = _significant_tokens(p.product_name, *p.ingredients, *p.key_benefits, p.usp)
        if tokens and not any(t in combined_low for t in tokens):
            issues.append("weak_product_relevance")
        if p.ingredients and any(_has_ingredient_dump(t, p.ingredients) for t in texts):
            issues.append("ingredient_dump")

    hook_text = texts[0].strip() if texts else ""
    if hook_text and p is not None and p.product_name:
        first_words = hook_text.split()[:5]
        if any(tok.lower() in " ".join(first_words).lower() for tok in _significant_tokens(p.product_name)):
            issues.append("product_first_hook")

    return issues


def scope_changed_text(data: dict, scope: str, target_scene_label: str = "") -> str:
    """The text a given narrow regenerate scope is actually allowed to
    change — so the narrow-scope safety gate only checks (and can only ask
    to fix) what that scope owns, never flagging a pre-existing issue in a
    block the current edit wasn't meant to touch."""
    hook_text = (data.get("hook") or {}).get("text", "") if isinstance(data.get("hook"), dict) else ""
    cta_text = (data.get("cta") or {}).get("text", "") if isinstance(data.get("cta"), dict) else ""
    body = [b for b in (data.get("body") or []) if isinstance(b, dict)]

    if scope == "hook":
        return hook_text
    if scope == "cta":
        return cta_text
    if scope in ("science", "story"):
        return " ".join(b.get("text", "") for b in body if b.get("section") == scope)
    if scope == "product_explanation":
        return " ".join(b.get("text", "") for b in body if b.get("section") in ("product_intro", "ingredients"))
    if scope == "specific_scene":
        return " ".join(b.get("text", "") for b in body if b.get("scene_label") == target_scene_label)
    if scope == "emotional_tone":
        # Touches every block's text — same surface as a full-script check.
        return " ".join([hook_text] + [b.get("text", "") for b in body] + [cta_text])
    return ""


def enforce_narrow_scope(original: dict, rewritten: dict, scope: str, target_scene_label: str = "") -> dict:
    """Deterministically enforces the narrow-scope contract ("Improve Hook
    changes ONLY the hook") regardless of whether the model actually
    complied — a targeted-rewrite pass can drift and touch other blocks
    despite being told not to, so this forces every block outside the
    scope's ownership back to its pre-rewrite value. emotional_tone is the
    one scope that legitimately owns every block, so it's returned as-is."""
    if scope == "emotional_tone":
        return rewritten
    merged = dict(original)
    if scope == "hook":
        merged["hook"] = rewritten.get("hook", original.get("hook"))
        return merged
    if scope == "cta":
        merged["cta"] = rewritten.get("cta", original.get("cta"))
        return merged

    original_body = [b for b in (original.get("body") or []) if isinstance(b, dict)]
    rewritten_body = [b for b in (rewritten.get("body") or []) if isinstance(b, dict)]
    if len(original_body) != len(rewritten_body):
        # The model changed the block count despite instructions not to —
        # can't safely merge index-by-index, so trust the rewrite wholesale
        # rather than silently dropping content.
        return rewritten

    def owns(block: dict) -> bool:
        if scope in ("science", "story"):
            return block.get("section") == scope
        if scope == "product_explanation":
            return block.get("section") in ("product_intro", "ingredients")
        if scope == "specific_scene":
            return block.get("scene_label") == target_scene_label
        return False

    merged["body"] = [
        rw_block if owns(orig_block) else orig_block
        for orig_block, rw_block in zip(original_body, rewritten_body)
    ]
    return merged


_EVAL_SYSTEM_PROMPT = """You are a strict but fair creative-quality auditor for a short-form ad
script pipeline. You did not write this script — you're reviewing someone else's draft against a
short checklist. Be honest and specific: most drafts are actually fine and should pass, so don't
invent problems to seem thorough.

Do NOT penalize simplicity — a short, sharp, simple script is not a defect. Only flag a real
problem, and only from this exact list of codes:
- "weak_hook": the hook doesn't create real curiosity, or is interchangeable with any product
- "hook_no_payoff": the hook opens a promise/question the body never actually answers
- "feature_dump": lists benefits/features without one central creative idea connecting them
- "weak_product_relevance": the product feels stuffed in, or this script would work for almost
  any unrelated product with no meaningful change
- "weak_audience_relevance": vague "everyone" language instead of a concrete situation this exact
  audience would recognize
- "disconnected_flow": beats feel like unrelated sentences rather than one script going somewhere
- "weak_cta": a reflexive "buy now"/"try it today" close that doesn't match the story/tone
- "unnatural_language": for Hindi/Hinglish, reads like a stiff translation, not natural spoken
  language a real person would use on camera
- "format_mismatch": doesn't fit the requested format's real conventions (e.g. a static creative
  written as a spoken monologue)
- "unsupported_claim": a specific outcome/efficacy claim (a result, a timeframe, a percentage, a
  medical/absolute claim) that ISN'T stated in the given ingredients/benefits/USP below — the mere
  presence of an ingredient is not proof of a specific outcome. Do NOT flag ordinary benefit
  language ("helps", "supports", "designed for", naming a given ingredient/benefit) — only flag a
  claim that goes beyond what was actually given.
- "competitor_swappable": this exact script (with only the brand/product name swapped) could run
  unchanged for a directly competing product with a different real formulation — nothing in the
  hook, story, or benefits is actually specific to THIS product's given facts.
- "interchangeable_beats": two or more body beats could swap order (or be deleted) without the
  story losing meaning or causal logic — a checklist of points rather than a sequence where each
  beat happens BECAUSE of the one before it.
- "filler_padding": length was added by restating an already-made point in different words, a
  generic motivational line, or repeating the product name, rather than a genuinely new beat
  (situation, objection, escalation, proof, consequence, or emotional turn).
- "generic_insight": the story's underlying premise is a restated category-level truth ("parents
  want their kids healthy") rather than a specific, narrow, recognizable human situation.
- "generic_creative_premise": strip away the wording — the underlying idea is still just "problem,
  then product, then benefit" with no specific situation, device, or reversal driving it.
- "slogan_as_hook": the hook reads like a title or tagline for the ad (e.g. a short capitalized
  phrase) rather than a real line, moment, or piece of dialogue a viewer would actually hear/see.
- "explains_instead_of_shows": a line of dialogue or narration STATES the ad's underlying insight or
  metaphor directly (e.g. "the habit isn't just the packet, it's the whole ritual of reach, break,
  and familiar taste") rather than a real person reacting, teasing, questioning, hesitating, noticing
  something, or revealing character — it reads like a creative strategist explaining the concept, not
  a character speaking. Do NOT flag ordinary, simple, natural dialogue just for being plain.
- "generic_ai_ad": step back and judge the WHOLE script the way a creative director reviewing it
  against this brand's actual real, proven ad scripts would — not any single line, the overall feel.
  Flag this when the script reads like competent-but-generic AI ad copy rather than something that
  could sit alongside this brand's real winning references: a WINNING REFERENCE/STRUCTURAL REFERENCE
  block was given below but the script's actual idea doesn't reflect its level of specificity (no real
  hook device, no real human insight, no real proof device, no earned payoff — just a pleasant-sounding
  situation with a product dropped into it), OR the situation is so generic that it could be reskinned
  for a completely different product/brand in this category with almost no change. This is a holistic
  judgment call, not a checklist — only flag it when the script genuinely feels like it doesn't belong
  in the same creative universe as the reference, not for merely being simple or short.

Return ONLY this JSON, no prose, no markdown fences:
{"pass": boolean, "issues": [string]}
pass=true and issues=[] when the script is genuinely fine."""


def _build_eval_user_message(data: dict, payload) -> str:
    p = getattr(payload, "structured_product", None)
    s = getattr(payload, "selected_situation", None)
    hook_text = (data.get("hook") or {}).get("text", "")
    body_texts = [b.get("text", "") for b in (data.get("body") or []) if isinstance(b, dict)]
    cta_text = (data.get("cta") or {}).get("text", "")
    selected_hook = getattr(payload, "selected_hook_text", "") or "(none — AI wrote its own opening)"

    return (
        f"Product: {getattr(p, 'product_name', 'unknown')}\n"
        f"Target audience: {getattr(p, 'target_audience', 'unknown')}\n"
        f"Given ingredients: {', '.join(getattr(p, 'ingredients', []) or []) or 'none given'}\n"
        f"Given benefits/USP: {', '.join(getattr(p, 'key_benefits', []) or []) or 'none given'} / "
        f"{getattr(p, 'usp', '') or 'none given'}\n"
        f"Content type: {getattr(getattr(payload, 'content_type', None), 'value', 'video')}\n"
        f"Format: {getattr(payload, 'format', '') or 'default'}\n"
        f"Script language: {getattr(getattr(payload, 'script_language', None), 'value', 'english')}\n"
        f"Story situation: {getattr(s, 'title', '')} — {getattr(s, 'description', '')}\n"
        f"Selected hook line (if the user picked one, it must survive intact — do not flag it as "
        f"weak just for being simple): {selected_hook}\n\n"
        f"Generated hook: {hook_text}\n"
        f"Generated body:\n" + "\n".join(f"- {t}" for t in body_texts) + "\n"
        f"Generated CTA: {cta_text}"
    )


def llm_quality_issues(data: dict, payload) -> list[str]:
    """One small, cheap evaluation call — only meant to be invoked when
    deterministic_issues() found nothing, to catch what regex can't. Routed
    to the validation tier (Flash-Lite, Option C §9): this is semantic
    judgment a regex can't do, but it's a routine, high-volume check, not
    the final creative-director decision — cheap-but-real reasoning, not the
    deepest available reasoning."""
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                contents=[_build_eval_user_message(data, payload)],
                model=settings.validation_model,
                max_output_tokens=300,
                json_mode=True,
                label="script_quality_eval",
            ),
            label="script_quality_eval",
            max_attempts=2,
        )
        result = json.loads(text)
        issues = result.get("issues") or []
        return [i for i in issues if isinstance(i, str)]
    except Exception as e:
        logger.warning("Quality-gate LLM evaluation failed, treating as pass: %s", e)
        return []


_ISSUE_INSTRUCTIONS: dict[str, str] = {
    "generic_language": (
        "it contains generic, cliche advertising language that could appear in any ad — find and "
        "replace every such phrase with specific, human, non-generic copy"
    ),
    "weak_hook": (
        "the hook is weak — generic, interchangeable with any product, or fails to create real "
        "curiosity; give it a genuinely different, sharper creative mechanism"
    ),
    "hook_no_payoff": (
        "the hook opens a promise or question the body never actually answers — make the body "
        "genuinely pay off what the hook opened"
    ),
    "feature_dump": (
        "it lists benefits/features without one central creative idea connecting them — rebuild it "
        "around a single clear creative concept instead of a feature dump"
    ),
    "weak_product_relevance": (
        "the product integration feels forced or generic — this script could apply to almost any "
        "product; make the product specifically and naturally central to this exact story"
    ),
    "weak_audience_relevance": (
        "it uses vague, generic audience language instead of a concrete, specific situation this "
        "exact audience would recognize"
    ),
    "disconnected_flow": (
        "the beats feel like disconnected sentences rather than one script that goes somewhere — "
        "build a clear throughline from hook to CTA"
    ),
    "weak_cta": (
        "the CTA is a generic, unearned close — make it match the tone, audience, and creative idea "
        "instead of a reflexive \"buy now\""
    ),
    "unnatural_language": (
        "the language reads like a stiff translation rather than something a real person would "
        "naturally say out loud — rewrite it directly in the natural spoken register, do not "
        "translate sentence-by-sentence"
    ),
    "format_mismatch": "it doesn't fit the requested format's real conventions — rewrite it to actually match how this format is really made",
    "unsupported_claim": (
        "it contains a specific, unsupported outcome or efficacy claim — a timeframe ('in 2 weeks'), "
        "a percentage, a guarantee, or absolute/medical language ('cures', 'removes', 'prevents', "
        "'eliminates') that goes beyond what the given product info actually states. Fix this by "
        "REMOVING the specific claim, not by substituting a different specific claim: describe the "
        "ingredient, the routine/experience, or the given benefit in general terms instead (e.g. "
        "name the ingredient, or say it's 'designed for'/'part of a routine focused on X' rather "
        "than promising a result, a timeframe, or a percentage). The presence of an ingredient is "
        "NOT proof of a specific outcome — do not invent a different number, timeframe, or absolute "
        "verb to replace the one removed. Only keep a specific claim if the product info given below "
        "explicitly states it"
    ),
    "missing_hook": "the hook is missing or empty — write a real opening line",
    "missing_cta": "the CTA is missing or empty — write a real closing line",
    "empty_body": "the body is empty or missing — write the actual story beats",
    "duplicate_lines": "some blocks repeat the exact same line — rewrite so every block says something distinct",
    "ingredient_dump": (
        "one or more lines just list ingredients/features joined by commas ('contains X, Y, Z and "
        "W') with no story connecting them — rebuild that beat as: the problem it answers, then the "
        "one relevant property, then why that specific property matters to THIS audience, not a "
        "label read aloud"
    ),
    "competitor_swappable": (
        "this script could run unchanged for a directly competing product with the brand name "
        "swapped — make the hook, story, and benefits specifically true of THIS product's given "
        "facts and THIS audience's exact situation, not generic category language"
    ),
    "interchangeable_beats": (
        "two or more beats could be reordered or deleted without the story losing meaning — rewrite "
        "so each beat is caused by or motivates the one before it, not a checklist of separate points"
    ),
    "filler_padding": (
        "length was added by restating an already-made point, a generic motivational line, or "
        "repeating the product name — replace the padding with one genuinely new beat (a new "
        "objection, escalation, proof point, consequence, or emotional turn) instead"
    ),
    "generic_insight": (
        "the story's underlying premise is a restated category-level truth rather than a specific, "
        "narrow, recognizable human situation — rebuild the story around a more specific behavior, "
        "moment, or contradiction this exact audience would recognize"
    ),
    "explanatory_language_overuse": (
        "the script is dominated by abstract/explanatory phrasing (lines that state an insight or "
        "theme directly, e.g. \"the habit isn't just X, it's Y\") instead of shown behavior — rebuild "
        "the affected beats as action + reaction + dialogue + visual: replace each explanatory line "
        "with a concrete physical action, a character's reaction, or a piece of natural dialogue that "
        "lets the viewer infer the same idea instead of being told it"
    ),
    "explains_instead_of_shows": (
        "one or more dialogue lines state the ad's underlying insight or metaphor directly, like a "
        "creative strategist explaining the concept rather than a real person talking — rewrite that "
        "dialogue so the character reacts, teases, questions, hesitates, notices something, or reveals "
        "who they are through natural speech, never a line that announces the ad's own message"
    ),
    # Filmable hard-gate fix (2026-09-18 task) — exact rewrite instruction
    # wording as specified: dramatize the SAME approved concept better,
    # never discard it or swap the creative mechanism just to dodge the
    # issue.
    "not_filmable_video": (
        "Rewrite the actual story into filmable scenes. Replace explanations with observable action, "
        "reaction, dialogue, visual behavior and concrete beats. Preserve the approved concept, hook "
        "and product truth. Do not change the creative mechanism merely to avoid the issue."
    ),
    # Winning-reference-DNA fix (2026-09-18 task) — deliberately distinct
    # from the other issue codes above (which each catch one narrow
    # symptom): this one names the WHOLE-SCRIPT gap directly, so a rewrite
    # triggered by it is explicitly told to raise the creative bar to
    # reference level, not just patch a line.
    "generic_ai_ad": (
        "the script reads like competent but generic AI ad copy rather than something that belongs "
        "beside this brand's actual winning reference scripts — rebuild the underlying advertising "
        "idea to match the reference's level of specificity: a real, specific hook device; a real "
        "human insight (not a category-level generality); a creative mechanism that actually drives "
        "the scenes; and a payoff earned by that mechanism. Do not just add more scenes, action lines, "
        "or cinematic language — the IDEA itself needs to be stronger, not just its presentation."
    ),
    # Beat-outline / architecture-enforcement issue codes (post-script pass,
    # see architecture_validation_service.py) — reuse this same instruction
    # map and rewrite_reason() so the existing single-rewrite mechanism
    # handles them with no new plumbing.
    "missing_required_beat": (
        "a beat required by the chosen creative architecture is missing or only superficially "
        "present — add it back as a genuine, causally-connected beat, not a token line"
    ),
    "architecture_abandoned": (
        "the script doesn't actually use the required format/interaction style of the chosen "
        "architecture (e.g. it was supposed to be a real two-voice dialogue and became a monologue) "
        "— rewrite it to genuinely use that format, not just narrate around it"
    ),
    "no_emotional_progression": (
        "the architecture's expected emotional arc doesn't actually happen — the tone stays flat "
        "instead of moving through the stages it's supposed to (e.g. skeptical -> reassured -> "
        "convinced) — rewrite so each beat's emotional register is genuinely different from the last"
    ),
    "proof_mechanism_missing": (
        "the architecture's required proof/demonstration approach isn't actually used — add a "
        "concrete, testable detail (a number, a before/after, a named specific) instead of an "
        "asserted claim"
    ),
    "weak_creative_idea": (
        "there's no specific human observation here — it reads as a category-level generality; "
        "rebuild around a sharper, more specific insight that only makes sense for this exact "
        "audience and situation"
    ),
    "no_memorable_device": (
        "nothing here is distinctive — no device, line, or structural twist a viewer would actually "
        "remember or repeat; add one genuine memorable element that supports the idea, don't just "
        "decorate it"
    ),
    "no_curiosity": (
        "the story doesn't create a real question the viewer wants answered — sharpen the hook/setup "
        "so there's a genuine, specific curiosity gap"
    ),
    "story_static": (
        "nothing changes or evolves across the beats — rewrite so the situation, the character's "
        "understanding, or the stakes genuinely shift as the story progresses"
    ),
    "unearned_cta": (
        "the ending is reached, not earned — there's no real payoff before the CTA lands; add a "
        "genuine resolution beat before closing"
    ),
    "hook_not_intact": (
        "the hook drifted too far from the approved hook line — restore its core wording/structure "
        "(a faithful translation/localization is fine, an unrelated new opening is not)"
    ),
    "product_reveal_moved": (
        "the product appeared at a different point than the chosen architecture's reveal timing "
        "calls for — move the product's first mention back to where the approved outline placed it"
    ),
    "category_overfit": (
        "the script uses tobacco/gutka/pan-masala-specific situations or vocabulary that don't "
        "belong to this product's actual category — rebuild the relevant beat(s) around a situation "
        "genuinely specific to THIS product and audience instead"
    ),
    "generic_creative_premise": (
        "underneath the wording, this is still a generic problem-then-product-then-benefit ad with "
        "no specific situation, device, or reversal — rebuild it around one concrete, original "
        "situation with an actual turn in it, not a topic"
    ),
    "slogan_as_hook": (
        "the hook reads like a title/tagline for the ad, not a real line a viewer would hear or "
        "see — rewrite it as an actual moment, line of dialogue, or observation, not a name for the "
        "concept"
    ),
    "product_first_hook": (
        "the hook opens with the product/brand name itself — open on the human situation instead "
        "and let the product enter later, at the point the story actually earns it"
    ),
    "missing_turning_point": (
        "there's no moment where something is realized, discovered, or decided — add a genuine "
        "turning point before the resolution, not just situation then product then done"
    ),
    "missing_payoff": (
        "the story sets something up but never resolves or lands it — add a concrete payoff beat "
        "that actually pays off what the hook and setup promised"
    ),
    "generic_cta": (
        "the CTA doesn't connect to this script's specific premise or decision — it would fit any "
        "script in this category unchanged; rewrite it to close on the exact decision/idea this "
        "story was actually about"
    ),
    "product_forced_into_story": (
        "the product's entry doesn't feel inevitable — it reads as placed there to be mentioned "
        "rather than because the situation needed it; rebuild the moment before it so the product is "
        "the obvious next step, not an announcement"
    ),
    "reference_dna_mismatch": (
        "the script ignores the reference-DNA mechanism given for this architecture (its hook "
        "device, proof device, reveal timing, or CTA style) and defaults to a generic, unrelated ad "
        "shape instead — rebuild the relevant beat(s) to actually use that mechanism"
    ),
    "category_drift": (
        "the script no longer treats the product according to the given Product Creative Contract — "
        "it has been reinterpreted as a different kind of product, used in a context the contract "
        "marks as forbidden, or given to the wrong audience/use case. Repair this while preserving "
        "the creative idea/device where possible: rebuild the relevant beat(s) so the product is used "
        "exactly as its real use case describes (see the contract's allowed contexts), never redefine "
        "what the product fundamentally is just because a word in its name suggests something else"
    ),
    "not_visually_executable": (
        "this reads as pure narration/conversation with nothing a camera could actually shoot — "
        "rewrite it so each beat implies a concrete visual (an action, a setting, a product moment), "
        "not just a line being said"
    ),
    "territory_mismatch": (
        "the script does not actually express the approved creative territory — it silently slid back "
        "into a generic product story, an ingredient list, generic testimonial language, or a standard "
        "problem-then-product-then-benefits-then-CTA shape instead of genuinely dramatizing the "
        "territory's human tension and creative question"
    ),
    "same_idea_different_clothes": (
        "despite a new setting/character/device, this is fundamentally the same underlying creative "
        "territory as a recently generated concept for this product — the underlying human tension and "
        "creative question need to genuinely change, not just the surface execution"
    ),
    # Phase 3C — story-to-film execution codes (architecture_validation_service's
    # Creative Director eval, REVIEWER 2.5). These target the specific gap
    # where a script is product-correct, on-category, and safely claimed, but
    # still converts the selected creative idea into generic ad copy.
    "title_story_mismatch": (
        "the selected story situation's title names a concrete concept, but the script's actual "
        "content never delivers it — rebuild the script so the concept the title names (the specific "
        "relationship, scene, or event it implies) genuinely happens in the script, not just a loosely "
        "related theme"
    ),
    "metaphor_not_embodied": (
        "a metaphor or feeling is stated or explained in narration rather than shown — rebuild it so "
        "the metaphor is embodied through a specific character, a concrete event, and a visual "
        "progression the script actually describes, not just asserted as a line of narration"
    ),
    "no_concrete_event": (
        "for this format, an actual event should be happening (a discovery, confrontation, reversal, "
        "unexpected action, reveal, social reaction, decision, interruption, or demonstration) and "
        "instead this is purely explanatory narration — rebuild the middle of the script around one "
        "real, specific event"
    ),
    "announcement_mode": (
        "the underlying structure is problem -> product introduction -> features/ingredients -> "
        "generic positive-lifestyle statement -> CTA, with the product entering as an announcement — "
        "rebuild it so the product's entry is caused by a specific moment in the situation, not "
        "introduced as news"
    ),
    "hook_abstract_not_situational": (
        "the hook restates or explains the product category/theme in the abstract instead of opening "
        "on a character, situation, unexpected behavior, curiosity gap, or visual event — rewrite the "
        "hook to open on something specific happening, not a category-level statement"
    ),
    "hook_tactic_not_executed": (
        "an approved hook TACTIC was given (e.g. Question, Reaction in Action, Teaser Hook) but the "
        "written hook doesn't actually execute it — rebuild the first 1-3 seconds so the approved "
        "visual/action/dialogue event genuinely happens on screen/in the line, in the exact tactic's "
        "style, not flattened into a generic spoken sentence"
    ),
    "payoff_repeats_setup": (
        "the ending just restates the opening metaphor/feeling in different words instead of paying it "
        "off — rebuild the ending as a genuine escalation, reveal/reversal, or resolution that actually "
        "happened, not a repeated statement of the same idea"
    ),
    "memorability_relies_on_tagline": (
        "removing the closing tagline/slogan line would leave nothing memorable — the story, hook, and "
        "beats themselves are forgettable and only the last line was written to be quotable. Build one "
        "genuinely memorable element INTO the story itself (a specific action, image, or moment a viewer "
        "would actually recall), not a punchy line bolted on at the end to compensate for a forgettable middle"
    ),
}

# "FINAL CREATIVE DIRECTOR TEST" threshold — when an evaluation call returns
# this many or more distinct weak dimensions, a line-level patch is treated
# as insufficient; rewrite_reason() escalates its single instruction to
# "write a new premise" instead of "fix these specific lines". Still just
# ONE rewrite call via the existing mechanism — this only changes what that
# one call is told to do, never how many calls happen.
PREMISE_ESCALATION_THRESHOLD = 3


# A script can fail the ordinary "3+ issues" threshold on execution alone
# (weak hook, filler, disconnected beats) while the underlying creative
# TERRITORY it was asked to dramatize was fine — patch execution, keep the
# territory. These two codes specifically mean the TERRITORY itself is the
# problem (the script never actually expressed it, or it's indistinguishable
# from a recently used one) — even a single occurrence means the territory,
# not just the writing, needs to change. See script_service._rewrite_context_for_issues.
TERRITORY_WEAK_CODES = {"territory_mismatch", "same_idea_different_clothes"}


def is_territory_weak(issues: list[str]) -> bool:
    return any(i in TERRITORY_WEAK_CODES for i in issues)


def is_premise_escalation(issues: list[str]) -> bool:
    """True when rewrite_reason(issues) will produce the escalated "write a
    new premise" instruction rather than a targeted patch instruction — the
    caller (script_service._apply_quality_gate/_apply_architecture_gate)
    uses this to decide whether the OLD premise/outline may still be
    attached to the rewrite call as mandatory context. Attaching it during
    an escalation is a direct contradiction (the premise block says
    "mandatory — execute it, do not replace it" in the same prompt as an
    instruction to discard it), observed live: whenever both fired together,
    the rewrite call received self-contradictory instructions.

    Also true whenever is_territory_weak(issues) — a single territory_mismatch/
    same_idea_different_clothes finding means the LENS itself is wrong, which
    a line-level patch can never fix, regardless of how many other issues
    happen to be present."""
    return len(dict.fromkeys(issues)) >= PREMISE_ESCALATION_THRESHOLD or is_territory_weak(issues)


def rewrite_reason(issues: list[str]) -> str:
    """Turns issue codes into one instruction for a single targeted rewrite
    pass. Never exposed to the user — internal to the generation pipeline.

    When `len(issues) >= PREMISE_ESCALATION_THRESHOLD` (3+ distinct weak
    dimensions — the "final creative director test" failing on multiple
    fronts at once), the instruction escalates from "fix these specific
    things" to "the current creative premise itself doesn't work — write a
    genuinely new one", since patching individual lines can't fix a script
    that's fundamentally generic. Still exactly one rewrite call either way —
    this only changes the instruction given to that one call."""
    unique = list(dict.fromkeys(issues))
    sentences = [_ISSUE_INSTRUCTIONS[i] for i in unique if i in _ISSUE_INSTRUCTIONS]
    if not sentences:
        return "Rewrite this script — the current draft feels generic and needs a sharper, more specific creative pass."
    reason_list = "; and ".join(sentences)
    if is_territory_weak(unique):
        return (
            "The creative TERRITORY this script was supposed to dramatize did not survive into the "
            "actual writing (or is indistinguishable from a recently used one) — patching lines cannot "
            "fix this. Do NOT just edit the existing draft — pick a genuinely different underlying "
            "creative territory (a different human tension and creative question, not just a different "
            "character/setting/device for the same one) and write from it. Keep only the product's "
            "given facts and the target duration/format/language/tone. Specifically, the previous "
            "attempt failed because " + reason_list + "."
        )
    if len(unique) >= PREMISE_ESCALATION_THRESHOLD:
        return (
            "This draft is weak on 3 or more fundamental creative dimensions, so patching individual "
            "lines will not fix it. Do NOT just edit the existing draft — throw out the current "
            "creative premise entirely and write a genuinely NEW one: a different human insight, a "
            "different hook, a different story angle and turning point. Keep only the product's given "
            "facts, the target duration/format/language/tone, and (if a beat outline or architecture "
            "was given) its required beats — everything else about the creative idea should change. "
            "Specifically, the previous attempt failed because " + reason_list + "."
        )
    return "Rewrite this script because " + reason_list + "."
