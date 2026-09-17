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
from dataclasses import dataclass, field

from app.config import settings
from app.services.beat_outline_service import BeatOutline
from app.services.creative_architecture import Architecture
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import ProductCreativeContract
from app.services.product_context_validator import detect_category_drift_signal

logger = logging.getLogger("architecture_validation_service")


# Phase 3C, Part 15 — format-aware calibration for the story-execution
# checks below (announcement_mode, no_concrete_event, hook_abstract_not_
# situational, payoff_repeats_setup, metaphor_not_embodied). These checks
# must not force every format into a cinematic three-act structure — a
# testimonial or a static graphic has genuinely different conventions.
_LENIENT_FORMAT_GUIDANCE: dict[str, str] = {
    "ugc_talking_head": (
        "This is a UGC/talking-head format — authenticity and a specific, credible personal moment "
        "matter more than a three-act plot. Do NOT flag no_concrete_event just because there's no "
        "reversal or twist; DO flag it if the account is so generic it could be anyone talking about "
        "anything, with no specific detail at all."
    ),
    "testimonial": (
        "This is a testimonial format — a real-sounding personal account of an experience matters "
        "more than a dramatized scene. Do NOT require a three-act plot; DO check that it describes a "
        "specific, concrete experience rather than generic praise."
    ),
    "product_demo": (
        "This is a product-demonstration format — the demonstration itself IS the event. Judge "
        "dramatic_event by whether a concrete demonstration/moment is actually shown, not by whether "
        "there's a narrative twist."
    ),
    "product_showcase": (
        "This is a product-showcase format — clear, specific presentation of the product matters more "
        "than a dramatized scene. Do NOT require a three-act plot."
    ),
    "explainer": (
        "This is an explainer format — a concrete, specific example or demonstration matters more "
        "than plot. Do NOT require a narrative reversal."
    ),
    "educational_video": (
        "This is an educational format — credibility and a concrete, specific example matter more "
        "than plot. Do NOT require a narrative reversal."
    ),
    "podcast": (
        "This is a podcast/conversational format — a specific, credible point of view matters more "
        "than a dramatized scene. Do NOT require a three-act plot."
    ),
    "whiteboard": (
        "This is a whiteboard/explainer format — clarity of the concrete idea being explained matters "
        "more than dramatized plot."
    ),
}


def _format_guidance(content_type: str, format_value: str) -> str:
    if content_type == "static":
        return (
            "FORMAT NOTE: this is a STATIC creative (a single graphic/slide), not a video script. Do "
            "NOT flag no_concrete_event, no_curiosity, or story_static for lacking a filmed scene — "
            "judge dramatic_event/visual_potential by whether the visual idea and copy relationship is "
            "sharp and specific, not by cinematic story structure."
        )
    guidance = _LENIENT_FORMAT_GUIDANCE.get(format_value or "")
    if guidance:
        return f"FORMAT NOTE: {guidance}"
    return (
        "FORMAT NOTE: this is a narrative-driven format — apply the concrete-event, human-tension, "
        "and payoff checks at full strength."
    )


def _parse_eval_json(raw_text: str) -> dict:
    """Same light cleanup convention as script_service._parse_script_json —
    strips markdown fences a model can still emit despite json_mode, and
    trailing commas — before falling through to json.loads. No LLM repair
    call here (this stays a cheap, best-effort parse): a genuine failure
    still raises and the caller's fail-open except-block handles it."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned)


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
    data: dict, outline: BeatOutline | None, architecture: Architecture, product_name: str,
    contract: ProductCreativeContract | None = None,
) -> list[str]:
    """Free, regex/arithmetic-only checks. No API call."""
    issues: list[str] = []
    texts = _block_texts(data)
    if not texts:
        return issues

    # Category-drift pre-check — cheap, relationship-based, and only ever
    # runs at all when this specific product's contract flags a known risky
    # role (e.g. Herbal Masala's food/cooking risk); a product with no
    # role_risk_keys never triggers this. Critical severity: a category
    # error must force a rewrite regardless of how well anything else scores.
    if contract is not None and detect_category_drift_signal(" ".join(texts), contract):
        issues.append("category_drift")

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


_EVAL_SYSTEM_PROMPT = """You are several reviewers in one, evaluating a finished ad script honestly and
specifically. Most scripts that reach this stage are reasonably solid — don't invent problems to
seem thorough, but don't wave through real ones either.

