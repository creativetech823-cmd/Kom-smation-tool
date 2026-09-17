"""Beat Outline generation & validation — turns "architecture selection" from
advisory guidance into an actually-enforced scaffold.

Insight -> Architecture -> Hook -> BEAT OUTLINE -> Beat Validation -> Script

The outline is a structural blueprint (what happens in each beat, not
polished dialogue) generated in its own LLM call, checked against the
architecture's required_beats/reveal-timing/prohibited_patterns via a cheap
deterministic pass AND a small LLM story-quality pass, and only handed to
the script-writing prompt once it passes (or after MAX_OUTLINE_ATTEMPTS
attempts, whichever comes first — this never blocks generation entirely,
matching every other stage's fail-open convention in this pipeline).
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.config import settings
from app.services.creative_architecture import Architecture
from app.services.creative_premise_service import CreativePremise
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import ProductCreativeContract
from app.services.product_context_validator import detect_category_drift_signal

logger = logging.getLogger("beat_outline_service")

MAX_OUTLINE_ATTEMPTS = 2


@dataclass
class BeatOutlineItem:
    beat_number: int
    purpose: str
    content: str
    emotional_state: str
    must_include: list[str] = field(default_factory=list)


@dataclass
class BeatOutline:
    architecture: str
    hook: str
    human_insight: str
    beats: list[BeatOutlineItem]
    product_reveal_beat: int
    proof_beat: int
    payoff_beat: int
    cta_beat: int

    def prompt_block(self) -> str:
        beats_text = "\n".join(
            f"  Beat {b.beat_number} [{b.emotional_state}] — {b.purpose}: {b.content}"
            + (f" (must include: {', '.join(b.must_include)})" if b.must_include else "")
            for b in self.beats
        )
        return (
            "APPROVED BEAT OUTLINE (mandatory — this is the story blueprint you must write from):\n"
            f"{beats_text}\n"
            f"Product reveal happens at beat {self.product_reveal_beat}.\n"
            f"Proof/demonstration happens at beat {self.proof_beat}.\n"
            f"Payoff happens at beat {self.payoff_beat}.\n"
            f"CTA is beat {self.cta_beat} (the final beat).\n\n"
            "Follow the approved beat outline exactly.\n"
            "Do not:\n"
            "- remove beats\n"
            "- reorder beats\n"
            "- invent a different architecture\n"
            "- turn dialogue into monologue (or vice versa) if the outline specifies an interaction format\n"
            "- introduce the product earlier than the specified reveal beat\n"
            "- add generic advertising lines\n"
            "- add filler to reach length\n"
            "You may improve natural language and dialogue, expand a beat's content into more than one "
            "script block if the duration allows, and adapt wording to this exact product/audience — but "
            "preserve the underlying story structure, beat order, and beat count above.\n"
        )


# --- Deterministic reveal-timing expectation, derived from the architecture's
# own product_reveal_logic prose (kept as free text there because the prompt
# needs it in natural language; parsed here into a checkable fraction range).
_REVEAL_TIMING_BANDS: list[tuple[re.Pattern, tuple[float, float]]] = [
    (re.compile(r"\bimmediate\b.*\btotal\b|\btotal\b.*\bimmediate\b", re.IGNORECASE), (0.0, 0.15)),
    (re.compile(r"\bimmediate\b", re.IGNORECASE), (0.0, 0.25)),
    (re.compile(r"\bvery late\b", re.IGNORECASE), (0.65, 1.0)),
    (re.compile(r"\blate\b", re.IGNORECASE), (0.5, 1.0)),
    (re.compile(r"\bearly-to-mid\b", re.IGNORECASE), (0.0, 0.5)),
    (re.compile(r"\bearly\b", re.IGNORECASE), (0.0, 0.4)),
    (re.compile(r"\bmid\b", re.IGNORECASE), (0.25, 0.7)),
]


def expected_reveal_fraction(architecture: Architecture) -> tuple[float, float]:
    text = architecture.product_reveal_logic
    for pattern, band in _REVEAL_TIMING_BANDS:
        if pattern.search(text):
            return band
    return (0.0, 1.0)  # architecture doesn't specify — no constraint


def validate_outline_deterministic(
    outline: BeatOutline, architecture: Architecture, contract: ProductCreativeContract | None = None
) -> list[str]:
    """Free, regex/arithmetic-only checks. No API call."""
    issues: list[str] = []
    n = len(outline.beats)
    if n == 0:
        return ["outline_empty"]

    # PRODUCT TRUTH check — catches category drift at the STRUCTURAL blueprint
    # stage, before a line of polished dialogue is ever written. Only ever
    # runs for a product whose contract flags a known risky role.
    if contract is not None and contract.role_risk_keys:
        combined = " ".join(b.content for b in outline.beats)
        if detect_category_drift_signal(combined, contract):
            issues.append("outline_category_drift")

    if n < len(architecture.required_beats):
        issues.append("outline_missing_required_beats")

    if outline.cta_beat != n:
        issues.append("outline_cta_not_final_beat")

    if outline.product_reveal_beat < 1 or outline.product_reveal_beat > n:
        issues.append("outline_invalid_product_reveal_beat")
    else:
        lo, hi = expected_reveal_fraction(architecture)
        actual_fraction = (outline.product_reveal_beat - 1) / max(1, n - 1) if n > 1 else 0.0
        # A little slack either side — this is a band, not a pixel-exact rule.
        if not (lo - 0.15 <= actual_fraction <= hi + 0.15):
            issues.append("outline_product_reveal_timing_off")

    if "none" not in architecture.proof_mechanism.lower() and outline.proof_beat < 1:
        issues.append("outline_missing_proof_beat")

    if outline.payoff_beat < 1:
        issues.append("outline_missing_payoff_beat")

    beat_contents = [b.content.strip().lower() for b in outline.beats if b.content.strip()]
    if len(beat_contents) != len(set(beat_contents)) and len(beat_contents) > 1:
        issues.append("outline_duplicate_beats")

    return issues


_LLM_VALIDATION_SYSTEM_PROMPT = """You are a strict story-structure auditor reviewing a beat outline
(a blueprint, not polished dialogue) BEFORE it gets written into a final script. You did not write
it — review it honestly, most outlines that reach this stage are close to fine, don't invent
problems.

