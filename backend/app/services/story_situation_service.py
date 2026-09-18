import json
import logging
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.models.product import ScriptLanguage, StorySituation, StorySituationsInput, StorySituationsResult
from app.services import claim_safety_service
from app.services.creative_angles import catalog_prompt_block, valid_angle_labels
from app.services.creative_mechanism_catalog import catalog_prompt_block as mechanism_catalog_prompt_block
from app.services.creative_mechanism_catalog import valid_mechanism_label
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import build_product_creative_contract
from app.services.product_context_validator import detect_category_drift_signal
from app.services.semantic_story_judge_service import SemanticJudgment, dedupe_by_cluster, judge_story_situations

logger = logging.getLogger("story_situation_service")

# Story Ideas UI hard cap (2026-09-18 task, Part 12) — one generation NEVER
# shows more than this many cards, enforced server-side regardless of what
# StorySituationsInput.count requests.
MAX_STORY_IDEAS_PER_GENERATION = 6

# Internal candidate POOL size (Part 6) — generate a larger set, then filter
# down to the final MAX_STORY_IDEAS_PER_GENERATION, rather than generating
# exactly six and hoping all six survive every gate. Scales with the
# requested count but stays inside the 12-20 range the task specifies.
_POOL_MIN = 12
_POOL_MAX = 20
_POOL_MULTIPLIER = 3


def _pool_size(requested_count: int) -> int:
    return min(_POOL_MAX, max(_POOL_MIN, requested_count * _POOL_MULTIPLIER))


# Above this genericness_risk (as a fraction of the mechanism cap check
# below), no single creative_mechanism may claim more than this share of the
# final selection — the mechanism-VARIETY requirement (Part 4): "2-3 may use
# X, 2-3 may use Y, others use different mechanisms" as a soft cap, not a
# forced distribution.
_MAX_PER_MECHANISM_IN_FINAL = 3

_LANGUAGE_NOTES: dict[ScriptLanguage, str] = {
    ScriptLanguage.english: (
        'LANGUAGE: Write every "title" and "description" in natural conversational English.\n\n'
    ),
    ScriptLanguage.hindi: (
        'LANGUAGE (mandatory): Write every "title" and "description" ENTIRELY in Devanagari script '
        "(हिंदी), the way a creative director would actually pitch it in the room — natural spoken "
        "Hindi, not a stiff formal translation. Write directly in Hindi from the first draft; do NOT "
        "compose it in English and translate. The product/brand name itself may stay in Roman script "
        "if that's how it's branded.\n\n"
    ),
    ScriptLanguage.hinglish: (
        'LANGUAGE (mandatory): Write every "title" and "description" in natural spoken Hinglish — '
        "Hindi sentence structure and vocabulary in ROMAN (Latin) script, code-switching to English "
        "for words Indian audiences naturally say in English — the way a creative director would "
        "actually pitch it in the room. Write directly in Hinglish from the first draft; do NOT "
        "compose it in English and translate it — a translated pitch always reads stiff.\n\n"
    ),
}


def _language_note(language: ScriptLanguage) -> str:
    return _LANGUAGE_NOTES.get(language, _LANGUAGE_NOTES[ScriptLanguage.hinglish])


