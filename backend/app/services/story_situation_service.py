import json
import logging
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.models.product import ScriptLanguage, StorySituation, StorySituationsInput, StorySituationsResult
from app.services.creative_angles import catalog_prompt_block, valid_angle_labels
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import build_product_creative_contract
from app.services.product_context_validator import detect_category_drift_signal
from app.services.semantic_story_judge_service import dedupe_by_cluster, judge_story_situations

logger = logging.getLogger("story_situation_service")

# When the contract flags a known risky role, ask for a few extra candidates
# so filtering out any that drift still leaves a full batch — cheap (same
# single call, slightly larger response) and only changes behavior for a
# product that actually carries a role_risk_key; every other product's
# request is completely unchanged.
_DRIFT_FILTER_BUFFER = 4

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

{language_note}For each situation produce:
- "title": a punchy 3-7 word title
- "description": 1-3 sentences establishing the person, their situation, and the emotional stakes
- "emotion": the core emotion driving it (e.g. "fear", "pride", "relief", "hope")
- "persona": the protagonist/target character (e.g. "first-time gym-goer", "worried father")
- "marketing_angle": the strategic angle this story sells on (e.g. "myth vs reality", "transformation", "expert authority")
- "category": a short thematic label you choose for this situation (e.g. "Emotional", "Educational")
- "difficulty": "easy", "medium", or "hard" — how complex this would be to actually produce (cast, locations, VFX)
- "estimated_length": a realistic short-form runtime, one of "15s", "30s", "60s"
- "virality_score": a number 0.0-10.0 with one decimal place, your honest calibrated estimate of shareability —
  spread your scores realistically across the batch, do not cluster everything above 9

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
        angle_catalog=catalog_prompt_block(), language_note=_language_note(language)
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


def generate_situations(payload: StorySituationsInput) -> StorySituationsResult:
    """Stage 3.5 — structured product -> diverse story-situation options for
    the user to pick from. This is the FIRST creative decision in the whole
    pipeline (Product -> ProductCreativeContract -> Choose Your Story ->
    ... -> Final Script), so it now builds and is grounded by the same
    Product Creative Contract every later stage receives — the user can no
    longer be offered a card that fundamentally misrepresents what the
    product is before the script pipeline ever runs."""
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

    # Only pad the request (and only filter afterward) for a product whose
    # contract actually flags a known risky role — every other product's
    # request/response shape is completely unchanged.
    has_role_risk = bool(contract.role_risk_keys)
    request_count = payload.count + _DRIFT_FILTER_BUFFER if has_role_risk else payload.count

    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_system_prompt(payload.script_language),
            contents=[_build_user_message(payload, contract_block, request_count)],
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

        # Phase 3 — Semantic Story Judge: catches drift that uses none of
        # the deterministic detector's known patterns (e.g. "gets ready for
        # his morning routine before his workout" — no food/fitness-
        # supplement keyword, but the product's role has still quietly
        # become a generic wellness item). Only ever runs for a product
        # whose contract already flagged a real risk — same cost-control
        # gate as the deterministic check.
        judgments = judge_story_situations(contract, raw_items) if raw_items else []
        if judgments is None:
            # Judge unavailable this run (Phase 3 §K) — conservative
            # degrade to the deterministic-only result already computed
            # above. NEVER "judge failed -> trust the raw candidates";
            # that would reopen exactly the fail-open hole Phase 2C closed.
            logger.warning(
                "Semantic story judge unavailable for %s — keeping deterministic-only result (%d candidates)",
                p.product_name, len(raw_items),
            )
        else:
            # UNCERTAIN and CLEAR_DRIFT are both excluded — "uncertain" is
            # never silently accepted (§A6). Any candidate the judge didn't
            # return a judgment for at all is also excluded, not trusted.
            clear_pass_judgments = [j for j in judgments if j.decision == "clear_pass" and j.candidate_index < len(raw_items)]
            semantic_dropped = len(raw_items) - len(clear_pass_judgments)
            if semantic_dropped:
                logger.info(
                    "Semantic judge filtered %d additional story situation(s) for %s (clear_drift or uncertain)",
                    semantic_dropped, p.product_name,
                )
            # Semantic deduplication ("same idea, different clothes", Phase
            # 3 Part C) over whatever survived judging — dedupe_by_cluster
            # returns original candidate_index values, no re-indexing needed.
            keep_indices = dedupe_by_cluster(clear_pass_judgments)
            dedup_dropped = len(clear_pass_judgments) - len(keep_indices)
            if dedup_dropped:
                logger.info(
                    "Semantic dedup removed %d near-duplicate story situation(s) for %s",
                    dedup_dropped, p.product_name,
                )
            raw_items = [item for i, item in enumerate(raw_items) if i in keep_indices]

    situations = []
    for item in raw_items[:payload.count]:
        item = {**item, "recommended_angles": valid_angle_labels(item.get("recommended_angles", []))}
        situations.append(StorySituation(id=uuid.uuid4().hex[:12], **item))
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