Check ONLY these things, and return issue codes from this exact list:
- "no_real_human_insight": the outline's premise is a restated category-level truth, not a specific
  situation.
- "no_escalation": nothing gets more urgent/interesting/complicated as the beats progress — it reads
  as a flat list of facts.
- "beats_not_causal": a beat doesn't follow FROM the one before it — remove any beat and the story
  wouldn't actually break.
- "no_turning_point": there's no moment where something genuinely changes (a realization, a
  discovery, a decision) — it's just situation, then product, then done.
- "no_payoff": the ending doesn't resolve or land anything — it just stops.
- "required_beat_missing_in_spirit": one of the architecture's REQUIRED beats isn't genuinely present
  even if the outline claims it is (e.g. "objection" beat exists but doesn't name a real objection).
- "prohibited_pattern_present": the outline matches one of the architecture's own listed prohibited
  patterns.
- "premise_diluted": a creative premise was given, but the outline reverts to a generic version of it
  (the specific situation/device/reversal the premise described isn't actually what the beats do) —
  only flag this if a premise was actually given below.

Return ONLY this JSON, no prose, no markdown fences:
{"issues": [string]}
issues=[] when the outline is genuinely fine."""


def _outline_eval_user_message(outline: BeatOutline, architecture: Architecture, premise: CreativePremise | None = None) -> str:
    beats_text = "\n".join(f"Beat {b.beat_number} [{b.emotional_state}]: {b.purpose} — {b.content}" for b in outline.beats)
    required = "\n".join(f"- {b}" for b in architecture.required_beats)
    prohibited = "\n".join(f"- {p}" for p in architecture.prohibited_patterns)
    premise_block = (
        f'Creative premise this outline must execute: "{premise.statement}" (device: {premise.creative_device})\n'
        if premise else ""
    )
    return (
        f"Architecture: {architecture.name}\n"
        f"Required beats this outline must genuinely satisfy:\n{required}\n"
        f"Prohibited patterns:\n{prohibited}\n\n"
        f"Human insight the outline should be built around: {outline.human_insight or '(none given)'}\n"
        f"{premise_block}"
        f"Hook: {outline.hook}\n\n"
        f"Outline:\n{beats_text}"
    )


def validate_outline_llm(outline: BeatOutline, architecture: Architecture, premise: CreativePremise | None = None) -> list[str]:
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_LLM_VALIDATION_SYSTEM_PROMPT,
                contents=[_outline_eval_user_message(outline, architecture, premise)],
                model=settings.creative_model,
                max_output_tokens=300,
                json_mode=True,
                label="beat_outline_eval",
            ),
            label="beat_outline_eval",
            max_attempts=2,
        )
        data = json.loads(text)
        issues = data.get("issues") or []
        return [i for i in issues if isinstance(i, str)]
    except Exception as e:
        logger.warning("Beat outline LLM validation failed, treating as pass: %s", e)
        return []


_OUTLINE_SYSTEM_PROMPT = """You are a creative director building a STORY BLUEPRINT — not a script,
not dialogue, just the structural beats a script will later be written from. Each beat is a short
description of WHAT HAPPENS and WHY, not spoken lines.

You MUST include every one of the architecture's REQUIRED BEATS below, in the given causal order
(you may add extra optional beats between them if duration allows, but never skip, merge, or
reorder the required ones). You MUST NOT produce anything matching the PROHIBITED PATTERNS.

If a CREATIVE PREMISE is given below, it has ALREADY decided what the interesting idea is — your
job is to build the beats that DRAMATIZE that exact premise, not a safer or more generic version of
it. Every beat should exist because it's a consequence of the premise's specific situation/device; if
a beat would be identical regardless of which premise was chosen, rewrite it so it isn't.

CRITICAL: do not default to tropes from a different product category. Build a situation genuinely
specific to THIS product, audience, and insight — never reuse tobacco/gutka/pan-shop/quitting-
addiction/chewing/smell-related situations unless the actual product given below is actually in
that category.

For each beat, specify beat_number, purpose (its structural job, e.g. "confession", "objection #1",
"product reveal"), content (what actually happens — one or two sentences, not dialogue), emotional_state
(one or two words), and must_include (a short list of any specific facts/details that MUST appear here,
e.g. a named ingredient, a specific number — empty list if none).

Also identify: product_reveal_beat (the beat number where the product/brand first appears),
proof_beat (the beat number carrying the proof/demonstration, 0 if this architecture has none),
payoff_beat (the beat number where the emotional/story payoff lands), cta_beat (always the final
beat number).

Return ONLY this JSON, no prose, no markdown fences:
{
  "beats": [
    {"beat_number": int, "purpose": string, "content": string, "emotional_state": string, "must_include": [string]}
  ],
  "product_reveal_beat": int,
  "proof_beat": int,
  "payoff_beat": int,
  "cta_beat": int
}"""


def _outline_user_message(
    architecture: Architecture,
    hook: str,
    human_insight: str,
    product_name: str,
    category: str,
    target_audience: str,
    target_duration_bucket: str,
    retry_note: str = "",
    premise: CreativePremise | None = None,
    contract_block: str = "",
) -> str:
    return (
        f"{contract_block}\n"
        f"{architecture.outline_prompt_block()}\n"
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience: {target_audience}\n"
        f"Target duration: ~{target_duration_bucket or '30s'}\n"
        f"Approved hook: \"{hook}\"\n"
        f"Human insight: {human_insight or '(none discovered)'}\n"
        f"{premise.prompt_block() if premise else ''}"
        f"{retry_note}"
    )


def _parse_outline(data: dict, architecture: Architecture, hook: str, human_insight: str) -> BeatOutline:
    raw_beats = data.get("beats") or []
    beats = [
        BeatOutlineItem(
            beat_number=int(b.get("beat_number") or i + 1),
            purpose=str(b.get("purpose") or ""),
            content=str(b.get("content") or ""),
            emotional_state=str(b.get("emotional_state") or ""),
            must_include=[str(m) for m in (b.get("must_include") or []) if isinstance(m, (str, int, float))],
        )
        for i, b in enumerate(raw_beats)
        if isinstance(b, dict)
    ]
    n = len(beats)
    return BeatOutline(
        architecture=architecture.key,
        hook=hook,
        human_insight=human_insight,
        beats=beats,
        product_reveal_beat=int(data.get("product_reveal_beat") or 0),
        proof_beat=int(data.get("proof_beat") or 0),
        payoff_beat=int(data.get("payoff_beat") or n),
        cta_beat=int(data.get("cta_beat") or n),
    )


def generate_and_validate_outline(
    *,
    architecture: Architecture,
    hook: str,
    human_insight: str,
    product_name: str,
    category: str,
    target_audience: str,
    target_duration_bucket: str,
    premise: CreativePremise | None = None,
    contract: ProductCreativeContract | None = None,
) -> tuple[BeatOutline | None, list[str]]:
    """Up to MAX_OUTLINE_ATTEMPTS generate+validate rounds. Returns
    (outline_or_None, remaining_issues). Never raises: on total failure
    returns (None, []) so the caller falls back to the pre-outline behavior
    (architecture guidance still reaches the writing prompt as free text,
    same as before this module existed)."""
    last_outline: BeatOutline | None = None
    last_issues: list[str] = []
    retry_note = ""
    contract_block = contract.prompt_block() if contract is not None else ""

    for attempt in range(1, MAX_OUTLINE_ATTEMPTS + 1):
        try:
            user_msg = _outline_user_message(
                architecture, hook, human_insight, product_name, category, target_audience,
                target_duration_bucket, retry_note, premise, contract_block,
            )
            text = call_openrouter_with_retry(
                lambda: generate_text(
                    system_instruction=_OUTLINE_SYSTEM_PROMPT,
                    contents=[user_msg],
                    model=settings.creative_model,
                    max_output_tokens=1200,
                    json_mode=True,
                    label="beat_outline",
                ),
                label="beat_outline",
            )
            data = json.loads(text)
            outline = _parse_outline(data, architecture, hook, human_insight)
        except Exception as e:
            logger.warning("Beat outline generation attempt %d failed: %s", attempt, e)
            continue

        issues = validate_outline_deterministic(outline, architecture, contract)
        if not issues:
            issues = validate_outline_llm(outline, architecture, premise)

        last_outline, last_issues = outline, issues
        if not issues:
            return outline, []

        logger.info("Beat outline attempt %d flagged %s", attempt, issues)
        retry_note = (
            f"\nYour previous outline attempt failed validation for: {', '.join(issues)}. Fix these "
            f"specific problems in this new attempt — keep what worked, rebuild what didn't.\n"
        )

    return last_outline, last_issues