_SYSTEM_PROMPT_TEMPLATE = """You are an award-winning creative director at an advertising agency, running an
ideation session — NOT writing a script. Your job is to propose distinct marketing angles ("story
situations") for a product: each one names a person, a problem or context, and an emotional arc
that could become a short-form video ad. A story situation is a premise, never dialogue or scenes.

If a PRODUCT CREATIVE CONTRACT is given below, it is immutable factual grounding — read it FIRST,
before inventing anything. Generate story situations INSIDE the product's actual factual category and
intended consumer behavior. Do not infer what the product is used for from an ambiguous word in its
name (a product with "masala" in its name is not automatically a cooking ingredient if the contract
says otherwise). This is not a restriction on setting, character, emotion, humor, or structure — a
situation can still involve family, friends, office, festivals, restaurants, travel, or any social
context, AS LONG AS the product's actual real-world role in that situation stays correct. The
difference is never the setting; it's what role the product plays. Follow this hierarchy:
PRODUCT TRUTH -> AUDIENCE -> BEHAVIOR -> TENSION -> SITUATION -> STORY — never PRODUCT NAME ->
free association -> situation.

You must work for ANY industry (FMCG, healthcare, finance, education, SaaS, e-commerce, automotive,
real estate, etc.) — never fall back on a fixed list of personas or categories. Infer the personas,
emotional categories, and marketing angles that make sense for THIS specific product, audience, and
category from the data you're given (and from the Product Creative Contract above, when given, which
takes precedence over any generic assumption). Reason about who actually buys/uses/is affected by this
product, what they fear or hope for, and what conflicts or transformations are believable for them.

IMPORTANT — do not overcorrect into repetition: if a Product Creative Contract narrows the product's
real category (e.g. a habit-replacement product), that does NOT mean every situation must explicitly
mention the specific habit — vary the human situation, tension, and storytelling device while keeping
the product's role consistent with the contract. Forcing the same literal scenario into every card is
exactly the generic convergence this whole exercise exists to avoid.

Maximize diversity across the full set of situations you return. No two situations may share the same
persona archetype, hook angle, emotional core, conflict, or resolution. Vary across multiple thematic
categories in the same batch (for example: emotional/relational stories, inspirational/transformation
stories, educational/expert-authority stories, social/peer-context stories, everyday-lifestyle stories)
— but choose category labels that fit this product rather than reusing a fixed taxonomy.

CREATIVE DNA — real reference ad scripts for this exact space show these are the mechanisms that
actually work; build candidates FROM them, don't just describe a product:
- SHOW THE BEHAVIOR, don't explain the emotion — a specific action (reaching into a pocket, opening a
  packet, checking a note) beats an abstract feeling statement every time.
- An OBJECT can carry the whole story (a packet, a rupee note, a physical ritual) — it can create
  curiosity, contrast, and a reveal on its own.
- RITUAL CONTINUITY: the strongest recurring idea is not "quit the habit" — it's "the familiar
  ritual/taste continues through a different choice." Do not force this into every candidate.
- Persuasion mostly comes from a PEER, a colleague, a sibling, or the person's OWN realization — not
  primarily an authority figure lecturing them. Family stories are fine; avoid a parent/doctor simply
  telling the person what to do as the default device.
- Natural, conversational, SPEAKABLE Hinglish/Hindi — never stiff AI-advertising phrasing like "every
  choice is a step toward a healthier tomorrow."
- VALUE MATH is a real mechanism, not just "a money angle": a specific number, visually accumulated
  (a daily amount into a monthly total), that produces a realization — use it where it genuinely fits.
- CHARACTER-AS-PROOF: a character's personality can be established through behavior BEFORE the product
  ever appears, so the product choice reads as a natural extension of who they are.
- Prefer concrete, sensory, BEHAVIORAL specificity over abstract statements ("his life was full of
  stress" is weak; a specific recurring action is strong).

CREATIVE MECHANISM VOCABULARY — internally construct each candidate from a HUMAN SITUATION + a SPECIFIC
BEHAVIOR + an OBJECT/RITUAL + a TENSION + one of these CREATIVE MECHANISMS + the PRODUCT'S ROLE + a
REVEAL/TURN + a PAYOFF. These are primitives to combine, never mandatory templates — preserve real
creative freedom in how you use them:

{mechanism_catalog}

IMPORTANT — do not force the same one or two mechanisms into every candidate. Across the full batch you
return, aim for REFERENCE-INSPIRED VARIETY: several genuinely different mechanisms represented (not
every candidate as object-driven-reveal-plus-ritual-replacement), so the set doesn't read as the same
advertisement with different characters wearing different mechanism labels.

{language_note}For each situation produce:
- "title": a punchy 3-7 word title
- "description": 1-3 sentences establishing the person, their situation, and the emotional stakes
- "human_situation": the specific person and moment this plays out in — more concrete than `description`,
  answering "who, specifically, and in what specific moment?"
- "behavioral_tension": a SPECIFIC, observable tension (e.g. "hiding a habit from a colleague who'd
  judge him"), never a category-level generality ("wants a better life")
- "creative_mechanism": exactly ONE label from the CREATIVE MECHANISM VOCABULARY above, copied exactly
- "creative_engine": ONE sentence combining the specific behavior + object/ritual + creative turn —
  e.g. "At a family photo, a grandfather's familiar pocket-reach creates an expected reveal, but the
  object in his hand has changed." Must be concrete enough that an independent reader could picture the
  actual moment, not a restated theme.
- "product_role": the specific job the product does INSIDE this idea (not "it's mentioned")
- "emotion": the core emotion driving it (e.g. "fear", "pride", "relief", "hope")
- "persona": the protagonist/target character (e.g. "first-time gym-goer", "worried father")
- "marketing_angle": the strategic angle this story sells on (e.g. "myth vs reality", "transformation", "expert authority")
- "category": a short thematic label you choose for this situation (e.g. "Emotional", "Educational")
- "difficulty": "easy", "medium", or "hard" — how complex this would be to actually produce (cast, locations, VFX)
- "estimated_length": a realistic short-form runtime, one of "15s", "30s", "60s"
- "virality_score": a number 0.0-10.0 with one decimal place, your honest calibrated estimate of shareability —
  spread your scores realistically across the batch, do not cluster everything above 9

GENERICNESS SELF-CHECK before finalizing each candidate — if any answer is NO, revise or replace it:
(1) Remove the product name — is there still an interesting human situation? (2) Could this exact
concept sell toothpaste, perfume, insurance, or another unrelated consumer product unchanged? If yes,
it's too generic. (3) Is there a specific behavior that makes this impossible to swap into another
generic story? (4) Is it driven by an event/behavior/object/reveal, not an emotional explanation?

If a list of already-shown titles is provided, none of your new situations may repeat those titles or
be near-duplicates of their premise — treat them as creatively off-limits.

For every situation, also pick "recommended_angles": 5-8 CREATIVE ANGLES (execution styles — HOW the
story is filmed/told, not the marketing_angle, which is WHY it sells) that genuinely fit THIS
situation's persona, conflict, and production complexity. Choose only from this vocabulary, copying
labels exactly as written — do not invent new ones or reword them:

{angle_catalog}

Pick angles that are actually distinct fits for this specific situation, not a generic default set —
e.g. a father-son story genuinely suits "Father-Son", "Emotional Conversation", or "Meta Glasses POV"
(a father's first-person view), while a factory-workers-quit-together story suits "Social Experiment /
Challenge" or "Documentary" far more than "Doctor Testimonial".

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{{
  "situations": [
    {{
      "title": string,
      "description": string,
      "human_situation": string,
      "behavioral_tension": string,
      "creative_mechanism": string,
      "creative_engine": string,
      "product_role": string,
      "emotion": string,
      "persona": string,
      "marketing_angle": string,
      "category": string,
      "difficulty": string,
      "estimated_length": string,
      "virality_score": number,
      "recommended_angles": [string]
    }}
  ]
}}
"""


