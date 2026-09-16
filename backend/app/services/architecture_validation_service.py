"""Post-script validation — Parts 5, 6, 7 of the beat-outline enforcement
upgrade. Runs AFTER the script is written from an approved outline, as an
extra gate on top of (not a replacement for) the existing script_quality.py
gate. Answers three separate questions:

1. Architecture compliance — did the WRITTEN script actually keep the
   approved outline's structure (Part 5)?
2. Creative Director evaluation — does this read as a distinct creative
   idea or generic AI copy (Part 6)?
3. Strengthened competitor-swappable test (Part 7).

Combined into ONE LLM call (plus cheap deterministic pre-checks) to avoid
tripling the LLM-call count for three closely related evaluation concerns.
Issue codes feed straight into script_quality.rewrite_reason() for the
existing single targeted-rewrite mechanism — no new rewrite machinery
needed. Never raises: any failure here returns no issues (fail-open, same
convention as every other stage in this pipeline).
"""

import json
import logging
import re

from app.config import settings
from app.services.beat_outline_service import BeatOutline
from app.services.creative_architecture import Architecture
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("architecture_validation_service")


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


def _hook_intact(script_hook_text: str, approved_hook: str) -> bool:
    """Fuzzy-ish, deterministic: the approved hook's significant words
    should mostly survive into the written hook (a light localization/
    translation pass is expected and fine; a fully different hook is not)."""
    if not approved_hook:
        return True
    approved_words = set(re.findall(r"[A-Za-zऀ-ॿ]{3,}", approved_hook.lower()))
    hook_words = set(re.findall(r"[A-Za-zऀ-ॿ]{3,}", script_hook_text.lower()))
    if not approved_words:
        return True
    overlap = len(approved_words & hook_words) / len(approved_words)
    return overlap >= 0.3  # generous — translation/localization changes most word forms


def _first_product_mention_fraction(texts: list[str], product_name: str) -> float | None:
    if not product_name:
        return None
    name_tokens = [t for t in re.findall(r"[A-Za-z]{3,}", product_name) if t.lower() not in ("the", "and")]
    if not name_tokens:
        return None
    for i, text in enumerate(texts):
        low = text.lower()
        if any(tok.lower() in low for tok in name_tokens):
            return i / max(1, len(texts) - 1) if len(texts) > 1 else 0.0
    return None  # product never mentioned at all — a different, existing check catches that


def validate_script_against_outline_deterministic(
    data: dict, outline: BeatOutline | None, architecture: Architecture, product_name: str
) -> list[str]:
    """Free, regex/arithmetic-only checks. No API call."""
    issues: list[str] = []
    texts = _block_texts(data)
    if not texts:
        return issues

    hook_text = texts[0]
    if outline and not _hook_intact(hook_text, outline.hook):
        issues.append("hook_not_intact")

    if outline and outline.beats:
        from app.services.beat_outline_service import expected_reveal_fraction

        actual = _first_product_mention_fraction(texts, product_name)
        if actual is not None:
            lo, hi = expected_reveal_fraction(architecture)
            if not (lo - 0.2 <= actual <= hi + 0.2):
                issues.append("product_reveal_moved")

    # A script with far fewer distinct blocks than the outline's beat count
    # suggests beats were merged/dropped wholesale, not just tightened.
    if outline and outline.beats and len(texts) < max(2, len(outline.beats) * 0.5):
        issues.append("missing_required_beat")

    return issues


