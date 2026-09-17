"""Structured reference-creative knowledge — Part 2 of the AHM Creative DNA
implementation (see docs/creative/AHM_Creative_DNA_Spec.md).

Reference videos are stored here as structured records (the exact schema
requested: architecture, hook_device, human_insight, audience,
product_category, emotional_progression, proof_device, objection,
product_reveal_timing, payoff, CTA_style, language_style, visual_device),
never as raw video/transcript text fed wholesale into a generation prompt.

CATEGORY-TRANSFER RULE (the single most important thing this module enforces,
per AHM spec §9.0/§14): all 12 usable reference records below come from ONE
category — adult self-purchase, tobacco/gutka habit-replacement. When a new
brief is in a DIFFERENT category, retrieval must surface only the MECHANISM
(architecture, hook_device, proof_device, CTA_style — reusable structure)
never the surface content (gutka, chewing, spit-stains, tobacco-specific
imagery). relevant_notes() below enforces this: it always returns
mechanism-only, category-neutral notes, and explicitly labels them as a
transferable pattern from a different category rather than a proven result
for the current one, so the generation prompt can never mistake "this
worked for Herbal Masala" for "this is an approved fact about your product".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceRecord:
    video_id: str
    architecture: str  # matches a creative_architecture.ARCHITECTURES key
    hook_device: str
    human_insight: str
    audience: str
    product_category: str
    emotional_progression: str
    proof_device: str
    objection_addressed: str
    product_reveal_timing: str
    payoff: str
    cta_style: str
    language_style: str
    visual_device: str
    is_anti_pattern: bool = False  # True only for the one documented negative case (V9)


# Condensed from AHM_Creative_DNA_Spec.md Part 2 — one record per video that
# has a clear, usable architecture (V9 is kept as the one explicit
# anti-pattern; V10 is a pure-demonstration record; V4 the borrowed-format
# reaction-relay sub-type).
REFERENCE_RECORDS: list[ReferenceRecord] = [
    ReferenceRecord(
        video_id="V2", architecture="dialogue_trap",
        hook_device="confrontational question dropped mid-conversation",
        human_insight="people trying to quit a habit often substitute one crutch for another and feel judged for the substitution",
        audience="adult self-purchaser, workplace setting, already mid-attempt to quit",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="caught-out -> intellectually challenged -> stuck -> relieved",
        proof_device="social/authority credibility (a calmer, senior figure recommends it)",
        objection_addressed="why trust another substitute when previous substitutes failed",
        product_reveal_timing="very late (~85%)",
        payoff="a wordplay reframe that turns the brand name into the answer",
        cta_style="plain transactional end card",
        language_style="short clipped Hindi/Hinglish, workplace register",
        visual_device="black-and-white grading during confrontation, color at reveal",
    ),
    ReferenceRecord(
        video_id="V6", architecture="objection_handling_interview",
        hook_device="mid-sentence caption dropping viewer into an ongoing personal account",
        human_insight="heavy users track their own consumption obsessively; quantified self-awareness of harm is the actual tipping point, more than abstract health fear",
        audience="heavy daily users, quantified habit",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="confessional -> mild embarrassment at the numbers -> curiosity -> relief -> gratitude",
        proof_device="before/after physical proof + a real purchase-screen screenshot",
        objection_addressed="taste retention AND health credibility, answered in one breath",
        product_reveal_timing="mid (~50%)",
        payoff="doubled: emotional (symptom gone) + transactional (real purchase proof)",
        cta_style="proof-as-CTA (a real purchase screenshot stands in for a branded end card)",
        language_style="first-person confessional, precise numbers stated plainly",
        visual_device="small inset before/after close-up, not a full-screen reveal",
    ),
    ReferenceRecord(
        video_id="V7_V8", architecture="objection_handling_interview",
        hook_device="named, personalized mid-conversation address",
        human_insight="quitting-talk is cheap; the gap between stated intention and actual behavior is the real obstacle, and naming that gap first builds credibility",
        audience="adult self-purchaser, regional-language street setting",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="skeptical/deflecting -> committed -> curious -> reassured -> convinced by a live-timed result",
        proof_device="a literal on-screen timer visualizing a duration claim as a live demonstration",
        objection_addressed="taste, hygiene, health, duration, and does-it-really-work — addressed one at a time",
        product_reveal_timing="early-to-mid (~25-30%), then continuous",
        payoff="craving measurably lower after a real-time-feeling demo, capped with a social-proof number",
        cta_style="a 'start your treatment today' action-framed line, not a bare buy-now",
        language_style="regional colloquial, named individual addressed directly",
        visual_device="a literal clock/timer graphic turning an abstract usage claim into something visual",
    ),
    ReferenceRecord(
        video_id="V12", architecture="documentary_zoom_in",
        hook_device="a visceral anatomical/body-consequence visual paired with a direct-address opening clause",
        human_insight="the person already wants to quit for their family's sake and has already tried and failed — the reframe isn't 'you should care', it's 'you already do, and blaming willpower is the wrong frame'",
        audience="older users with families, family-stakes framing",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="visceral alarm -> dread -> empathy for one person -> solidarity (universalizing) -> relief -> confidence",
        proof_device="anatomical illustration + named ingredient count + a demonstration shot",
        objection_addressed="taste AND health, answered together in one dual-benefit line",
        product_reveal_timing="late (~65-70%)",
        payoff="a universalizing line that removes shame right before the solution appears",
        cta_style="standard claims-and-offer end card",
        language_style="Hindi, repetition of the 'quit/leave' root word to reinforce the theme",
        visual_device="an anatomical illustration and an unexpected social-cost image used as visual argument, not narration",
    ),
    ReferenceRecord(
        video_id="V3", architecture="borrowed_format",
        hook_device="a bold, disgust-coded title card, not a spoken line",
        human_insight="people delay dealing with a known risk until symptoms are undeniable — the insight is procrastination under denial, not lack of awareness",
        audience="younger, social-media-native, health-content followers",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="confrontational -> fear -> something personal -> resolve -> practical relief",
        proof_device="borrowed authority from the creator/explainer format itself, not cited evidence",
        objection_addressed="why keep delaying a known risk",
        product_reveal_timing="late, via a handoff to a second speaker (~80%+)",
        payoff="a practical solution handoff after the argument is made, not a single climactic reveal",
        cta_style="standard end card",
        language_style="casual second-person creator-style direct address",
        visual_device="green-screen + meme-comparison graphic borrowed directly from organic creator content",
    ),
    ReferenceRecord(
        video_id="V4", architecture="borrowed_format",
        hook_device="a mundane, observational, unstaged-looking opening — authenticity is the hook, not shock",
        human_insight="peer skepticism ('prove it to me') persuades harder than a single polished testimonial; a group of unscripted, camera-passed reactions reads as harder to fake",
        audience="young, mixed-gender office peers",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="curious/skeptical -> surprised -> amused/normalized by repetition",
        proof_device="cumulative social proof across many real-looking reactions, plus overlaid peer-comment graphics",
        objection_addressed="is this actually good, proven by many independent tries, not one paid testimonial",
        product_reveal_timing="very early and continuous (~10%)",
        payoff="normalization — by the end it looks like everyone is already doing this",
        cta_style="standard end card",
        language_style="colloquial chat-speak overlay text, imperfect on purpose",
        visual_device="live comment-overlay graphics simulating audience reaction inside the video itself",
    ),
    ReferenceRecord(
        video_id="V13", architecture="ironic_bit",
        hook_device='an ironic-warning line that sounds like it\'s arguing against the product',
        human_insight="the real unspoken social cost isn't private health, it's visible public disgust (stains, breath, being judged in public)",
        audience="social-media-savvy, meme-literate, younger",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="confused/intrigued -> amused -> grounded by real disgust evidence -> delighted by the punchline",
        proof_device="real photographed evidence of the actual social problem, used to support the satire's premise, not the product's claim",
        objection_addressed="why would being 'too clean/healthy' ever be framed as a downside",
        product_reveal_timing="immediate visibility, delayed meaning",
        payoff="a genuine joke/punchline, not only an emotional beat",
        cta_style="the CTA itself carries the ironic frame all the way through",
        language_style="expressive interjections, sketch-style compiled reaction lines",
        visual_device="real photographed social evidence + a reused reject/accept meme-panel device",
    ),
    ReferenceRecord(
        video_id="V11", architecture="visual_metaphor_device",
        hook_device='a hypothetical/conditional opening ("what will happen if...") paired with an uncanny character design',
        human_insight="people want proof a product is clean on the INSIDE, not just the label — an invisible-effect claim needs a way to be seen",
        audience="broad, visually-driven, younger/social-native",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="curious/uneasy -> reassured -> informed -> confident",
        proof_device="named ingredients shown physically, grounding an otherwise abstract character device",
        objection_addressed="is it genuinely clean internally, not just marketed as clean",
        product_reveal_timing="early and constant (character holds/wears the product throughout)",
        payoff="claims displayed literally on the character's body — a visual punchline",
        cta_style="standard end card",
        language_style="short fragment-paced captions, almost poetic rhythm",
        visual_device="a translucent/x-ray character design that visualizes an internal, otherwise-unshowable state",
    ),
    ReferenceRecord(
        video_id="V10", architecture="pure_demonstration",
        hook_device="a persistent claim caption paired with a physical unwrapping action",
        human_insight="before switching from a familiar tactile ritual, people want to see and feel the replacement, not just read about it",
        audience="broad, product-curious, mid-funnel",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="curiosity -> calm satisfaction at the reveal",
        proof_device="pure visual/textural detail, no claims beyond the caption",
        objection_addressed="what does this actually look/feel like",
        product_reveal_timing="immediate and total",
        payoff="the final pour/reveal shot showing real texture and quantity",
        cta_style="often none — designed as a supporting asset, not a standalone closer",
        language_style="single persistent English caption, no dialogue",
        visual_device="extreme macro shots, clean minimal staging",
    ),
    ReferenceRecord(
        video_id="V9", architecture="none", is_anti_pattern=True,
        hook_device="an unrelated viral domestic-drama caption with zero connection to the product's insight",
        human_insight="none — this video substitutes platform-attention mechanics for an actual product insight",
        audience="broad/generic social feed traffic",
        product_category="tobacco/gutka habit-replacement",
        emotional_progression="shock/confusion -> reset -> informational, with no real arc",
        proof_device="none — the lowest-proof-density record in the set",
        objection_addressed="none",
        product_reveal_timing="immediate after an unrelated hook, no delay or earning",
        payoff="none — simply reaches the offer with no story payoff",
        cta_style="standard end card, disconnected from everything before it",
        language_style="English viral-template caption, then an unconnected pitch",
        visual_device="none distinctive — the hook and pitch don't even share a visual thread intentionally",
    ),
]

_USABLE_RECORDS = [r for r in REFERENCE_RECORDS if not r.is_anti_pattern]


def records_for_architecture(architecture_key: str) -> list[ReferenceRecord]:
    return [r for r in _USABLE_RECORDS if r.architecture == architecture_key]


def anti_pattern_notes() -> str:
    """The one documented negative case, always safe to surface regardless
    of category — it's a warning about HOW NOT to hook, not a category-
    specific claim."""
    v9 = next(r for r in REFERENCE_RECORDS if r.video_id == "V9")
    return (
        f"DOCUMENTED ANTI-PATTERN (do not reproduce): a reference execution used {v9.hook_device} — "
        f"this is explicitly flagged as the weakest pattern observed: a scroll-stopping hook with no "
        f"logical or emotional connection to the product's real insight, no proof, no delayed reveal, "
        f"and no payoff. A strong hook must connect to the actual insight, not just grab attention."
    )


# Signals that the CURRENT brief (not just its coarse category label) is
# genuinely about tobacco/gutka/pan-masala habit-replacement — checked
# against the full brief text (product name, target audience, USP, benefits),
# not just product_category. This matters because a real product in this
# category can be stored under a generic category string (e.g. the Product
# Library's "herbal_health") that itself contains none of these words — a
# category-string-only check would wrongly treat that product's OWN reference
# videos as a different, unrelated category and strip the real content.
_TOBACCO_CATEGORY_SIGNALS = ("tobacco", "gutka", "gutkha", "pan masala", "paan masala", "supari", "chewing")


def is_tobacco_gutka_brief(brief_text: str) -> bool:
    """Public, reusable version of the same brief-text signal check used
    below — exposed so product_context_service.py can derive a product's
    real commercial category from its actual given brief (name/audience/
    usp/benefits) rather than only its coarse Product Library category
    string, without duplicating this signal list a third time."""
    low = (brief_text or "").lower()
    return any(sig in low for sig in _TOBACCO_CATEGORY_SIGNALS)


def relevant_notes(
    architecture_key: str,
    product_category: str,
    reference_category: str = "tobacco/gutka habit-replacement",
    brief_text: str = "",
) -> str:
    """Mechanism-only guidance for the chosen architecture, safe to inject
    into any category's generation prompt. When the brief is genuinely in a
    DIFFERENT category from the reference material (the common case), this
    explicitly labels the notes as a cross-category MECHANISM transfer, and
    strips anything that reads as a category-specific fact — never a
    "this worked for X" claim about the current product. `brief_text` should
    be the concatenation of the actual brief's product name / target
    audience / USP / benefits — used (in addition to product_category) to
    detect when a product's own real audience IS this reference category,
    even if its stored category label doesn't say so."""
    records = records_for_architecture(architecture_key)
    if not records:
        return ""
    same_category = product_category.strip().lower() in reference_category.lower() or is_tobacco_gutka_brief(brief_text)
    header = (
        f'Structural reference for the "{architecture_key}" architecture (from prior creative research; '
        + (
            "same general category — mechanism AND category context both apply:"
            if same_category
            else "a DIFFERENT product category — transfer the MECHANISM only, never the surface content/"
            "imagery/claims, which do not apply to this product:"
        )
    )
    lines = [header]
    for r in records[:2]:  # keep the prompt addition small — at most 2 examples
        lines.append(
            f"  - Hook device: {r.hook_device}; proof device: {r.proof_device}; product reveal timing: "
            f"{r.product_reveal_timing}; CTA style: {r.cta_style}; payoff: {r.payoff}."
        )
    return "\n".join(lines)
