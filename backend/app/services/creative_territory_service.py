"""Creative Territory — the stage BEFORE premise generation that decides
"what fundamentally different human/creative lens should this ad explore?"

Insight -> TERRITORY (this module) -> Architecture -> Premise -> Hook -> Beat Outline -> Script

Why this exists: creative_premise_service already generates several distinct
premises and self-scores a diversity_from_recent criterion, but live testing
showed that isn't strong enough on its own — premises kept landing in the
same underlying territory (e.g. Immune Care's "a peer confronts the
protagonist about reactive-not-preventive behavior") even when the surface
execution (setting, character, device) varied. A territory is one level of
abstraction ABOVE a premise: not a situation or a device, but the underlying
human/behavioural/cultural lens the premise will later dramatize. Deciding
this FIRST, with an explicit anti-convergence check against recent territory
history, gives premise generation a genuinely different starting point each
time instead of just a different way to write the same starting point.

Never raises: a failure returns None, and the caller proceeds exactly as it
did before this stage existed (premise generation without a territory
block — the same fail-open convention as every other stage here).
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import ProductCreativeContract
from app.services.product_context_validator import detect_category_drift_signal

logger = logging.getLogger("creative_territory_service")

MIN_CANDIDATES = 5
# Was 8 — live testing showed 8 candidates x 13 text fields each routinely
# exceeded the token budget, truncating mid-string and failing JSON parsing
# on ~40% of calls. 6 keeps the "5-8" range's lower-middle while actually
# fitting reliably in the (now larger) token budget below.
MAX_CANDIDATES = 6

# Self-scored 1-5 each. novelty and distance_from_recent are DELIBERATELY
# separate from the "quality" dimensions — see select_strongest_territory:
# a low distance_from_recent isn't averaged away by high quality scores, it
# gates whether the candidate is even eligible, matching the task's explicit
# "novelty cannot be treated as just another small scoring number."
_SCORE_KEYS = [
    "human_truth",
    "product_relevance",
    "audience_relevance",
    "creative_potential",
    "visual_potential",
    "reference_dna_fit",
    "product_integration",
    "claim_safety",
    "novelty",
    "distance_from_recent",
]

# Below this self-scored distance_from_recent, a candidate is treated as
# "substantially the same underlying territory as something recently used"
# per the task's explicit rule, and excluded unless the whole pool is this
# close (fail-open — never reject every candidate outright).
_MIN_DISTANCE_FROM_RECENT = 3


@dataclass
class CreativeTerritory:
    territory_name: str
    territory_description: str
    human_tension: str
    behavioural_truth: str
    creative_question: str
    emotional_engine: str
    possible_story_world: str
    product_role: str
    why_it_fits_product: str
    reference_dna_fit: str
    novelty_vs_recent_concepts: str
    distinct_from_other_candidates: str
    claim_safety_note: str = ""
    avoidance_reason_if_rejected: str = ""
    scores: dict = field(default_factory=dict)
    total_score: int = 0

    def prompt_block(self) -> str:
        return (
            "CREATIVE TERRITORY (mandatory — the human/creative LENS every downstream stage must "
            "operate inside; the premise, hook, beats, and final script must all genuinely express "
            "this territory, not quietly slide back into a generic product story):\n"
            f'Territory: "{self.territory_name}" — {self.territory_description}\n'
            f"Human tension: {self.human_tension}\n"
            f"Behavioural truth: {self.behavioural_truth}\n"
            f"Creative question this territory poses: {self.creative_question}\n"
            f"Emotional engine: {self.emotional_engine}\n"
            f"Possible story world: {self.possible_story_world}\n"
            f"Product's role inside this territory: {self.product_role}\n"
            f"Why this territory genuinely fits this product: {self.why_it_fits_product}\n"
            "This is a LENS, not a scene — the premise below dramatizes it into one specific "
            "situation, but every beat must still be explainable as \"this happens because of the "
            "territory\", not just \"this happens because it's a common ad trope.\"\n"
        )


_SYSTEM_PROMPT = """You are a creative strategist deciding CREATIVE TERRITORY — the underlying human/
behavioural/cultural/emotional lens an ad will explore — BEFORE anyone writes a premise, a hook, or a
line of script. This is one level more abstract than a premise: a premise is one specific situation; a
territory is the LENS that situation would be an example of.

