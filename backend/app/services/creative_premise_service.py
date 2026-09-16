"""Creative Premise — the missing link between a human insight (a topic/
truth) and a beat outline (a structure).

Insight -> Architecture -> PREMISE (this module) -> Hook -> Beat Outline -> Script

A human insight ("mothers feel judged for outsourcing their child's immunity
routine") is still just a topic. A premise is the one-sentence ANSWER to
"what is the interesting idea of this ad?" — a specific situation, reversal,
or device the insight gets dramatized through. Without this stage, beat
generation has nothing to build beats FROM except the raw insight, and the
safest, most literal translation of a raw insight into beats is exactly the
generic Problem -> Product -> Ingredients -> CTA shape this stage exists to
prevent.

Generates several distinct candidate premises in ONE call, self-scores each
against concrete criteria (never exposed to the user — internal selection
only), and returns the strongest survivor. Never raises: a failure returns
None, and the caller proceeds with insight+architecture alone, same
fail-open convention as every other stage in this pipeline.
"""

import json
import logging
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("creative_premise_service")

MIN_CANDIDATES = 3
MAX_CANDIDATES = 5

# The 9 evaluation criteria from the brief, each scored 1-5 by the model
# itself in the SAME call that generates the candidates (keeps this a single
# LLM call rather than generate-then-separately-judge).
_SCORE_KEYS = [
    "originality",
    "curiosity",
    "emotional_truth",
    "visual_potential",
    "product_integration",
    "reference_dna_fit",
    "non_swappable",
    "story_potential",
    "claim_safety",
]


@dataclass
class CreativePremise:
    statement: str
    creative_device: str
    situation: str
    why_curious: str
    why_not_swappable: str
    scores: dict = field(default_factory=dict)
    total_score: int = 0

    def prompt_block(self) -> str:
        return (
            "CREATIVE PREMISE (mandatory — this IS the idea; execute it, do not quietly replace it "
            "with a safer, more generic version of itself):\n"
            f'Premise: "{self.statement}"\n'
            f"Creative device/mechanism: {self.creative_device}\n"
            f"Concrete situation it plays out in: {self.situation}\n"
            f"Why this creates curiosity: {self.why_curious}\n"
            f"Why a competitor's product couldn't just swap in unchanged: {self.why_not_swappable}\n"
            "This premise is not a topic and not a restated benefit — every beat below must exist "
            "because it serves THIS specific idea. If a beat could be written the same way for any "
            "other product in this category, it isn't executing the premise yet.\n"
        )


_SYSTEM_PROMPT = """You are a creative director generating CREATIVE PREMISES — not scripts, not
beats, one sentence each — for a short-form ad. A premise is the answer to "what is the interesting
idea here?" It is NOT a restated insight or topic.

BAD premise (a topic, not an idea): "A mother wants her child to eat healthy."
BETTER premise (a situation with a reversal): "Turn an everyday family argument about food into a
surprising reveal about what people ignore in their own kitchen."
The difference: the bad version describes a want. The better version describes a SITUATION with a
turn in it — something happens, and something is discovered or reversed. Do not copy this example's
content — invent an original premise specific to the actual product/audience given below.

Every premise you generate must:
- Create curiosity — a viewer must want to know what happens next, not just learn a fact.
- Describe a SITUATION, not a topic — something is happening, not just something being true.
- Have a clear turning point, reveal, or payoff — something changes or is discovered.
- Make the product relevant TO the idea itself, not bolted onto the end of it.
- Be hard to swap: if the product/brand were replaced with a direct competitor's, the premise
  should genuinely stop working, not just need a name change.
- Not depend on any claim beyond what's actually given below.
- Not simply be "X problem -> use [product]."
- Not be an ingredient list disguised as a situation.
- Not open on a generic health slogan or close on a generic emotional slogan unless the specific
  concept genuinely earns that close.

Generate between 3 and 5 candidates. They must be genuinely different from each other — different
situations, different creative devices, different emotional registers — not 5 rewordings of the same
underlying idea. If you cannot find that many genuinely distinct ideas, generate fewer rather than
padding with near-duplicates.

CRITICAL — ground every premise in the ACTUAL given product, audience, and situation below, not a
generic category assumption:
- If the target audience/brief below explicitly describes a specific existing habit, consumption
  pattern, or switching decision (for example, an existing tobacco/gutka/pan-masala habit a person is
  trying to move away from), that IS this product's real context — build premises around that real
  tension, do not sanitize it into a generic family/wellness topic instead.
- If the given audience/brief does NOT describe that kind of situation, do not invent one — build
  premises from whatever situation actually is given, specific to this product's real category and
  audience, never defaulting to tropes (tobacco, gutka, pan-shop, quitting an addiction, chewing,
  smell) that belong to an unrelated product.

For each candidate, also self-score it honestly, 1-5 each, on: originality, curiosity, emotional_truth
(does it reflect something real, not sentimental), visual_potential (can a camera actually show this),
product_integration (does the product feel necessary, not attached), reference_dna_fit (does it fit
the hook/proof/reveal-timing mechanism given below for the chosen architecture), non_swappable (how
hard would this be to swap for a competitor — 5 = very hard), story_potential (room for real
escalation), claim_safety (5 = makes no claim beyond what's given).

Return ONLY this JSON, no prose, no markdown fences:
{
  "candidates": [
    {
      "statement": string,
      "creative_device": string,
      "situation": string,
      "why_curious": string,
      "why_not_swappable": string,
      "scores": {"originality": int, "curiosity": int, "emotional_truth": int, "visual_potential": int,
                 "product_integration": int, "reference_dna_fit": int, "non_swappable": int,
                 "story_potential": int, "claim_safety": int}
    }
  ]
}"""