REVIEWER 0 — PRODUCT TRUTH / CATEGORY ALIGNMENT. This runs FIRST and is a PREREQUISITE, not one more
score to average in: if a PRODUCT CREATIVE CONTRACT is given below, check whether the script still
treats the product according to that contract's actual category/use case/audience/consumption context,
or whether the creative has silently reinterpreted what the product IS (e.g. a product whose real use
case is a tobacco/gutka alternative being shown added to food as a cooking ingredient). A script with
high originality, memorability, or a clever device but the WRONG product category must still fail —
category alignment is not averaged against creative quality, it gates it. Creative freedom in
storytelling device, metaphor, character, setting, tone, and structure is expected and does not count
as drift on its own.

REVIEWER 1 — ARCHITECTURE COMPLIANCE. You are told which structural architecture this script was
supposed to follow, and its required beats. Check:
- Are the required beats genuinely present (in spirit, not just labeled)?
- Is the actual FORMAT being used (e.g. if the architecture requires two distinct voices in
  conflict, is that genuinely happening, not a disguised monologue)?
- Is the emotional progression the architecture calls for actually present?
- Is the proof mechanism the architecture calls for actually used?

REVIEWER 2 — CREATIVE DIRECTOR. You are a working creative director rejecting a junior writer's draft,
not a supportive writing assistant helping them feel good about it — your job is to find the real
reasons this doesn't work yet, not to soften them. Product-correctness, safe claims, and clean grammar
are the FLOOR, never a substitute for a real creative idea; do not let them talk you into a pass. Reject
on sight: generic emotional writing with no specific observation behind it; artificial/stilted dialogue
that exists to deliver information rather than how a person actually talks; a metaphor so predictable
it could be guessed before the script explains it; forced family emotion used as a shortcut past an
actual idea; a body that's mostly VO explaining what's happening instead of something happening;
a product announcement wearing a story's clothes; generic advertising phrasing; a dramatic event too
weak to justify the beat it's carrying; the product placed in the story ornamentally rather than
necessarily; a punchline that reads as written-to-be-quotable rather than earned by what came before;
and a script whose only memorable element is a tagline/slogan line — if removing that one line would
leave nothing memorable, the underlying idea itself was never memorable, only its wrapper. Do not ask
"is this award-winning" — instead apply two concrete tests first: (1) Would a viewer remember the IDEA
tomorrow, not just recall that an ad played? (2) Remove the brand/product name entirely — is what's left
still an interesting film idea, or is there nothing there without the product? If test 2 fails, the
premise itself is weak, not just the execution. Then also evaluate whether this demonstrates the real
characteristics of campaign-quality advertising:
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
- Is this script VISUALLY EXECUTABLE — could a director actually shoot this (concrete actions,
  settings, product moments), not just a voice reading lines with nothing to film? A static/graphic
  format should specify what appears on-screen, not only read like spoken copy.

