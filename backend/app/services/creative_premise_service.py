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
from app.services.product_context_service import ProductCreativeContract
from app.services.product_context_validator import detect_category_drift_signal

logger = logging.getLogger("creative_premise_service")

MIN_CANDIDATES = 3
MAX_CANDIDATES = 7

# The 10 evaluation criteria, each scored 1-5 by the model itself in the SAME
# call that generates the candidates (keeps this a single LLM call rather
# than generate-then-separately-judge). diversity_from_recent is neutral
# (auto-filled 5) when no recent-territory history was given — see
# _parse_candidate.
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
    "diversity_from_recent",
]


@dataclass
class CreativePremise:
    statement: str
    creative_device: str
    situation: str
    why_curious: str
    why_not_swappable: str
    # Explicit structured breakdown (task: "for each premise explicitly
    # record HUMAN INSIGHT / CREATIVE IDEA / VISUAL DEVICE / EMOTIONAL ENGINE
    # / PRODUCT ROLE / PAYOFF") — these are what creative_memory_service
    # persists as "territory" for the NEXT fresh generation to diverge from,
    # since comparing on creative_device text alone is too coarse (e.g. two
    # premises can both be "visual metaphor" while using genuinely different
    # engines, or share the same underlying engine under different wording).
    visual_device: str = ""
    emotional_engine: str = ""
    product_role: str = ""
    payoff: str = ""
    narrative_device: str = ""
    # FILMABLE CONCEPT (Phase 3C) — "what is the film?" must be answerable
    # BEFORE "what are the lines?". These four, together with visual_device
    # (WHAT WILL WE SEE) and payoff (THE REVEAL), are the concrete questions
    # a premise must answer or it's a metaphor/topic, not yet a story — see
    # _is_filmable_concept_weak().
    who: str = ""  # WHO — the specific character/persona this plays out through
    concrete_event: str = ""  # WHAT HAPPENS — an actual event, not a stated feeling
    human_tension: str = ""  # WHAT IS THE TENSION — specific and observable, not "wants a better life"
    what_changes: str = ""  # WHAT CHANGES — the before/after this event causes
    scores: dict = field(default_factory=dict)
    total_score: int = 0

    def prompt_block(self) -> str:
        return (
            "CREATIVE PREMISE (mandatory — this IS the idea; execute it, do not quietly replace it "
            "with a safer, more generic version of itself):\n"
            f'Premise: "{self.statement}"\n'
            f"Creative device/mechanism: {self.creative_device}\n"
            f"Narrative device: {self.narrative_device}\n"
            f"WHO: {self.who}\n"
            f"WHAT HAPPENS (the concrete event): {self.concrete_event}\n"
            f"THE TENSION: {self.human_tension}\n"
            f"WHAT CHANGES: {self.what_changes}\n"
            f"Visual device (what a camera actually shows): {self.visual_device}\n"
            f"Emotional engine: {self.emotional_engine}\n"
            f"Product role in the story: {self.product_role}\n"
            f"Payoff/reveal: {self.payoff}\n"
            f"Concrete situation it plays out in: {self.situation}\n"
            f"Why this creates curiosity: {self.why_curious}\n"
            f"Why a competitor's product couldn't just swap in unchanged: {self.why_not_swappable}\n"
            "This premise is not a topic and not a restated benefit — every beat below must exist "
            "because it serves THIS specific idea. If a beat could be written the same way for any "
            "other product in this category, it isn't executing the premise yet. If a metaphor is "
            "used anywhere (statement, situation, or elsewhere), WHAT HAPPENS/WHO/WHAT CHANGES above "
            "describe how that metaphor is FILMED through a character and an event — the script must "
            "dramatize it, not explain it in narration.\n"
        )