def _system_prompt(language: ScriptLanguage) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        angle_catalog=catalog_prompt_block(),
        mechanism_catalog=mechanism_catalog_prompt_block(),
        language_note=_language_note(language),
    )


def _build_user_message(payload: StorySituationsInput, contract_block: str, request_count: int) -> str:
    p = payload.structured_product
    exclude_block = (
        "\n".join(f"- {t}" for t in payload.exclude_titles) if payload.exclude_titles else "(none yet)"
    )

    return (
        f"{contract_block}\n"
        f"Product: {p.product_name}\n"
        f"Target audience: {p.target_audience}\n"
        f"Product category: {payload.product_category}\n"
        f"Ingredients: {', '.join(p.ingredients) or 'unknown'}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Tone: {p.tone or 'unspecified'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n\n"
        f"Generate exactly {request_count} story situations.\n\n"
        f"Titles already shown to the user (do not repeat or near-duplicate these):\n{exclude_block}"
    )


def _situation_text(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "description", "persona", "marketing_angle"))


def _claim_safety_fields(payload: StorySituationsInput) -> "tuple[str, list[str], list[str]]":
    """product_name, ingredients, approved_claims — same preference order as
    script_service._claim_safety_inputs (Product Library context first, the
    manually structured product otherwise), duplicated locally rather than
    imported since script_service.py's version takes a ScriptGenerationInput,
    not a StorySituationsInput; the logic is intentionally identical."""
    ctx = payload.product_context
    p = payload.structured_product
    if ctx is not None:
        return ctx.name, list(getattr(ctx, "ingredients", []) or p.ingredients), list(getattr(ctx, "approved_claims", []) or [])
    return p.product_name, list(p.ingredients or []), []


def _claim_safety_prefilter_evidence(item: dict, product_name: str, ingredients: list[str]) -> str:
    """Free, deterministic-only screen (Part 9/10) — reuses
    claim_safety_service's regex detectors directly rather than its full
    check_claim_safety_and_coercion(), since that escalates to an LLM call
    on every miss and this runs once PER CANDIDATE in a 12-20 candidate
    pool (a per-candidate LLM call would be far too costly here). The
    implied/metaphorical-claim and emotional-coercion layer that regex
    structurally can't catch is instead handled by the SAME batched
    semantic judge call below (see SemanticJudgment.implied_claim/
    emotional_coercion) — one LLM call for the whole pool, not one per
    candidate. Returns the offending clause, or ""."""
    text = _situation_text(item)
    evidence = claim_safety_service.detect_explicit_ingredient_efficacy_claim(text, ingredients)
    if evidence:
        return evidence
    return claim_safety_service.detect_explicit_product_efficacy_claim(text, product_name)


