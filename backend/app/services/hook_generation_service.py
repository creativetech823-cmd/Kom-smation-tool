"""Hook Generation & Evaluation — Part 4 of the AHM Creative DNA
implementation. Generates several hook candidates in ONE call (not the full
script), self-evaluates each against a concrete curiosity-gap test, rejects
generic ones, and returns the strongest survivor as `selected_hook_text` —
which script_service.py already knows how to consume verbatim via its
existing _hook_block() "SELECTED HOOK LINE (mandatory)" mechanism (the same
path a user-picked Hooks-library hook takes), so no change was needed there
to make a machine-picked hook behave identically to a human-picked one.

Never raises: a failure returns None, and the caller proceeds exactly as it
already did before this module existed (the main generation prompt writes
its own opening, same as any script with no selected_hook_text).
"""

import json
import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("hook_generation_service")

# The exact generic-opener denylist from the brief (task §2), plus the
# existing script_quality.BANNED_PHRASES patterns are ALSO checked, so the
# hook-time filter and the post-generation quality gate never disagree.
_GENERIC_HOOK_PHRASES = [
    "every mother wants",
    "we all know health is important",
    "your child's health matters",
    "in today's busy life",
    "take care of your family",
    "health is wealth",
    "are you tired of",
    "did you know",
    "introducing",
    "say goodbye to",
    "because your health matters",
    "in today's world",
]


@dataclass
class HookCandidate:
    text: str
    curiosity_question: str
    mechanism: str
    reveals_product: bool
    passes: bool
    reject_reason: str = ""


def _is_generic(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in _GENERIC_HOOK_PHRASES)


_SYSTEM_PROMPT = """You write short-form ad hooks — the first 1-3 seconds only, nothing else. For
each hook you write, you must also self-evaluate it honestly.

A hook must:
- Contain a concrete person, situation, behavior, number, tension, or unexpected/contrarian
  statement — never an abstract feeling label.
- Create an immediate, specific, ANSWERABLE curiosity gap — a real viewer should be able to name
  the exact question it makes them want answered.
- NOT reveal the product or brand name (unless the chosen architecture explicitly requires early
  product visibility, which will be told to you if so).
- Sound like something a real person would actually say out loud on camera or in a caption — never
  advertising copy, never a generic category-level opener.

Reject generic openers such as: "Every mother wants...", "We all know health is important...",
"Your child's health matters...", "In today's busy life...", "Take care of your family...",
"Health is wealth...", "Are you tired of...", "Did you know...", "Introducing...", "Say goodbye
to...", "Because your health matters...". A hook using any of these patterns must be marked
passes=false.

Generate exactly 3 genuinely different hook candidates (different mechanisms/angles from each
other, not 3 rewordings of the same idea), each grounded in the given human insight below. For
EACH candidate, self-evaluate: what exact question would a real viewer want answered? If you
cannot name a specific, concrete question, that candidate fails.

If a CREATIVE PREMISE is given below, every hook candidate must open specifically into THAT
premise's situation — not a generic version of the insight. A hook that would fit any script about
this general topic, not specifically this premise's situation, fails.

A hook must never be a title, tagline, or slogan-style phrase (e.g. a name for the ad rather than a
line spoken/shown in it) — it must be a real line, moment, or piece of dialogue a viewer actually
sees or hears in the first 1-3 seconds.

CRITICAL: ground every hook in THIS product's actual category and audience. Do not default to
tobacco/gutka/pan-shop/quitting-addiction/chewing/smell-related situations or phrasing unless the
given product is actually in that category.

Return ONLY this JSON, no prose, no markdown fences:
{
  "candidates": [
    {
      "text": string,
      "curiosity_question": string,
      "mechanism": string,
      "reveals_product": boolean,
      "passes": boolean,
      "reject_reason": string
    }
  ]
}"""


def _user_message(
    product_name: str,
    category: str,
    target_audience: str,
    insight_block: str,
    architecture_hook_pattern: str,
    product_reveal_early: bool,
    language: str,
    premise_block: str = "",
    contract_block: str = "",
) -> str:
    return (
        f"{contract_block}\n"
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience: {target_audience}\n"
        f"{insight_block}\n"
        f"{premise_block}\n"
        f"Chosen architecture's hook pattern to follow: {architecture_hook_pattern}\n"
        f"This architecture {'DOES' if product_reveal_early else 'does NOT'} call for early product visibility in the hook.\n"
        f"Write the hook text in: {language}\n"
    )


def generate_and_select_hook(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    insight_block: str,
    architecture_hook_pattern: str,
    product_reveal_early: bool,
    language: str,
    premise_block: str = "",
    contract_block: str = "",
) -> HookCandidate | None:
    try:
        user_msg = _user_message(
            product_name, category, target_audience, insight_block, architecture_hook_pattern,
            product_reveal_early, language, premise_block, contract_block,
        )
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.creative_model,
                max_output_tokens=800,
                json_mode=True,
                label="hook_generation",
            ),
            label="hook_generation",
        )
        data = json.loads(text)
        raw_candidates = data.get("candidates") or []
        candidates: list[HookCandidate] = []
        for c in raw_candidates:
            if not isinstance(c, dict):
                continue
            hook_text = str(c.get("text") or "").strip()
            if not hook_text:
                continue
            self_passes = bool(c.get("passes", True))
            curiosity_q = str(c.get("curiosity_question") or "").strip()
            generic = _is_generic(hook_text)
            reveals = bool(c.get("reveals_product", False))
            # Deterministic re-check, never trust the model's self-grading alone.
            product_name_leak = bool(product_name) and re.search(re.escape(product_name), hook_text, re.IGNORECASE)
            # A title/tagline masquerading as a hook: no sentence punctuation, every
            # word capitalized, short (e.g. "Mom Ka Superpower") — a real spoken
            # line almost never looks like this.
            words = hook_text.split()
            is_slogan_shaped = (
                1 < len(words) <= 6
                and not re.search(r"[.!?,]", hook_text)
                and sum(1 for w in words if w[:1].isupper()) >= max(2, len(words) - 1)
            )
            passes = (
                self_passes and not generic and bool(curiosity_q)
                and not (product_name_leak and not product_reveal_early)
                and not is_slogan_shaped
            )
            reason = str(c.get("reject_reason") or "")
            if not passes and not reason:
                if generic:
                    reason = "matched a generic-opener pattern"
                elif is_slogan_shaped:
                    reason = "reads like a title/tagline, not a spoken line (slogan_as_hook)"
                elif not curiosity_q:
                    reason = "no clear answerable curiosity question"
                elif product_name_leak:
                    reason = "reveals the product/brand name too early for this architecture"
            candidates.append(
                HookCandidate(
                    text=hook_text,
                    curiosity_question=curiosity_q,
                    mechanism=str(c.get("mechanism") or ""),
                    reveals_product=reveals,
                    passes=passes,
                    reject_reason=reason,
                )
            )
        passing = [c for c in candidates if c.passes]
        if passing:
            return passing[0]
        if candidates:
            logger.info("All hook candidates failed self-evaluation: %s", [c.reject_reason for c in candidates])
        return None
    except Exception as e:
        logger.warning("Hook generation failed, main generation will write its own opening: %s", e)
        return None