_SYSTEM_PROMPT = """You are a creative director generating CREATIVE PREMISES — not scripts, not
beats, one sentence each — for a short-form ad. A premise is the answer to "what is the interesting
idea here?" It is NOT a restated insight or topic.

If an APPROVED CREATIVE TERRITORY is given below, every premise you generate MUST dramatize THAT
territory into one specific situation — the territory is the lens (the underlying human tension and
creative question), the premise is one concrete example of it. Do not invent a different territory or
quietly drift back to a generic angle; every candidate should be a genuinely different SITUATION
inside the same approved lens, not a different lens.

If a CHOSEN STORY SITUATION is given below, it is not optional background — it is the user's own
already-made creative decision, and every candidate premise MUST be a genuine dramatization of THAT
exact concept. Its title is a compressed name for a concrete concept (e.g. a title like "Doctor ki
Advice, Healthy Life" means an actual doctor-patient scene — a consultation, an observation, unexpected
advice — must be part of the premise; a title naming a mother and son means an actual mother/son
relationship and an observable change must be part of it). Do not invent an unrelated premise that only
loosely gestures at the title's theme while actually being about something else — that is exactly the
failure this instruction exists to prevent. If the given description is more abstract than the title
(e.g. a mood or a metaphor), your job is to give it a WHO, a concrete EVENT, and a VISUAL mechanism —
FILM the metaphor through a character and something happening, never just restate or explain it.

EVERY premise, whether or not a chosen situation was given, must answer these concretely — if you
cannot answer one specifically, the premise is not ready yet:
- WHO does this happen to? (a specific person/persona, not "people" or "consumers")
- WHAT HAPPENS? (an actual event — a discovery, confrontation, reversal, unexpected action, reveal,
  social reaction, decision, interruption, demonstration — not just a feeling being described)
- WHAT IS THE TENSION? (something specific and observable — e.g. "hiding a habit from a colleague",
  not "wants a better life")
- WHAT CHANGES? (a concrete before/after this event causes)
A metaphor is not yet a story: "life feels colourless" is a feeling, not an event. It only becomes a
premise once it's embodied through a character, a situation, a concrete event, and a visual
progression — e.g. someone's world visually monochrome until a specific moment interrupts it. State
the concrete event, not the abstraction alone.

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

Generate between 3 and 7 candidates (prefer 5-7 when the brief genuinely supports that many distinct
angles). They must be genuinely different from each other — different situations, different creative
devices, different emotional registers — not 7 rewordings of the same underlying idea. If you cannot
find that many genuinely distinct ideas, generate fewer rather than padding with near-duplicates.

AVOID THE FIRST-INSTINCT DEVICE: for certain problem types, one device is so obvious it gets
generated by default every time, which defeats the purpose of generating multiple candidates at all.
Two concrete examples — do not let your candidate set default to these unless you've genuinely
considered and rejected real alternatives: (1) for a habit-replacement/craving problem, a personified
"craving creature/monster" that gets tamed, fed, or satisfied by the product; (2) for a
prevention/daily-wellness problem, a skeptical peer/colleague/mentor who confronts someone for only
acting reactively instead of preventively (this includes ANY dressed-up version of the same device —
a friend, a colleague, a mentor, a "future self", a family member, in an office/home/gym/anywhere —
the confronting-someone-about-being-reactive STRUCTURE is what makes it the same device, not the
specific relationship or setting). If a candidate you're about to write matches either pattern,
replace it with a genuinely different creative engine instead. Some engines to draw from (use
whichever the product/insight actually supports — never force one that doesn't fit): social
observation, behavioral contradiction, unexpected demonstration, character conflict, reverse
psychology, confession, documentary observation, absurdist humor, objection reversal, cultural
ritual, transformation, consequence reveal, interview, experiment, comparison, narrative mystery. At
most ONE of your candidates may use a personification/creature device, and at most ONE may use a
skeptical-third-party-confrontation device — the rest must come from genuinely different engines.

DIVERSITY FROM RECENT GENERATIONS: if a "RECENTLY USED CREATIVE TERRITORY" block is given below, it
lists the underlying engine/device/narrative-structure of concepts already generated for this exact
product — not by wording, by MECHANISM. A candidate that uses the same underlying mechanism as one of
those (a different character, a different metaphor object, a different profession, or different
wording standing in for the identical structure) is NOT a new candidate — it is a duplicate and must
be replaced with something that pulls from a genuinely different creative engine. "Different wording"
never counts as different. If none is given, this is the first generation for this product — no
constraint from this section applies.

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

For each candidate, explicitly record its HUMAN INSIGHT (already given below — restate which part
this candidate actually dramatizes), CREATIVE IDEA (the one-sentence premise), WHO, WHAT HAPPENS (the
concrete event), THE TENSION, WHAT CHANGES, VISUAL DEVICE (the specific thing a camera shows — not "a
person talking"), EMOTIONAL ENGINE (the feeling driving the piece: e.g. dread, pride, relief,
embarrassment, defiance, nostalgia — not just "positive"), NARRATIVE DEVICE (the structural shape:
e.g. confrontation, reveal, demonstration, mystery, montage, confession — the abstraction that stays
the same even if characters/objects change), PRODUCT ROLE (what specific job the product does inside
the idea, not "it's mentioned"), and PAYOFF (what the ending actually resolves or reveals — must
escalate/reveal/resolve the setup, not just restate it).

Then also self-score it honestly, 1-5 each, on: originality (a device that's the obvious first-instinct
choice for this exact problem type — see above — scores at most 3 here even if well-executed; true
originality requires more than good writing), curiosity, emotional_truth (does it reflect something
real, not sentimental), visual_potential (can a camera actually show this), product_integration (does
the product feel necessary, not attached), reference_dna_fit (does it fit the hook/proof/reveal-timing
mechanism given below for the chosen architecture), non_swappable (how hard would this be to swap for
a competitor — 5 = very hard), story_potential (room for real escalation), claim_safety (5 = makes no
claim beyond what's given), diversity_from_recent (5 = uses a genuinely different narrative device AND
emotional engine than everything in the RECENTLY USED CREATIVE TERRITORY block below; 1 = same
underlying mechanism as one of those with only wording/characters changed; score 5 automatically if no
such block is given — there is nothing to be different from yet).

Return ONLY this JSON, no prose, no markdown fences:
{
  "candidates": [
    {
      "statement": string,
      "creative_device": string,
      "narrative_device": string,
      "who": string,
      "concrete_event": string,
      "human_tension": string,
      "what_changes": string,
      "visual_device": string,
      "emotional_engine": string,
      "product_role": string,
      "payoff": string,
      "situation": string,
      "why_curious": string,
      "why_not_swappable": string,
      "scores": {"originality": int, "curiosity": int, "emotional_truth": int, "visual_potential": int,
                 "product_integration": int, "reference_dna_fit": int, "non_swappable": int,
                 "story_potential": int, "claim_safety": int, "diversity_from_recent": int}
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
    recent_territory_block: str = "",
    territory_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
) -> str:
    return (
        f"{contract_block}\n"
        f"Product: {product_name}\n"
        f"Category: {category}\n"
        f"Target audience (as given — read this carefully for the real situation): {target_audience}\n"
        f"USP: {usp or 'not given'}\n"
        f"Key benefits: {', '.join(benefits) or 'not given'}\n\n"
        f"{insight_block}\n"
        + (f"\nAPPROVED CREATIVE TERRITORY:\n{territory_block}\n" if territory_block else "")
        + (f"\nCHOSEN STORY SITUATION (the user's own creative decision — every candidate must "
           f"genuinely dramatize this exact concept, not just gesture at its theme):\n{situation_block}\n"
           if situation_block else "")
        + f"Chosen architecture: {architecture_name} — {architecture_purpose}\n"
        f"{reference_dna_notes}\n"
        + (f"\n{recent_territory_block}\n" if recent_territory_block else "")
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
        visual_device=str(raw.get("visual_device") or ""),
        emotional_engine=str(raw.get("emotional_engine") or ""),
        product_role=str(raw.get("product_role") or ""),
        payoff=str(raw.get("payoff") or ""),
        narrative_device=str(raw.get("narrative_device") or ""),
        who=str(raw.get("who") or ""),
        concrete_event=str(raw.get("concrete_event") or ""),
        human_tension=str(raw.get("human_tension") or ""),
        what_changes=str(raw.get("what_changes") or ""),
        scores=scores,
        total_score=sum(scores.values()),
    )


# FILMABLE CONCEPT gate (Phase 3C, Part 4) — a deterministic safety net, same
# convention as _is_restated_insight: don't just trust the model's own
# self-scoring, check the structural fields it was required to fill in
# actually got filled in with something real. A candidate missing 2+ of its
# four required filmable-concept answers is still a topic/metaphor, not yet a
# story, regardless of how well it scored itself.
_GENERIC_PLACEHOLDER_SIGNALS = ("n/a", "none", "not applicable", "tbd", "-")


def _is_answered(value: str) -> bool:
    v = value.strip().lower()
    return len(v) >= 8 and v not in _GENERIC_PLACEHOLDER_SIGNALS


def _is_filmable_concept_weak(premise: CreativePremise) -> bool:
    required = (premise.who, premise.concrete_event, premise.human_tension, premise.what_changes)
    unanswered = sum(1 for v in required if not _is_answered(v))
    return unanswered >= 2


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


def select_strongest_premise(
    candidates: list[CreativePremise], contract: ProductCreativeContract | None = None
) -> CreativePremise | None:
    """Deterministic selection — never a second LLM call. Filters out any
    candidate that's really just a restated insight despite scoring itself
    well, then picks the highest total score (which already includes
    diversity_from_recent — quality/originality/fit are not overridden by
    diversity alone, they're summed alongside it, per "optimize for
    QUALITY x ORIGINALITY x PRODUCT FIT x DIVERSITY, not diversity alone"),
    tie-broken by non_swappable (the brief's own strongest signal of a
    genuine creative idea vs. a generic one) then curiosity.

    PRODUCT TRUTH filter: a candidate whose statement/situation/creative
    device shows the deterministic category-drift signal (only checked at
    all for a product whose contract flags a known risky role) is excluded
    before scoring, same fail-open convention as the restated-insight
    filter — category correctness is a prerequisite, not a score.

    FILMABLE CONCEPT filter: a candidate that never answers who/what-happens/
    tension/what-changes concretely (see _is_filmable_concept_weak) is
    excluded next, same fail-open fallback — prefer a candidate that
    actually answers "what is the film?" over one that only sounds good."""
    valid = [c for c in candidates if not _is_restated_insight(c.statement)]
    pool = valid or candidates  # if everything got filtered, fall back rather than return nothing
    filmable = [c for c in pool if not _is_filmable_concept_weak(c)]
    pool = filmable or pool
    if contract is not None and contract.role_risk_keys:
        category_safe = [
            c for c in pool
            if not detect_category_drift_signal(" ".join([c.statement, c.situation, c.creative_device]), contract)
        ]
        pool = category_safe or pool
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
    recent_territory_block: str = "",
    territory_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
) -> list[CreativePremise]:
    """Never raises — returns [] on any failure, caller proceeds without a
    premise (same fail-open convention as every other stage).

    recent_territory_block (from creative_memory_service) is the diversity
    memory: a rendering of what creative territory recent FRESH generations
    for this exact product already used, so this call can steer away from
    it. Empty on the first generation for a product — no behavior change
    from before this existed.

    territory_block (from creative_territory_service, when the territory
    stage succeeded) is the approved creative territory every candidate
    premise must dramatize — empty when territory selection failed/was
    unavailable, in which case premise generation proceeds exactly as it
    did before the territory stage existed.

    situation_block (Phase 3C — from the user's OWN chosen Story Situation
    card, payload.selected_situation) is what every candidate premise must
    actually dramatize when one was picked; this is the fix for the root
    cause where premise generation used to run completely disconnected from
    the concept the user already chose (e.g. a "Doctor ki Advice" card
    producing a script with no doctor in it) — empty when no situation was
    selected yet (e.g. Choose-Your-Story card generation itself), in which
    case premise generation proceeds exactly as it did before."""
    try:
        user_msg = _user_message(
            product_name, category, target_audience, usp, benefits or [], insight_block,
            architecture_name, architecture_purpose, reference_dna_notes, recent_territory_block,
            territory_block, contract_block, situation_block,
        )
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.creative_model,
                max_output_tokens=3200,
                json_mode=True,
                label="creative_premise",
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


def generate_and_select_premise(contract: ProductCreativeContract | None = None, **kwargs) -> CreativePremise | None:
    candidates = generate_premises(**kwargs)
    if not candidates:
        return None
    if len(candidates) < MIN_CANDIDATES:
        logger.info("Only %d creative premise candidate(s) generated (wanted >= %d)", len(candidates), MIN_CANDIDATES)
    return select_strongest_premise(candidates, contract)