def _select_final_six(
    items: list[dict], candidate_indices: list[int], judgment_by_index: dict[int, SemanticJudgment], limit: int,
) -> list[int]:
    """Mechanism-variety-aware selection (Part 4/8) over `candidate_indices`
    ONLY (the actual gate survivors — a non-survivor must never occupy a
    mechanism-cap slot and crowd out a survivor sharing its mechanism).
    Ranks by creative_potential (highest first), then greedily fills the
    final list while capping how many candidates share the same
    creative_mechanism at _MAX_PER_MECHANISM_IN_FINAL, so the result is
    "reference-inspired variety", not "reference-mechanism repetition".
    Falls through to fill any remaining slots ignoring the cap if too few
    distinct mechanisms exist among the survivors — never returns fewer
    than min(limit, len(candidate_indices)) purely because of the variety
    preference. Returns original list indices."""
    ranked = sorted(
        candidate_indices,
        key=lambda i: judgment_by_index[i].creative_potential if i in judgment_by_index else 0.0,
        reverse=True,
    )
    mechanism_counts: dict[str, int] = {}
    selected: list[int] = []
    for i in ranked:
        if len(selected) >= limit:
            break
        mechanism = str(items[i].get("creative_mechanism") or "")
        if mechanism_counts.get(mechanism, 0) >= _MAX_PER_MECHANISM_IN_FINAL:
            continue
        selected.append(i)
        mechanism_counts[mechanism] = mechanism_counts.get(mechanism, 0) + 1
    if len(selected) < limit:
        for i in ranked:
            if len(selected) >= limit:
                break
            if i not in selected:
                selected.append(i)
    return selected


# STRONG CONCEPT badge (Part 15) — an AND of multiple independently-earned
# conditions, never a numeric score threshold alone. A candidate scoring
# 9.1/10 on creative_potential alone does NOT automatically qualify; it must
# also be unambiguously product-correct, non-generic, claim-safe, and
# genuinely distinct (survived dedup).
_STRONG_CONCEPT_MIN_ROLE_ALIGNMENT = 0.8
_STRONG_CONCEPT_MIN_CREATIVE_POTENTIAL = 0.7
_STRONG_CONCEPT_MAX_GENERICNESS = 0.5


def _is_strong_concept(j: "SemanticJudgment | None") -> bool:
    if j is None:
        return False
    return (
        j.decision == "clear_pass"
        and not j.implied_claim
        and not j.emotional_coercion
        and j.genericness_risk <= _STRONG_CONCEPT_MAX_GENERICNESS
        and j.creative_potential >= _STRONG_CONCEPT_MIN_CREATIVE_POTENTIAL
        and j.product_role_alignment >= _STRONG_CONCEPT_MIN_ROLE_ALIGNMENT
    )