REVIEWER 2.5 — STORY-TO-FILM EXECUTION (Phase 3C — this is the single most common real failure: a
script that is product-correct, on-category, safely claimed, and grammatically polished, but still
converts a specific creative idea into generic advertisement copy). Apply the FORMAT NOTE given below
before judging any of this — a testimonial/UGC/demo/explainer/static format has different, equally
valid conventions and must not be forced into a cinematic plot it was never meant to have.
- TITLE/STORY INTEGRITY (only when a CHOSEN STORY SITUATION is given below): its title names a
  concrete concept (e.g. "Doctor ki Advice" implies an actual doctor-patient scene; "Maa Ki Dua, Badla
  Beta" implies an actual mother/son relationship and an observable change). Does the SCRIPT actually
  contain that concept as real content — a scene, an exchange, a relationship, an event — or does the
  script just generically gesture at a related theme while the concrete concept named by the title
  never actually appears? A script that never delivers what its own selected title promises fails
  this, no matter how polished the copy is elsewhere.
- METAPHOR VS STORY: a line that STATES or EXPLAINS a metaphor/feeling in narration ("life feels
  colourless", "it's like a loop") is not yet a story — it only becomes one when it's embodied through
  a character, a concrete event, and a visual progression the script actually describes (not just
  asserts). If the script's central idea stays at the level of an explained metaphor with no character/
  event/visual mechanism actually dramatizing it, that's a real defect.
- CONCRETE EVENT (apply per the FORMAT NOTE — full strength for narrative-driven formats, relaxed for
  UGC/testimonial/demo/explainer/static as the note describes): is there an actual event — a discovery,
  confrontation, reversal, unexpected action, reveal, social reaction, decision, interruption,
  demonstration, behavioral contrast — or is this purely explanatory narration with nothing happening?
- GENERIC ANNOUNCEMENT STRUCTURE: does the script's underlying shape reduce to problem -> product
  introduction -> features/ingredients -> generic positive-lifestyle statement -> CTA, with the product
  entering as an announcement rather than a natural, necessary part of a specific situation? This can be
  true even when every individual line is well-written and product-correct — judge the STRUCTURE, not
  the sentence quality. Detect this from the underlying shape of what happens, never from matching
  specific words or phrases.
- HOOK SERVES THE STORY: does the hook establish a character, situation, unexpected behavior, curiosity
  gap, or visual event — or does it just restate/explain the product category or the ad's own theme in
  the abstract (a line that could open literally any script about this general topic)?
- PAYOFF ACTUALLY PAYS OFF: does the ending create a genuine escalation -> reveal/reversal ->
  resolution (or an equivalent format-appropriate landing), or does it just restate the opening
  metaphor/feeling in different words, with nothing new having actually happened?

REVIEWER 3 — TERRITORY COMPLIANCE (only applies if an APPROVED CREATIVE TERRITORY is given below).
The territory is the underlying human/behavioural LENS the script was supposed to explore — a level
above the specific premise. Check:
- Does the ACTUAL WRITTEN SCRIPT genuinely express the territory's human tension and creative
  question, or did it quietly drift into a generic product story, an ingredient list, generic
  testimonial language, or a standard problem-then-product-then-benefits-then-CTA shape? A territory
  that exists only in the given metadata but isn't actually visible in the script text fails this.
- If RECENTLY USED TERRITORIES are given below, is this script's actual realized idea (not just its
  wording) fundamentally the same underlying territory as one of those, with only the character/
  setting/device changed? Apply the same-idea-different-clothes test: would swapping the character/
  setting/device of the recent one produce this same script? If yes, that's a real problem.

Return ONLY issue codes from this exact list, nothing invented:
- "category_drift": the script no longer treats the product according to its given Product Creative
  Contract — it has been reinterpreted as a different kind of product, used in a context the contract
  marks as forbidden, or given to a different audience/use case than the contract states
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
- "not_visually_executable": this reads as conversation/narration with nothing a camera could
  actually shoot — no concrete action, setting, or product moment, just lines being said
- "territory_mismatch": an approved territory was given but the actual script doesn't express it —
  it drifted into a generic product story, ingredient list, testimonial language, or standard
  problem/product/benefits/CTA shape instead
- "same_idea_different_clothes": the script's REALIZED idea is fundamentally the same underlying
  territory as one of the RECENTLY USED TERRITORIES given below, just with the character/setting/
  device changed
- "title_story_mismatch": a CHOSEN STORY SITUATION was given below and its title names a concrete
  concept, but the script's actual content never delivers that concept — only use this code when a
  chosen story situation was actually given
- "metaphor_not_embodied": a metaphor/feeling is stated or explained in narration but never embodied
  through a character, a concrete event, and a visual progression the script actually describes
- "no_concrete_event": per the FORMAT NOTE below, this format expects an actual event and the script
  is purely explanatory narration with nothing happening — do not use this code for a format the
  FORMAT NOTE says should be judged leniently unless it fails even that relaxed bar
- "announcement_mode": the script's underlying structure reduces to problem -> product introduction ->
  features/ingredients -> generic positive-lifestyle statement -> CTA, with the product entering as an
  announcement rather than a natural part of a specific situation
- "hook_abstract_not_situational": the hook restates/explains the product category or theme in the
  abstract instead of establishing a character, situation, unexpected behavior, curiosity gap, or
  visual event
- "payoff_repeats_setup": the ending just restates the opening metaphor/feeling in different words
  instead of creating a genuine escalation, reveal/reversal, or resolution
- "memorability_relies_on_tagline": if you mentally removed the closing tagline/slogan line, would
  anything about this script still be memorable? If the answer is no — the story, hook, and beats are
  forgettable and only the closing line was written to be quotable — the underlying idea was never
  memorable, only its wrapper. Flag this; a strong script is memorable because of what happens, not
  because of a punchy last line bolted on to compensate.

Also return a "scores" object, 1-5 each (used for reporting/benchmarking, not for the pass/fail issues
list above — score honestly and independently of which issues you flagged): "story_execution" (does the
script visibly execute a specific creative idea, not just describe one), "title_integrity" (per
TITLE/STORY INTEGRITY above; score 5 when no situation was given — nothing to check), "premise_integrity"
(does the script actually deliver the given creative premise, when one is given), "narrative_device_
integrity" (does the script actually use the stated narrative device, when one is given),
"dramatic_event" (per CONCRETE EVENT above, respecting the FORMAT NOTE), "human_tension" (specific and
observable, not a category-level generality), "visual_potential" (could a director shoot this from
concrete, specific actions/settings), "memorability" (one distinctive idea a viewer would remember, not
just "this brand is good"), "product_integration" (does the product feel necessary to the idea, not
pasted in), "hook_quality" (per HOOK SERVES THE STORY above), "payoff_quality" (per PAYOFF ACTUALLY PAYS
OFF above), "creative_concept_strength" (an overall honest 1-5 read on the underlying idea, independent
of how polished the prose is).

Return ONLY this JSON, no prose, no markdown fences:
{"issues": [string], "scores": {"story_execution": int, "title_integrity": int, "premise_integrity": int,
"narrative_device_integrity": int, "dramatic_event": int, "human_tension": int, "visual_potential": int,
"memorability": int, "product_integration": int, "hook_quality": int, "payoff_quality": int,
"creative_concept_strength": int}, "announcement_mode": boolean, "abstract_copy_risk": boolean}
issues=[] when the script is genuinely fine on all fronts. announcement_mode/abstract_copy_risk must
agree with whether "announcement_mode"/generic abstract-copy issue codes were returned above."""


def _eval_user_message(
    data: dict,
    outline: BeatOutline | None,
    architecture: Architecture,
    product_name: str,
    audience: str,
    reference_dna_notes: str = "",
    territory_block: str = "",
    recent_territories_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
    content_type: str = "",
    format_value: str = "",
) -> str:
    hook_text = (data.get("hook") or {}).get("text", "") if isinstance(data.get("hook"), dict) else ""
    body_texts = [b.get("text", "") for b in (data.get("body") or []) if isinstance(b, dict)]
    cta_text = (data.get("cta") or {}).get("text", "") if isinstance(data.get("cta"), dict) else ""
    required = "\n".join(f"- {b}" for b in architecture.required_beats)
    ref_block = f"\nReference-DNA notes for this architecture:\n{reference_dna_notes}\n" if reference_dna_notes else ""
    territory_section = f"\nAPPROVED CREATIVE TERRITORY:\n{territory_block}\n" if territory_block else ""
    recent_section = f"\n{recent_territories_block}\n" if recent_territories_block else ""
    contract_section = f"\n{contract_block}\n" if contract_block else ""
    situation_section = f"\nCHOSEN STORY SITUATION:\n{situation_block}\n" if situation_block else ""
    format_section = f"\n{_format_guidance(content_type, format_value)}\n"
    return (
        f"{contract_section}"
        f"Architecture: {architecture.name}\n"
        f"Required beats:\n{required}\n"
        f"Expected emotional progression: {architecture.emotional_progression}\n"
        f"Expected proof mechanism: {architecture.proof_mechanism}\n"
        f"Product: {product_name}\n"
        f"Audience: {audience}\n"
        f"{ref_block}"
        f"{territory_section}"
        f"{situation_section}"
        f"{recent_section}"
        f"{format_section}\n"
        f"Generated hook: {hook_text}\n"
        f"Generated body:\n" + "\n".join(f"- {t}" for t in body_texts) + "\n"
        f"Generated CTA: {cta_text}"
    )


@dataclass
class ScriptExecutionEvaluation:
    """Full parsed result of the Creative Director call (Phase 3C) — issues
    drive the existing pass/fail gate+rewrite mechanism unchanged; scores/
    flags are additive, used by the Creative Quality Benchmark
    (creative_quality_benchmark.py) to report before/after story-execution
    quality without a second LLM call."""

    issues: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    announcement_mode: bool = False
    abstract_copy_risk: bool = False

    @property
    def passed(self) -> bool:
        return not self.issues


def evaluate_script_execution(
    data: dict,
    outline: BeatOutline | None,
    architecture: Architecture,
    product_name: str,
    audience: str,
    reference_dna_notes: str = "",
    territory_block: str = "",
    recent_territories_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
    content_type: str = "",
    format_value: str = "",
) -> ScriptExecutionEvaluation:
    """The full Creative Director evaluation (issues + Phase 3C story-
    execution scores). Never raises: any failure returns an empty/neutral
    result, same fail-open convention as every other stage — the caller
    treats an empty issues list as a pass and empty scores as "no benchmark
    data available" rather than a score of zero."""
    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_EVAL_SYSTEM_PROMPT,
                contents=[_eval_user_message(
                    data, outline, architecture, product_name, audience, reference_dna_notes,
                    territory_block, recent_territories_block, contract_block,
                    situation_block, content_type, format_value,
                )],
                # This IS the "Final Creative Director" evaluation (Option C
                # §5A) — the highest-value judgment call in the post-write
                # gates, deciding whether the concept is distinctive, on-
                # category, and worth keeping. Deliberately routed to the
                # final_script tier (Pro), not the cheap creative-exploration
                # tier, even though it's a "check" — its reasoning quality
                # matters as much as the writer's.
                model=settings.final_script_model,
                # Phase 3C live testing found the ORIGINAL 350-token budget
                # (and a first attempt at 1100) both truncated almost every
                # call, even though the visible JSON itself is short — this
                # Pro-tier reasoning model spends a large, variable share of
                # max_tokens on internal reasoning before it ever starts
                # writing the visible completion (observed: ~1085 reported
                # output_tokens for 111 visible characters of JSON, cut off
                # mid-string). 4000 gives real headroom for that reasoning
                # overhead; still a fraction of the 16000-token writer budget
                # since actual BILLED cost tracks real tokens used, not this
                # ceiling.
                max_output_tokens=4000,
                json_mode=True,
                label="final_creative_director",
            ),
            label="final_creative_director",
            max_attempts=2,
        )
        result = _parse_eval_json(text)
        issues = result.get("issues") or []
        issues = [i for i in issues if isinstance(i, str)]
        # Deterministic safety net: these codes are only meaningful when
        # there was something to check against. Live testing showed the
        # model can still return them speculatively even with no territory
        # section in its prompt at all (territory generation failed/wasn't
        # available for this run) — strip rather than trust self-restraint.
        if not territory_block:
            issues = [i for i in issues if i != "territory_mismatch"]
        if not recent_territories_block:
            issues = [i for i in issues if i != "same_idea_different_clothes"]
        if not situation_block:
            issues = [i for i in issues if i != "title_story_mismatch"]
        raw_scores = result.get("scores") or {}
        scores = {k: int(v) for k, v in raw_scores.items() if isinstance(v, (int, float))}
        return ScriptExecutionEvaluation(
            issues=issues,
            scores=scores,
            announcement_mode=bool(result.get("announcement_mode")),
            abstract_copy_risk=bool(result.get("abstract_copy_risk")),
        )
    except Exception as e:
        logger.warning("Architecture/creative-director evaluation failed, treating as pass: %s", e)
        return ScriptExecutionEvaluation()


def llm_architecture_and_creative_director_issues(
    data: dict,
    outline: BeatOutline | None,
    architecture: Architecture,
    product_name: str,
    audience: str,
    reference_dna_notes: str = "",
    territory_block: str = "",
    recent_territories_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
    content_type: str = "",
    format_value: str = "",
) -> list[str]:
    """Thin wrapper kept for the existing gate call site — returns just the
    issues list that drives _apply_architecture_gate's pass/fail decision."""
    return evaluate_script_execution(
        data, outline, architecture, product_name, audience, reference_dna_notes,
        territory_block, recent_territories_block, contract_block,
        situation_block, content_type, format_value,
    ).issues
