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
]

# Patterns that need a wildcard, not a plain substring.
_BANNED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\btake your .{1,40} to the next level\b", re.IGNORECASE),
]

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

    # Video-only structural checks — several static formats (thumbnail,
    # quote_graphic) legitimately ship an empty body or empty cta.
    if content_type != "static":
        hook_text = (data.get("hook") or {}).get("text", "") if isinstance(data.get("hook"), dict) else ""
        cta_text = (data.get("cta") or {}).get("text", "") if isinstance(data.get("cta"), dict) else ""
        if not hook_text.strip():
            issues.append("missing_hook")
        if not cta_text.strip():
            issues.append("missing_cta")
        if not data.get("body"):
            issues.append("empty_body")

    non_empty = [t.strip() for t in texts if t.strip()]
    if len(non_empty) != len(set(non_empty)) and len(non_empty) > 1:
        issues.append("duplicate_lines")

    p = getattr(payload, "structured_product", None)
    if p is not None:
        tokens = _significant_tokens(p.product_name, *p.ingredients, *p.key_benefits, p.usp)
        if tokens and not any(t in combined_low for t in tokens):
            issues.append("weak_product_relevance")

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
    deterministic_issues() found nothing, to catch what regex can't."""
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                contents=[_build_eval_user_message(data, payload)],
                model=settings.openrouter_text_model,
                max_output_tokens=300,
                json_mode=True,
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
}


def rewrite_reason(issues: list[str]) -> str:
    """Turns issue codes into one instruction for a single targeted rewrite
    pass. Never exposed to the user — internal to the generation pipeline."""
    unique = list(dict.fromkeys(issues))
    sentences = [_ISSUE_INSTRUCTIONS[i] for i in unique if i in _ISSUE_INSTRUCTIONS]
    if not sentences:
        return "Rewrite this script — the current draft feels generic and needs a sharper, more specific creative pass."
    return "Rewrite this script because " + "; and because ".join(sentences) + "."