_EVAL_SYSTEM_PROMPT = """You are two reviewers in one, evaluating a finished ad script honestly and
specifically. Most scripts that reach this stage are reasonably solid — don't invent problems to
seem thorough, but don't wave through real ones either.

REVIEWER 1 — ARCHITECTURE COMPLIANCE. You are told which structural architecture this script was
supposed to follow, and its required beats. Check:
- Are the required beats genuinely present (in spirit, not just labeled)?
- Is the actual FORMAT being used (e.g. if the architecture requires two distinct voices in
  conflict, is that genuinely happening, not a disguised monologue)?
- Is the emotional progression the architecture calls for actually present?
- Is the proof mechanism the architecture calls for actually used?

REVIEWER 2 — CREATIVE DIRECTOR. Do not ask "is this award-winning" — instead evaluate whether this
demonstrates the real characteristics of campaign-quality advertising:
- Is there a specific human observation, not a category-level generality?
- Is there a fresh perspective, not the most obvious angle for this product?
- Is the central idea immediately understandable?
- Is there a memorable creative device (a device, a line, a structural twist)?
- Does the story create real curiosity and then evolve — does something change?
- Is there a genuine TURNING POINT — a moment where something is realized, discovered, or decided —
  not just situation, then product, then done?
- Is there an emotional or intellectual payoff, and does the ending feel earned (not just reached)?
- COMPETITOR-SWAPPABLE TEST: if the product name, ingredients, and brand were replaced with a
  competing product's, would this exact script still work almost unchanged? If yes, that's a real
  problem — flag it.
- If REFERENCE-DNA NOTES are given below, does this script's hook/proof/reveal-timing/CTA style
  reflect that mechanism at all, or does it ignore the reference material entirely and default to a
  completely generic ad shape instead?

Return ONLY issue codes from this exact list, nothing invented:
- "missing_required_beat": a required beat isn't genuinely present, even if superficially labeled
- "architecture_abandoned" (also covers "architecture_not_executed"): the script doesn't actually
  use the required format/interaction style (e.g. a "dialogue" architecture written as one person's
  monologue)
- "no_emotional_progression": the architecture's expected emotional arc doesn't actually happen
- "proof_mechanism_missing": the architecture's required proof/demonstration approach isn't used
- "weak_creative_idea": no specific human observation — reads as a category-level generality
- "no_memorable_device": nothing distinctive — no device, line, or structural twist a viewer would remember
- "no_curiosity": the story doesn't create a real question the viewer wants answered
- "story_static": nothing changes or evolves across the beats
- "missing_turning_point": no moment where something is realized, discovered, or decided
- "missing_payoff": the story sets something up but never resolves or lands it
- "unearned_cta": the ending is reached, not earned — no real payoff before it
- "generic_cta": the CTA doesn't connect to this script's specific premise/decision — it would fit
  any script in this category unchanged
- "product_forced_into_story": the product's entry doesn't feel inevitable — it reads as placed to
  be mentioned, not because the situation needed it
- "competitor_swappable": swap the product/ingredients/brand for a direct competitor's and this
  script would work almost unchanged
- "reference_dna_mismatch": reference-DNA notes were given but the script's execution ignores that
  mechanism entirely and defaults to a generic, unrelated ad shape instead

Return ONLY this JSON, no prose, no markdown fences:
{"issues": [string]}
issues=[] when the script is genuinely fine on both fronts."""


def _eval_user_message(
    data: dict,
    outline: BeatOutline | None,
    architecture: Architecture,
    product_name: str,
    audience: str,
    reference_dna_notes: str = "",
) -> str:
    hook_text = (data.get("hook") or {}).get("text", "") if isinstance(data.get("hook"), dict) else ""
    body_texts = [b.get("text", "") for b in (data.get("body") or []) if isinstance(b, dict)]
    cta_text = (data.get("cta") or {}).get("text", "") if isinstance(data.get("cta"), dict) else ""
    required = "\n".join(f"- {b}" for b in architecture.required_beats)
    ref_block = f"\nReference-DNA notes for this architecture:\n{reference_dna_notes}\n" if reference_dna_notes else ""
    return (
        f"Architecture: {architecture.name}\n"
        f"Required beats:\n{required}\n"
        f"Expected emotional progression: {architecture.emotional_progression}\n"
        f"Expected proof mechanism: {architecture.proof_mechanism}\n"
        f"Product: {product_name}\n"
        f"Audience: {audience}\n"
        f"{ref_block}\n"
        f"Generated hook: {hook_text}\n"
        f"Generated body:\n" + "\n".join(f"- {t}" for t in body_texts) + "\n"
        f"Generated CTA: {cta_text}"
    )


def llm_architecture_and_creative_director_issues(
    data: dict,
    outline: BeatOutline | None,
    architecture: Architecture,
    product_name: str,
    audience: str,
    reference_dna_notes: str = "",
) -> list[str]:
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                contents=[_eval_user_message(data, outline, architecture, product_name, audience, reference_dna_notes)],
                model=settings.openrouter_text_model,
                max_output_tokens=300,
                json_mode=True,
            ),
            label="architecture_creative_director_eval",
            max_attempts=2,
        )
        result = json.loads(text)
        issues = result.get("issues") or []
        return [i for i in issues if isinstance(i, str)]
    except Exception as e:
        logger.warning("Architecture/creative-director evaluation failed, treating as pass: %s", e)
        return []