def _user_message(
    product_name: str,
    category: str,
    target_audience: str,
    usp: str,
    benefits: list[str],
    insight_block: str,
    architecture_name: str,
    architecture_purpose: str,
    reference_dna_notes: str,
) -> str:
    return (
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience (as given — read this carefully for the real situation): {target_audience}\n"
        f"USP: {usp or 'not given'}\n"
        f"Key benefits: {', '.join(benefits) or 'not given'}\n\n"
        f"{insight_block}\n"
        f"Chosen architecture: {architecture_name} — {architecture_purpose}\n"
        f"{reference_dna_notes}\n"
    )


def _parse_candidate(raw: dict) -> CreativePremise | None:
    if not isinstance(raw, dict):
        return None
    statement = str(raw.get("statement") or "").strip()
    if not statement:
        return None
    raw_scores = raw.get("scores") or {}
    scores = {k: int(raw_scores.get(k) or 0) for k in _SCORE_KEYS}
    return CreativePremise(
        statement=statement,
        creative_device=str(raw.get("creative_device") or ""),
        situation=str(raw.get("situation") or ""),
        why_curious=str(raw.get("why_curious") or ""),
        why_not_swappable=str(raw.get("why_not_swappable") or ""),
        scores=scores,
        total_score=sum(scores.values()),
    )


# A generated premise that's really just the insight restated ("a mother
# wants her child to be healthy") slipping past the model's own self-scoring
# — same denylist convention as creative_insight_service, applied here as a
# deterministic safety net rather than trusting self-grading alone.
_RESTATED_INSIGHT_SIGNALS = [
    "wants her child to be healthy",
    "wants their child to be healthy",
    "wants the best for",
    "cares about their family's health",
    "wants to be healthy",
]


def _is_restated_insight(statement: str) -> bool:
    low = statement.lower()
    return any(sig in low for sig in _RESTATED_INSIGHT_SIGNALS)


def select_strongest_premise(candidates: list[CreativePremise]) -> CreativePremise | None:
    """Deterministic selection — never a second LLM call. Filters out any
    candidate that's really just a restated insight despite scoring itself
    well, then picks the highest total score, tie-broken by non_swappable
    (the brief's own strongest signal of a genuine creative idea vs. a
    generic one) then curiosity."""
    valid = [c for c in candidates if not _is_restated_insight(c.statement)]
    pool = valid or candidates  # if everything got filtered, fall back rather than return nothing
    if not pool:
        return None
    return max(pool, key=lambda c: (c.total_score, c.scores.get("non_swappable", 0), c.scores.get("curiosity", 0)))


def generate_premises(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    usp: str = "",
    benefits: list[str] | None = None,
    insight_block: str = "",
    architecture_name: str = "",
    architecture_purpose: str = "",
    reference_dna_notes: str = "",
) -> list[CreativePremise]:
    """Never raises — returns [] on any failure, caller proceeds without a
    premise (same fail-open convention as every other stage)."""
    try:
        user_msg = _user_message(
            product_name, category, target_audience, usp, benefits or [], insight_block,
            architecture_name, architecture_purpose, reference_dna_notes,
        )
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.openrouter_text_model,
                max_output_tokens=1400,
                json_mode=True,
            ),
            label="creative_premise",
        )
        data = json.loads(text)
        raw_candidates = data.get("candidates") or []
        candidates = [c for c in (_parse_candidate(r) for r in raw_candidates) if c is not None]
        return candidates[:MAX_CANDIDATES]
    except Exception as e:
        logger.warning("Creative premise generation failed, proceeding without a premise: %s", e)
        return []


def generate_and_select_premise(**kwargs) -> CreativePremise | None:
    candidates = generate_premises(**kwargs)
    if not candidates:
        return None
    if len(candidates) < MIN_CANDIDATES:
        logger.info("Only %d creative premise candidate(s) generated (wanted >= %d)", len(candidates), MIN_CANDIDATES)
    return select_strongest_premise(candidates)
