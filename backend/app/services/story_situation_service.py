import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.models.product import ScriptLanguage, StorySituation, StorySituationsInput, StorySituationsResult
from app.services import claim_safety_service
from app.services.creative_angles import catalog_prompt_block, valid_angle_labels
from app.services.creative_mechanism_catalog import catalog_prompt_block as mechanism_catalog_prompt_block
from app.services.creative_mechanism_catalog import valid_mechanism_label
from app.services.hook_generation_service import _is_generic as _is_generic_hook_phrase
from app.services.hook_tactic_catalog import catalog_prompt_block as hook_tactic_catalog_prompt_block
from app.services.hook_tactic_catalog import valid_hook_tactic_label
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


# Budget-overshoot fix (2026-09-18 task) — the shared OpenRouter client
# default is 120s per HTTP attempt with up to 4 retries (~494s worst case
# for one call alone), which can already blow past the ~90s aggregate Story
# Ideas budget within the FIRST quality-floor attempt, before that loop's
# between-attempts budget check ever gets a chance to stop anything. These
# two constants bound ONLY the pool-generation call below (and, in
# semantic_story_judge_service.py, the judge call it triggers) — the two
# sequential LLM calls inside one Story Ideas "attempt" — without touching
# the shared 120s default any other pipeline stage still uses.
_STORY_IDEAS_CALL_TIMEOUT_SECONDS = 40.0
_STORY_IDEAS_MAX_ATTEMPTS = 2


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

HOOKS MENU — a hook has TWO SEPARATE layers, never confuse them: the HOOK TACTIC (HOW attention is
captured in the first 1-3 seconds — a technique) is a completely different thing from the CREATIVE
MECHANISM above (WHAT the underlying idea is). "Question" is a hook tactic; "the grandfather's pocket
reveal" is the creative mechanism/story — both get recorded, never merged into one field. For every
candidate, internally select the ONE hook tactic that genuinely fits its product/audience/creative
mechanism/situation/format/emotional trigger, from exactly this vocabulary:

{hook_tactic_catalog}

The selected tactic must be VISIBLE in the actual opening execution you describe, not just named. A
hook fails the quality bar and must be revised if it: could belong to any product, simply announces
the product, explains the benefit immediately with no curiosity created, reads as generic motivational
copy, doesn't create a visual/action/dialogue event, or doesn't connect naturally to this candidate's
own creative mechanism. Do NOT default to the same 2-3 hook tactics for every candidate — across the
full batch, intentionally create hook-tactic diversity while keeping every one genuinely well-fitted,
never forced just to hit a variety quota.

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
- "hook_type": exactly ONE label from the HOOKS MENU above, copied exactly — the TACTIC, never the idea
- "hook_mechanism": one sentence on WHY this tactic fits this product/audience/creative mechanism/
  situation/format/emotional trigger — the reasoning, not the execution itself
- "hook_execution": the actual concrete opening a viewer would see/hear in the first 1-3 seconds,
  visibly executing the chosen hook_type (e.g. for "Question": the actual line/moment the question is
  asked in-scene, not just a question mark appended to a sentence; for "Reaction in Action": the actual
  reaction described happening, before any cause is shown)
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
      "hook_type": string,
      "hook_mechanism": string,
      "hook_execution": string,
      "emotion": string,
      "persona": string,
      "marketing_angle": string,
      "category": string,
      "difficulty": string,
      "estimated_length": string,
      "virality_score": number
    }}
  ]
}}
"""

# Reliability fix (2026-09-18 task) — "recommended_angles" (a 5-8 item pick
# from a long catalog, per candidate) used to be generated for the WHOLE
# 12-20 candidate pool in the same call as everything else. It's the single
# largest purely-cosmetic field (used only by the UI's angle chips — never
# read by any filtering/selection/claim-safety/judge logic anywhere in this
# pipeline) and not needed to make the pool bigger/more verbose than it has
# to be for a model that's shown to truncate on large structured responses.
# Moved to a SEPARATE, much smaller enrichment call that only ever runs
# against the already-selected final <=6 survivors — same creative concept
# (angles are still generated, from the same catalog, with the same
# guidance), just deferred to operate on 6 items instead of 18. See
# _enrich_recommended_angles() below.
_ANGLE_ENRICHMENT_SYSTEM_PROMPT = """For each of the given short-form ad story situations, pick
"recommended_angles": 5-8 CREATIVE ANGLES (execution styles — HOW the story is filmed/told) that
genuinely fit THAT situation's persona, conflict, and production complexity. Choose only from this
vocabulary, copying labels exactly as written — do not invent new ones or reword them:

{angle_catalog}

Pick angles that are actually distinct fits for each specific situation, not a generic default set —
e.g. a father-son story genuinely suits "Father-Son", "Emotional Conversation", or "Meta Glasses POV"
(a father's first-person view), while a factory-workers-quit-together story suits "Social Experiment /
Challenge" or "Documentary" far more than "Doctor Testimonial".

Return ONLY this JSON, no prose, no markdown fences:
{{"angles": [{{"index": int, "recommended_angles": [string]}}]}}"""


def _angle_enrichment_user_message(situations_data: list[dict]) -> str:
    lines = [
        f"[{i}] title: {item.get('title', '')}\n"
        f"    description: {item.get('description', '')}\n"
        f"    persona: {item.get('persona', '')}\n"
        f"    marketing_angle: {item.get('marketing_angle', '')}"
        for i, item in enumerate(situations_data)
    ]
    return "\n".join(lines)


def _enrich_recommended_angles(situations_data: list[dict]) -> list[dict]:
    """Runs ONLY on the already-selected final survivors (<=
    MAX_STORY_IDEAS_PER_GENERATION, never the full pool). Never raises — a
    failure here just leaves recommended_angles unset on every item, which
    valid_angle_labels([]) already degrades safely to its documented
    fallback subset (never a missing/broken UI field, never blocks the
    response)."""
    if not situations_data:
        return situations_data
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_ANGLE_ENRICHMENT_SYSTEM_PROMPT.format(angle_catalog=catalog_prompt_block()),
                contents=[_angle_enrichment_user_message(situations_data)],
                model=settings.creative_model,
                max_output_tokens=1500,
                json_mode=True,
                label="story_situations_angle_enrichment",
                timeout=_STORY_IDEAS_CALL_TIMEOUT_SECONDS,
            ),
            label="story_situations_angle_enrichment",
            max_attempts=_STORY_IDEAS_MAX_ATTEMPTS,
        )
        data = _parse_situations_json(text)
        by_index = {int(e["index"]): e.get("recommended_angles", []) for e in data.get("angles", []) if "index" in e}
    except Exception as e:
        logger.warning("Recommended-angles enrichment failed, leaving angles unset (safe fallback applies): %s", e)
        return situations_data
    return [{**item, "recommended_angles": by_index.get(i, [])} for i, item in enumerate(situations_data)]


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    return text.strip()


def _salvage_array_objects(text: str, array_key: str) -> list[dict]:
    """Best-effort recovery for a TRUNCATED response (2026-09-18 task,
    "truncated JSON / incomplete final object"): when the response as a
    WHOLE doesn't parse because the model ran out of output budget partway
    through the array, most individual objects earlier in that array are
    still complete, valid JSON on their own — only the tail is cut off.
    Rather than discarding the entire batch over one incomplete trailing
    object, this scans for `array_key`'s `[...]`, finds each top-level
    `{...}` object by bracket-depth (not naive regex splitting — a value
    could itself contain braces/brackets in principle), and parses each
    independently, silently skipping any that don't parse (the incomplete
    tail, almost always). Returns [] (never raises) if the array itself
    can't even be located — the caller's existing "malformed JSON" error
    still fires in that case, exactly as before this fix."""
    marker = f'"{array_key}"'
    key_pos = text.find(marker)
    if key_pos == -1:
        return []
    array_start = text.find("[", key_pos)
    if array_start == -1:
        return []
    results: list[dict] = []
    i = array_start + 1
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] != "{":
            break
        depth = 0
        in_string = False
        escape = False
        start = i
        end = None
        while i < n:
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            i += 1
        if end is None:
            break  # ran off the end mid-object — this is the truncated tail, stop here
        candidate_text = text[start:end]
        try:
            obj = json.loads(candidate_text)
            if isinstance(obj, dict):
                results.append(obj)
        except json.JSONDecodeError:
            pass  # skip a malformed individual object, keep scanning the rest
        i = end
    return results


def _parse_situations_json(text: str, array_key: str = "situations") -> dict:
    """Robust parse for a story-ideas-shaped LLM JSON response (2026-09-18
    task): strips a markdown fence the model can still emit despite
    json_mode, strips trailing commas, and — only as a last resort, when
    the response still doesn't parse as a WHOLE — salvages whatever
    complete objects survive inside `array_key`'s array rather than
    discarding a truncated response entirely. A genuinely unrecoverable
    response (nothing parses, array not even found) still raises
    json.JSONDecodeError, unchanged from before this fix."""
    cleaned = _strip_markdown_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(no_trailing_commas)
    except json.JSONDecodeError as e:
        salvaged = _salvage_array_objects(cleaned, array_key)
        if salvaged:
            logger.warning(
                "Story-ideas response didn't parse as a whole (likely truncated) — salvaged %d complete "
                "object(s) from the '%s' array instead of discarding the entire batch.",
                len(salvaged), array_key,
            )
            return {array_key: salvaged}
        raise e


def _system_prompt(language: ScriptLanguage) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        angle_catalog=catalog_prompt_block(),
        mechanism_catalog=mechanism_catalog_prompt_block(),
        hook_tactic_catalog=hook_tactic_catalog_prompt_block(),
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


def _hook_quality_prefilter_reason(item: dict) -> str:
    """Free, deterministic HOOK QUALITY CHECK screen (Hooks Menu task) —
    reuses hook_generation_service's own generic-opener denylist rather than
    duplicating it, so the story-idea-level filter and the script-writing-
    time hook filter never disagree on what counts as generic. Deliberately
    does NOT reject a candidate purely for having no hook_execution at all
    (fail-open on absence, same convention as every optional-field default
    elsewhere in this pipeline) — only a candidate that DOES have one and it
    explicitly matches a known generic-opener pattern is rejected here. The
    deeper "does this genuinely create curiosity / connect to the creative
    mechanism" judgment is folded into the semantic judge's existing
    genericness_risk/creative_potential scoring (see
    semantic_story_judge_service._candidate_block, which now includes the
    hook fields), not a second LLM call."""
    execution = str(item.get("hook_execution") or "").strip()
    if execution and _is_generic_hook_phrase(execution):
        return "hook_execution matched a generic-opener pattern"
    return ""


_MAX_PER_HOOK_TYPE_IN_FINAL = 3


def _select_final_six(
    items: list[dict], candidate_indices: list[int], judgment_by_index: dict[int, SemanticJudgment], limit: int,
) -> list[int]:
    """Mechanism- AND hook-tactic-variety-aware selection (Part 4/8, extended
    by the Hooks Menu task for hook-tactic diversity) over `candidate_indices`
    ONLY (the actual gate survivors — a non-survivor must never occupy a
    variety-cap slot and crowd out a survivor sharing its mechanism/tactic).
    Ranks by creative_potential (highest first), then greedily fills the
    final list while capping how many candidates share the same
    creative_mechanism OR the same hook_type at their respective caps, so the
    result is "reference-inspired variety" on BOTH axes — never the same
    advertisement with different characters, and never the same 2-3 hook
    tactics reused for every concept. Falls through to fill any remaining
    slots ignoring both caps if too few distinct mechanisms/tactics exist
    among the survivors — never returns fewer than min(limit,
    len(candidate_indices)) purely because of the variety preference.
    Returns original list indices."""
    ranked = sorted(
        candidate_indices,
        key=lambda i: judgment_by_index[i].creative_potential if i in judgment_by_index else 0.0,
        reverse=True,
    )
    mechanism_counts: dict[str, int] = {}
    hook_type_counts: dict[str, int] = {}
    selected: list[int] = []

    def _fill(*, enforce_mechanism_cap: bool, enforce_hook_type_cap: bool) -> None:
        for i in ranked:
            if len(selected) >= limit:
                return
            if i in selected:
                continue
            mechanism = str(items[i].get("creative_mechanism") or "")
            hook_type = str(items[i].get("hook_type") or "")
            if enforce_mechanism_cap and mechanism_counts.get(mechanism, 0) >= _MAX_PER_MECHANISM_IN_FINAL:
                continue
            if enforce_hook_type_cap and hook_type_counts.get(hook_type, 0) >= _MAX_PER_HOOK_TYPE_IN_FINAL:
                continue
            selected.append(i)
            mechanism_counts[mechanism] = mechanism_counts.get(mechanism, 0) + 1
            hook_type_counts[hook_type] = hook_type_counts.get(hook_type, 0) + 1

    # Layered relaxation: both caps first, then relax hook-type diversity
    # (mechanism diversity matters more — it's the underlying idea, not just
    # the opening technique), then relax mechanism diversity too, so a pool
    # where every candidate happens to share one axis (e.g. all empty
    # hook_type) still gets genuine mechanism variety rather than both caps
    # collapsing together and letting the highest-scoring mechanism reclaim
    # every remaining slot.
    _fill(enforce_mechanism_cap=True, enforce_hook_type_cap=True)
    if len(selected) < limit:
        _fill(enforce_mechanism_cap=True, enforce_hook_type_cap=False)
    if len(selected) < limit:
        _fill(enforce_mechanism_cap=False, enforce_hook_type_cap=False)
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
            # Truncation fix (2026-09-18 task): bumped from 8192. A
            # reasoning-capable model can spend a large, variable share of
            # max_tokens on hidden reasoning before any visible output
            # starts (empirically confirmed for this exact failure class on
            # a different call site earlier this session) — 8192 was
            # sometimes insufficient headroom for an 18-candidate response
            # even before accounting for that. This is a ceiling, not a
            # guaranteed spend; real cost still tracks actual usage.
            max_output_tokens=16000,
            json_mode=True,
            label="story_situations",
            # Budget-overshoot fix (2026-09-18 task): a per-call timeout
            # shorter than the shared 120s client default — this call and
            # the semantic judge's are the two sequential LLM calls inside
            # one Story Ideas "attempt", and both must fit inside the ~90s
            # aggregate budget the quality-floor loop only checks BETWEEN
            # attempts (never mid-call). Story-Ideas-specific only — every
            # other pipeline stage's 120s default is untouched.
            timeout=_STORY_IDEAS_CALL_TIMEOUT_SECONDS,
        ),
        label="generate_situations",
        max_attempts=_STORY_IDEAS_MAX_ATTEMPTS,
    )

    try:
        data = _parse_situations_json(text)
    except json.JSONDecodeError as e:
        # Diagnostics fix (2026-09-18 task): previously logged nothing at
        # all beyond the bare error — this at least shows response length
        # and its head/tail (never the full text — could contain product
        # data — but shape alone tells you a lot: ends mid-string/mid-object
        # is a strong truncation signal, a trailing markdown fence is a
        # formatting signal, etc.), so a future occurrence is diagnosable
        # from logs alone without needing a live repro.
        logger.warning(
            "Story-ideas JSON parse failed (model=%s): length=%d chars, head=%r, tail=%r, error=%s",
            settings.creative_model, len(text), text[:120], text[-120:], e,
        )
        # Model-neutral (2026-09-18 task) — this used to hardcode "Gemini"
        # regardless of which model actually produced the bad response,
        # which made a production log line misleading evidence about which
        # model was really running. settings.creative_model is the exact
        # model= value the call above just used.
        raise ValueError(
            f"{settings.creative_model} returned malformed JSON while generating story ideas — the "
            "response may have been truncated. Try again, or ask for fewer situations."
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

    # Hooks Menu HOOK QUALITY CHECK — cheap deterministic screen (empty or
    # known-generic hook_execution), applied for every product.
    hook_ok_items = [item for item in raw_items if not _hook_quality_prefilter_reason(item)]
    hook_dropped = len(raw_items) - len(hook_ok_items)
    if hook_dropped:
        logger.info("Filtered %d candidate(s) with a low-quality hook execution for %s", hook_dropped, p.product_name)
    raw_items = hook_ok_items

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

    # Angle enrichment (2026-09-18 task, Option A) — runs on the already-
    # selected <=6 survivors only, never the 12-20 pool, so this small
    # second call never contributes to pool-generation truncation risk.
    final_items = _enrich_recommended_angles(final_items)

    situations = []
    for idx, item in enumerate(final_items):
        item = {**item, "recommended_angles": valid_angle_labels(item.get("recommended_angles", []))}
        item["creative_mechanism"] = valid_mechanism_label(item.get("creative_mechanism", ""))
        item["hook_type"] = valid_hook_tactic_label(item.get("hook_type", ""))
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

# Reliability fix (2026-09-18 task) — an AGGREGATE wall-clock budget for the
# whole quality-floor retry loop, on top of (never instead of) the existing
# per-call OpenRouter retry/timeout logic in openrouter_utils.py. Without
# this, up to MAX_QUALITY_FLOOR_ATTEMPTS full generate_situations() calls
# (each itself internally retried) could compound to many minutes with no
# overall cap — the confirmed mechanism behind the "Story Ideas stuck
# loading" report. Matches the frontend's POST_TIMEOUT_MS backstop
# (lib/api.ts) — this is the server-side half of the same fix.
DEFAULT_STORY_IDEAS_BUDGET_SECONDS = 90.0


@dataclass
class QualityFloorResult:
    situations: list[StorySituation] = field(default_factory=list)
    quality_floor_met: bool = False
    attempts_used: int = 0
    dominant_weakness: str = ""
    # True when the loop stopped because the wall-clock budget ran out
    # before max_attempts were exhausted (distinct from "tried everything
    # and still came up short") — surfaced for observability, not currently
    # part of the public API response.
    budget_exhausted: bool = False


def generate_situations_with_quality_floor(
    payload: StorySituationsInput,
    min_situations: int = MIN_ACCEPTABLE_SITUATIONS,
    max_attempts: int = MAX_QUALITY_FLOOR_ATTEMPTS,
    max_total_seconds: float | None = None,
) -> QualityFloorResult:
    """Calls the existing, unmodified generate_situations() up to
    max_attempts times. Each retry excludes every title already returned
    (rejected or not) so the model doesn't just resubmit the same batch.
    Never raises — a genuine below-floor result after all attempts (or after
    the time budget runs out) comes back as quality_floor_met=False with the
    BEST (most candidates) result seen across every attempt so far, never a
    fabricated filler card, and never silently discarding a stronger earlier
    attempt just because a later one happened to produce fewer candidates.

    max_total_seconds (2026-09-18 reliability fix), when given, is checked
    BEFORE starting each new attempt (never mid-attempt — an attempt already
    in flight always runs to its own completion/timeout, since interrupting
    a synchronous call partway through would leave the deterministic/claim-
    safety/semantic-judge gates in an inconsistent state). Once the budget is
    exhausted, no further attempts start and whatever the best result so far
    is gets returned immediately — the same fail-safe convention as every
    other stage in this pipeline (fewer/zero cards is safer than blocking
    indefinitely)."""
    start = time.monotonic()
    exclude = list(payload.exclude_titles)
    last_result = StorySituationsResult(situations=[])
    best_result = StorySituationsResult(situations=[])
    attempts_used = 0
    budget_exhausted = False
    for attempt in range(1, max_attempts + 1):
        if max_total_seconds is not None and (time.monotonic() - start) >= max_total_seconds:
            logger.warning(
                "Story-ideas quality-floor budget of %.0fs exhausted before attempt %d/%d — "
                "stopping retries, returning the best of %d already-generated candidate(s)",
                max_total_seconds, attempt, max_attempts, len(best_result.situations),
            )
            budget_exhausted = True
            break
        attempts_used = attempt
        current_payload = payload.model_copy(update={"exclude_titles": exclude})
        try:
            last_result = generate_situations(current_payload)
        except Exception as e:
            logger.warning("Quality-floor attempt %d/%d raised, treating as empty: %s", attempt, max_attempts, e)
            last_result = StorySituationsResult(situations=[])
        # Every candidate in last_result.situations already survived every
        # deterministic/claim-safety/category/semantic-judge gate inside
        # generate_situations() — "best" here means "most already-validated
        # candidates", never a relaxation of what counts as valid.
        if len(last_result.situations) > len(best_result.situations):
            best_result = last_result
        if len(last_result.situations) >= min_situations:
            return QualityFloorResult(situations=last_result.situations, quality_floor_met=True, attempts_used=attempt)
        logger.info(
            "Quality floor not met on attempt %d/%d (%d situation(s) survived, wanted >= %d) — retrying",
            attempt, max_attempts, len(last_result.situations), min_situations,
        )
        exclude = exclude + [s.title for s in last_result.situations]
    return QualityFloorResult(
        situations=best_result.situations,
        quality_floor_met=False,
        attempts_used=attempts_used,
        budget_exhausted=budget_exhausted,
        dominant_weakness=(
            "the story-ideas time budget ran out before enough candidates survived" if budget_exhausted else
            "every candidate across all attempts failed the product-truth/category-drift or "
            "semantic-dedup gate — the product/audience/category combination may need a richer brief, "
            "or this product's contract role_risk detection may be too strict for the given brief"
        ),
    )


def generate_situations_for_request(payload: StorySituationsInput) -> StorySituationsResult:
    """The router-facing entry point (2026-09-18 task, Part 13 — shortfall
    behavior; extended by the same-dated reliability fix with an aggregate
    time budget). Sets the quality floor to the FULL requested/capped count
    (not just >=1), so generate_situations_with_quality_floor's existing
    bounded-retry loop keeps trying (never regenerating the exact same
    batch — see its exclude-titles logic) until either the full count
    survives, MAX_QUALITY_FLOOR_ATTEMPTS is exhausted, or
    DEFAULT_STORY_IDEAS_BUDGET_SECONDS elapses. quality_floor_met then
    translates directly into generation_shortfall: False means the full
    requested set was reached, True means fewer survived — shown as-is to
    the user, never padded with a fabricated card to reach the count.

    Raises ValueError (never silently returns a fake "success" with zero
    cards) when NOT EVEN ONE candidate survived every gate — the router
    converts this to an explicit HTTP error, per the task's explicit "return
    a clear error rather than pretending generation succeeded"."""
    requested_count = min(payload.count, MAX_STORY_IDEAS_PER_GENERATION)
    result = generate_situations_with_quality_floor(
        payload, min_situations=requested_count, max_total_seconds=DEFAULT_STORY_IDEAS_BUDGET_SECONDS,
    )
    if not result.situations:
        raise ValueError(
            "No story ideas survived the product-truth, claim-safety, and creative-quality checks "
            + ("within the time budget" if result.budget_exhausted else "after retrying")
            + " — please try again, or adjust the product brief."
        )
    return StorySituationsResult(situations=result.situations, generation_shortfall=not result.quality_floor_met)