A territory is NOT:
- a script, a hook, a slogan, or a line of dialogue
- an architecture (dialogue/documentary/demonstration — that's HOW it gets built, not WHAT it explores)
- a visual gimmick or a specific device (a mirror, a calendar, a split-screen — those are devices a
  territory could be expressed THROUGH, not the territory itself)
- a different setting or character for the same underlying idea

CRITICAL TEST — "same idea, different clothes": if you changed the character, location, visual device,
dialogue format, or wording of two candidates and they would still be the same underlying advertising
idea, they are the SAME territory, not two different ones. For example "a friend confronts you about
your unhealthy routine" and "a colleague confronts you about your unhealthy routine" and "your spouse
confronts you about your unhealthy routine" are ALL the same territory (someone points out you're being
reactive, not proactive) — swapping the relationship doesn't create a new territory. But "the social
ritual of hiding a habit" and "the sensory experience of replacing a habit" ARE meaningfully different
territories, because the underlying human lens is genuinely different, not just redressed.

Discover territories from what is ACTUALLY given below — the real product, category, audience, human
insight, and reference-DNA notes — never from a generic template. Plausible KINDS of territory to
consider (not a checklist to fill in — invent what actually fits this specific product): the physical/
psychological ritual around the behavior; social identity/how the behavior is perceived; a hidden or
concealed behavior; the moment of deciding to change; the raw sensory experience; the specific cultural/
social environment around the category; one genuine, specific objection to changing; an everyday
(non-medical) consequence of the old behavior; an absurd contradiction worth exposing with humor;
something that can be shown rather than explained.

CRITICAL — category/usage grounding: if a PRODUCT CREATIVE CONTRACT is given below, treat its category,
use case, audience, and consumption context as FIXED FACT, not a creative starting point — every
territory must live inside that real context. Never redefine what the product fundamentally is, who
it's for, or how it's used based on a surface-level reading of the product's name (a word in a product
name can sound like it means something else — the contract, not the name, is the source of truth). A
territory may express this through any storytelling lens, device, or indirect metaphor; it must never
change the product's real-world role to do so.

Generate 5 to 6 candidate territories, genuinely different from EACH OTHER at the lens level (not just
different premises that would still count as the same territory per the test above — reread that test
before finalizing: if two candidates both reduce to "craving vs. willpower" or "urge vs. control" with
only different adjectives, they are ONE territory, not two). For each, record: territory_name,
territory_description, human_tension, behavioural_truth, creative_question, emotional_engine,
possible_story_world, product_role, why_it_fits_product, reference_dna_fit (does it fit the mechanism
style in the reference-DNA notes given below, if any), novelty_vs_recent_concepts (an honest sentence
comparing it against the RECENTLY USED TERRITORIES block below, if given), and
distinct_from_other_candidates (an honest sentence on how this differs from your OTHER candidates in
this same batch — if you can't articulate a real difference, it isn't one).

KEEP EVERY FIELD SHORT — one sentence or phrase each, never a paragraph. This is a structural map, not
prose; a long response risks being cut off before the JSON closes.

Self-score each 1-5 on: human_truth, product_relevance, audience_relevance, creative_potential,
visual_potential (can a camera actually show this world), reference_dna_fit, product_integration (is
the product a natural, necessary part of this lens, not attached to it), claim_safety (5 = requires no
claim beyond what's given), novelty (5 = a genuinely fresh angle for this product, not the first-
instinct one), distance_from_recent (5 = a genuinely different underlying lens than everything in the
RECENTLY USED TERRITORIES block below, per the "same idea different clothes" test — NOT just different
wording/characters/setting; 1 = essentially the same territory as one of those; score 5 automatically
if no such block is given).

Also run the AWARD-LEVEL TEST on each candidate mentally before scoring: would a viewer remember the
idea tomorrow; can it be explained in one sentence without the product name; is there a real human
observation underneath it; does it create curiosity before the product appears; does it have a built-in
payoff; could it become a film, not just dialogue; is the product naturally necessary to it; would
swapping to a competitor's product weaken the idea; is it specific to this audience. A candidate that
fails most of these should score low on creative_potential/product_integration/novelty rather than being
silently dropped — score honestly so selection can weigh it correctly.

If you believe a candidate is worth including despite being close to a recently used territory (a
genuinely strong, product-necessary reason), note that reason in avoidance_reason_if_rejected — leave
it empty otherwise.