def generate_situations(payload: StorySituationsInput) -> StorySituationsResult:
    """Stage 3.5 — structured product -> diverse story-situation options for
    the user to pick from. This is the FIRST creative decision in the whole
    pipeline (Product -> ProductCreativeContract -> Choose Your Story ->
    ... -> Final Script), so it now builds and is grounded by the same
    Product Creative Contract every later stage receives — the user can no
    longer be offered a card that fundamentally misrepresents what the
    product is before the script pipeline ever runs.

    Story Ideas Creative DNA upgrade (2026-09-18 task): generates a larger
    internal POOL (Part 6), screens it through claim-safety/category/
    genericness/distinctiveness gates, then selects a mechanism-variety-
    aware final six (Part 4/8) — never more than
    MAX_STORY_IDEAS_PER_GENERATION regardless of payload.count."""
    p = payload.structured_product
    ctx = payload.product_context
    contract = build_product_creative_contract(
        product_name=p.product_name,
        category=payload.product_category,
        target_audience=p.target_audience,
        usp=p.usp,
        benefits=list(p.key_benefits),
        product_context=ctx,
    )
    contract_block = contract.prompt_block()

    requested_count = min(payload.count, MAX_STORY_IDEAS_PER_GENERATION)
    has_role_risk = bool(contract.role_risk_keys)
    pool_count = _pool_size(requested_count)

    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_system_prompt(payload.script_language),
            contents=[_build_user_message(payload, contract_block, pool_count)],
            model=settings.creative_model,
            max_output_tokens=8192,
            json_mode=True,
            label="story_situations",
        ),
        label="generate_situations",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "Gemini returned malformed JSON while generating story ideas — the response may have "
            "been truncated. Try again, or ask for fewer situations."
        ) from e

    raw_items = data.get("situations", [])

    # Product-name/ingredient efficacy pre-filter (Part 9/10) — free,
    # deterministic, runs for EVERY product (not role-risk gated: an
    # unsupported claim is wrong regardless of category).
    product_name, ingredients, _approved = _claim_safety_fields(payload)
    claim_safe_items = [
        item for item in raw_items
        if not _claim_safety_prefilter_evidence(item, product_name, ingredients)
    ]
    claim_dropped = len(raw_items) - len(claim_safe_items)
    if claim_dropped:
        logger.info("Filtered %d candidate(s) with an explicit unsupported claim for %s", claim_dropped, p.product_name)
    raw_items = claim_safe_items

    if has_role_risk:
        # Product-truth safety net (Phase 2B §5-6): removes any candidate
        # whose title/description/persona/marketing_angle shows the product
        # being given a role its contract flags as forbidden (e.g. a food/
        # cooking role). Deterministic, free — the prompt fix above is the
        # primary mechanism; this only catches what still slips through.
        safe_items = [item for item in raw_items if not detect_category_drift_signal(_situation_text(item), contract)]
        dropped = len(raw_items) - len(safe_items)
        if dropped:
            logger.info("Filtered %d category-drifted story situation(s) for %s", dropped, p.product_name)
        # Deliberately NOT "safe_items or raw_items": unlike an internal
        # pipeline stage (territory/premise selection) that must pick SOME
        # candidate to let generation proceed, a story card is a user-facing
        # choice — showing fewer or zero cards (the user can click "Generate
        # More") is strictly safer than showing a full set of confirmed-wrong
        # ones. Falling back to the unfiltered set here would silently
        # defeat the entire filter in exactly the case that matters most:
        # every candidate genuinely misunderstood the product.
        raw_items = safe_items

    # Semantic Story Judge (Phase 3, extended by the 2026-09-18 Creative DNA
    # task) — now runs for EVERY product's pool, not just a role-risk one:
    # genericness/distinctiveness/claim-safety screening (Part 7/8/9-11) are
    # universal creative-quality concerns, not just category-drift concerns.
    # Still ONE batched call for the whole pool (cost control unchanged).
    judgments = judge_story_situations(contract, raw_items) if raw_items else []
    judgment_by_index: dict[int, SemanticJudgment] = {}
    if judgments is None:
        # Judge unavailable this run (Phase 3 §K) — conservative degrade to
        # the deterministic-only result already computed above, capped at
        # the requested count with no mechanism-variety selection (nothing
        # to rank by). NEVER "judge failed -> trust the raw candidates".
        logger.warning(
            "Semantic story judge unavailable for %s — keeping deterministic-only result (%d candidates)",
            p.product_name, len(raw_items),
        )
        final_items = raw_items[:requested_count]
    else:
        judgment_by_index = {j.candidate_index: j for j in judgments if j.candidate_index < len(raw_items)}
        # .passed now encodes decision==clear_pass AND non-generic AND no
        # implied claim AND no emotional coercion (Part 7/9-11) in one place
        # — see SemanticJudgment.passed.
        passed_judgments = [j for j in judgments if j.candidate_index < len(raw_items) and j.passed]
        semantic_dropped = len(raw_items) - len(passed_judgments)
        if semantic_dropped:
            logger.info(
                "Semantic judge filtered %d additional story situation(s) for %s (drift, generic, "
                "unsupported claim, or coercive framing)",
                semantic_dropped, p.product_name,
            )
        keep_indices = dedupe_by_cluster(passed_judgments)
        dedup_dropped = len(passed_judgments) - len(keep_indices)
        if dedup_dropped:
            logger.info(
                "Semantic dedup removed %d near-duplicate story situation(s) for %s", dedup_dropped, p.product_name,
            )
        survivor_indices = [i for i in range(len(raw_items)) if i in keep_indices]
        final_indices = _select_final_six(raw_items, survivor_indices, judgment_by_index, requested_count)
        final_items = [raw_items[i] for i in final_indices]
        judgment_by_index = {new_i: judgment_by_index[old_i] for new_i, old_i in enumerate(final_indices) if old_i in judgment_by_index}

    situations = []
    for idx, item in enumerate(final_items):
        item = {**item, "recommended_angles": valid_angle_labels(item.get("recommended_angles", []))}
        item["creative_mechanism"] = valid_mechanism_label(item.get("creative_mechanism", ""))
        strong = _is_strong_concept(judgment_by_index.get(idx))
        situations.append(StorySituation(id=uuid.uuid4().hex[:12], strong_concept=strong, **item))
    return StorySituationsResult(situations=situations)