Return ONLY this JSON, no prose, no markdown fences:
{
  "candidates": [
    {
      "territory_name": string,
      "territory_description": string,
      "human_tension": string,
      "behavioural_truth": string,
      "creative_question": string,
      "emotional_engine": string,
      "possible_story_world": string,
      "product_role": string,
      "why_it_fits_product": string,
      "reference_dna_fit": string,
      "novelty_vs_recent_concepts": string,
      "distinct_from_other_candidates": string,
      "avoidance_reason_if_rejected": string,
      "scores": {"human_truth": int, "product_relevance": int, "audience_relevance": int,
                 "creative_potential": int, "visual_potential": int, "reference_dna_fit": int,
                 "product_integration": int, "claim_safety": int, "novelty": int,
                 "distance_from_recent": int}
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
    reference_dna_notes: str,
    recent_territory_block: str,
    contract_block: str = "",
) -> str:
    return (
        f"{contract_block}\n"
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience (as given — read carefully for the real usage context): {target_audience}\n"
        f"USP: {usp or 'not given'}\n"
        f"Key benefits: {', '.join(benefits) or 'not given'}\n\n"
        f"{insight_block}\n"
        f"{reference_dna_notes}\n"
        + (f"\n{recent_territory_block}\n" if recent_territory_block else "")
    )


def _parse_candidate(raw: dict) -> CreativeTerritory | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("territory_name") or "").strip()
    if not name:
        return None
    raw_scores = raw.get("scores") or {}
    scores = {k: int(raw_scores.get(k) or 0) for k in _SCORE_KEYS}
    return CreativeTerritory(
        territory_name=name,
        territory_description=str(raw.get("territory_description") or ""),
        human_tension=str(raw.get("human_tension") or ""),
        behavioural_truth=str(raw.get("behavioural_truth") or ""),
        creative_question=str(raw.get("creative_question") or ""),
        emotional_engine=str(raw.get("emotional_engine") or ""),
        possible_story_world=str(raw.get("possible_story_world") or ""),
        product_role=str(raw.get("product_role") or ""),
        why_it_fits_product=str(raw.get("why_it_fits_product") or ""),
        reference_dna_fit=str(raw.get("reference_dna_fit") or ""),
        novelty_vs_recent_concepts=str(raw.get("novelty_vs_recent_concepts") or ""),
        distinct_from_other_candidates=str(raw.get("distinct_from_other_candidates") or ""),
        avoidance_reason_if_rejected=str(raw.get("avoidance_reason_if_rejected") or ""),
        scores=scores,
        total_score=sum(scores.values()),
    )


def _significant_tokens(*texts: str) -> set[str]:
    tokens: set[str] = set()
    for t in texts:
        for word in re.findall(r"[A-Za-z]{4,}", t or ""):
            tokens.add(word.lower())
    return tokens


_STOPWORDS = {
    "with", "that", "this", "their", "about", "someone", "person", "people", "product", "story",
    "makes", "being", "themselves", "which", "would", "could", "should", "while", "instead", "against",
}


def _deterministic_too_similar(a_tokens: set[str], b_tokens: set[str]) -> bool:
    """Free, regex-only safeguard alongside the model's own self-scoring —
    a crude but cheap "same idea, different clothes" check: high overlap in
    the significant (non-stopword) vocabulary describing the underlying
    tension/lens, independent of whether the model's self-score happened to
    be generous. Deliberately coarse (word overlap, not real semantics) —
    it's a safety net, not the primary mechanism."""
    a = a_tokens - _STOPWORDS
    b = b_tokens - _STOPWORDS
    if len(a) < 3 or len(b) < 3:
        return False
    overlap = len(a & b) / len(a | b)
    return overlap >= 0.5


def select_strongest_territory(
    candidates: list[CreativeTerritory],
    recent_concepts: list[dict] | None = None,
    contract: ProductCreativeContract | None = None,
) -> CreativeTerritory | None:
    """Deterministic — no second LLM call. Two-stage: (1) eligibility —
    exclude any candidate that is too close to a recently used territory,
    checked BOTH via the model's own distance_from_recent self-score AND a
    deterministic token-overlap safeguard against the actual recent
    territory text, unless doing so would empty the pool (never force
    novelty at the expense of having any candidate at all); (2) among the
    eligible pool, pick the highest total_score (which already sums
    human_truth/relevance/creative/visual/product-fit/claim-safety/novelty —
    quality and originality together, not novelty alone), tie-broken by
    product_integration then creative_potential."""
    if not candidates:
        return None

    # PRODUCT TRUTH filter — cheap, deterministic, and only ever active for
    # a product whose contract actually flags a known risky role (most
    # products' role_risk_keys is empty, so this is a no-op for them).
    # Category-correctness is a prerequisite, not one more score to weigh
    # against creative quality — a candidate that fails it is excluded
    # before scoring is even consulted, never merely penalized.
    if contract is not None and contract.role_risk_keys:
        category_safe = [
            c for c in candidates
            if not detect_category_drift_signal(
                " ".join([c.territory_name, c.territory_description, c.human_tension, c.possible_story_world, c.product_role]),
                contract,
            )
        ]
        candidates = category_safe or candidates  # fail-open: never reject every candidate outright

    recent = recent_concepts or []
    recent_token_sets = [
        _significant_tokens(
            c.get("territory_name", ""), c.get("human_tension", ""), c.get("creative_question", "")
        )
        for c in recent
        if c.get("territory_name")
    ]

    def too_close_to_recent(cand: CreativeTerritory) -> bool:
        if cand.scores.get("distance_from_recent", 5) < _MIN_DISTANCE_FROM_RECENT:
            return True
        cand_tokens = _significant_tokens(cand.territory_name, cand.human_tension, cand.creative_question)
        return any(_deterministic_too_similar(cand_tokens, rt) for rt in recent_token_sets)

    eligible = [c for c in candidates if not too_close_to_recent(c)]
    pool = eligible or candidates  # fail-open: never reject the entire batch

    # Cross-candidate dedup — a batch with no recent history at all (first
    # generation for a product) still needs real internal variety; the
    # model's own candidates can converge on each other even when nothing
    # existed to converge WITH. Greedily keep the highest-scoring candidate
    # from each cluster of mutually-similar ones (by the same deterministic
    # token-overlap test), rather than letting a near-duplicate silently win
    # just because it happened to self-score a point higher.
    pool_sorted = sorted(pool, key=lambda c: c.total_score, reverse=True)
    deduped: list[CreativeTerritory] = []
    for cand in pool_sorted:
        cand_tokens = _significant_tokens(cand.territory_name, cand.human_tension, cand.creative_question)
        if any(
            _deterministic_too_similar(cand_tokens, _significant_tokens(kept.territory_name, kept.human_tension, kept.creative_question))
            for kept in deduped
        ):
            continue
        deduped.append(cand)
    pool = deduped or pool  # fail-open here too

    return max(
        pool,
        key=lambda c: (c.total_score, c.scores.get("product_integration", 0), c.scores.get("creative_potential", 0)),
    )


def generate_territories(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    usp: str = "",
    benefits: list[str] | None = None,
    insight_block: str = "",
    reference_dna_notes: str = "",
    recent_territory_block: str = "",
    contract_block: str = "",
) -> list[CreativeTerritory]:
    """Never raises — returns [] on any failure, caller proceeds without a
    territory (premise generation falls back to its pre-territory
    behavior)."""
    try:
        user_msg = _user_message(
            product_name, category, target_audience, usp, benefits or [], insight_block,
            reference_dna_notes, recent_territory_block, contract_block,
        )
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.creative_model,
                max_output_tokens=6000,
                json_mode=True,
                label="creative_territory",
            ),
            label="creative_territory",
        )
        data = json.loads(text)
        raw_candidates = data.get("candidates") or []
        candidates = [c for c in (_parse_candidate(r) for r in raw_candidates) if c is not None]
        return candidates[:MAX_CANDIDATES]
    except Exception as e:
        logger.warning("Creative territory generation failed, proceeding without one: %s", e)
        return []


def generate_and_select_territory(
    recent_concepts: list[dict] | None = None,
    contract: ProductCreativeContract | None = None,
    **kwargs,
) -> CreativeTerritory | None:
    candidates = generate_territories(**kwargs)
    if not candidates:
        return None
    if len(candidates) < MIN_CANDIDATES:
        logger.info("Only %d creative territory candidate(s) generated (wanted >= %d)", len(candidates), MIN_CANDIDATES)
    return select_strongest_territory(candidates, recent_concepts, contract)