# --- Concept quality floor (Task V2 §13) -------------------------------------
# generate_situations() above already degrades safely to a thin or empty
# result when every candidate fails the category-drift/semantic-judge/dedup
# gates (deliberately — see the comment above "Deliberately NOT 'safe_items
# or raw_items'"), but on its own that's indistinguishable from "the caller
# just asked for fewer cards". This wrapper adds the missing piece: a bounded
# retry loop (try again with a different batch, excluding what already
# failed, rather than silently accepting a thin result) and an explicit,
# structured "creative quality not met" state distinct from success — without
# modifying generate_situations() itself or its existing behavior/tests.
MAX_QUALITY_FLOOR_ATTEMPTS = 3
MIN_ACCEPTABLE_SITUATIONS = 1


@dataclass
class QualityFloorResult:
    situations: list[StorySituation] = field(default_factory=list)
    quality_floor_met: bool = False
    attempts_used: int = 0
    dominant_weakness: str = ""


def generate_situations_with_quality_floor(
    payload: StorySituationsInput,
    min_situations: int = MIN_ACCEPTABLE_SITUATIONS,
    max_attempts: int = MAX_QUALITY_FLOOR_ATTEMPTS,
) -> QualityFloorResult:
    """Calls the existing, unmodified generate_situations() up to
    max_attempts times. Each retry excludes every title already returned
    (rejected or not) so the model doesn't just resubmit the same batch.
    Never raises — a genuine below-floor result after all attempts comes
    back as quality_floor_met=False with whatever (possibly empty) situations
    survived the LAST attempt, never a fabricated filler card."""
    exclude = list(payload.exclude_titles)
    last_result = StorySituationsResult(situations=[])
    for attempt in range(1, max_attempts + 1):
        current_payload = payload.model_copy(update={"exclude_titles": exclude})
        try:
            last_result = generate_situations(current_payload)
        except Exception as e:
            logger.warning("Quality-floor attempt %d/%d raised, treating as empty: %s", attempt, max_attempts, e)
            last_result = StorySituationsResult(situations=[])
        if len(last_result.situations) >= min_situations:
            return QualityFloorResult(situations=last_result.situations, quality_floor_met=True, attempts_used=attempt)
        logger.info(
            "Quality floor not met on attempt %d/%d (%d situation(s) survived, wanted >= %d) — retrying",
            attempt, max_attempts, len(last_result.situations), min_situations,
        )
        exclude = exclude + [s.title for s in last_result.situations]
    return QualityFloorResult(
        situations=last_result.situations,
        quality_floor_met=False,
        attempts_used=max_attempts,
        dominant_weakness=(
            "every candidate across all attempts failed the product-truth/category-drift or "
            "semantic-dedup gate — the product/audience/category combination may need a richer brief, "
            "or this product's contract role_risk detection may be too strict for the given brief"
        ),
    )


def generate_situations_for_request(payload: StorySituationsInput) -> StorySituationsResult:
    """The router-facing entry point (2026-09-18 task, Part 13 — shortfall
    behavior). Sets the quality floor to the FULL requested/capped count
    (not just >=1), so generate_situations_with_quality_floor's existing
    bounded-retry loop keeps trying (never regenerating the exact same
    batch — see its exclude-titles logic) until either the full count
    survives or MAX_QUALITY_FLOOR_ATTEMPTS is exhausted. quality_floor_met
    then translates directly into generation_shortfall: False means the
    full requested set was reached, True means fewer survived even after
    bounded retries — shown as-is to the user, never padded with a
    fabricated card to reach the count."""
    requested_count = min(payload.count, MAX_STORY_IDEAS_PER_GENERATION)
    result = generate_situations_with_quality_floor(payload, min_situations=requested_count)
    return StorySituationsResult(situations=result.situations, generation_shortfall=not result.quality_floor_met)
