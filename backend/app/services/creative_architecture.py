"""Creative Architecture library — Part 1 of the AHM Creative DNA
implementation (see docs/creative/AHM_Creative_DNA_Spec.md).

See select_architecture() at the bottom for the selection stage that picks
one of these for a given brief, given available proof/objections/tone.

A "story arc" in script_service.py's existing CREATIVE STRATEGY step (see
_creative_direction_block's step 5) is a *shape* (curiosity / story /
problem_insight / UGC / demonstration / emotional) — a single sentence of
guidance. An Architecture is the more specific engine that shape can run on:
who it fits, what proof it needs, where the product reveal belongs, and what
makes it fail. This module doesn't replace the existing arc mechanism — it
feeds a richer, more concrete prompt block into the SAME generation call, and
if selection fails for any reason the caller falls back to the arc-only
behavior that already existed, so nothing here can make generation worse.

CRITICAL DESIGN CONSTRAINT (see AHM_Creative_DNA_Spec.md §9.0 and §14): the
13 reference videos this library was reverse-engineered from are ALL for one
category (adult self-purchase, tobacco/gutka habit-replacement). Every
architecture below is therefore described in MECHANISM terms (what
structural job each beat does) rather than in that category's surface
tropes (gutka, chewing, spit-stains) — an architecture is applicable to any
product/category whose brief satisfies its `when_to_use` conditions, never
retrieved just because it appears in a "successful reference" set. See
creative_reference_dna.py for how the underlying reference material is kept
separate from this reusable structure.
"""

import json
import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("creative_architecture")


@dataclass(frozen=True)
class Architecture:
    key: str
    name: str
    creative_purpose: str
    when_to_use: str
    when_not_to_use: str
    hook_pattern: str
    beats: list[str]
    product_reveal_logic: str
    proof_mechanism: str
    emotional_progression: str
    cta_style: str
    required_inputs: list[str]
    failure_conditions: list[str]
    # Added for beat-outline enforcement (see beat_outline_service.py):
    # required_beats are the causal skeleton — an outline missing one of
    # these fails validation. optional_beats may be added/dropped depending
    # on requested duration. prohibited_patterns are checklist-style
    # anti-patterns the outline/script validators scan for directly (a
    # narrower, more mechanically-checkable list than the prose
    # failure_conditions above, which stays for the free-text prompt block).
    required_beats: list[str]
    optional_beats: list[str]
    prohibited_patterns: list[str]

    def prompt_block(self) -> str:
        beats_block = "\n".join(f"  {i}. {b}" for i, b in enumerate(self.beats, start=1))
        failures_block = "\n".join(f"  - {f}" for f in self.failure_conditions)
        return (
            f'CHOSEN CREATIVE ARCHITECTURE: "{self.name}"\n'
            f"Purpose: {self.creative_purpose}\n"
            f"Hook pattern for this architecture: {self.hook_pattern}\n"
            f"Beat-by-beat shape (adapt the wording/count to the requested duration and structure "
            f"quota below, but keep this causal shape and ordering intent):\n{beats_block}\n"
            f"Product reveal logic: {self.product_reveal_logic}\n"
            f"Proof mechanism to use: {self.proof_mechanism}\n"
            f"Emotional progression: {self.emotional_progression}\n"
            f"CTA style for this architecture: {self.cta_style}\n"
            f"This architecture specifically fails when:\n{failures_block}\n"
        )

    def outline_prompt_block(self) -> str:
        """Rendered for the beat-outline generation stage specifically —
        the required/optional/prohibited split the outline (not the final
        script) is graded against."""
        required_block = "\n".join(f"  {i}. {b}" for i, b in enumerate(self.required_beats, start=1))
        optional_block = "\n".join(f"  - {b}" for b in self.optional_beats) or "  (none)"
        prohibited_block = "\n".join(f"  - {p}" for p in self.prohibited_patterns)
        return (
            f'ARCHITECTURE: "{self.name}"\n'
            f"REQUIRED BEATS (every one of these must appear in the outline, in this causal order — "
            f"do not skip, merge two into one, or reorder):\n{required_block}\n"
            f"OPTIONAL BEATS (include only if the requested duration/depth genuinely has room):\n{optional_block}\n"
            f"PROHIBITED PATTERNS (the outline must not produce any of these):\n{prohibited_block}\n"
            f"Product reveal timing: {self.product_reveal_logic}\n"
            f"Proof mechanism: {self.proof_mechanism}\n"
            f"Expected emotional progression: {self.emotional_progression}\n"
            f"CTA style: {self.cta_style}\n"
        )


ARCHITECTURES: dict[str, Architecture] = {
    "dialogue_trap": Architecture(
        key="dialogue_trap",
        name="Dialogue Trap",
        creative_purpose=(
            "Exploit a real, nameable contradiction in the audience's own behavior or belief, using "
            "a two-person confrontation/challenge to surface it before the product ever appears."
        ),
        when_to_use=(
            "A specific, real contradiction exists in the target behavior (e.g. 'you're solving one "
            "problem by creating a smaller version of the same problem', 'you're avoiding the thing "
            "that would actually fix this'). Works with a believable peer/authority dynamic (mentor-"
            "junior, parent-adult child, senior colleague, older sibling)."
        ),
        when_not_to_use=(
            "No real contradiction exists in the brief — do not invent one just to force this "
            "architecture. Also weak for pure discovery/awareness objectives with no behavioral "
            "tension to confront."
        ),
        hook_pattern='A confrontational, specific question dropped mid-conversation ("Still going on?", "You\'re quitting X with Y?") — never a scene-setting establishing shot.',
        beats=[
            "Confrontation opens mid-exchange — the challenger notices something specific and names it.",
            "Confession — the other person admits the behavior plainly, without excuse.",
            "The contradiction is stated as a direct challenge, not a lecture.",
            "Helplessness — the person is genuinely stuck; the challenger doesn't offer a solution yet.",
            "Solution is revealed by the trusted figure, handed over (verbally or physically) as a specific answer to the exact contradiction just named.",
            "A wordplay/reframe payoff line that turns the brand/product name into the answer to the question just asked, if the product name genuinely supports one — otherwise a plain, earned closing line.",
        ],
        product_reveal_logic="Very late (roughly the final quarter of the script) — the product only appears once the contradiction and the person's helplessness are fully established.",
        proof_mechanism="Social/authority credibility (a calmer, more experienced figure recommending it) rather than statistics or demonstration.",
        emotional_progression="Caught-out/defensive -> intellectually challenged -> genuinely stuck -> relieved, shown a specific way out.",
        cta_style="Can be purely transactional/plain — the emotional payoff already lands in the reframe line, so the CTA doesn't need to carry it.",
        required_inputs=["a real, specific behavioral contradiction", "a believable second character/authority figure"],
        failure_conditions=[
            "The 'contradiction' is actually just a generic problem statement with no real logical tension.",
            "The product appears before the helplessness beat lands.",
            "The closing line is a generic tagline instead of a reframe that answers the exact question raised.",
        ],
        required_beats=[
            "Situation — confrontation opens mid-exchange, challenger notices something specific",
            "Person A states/admits the behavior plainly",
            "Person B (challenger) names the contradiction as a direct challenge",
            "Contradiction is exposed — Person A has no easy answer, genuinely stuck",
            "Product enters naturally, handed over by the trusted figure as the specific answer",
            "Proof/resolution — the specific way out is credible, not just asserted",
            "CTA",
        ],
        optional_beats=["A wordplay/reframe line that turns the product name into the answer"],
        prohibited_patterns=[
            "uninterrupted monologue (this architecture requires two distinct voices/positions in conflict)",
            "generic emotional introduction with no concrete confrontation",
            "product appearing in the first beat unless the brief explicitly justifies early visibility",
            "the challenger offering the solution before the helplessness beat lands",
        ],
    ),
    "objection_handling_interview": Architecture(
        key="objection_handling_interview",
        name="Objection-Handling Interview",
        creative_purpose=(
            "Build trust through specificity and testable proof by naming and answering the audience's "
            "actual, real objections one at a time, inside a first-person or interview-style account."
        ),
        when_to_use=(
            "The product/category has 2-4 well-known, real objections the target audience actually "
            "holds (does it work / is it safe / does it taste or feel right / how is this different / "
            "how long until it works). Strongest for self-purchasing adults with active skepticism."
        ),
        when_not_to_use=(
            "No real, specific objections are available for this product/category — do not invent "
            "generic ones just to fill the slot. Weak for pure top-of-funnel awareness with no "
            "purchase-consideration moment yet."
        ),
        hook_pattern="A mid-sentence, curiosity-gap opening that drops the viewer into an already-ongoing account (never 'let me tell you about...').",
        beats=[
            "Mid-conversation hook — viewer is dropped into an account already in progress.",
            "Skepticism/objection #1 named plainly, in the audience's own words.",
            "That objection addressed directly, with a specific detail (a number, a timeframe, a named ingredient/feature) — never a vague reassurance.",
            "Objection #2 named and addressed the same way.",
            "A concrete, testable demonstration or before/after result — something a real person could verify, not a claimed outcome.",
            "A specific, numeric social-proof detail if one is genuinely available (never invented).",
            "A CTA that frames adoption as one small, doable next step.",
        ],
        product_reveal_logic="Early-to-mid (roughly the first third), then the product stays continuously present/referenced for the rest of the script.",
        proof_mechanism="Concrete, testable, time-bound demonstration (a before/after, a timed result, a specific measurable change) — never an asserted claim card.",
        emotional_progression="Skeptical/deflecting -> curious -> reassured, one objection at a time -> convinced by a concrete result -> ready to act.",
        cta_style="Action-framed, story-integrated line ('start today') rather than a bare 'buy now'.",
        required_inputs=["at least one real, specific objection the audience holds", "at least one concrete/testable proof point from the given product data"],
        failure_conditions=[
            "Objections are generic ('is it good?') instead of specific and real.",
            "Every objection is only ever answered with a positive claim, never a specific detail.",
            "The proof offered is a bare assertion ('it works great') rather than something testable/concrete.",
        ],
        required_beats=[
            "Real objection named plainly, in the audience's own words",
            "Interviewer/questioner (or the person's own doubting inner voice) surfaces it",
            "Answer given, with a specific detail — never a vague reassurance",
            "A follow-up challenge or second objection pushes back further",
            "Proof — a concrete, testable demonstration or before/after result",
            "Resolution — the objection is genuinely put to rest, not just talked over",
            "CTA",
        ],
        optional_beats=["A specific, numeric social-proof detail, only if genuinely available"],
        prohibited_patterns=[
            "a fake interview format where only one person ever speaks (no real question/challenge voice)",
            "generic testimonial language with no specific, checkable detail attached",
            "unsupported claims — any efficacy/outcome claim not present in the given product data",
            "every objection answered with only a positive claim and no concrete detail",
        ],
    ),
    "documentary_zoom_in": Architecture(
        key="documentary_zoom_in",
        name="Documentary Zoom-In",
        creative_purpose=(
            "Earn credibility through gravity and scale before any commercial framing — establish the "
            "problem as real, systemic, and larger than one person, then zoom into one specific human "
            "consequence before the product appears."
        ),
        when_to_use=(
            "The category has a genuine, real, sourced problem dimension (documented, not invented) and "
            "the brief's audience is broader than just active buyers (concerned family, general "
            "public) or the objective calls for earned seriousness over polish."
        ),
        when_not_to_use=(
            "No real, sourceable stakes exist for this category/problem — never invent a statistic or "
            "societal-scale claim to force this architecture (see AHM spec's explicit caution: an "
            "unsourced-looking stats slide is a documented anti-pattern, not a template to imitate). "
            "Also weak for lighthearted/low-stakes products."
        ),
        hook_pattern="A stark, blunt title-card-style opening statement or a single unsettling visual/observational image — never a spoken joke or a soft opener.",
        beats=[
            "Macro/societal framing of the problem — scale, not personal complaint.",
            "Zoom into one specific, unnamed or lightly-observed human consequence.",
            "A universalizing line — this isn't only their story, it's shared and common (de-shames the individual before the product enters).",
            "Product reveal, only once credibility is fully earned.",
            "A dual-benefit line that answers two real concerns in one breath (e.g. effectiveness AND the thing they'd otherwise have to give up).",
            "Named, specific proof (an ingredient, a mechanism, a genuinely given detail) — never an invented statistic.",
        ],
        product_reveal_logic="Very late (roughly the final quarter to fifth of the script) — the latest reveal timing of any architecture; the delay is the credibility mechanism itself.",
        proof_mechanism="Real, sourced stakes/evidence if genuinely available; otherwise named specific product facts only — never a fabricated statistic.",
        emotional_progression="Alarm/gravity -> dread/scale -> empathy for the specific person -> solidarity (it's not just you) -> relief once the product appears.",
        cta_style="Plain, standard closing — the emotional work is already done by the universalizing beat.",
        required_inputs=["a genuinely real, documentable problem dimension for this category", "a specific, given product fact to resolve it with"],
        failure_conditions=[
            "A statistic or societal claim appears with no real source in the given product/brief data.",
            "The product appears before the universalizing beat.",
            "The tone breaks into humor or a sales pitch before the credibility-earning section is complete.",
        ],
        required_beats=[
            "Macro/societal framing of the problem — scale, not a personal complaint",
            "Zoom into one specific, observed human consequence",
            "Universalizing line — de-shames the individual before the product enters",
            "Product reveal, only once credibility is fully earned",
            "Dual-benefit line answering two real concerns in one breath",
            "Named, specific proof — never an invented statistic",
            "CTA",
        ],
        optional_beats=["A real, sourced statistic, only if one is genuinely given/available"],
        prohibited_patterns=[
            "an invented or unsourced-looking statistic",
            "the product appearing before the universalizing beat",
            "a joke or sales-pitch tone breaking in before credibility is fully earned",
        ],
    ),
    "borrowed_format": Architecture(
        key="borrowed_format",
        name="Borrowed-Format Creator Content",
        creative_purpose=(
            "Bypass ad-skepticism by adopting the visual/structural grammar of organic, non-ad content "
            "(a creator explainer, a group-reaction/vox-pop, a comment-section moment) so the opening "
            "doesn't register as advertising at all."
        ),
        when_to_use=(
            "Younger or social-native audiences; any category where third-party-feeling content "
            "outperforms overtly branded content; when the brief allows an unpolished, native-feeling "
            "register."
        ),
        when_not_to_use=(
            "A premium/prestige positioning that requires polish from frame one, or a category where "
            "an informal register would undercut trust (e.g. a serious medical claim needing to look "
            "authoritative, not casual)."
        ),
        hook_pattern="A cold open that reads as organic content in its own right (a direct-to-camera explainer beat, or a candid group/reaction moment) — the hook is format-recognition, not a single clever line.",
        beats=[
            "Format-native cold open (explainer monologue, or a candid multi-person reaction moment) with no product visible yet.",
            "The argument builds, or reactions accumulate across more than one person/beat, adding social proof cumulatively.",
            "A pivot/handoff to the brand — via a second voice, an overlay device, or a natural conversational turn — not an abrupt ad-voice shift.",
            "The product is shown inside the same native register established at the start, never suddenly polished/ad-voiced.",
        ],
        product_reveal_logic="Either very late (explainer sub-type, once the argument is made) or early-and-continuous (reaction/relay sub-type, where the format itself requires visible product) — pick based on which sub-type fits the brief.",
        proof_mechanism="Cumulative social proof (multiple reactions/voices) or borrowed authority from the creator-explainer register, not a claims card.",
        emotional_progression="Curious/skeptical -> normalized/amused as more voices agree -> the product feels like an already-adopted, ordinary choice by the end.",
        cta_style="Standard closing card; the persuasive work is already done by the normalization, so the CTA can be plain.",
        required_inputs=["a register/format that plausibly fits this platform and audience"],
        failure_conditions=[
            "The pivot to the brand suddenly sounds like ad copy, breaking the native register established at the open.",
            "There's only one voice/reaction when the format specifically needs cumulative social proof.",
        ],
        required_beats=[
            "Format-native cold open with no product visible yet",
            "Argument builds or reactions accumulate across more than one beat/voice",
            "Pivot/handoff to the brand — natural, not an abrupt ad-voice shift",
            "Product shown inside the same native register established at the open",
            "CTA",
        ],
        optional_beats=["A second/third accumulating voice or reaction for extra cumulative proof"],
        prohibited_patterns=[
            "the pivot suddenly sounding like polished ad copy",
            "only one voice when the format needs cumulative social proof",
            "the product appearing polished/ad-voiced instead of in the same native register",
        ],
    ),
    "ironic_bit": Architecture(
        key="ironic_bit",
        name="Ironic / Satirical Bit",
        creative_purpose=(
            "Use a genuine, ownable inversion (warning the audience away from something that's actually "
            "good) grounded in real, specific, recognizable social evidence, sustained all the way "
            "through to an ironic CTA."
        ),
        when_to_use=(
            "A real, specific, commonly-recognized social-disgust or social-cost dimension exists for "
            "the category that can be photographed/observed/named concretely, AND the brief's audience "
            "is meme-literate/humor-receptive."
        ),
        when_not_to_use=(
            "No real, specific, groundable social evidence is available — pure shock or an unrelated "
            "viral hook with no logical connection to the product's actual insight is an explicitly "
            "documented anti-pattern (see AHM spec Part 5), not a version of this architecture. Also "
            "wrong for serious/medical/high-stakes categories where irony would undercut credibility."
        ),
        hook_pattern='An ironic-warning line that sounds like it\'s arguing against the product ("Don\'t even accidentally buy this...") — must create real confusion/curiosity about why an ad would say that.',
        beats=[
            "Ironic warning hook.",
            "Mock-serious inversion — the 'downsides' listed are actually the product's real strengths.",
            "Real, specific, groundable evidence of the ACTUAL social problem being satirized (something observable/photographable, not abstract).",
            "The punchline that names the absurdity of the warning premise.",
            "A closing scene that reinforces the real social evidence once more.",
            "A CTA that maintains the ironic frame all the way through (the 'warning' language, meaning the opposite).",
        ],
        product_reveal_logic="Immediate visibility from frame one is fine, but the MEANING of why it's framed negatively is delayed until the joke resolves.",
        proof_mechanism="Real, specific, observable social evidence grounding the joke — the satire only works if the underlying evidence is real and instantly recognizable, not just funny.",
        emotional_progression="Confused/intrigued -> amused as the joke lands -> grounded by real evidence -> delighted by the punchline -> clear on the real message by the CTA.",
        cta_style="Must be written together with the hook — the CTA is where the ironic frame pays off, not a separate bolt-on line.",
        required_inputs=["a real, specific, sourceable/observable social-cost or social-disgust angle for this category"],
        failure_conditions=[
            "The hook is shocking/viral but has no logical or emotional connection to the product's actual insight (the documented anti-pattern).",
            "The grounding evidence is abstract/invented rather than something specific and recognizable.",
            "The CTA drops the ironic frame instead of paying it off.",
        ],
        required_beats=[
            "Ironic warning hook",
            "Mock-serious inversion — the listed 'downsides' are actually real strengths",
            "Real, specific, groundable evidence of the actual social problem being satirized",
            "Punchline naming the absurdity of the warning premise",
            "CTA that maintains the ironic frame all the way through",
        ],
        optional_beats=["A closing scene that reinforces the real social evidence once more"],
        prohibited_patterns=[
            "a shock/viral hook with no logical or emotional link to the product's real insight",
            "abstract or invented 'evidence' instead of something specific and recognizable",
            "the CTA dropping the ironic frame instead of paying it off",
        ],
    ),
    "visual_metaphor_device": Architecture(
        key="visual_metaphor_device",
        name="Visual Metaphor / Conceptual Device",
        creative_purpose=(
            "Make an invisible, internal, or emotional benefit concrete through a single sustained "
            "metaphor or device (a physical stand-in for craving, a visualized internal state, an "
            "object that embodies the feeling) rather than describing the benefit in words alone."
        ),
        when_to_use=(
            "The core benefit is genuinely hard to show literally (an internal/invisible effect, an "
            "emotional state, a 'before you even realize it' feeling) and a strong, specific metaphor "
            "or device exists that a director could actually shoot or an image generator could depict."
        ),
        when_not_to_use=(
            "The benefit is already concrete and visible (a device here would be decorative, not "
            "functional) or no genuinely apt metaphor is available — do not force a random visual "
            "gimmick that doesn't connect to the actual insight."
        ),
        hook_pattern='A hypothetical/conditional opening ("What happens if...") or the device itself introduced visually in the first beat — curiosity comes from the device\'s own strangeness or specificity.',
        beats=[
            "The device/metaphor is introduced and performs or embodies the abstract state rather than describing it.",
            "Reassurance/claim beats delivered in short, fragment-paced lines, still filtered through the device's logic.",
            "A concrete, real detail (a named ingredient, a specific fact) grounds the abstract device in something real.",
            "The device resolves — either it 'wins'/transforms, or hands off to a plain, real, credible moment.",
        ],
        product_reveal_logic="Either early-and-constant (the device holds/wears the product throughout) or a late hand-off to a real, literal moment once the abstract device has made its point — pick based on which better fits the brief.",
        proof_mechanism="The metaphor itself carries the argument visually; pair with at least one concrete, named product fact so it doesn't stay purely abstract.",
        emotional_progression="Curious/uneasy at the device -> reassured as it's explained -> grounded by the real detail -> confident by the resolution.",
        cta_style="Standard closing; the memorable work is already done by the device.",
        required_inputs=["a genuinely apt, specific metaphor or device for the invisible benefit being sold"],
        failure_conditions=[
            "The device is decorative and doesn't actually map onto the real benefit being claimed.",
            "The script never grounds the metaphor in any concrete, real product fact.",
        ],
        required_beats=[
            "The device/metaphor is introduced and performs/embodies the abstract state",
            "Reassurance/claim beats delivered through the device's own logic",
            "A concrete, real detail grounds the device in something real",
            "The device resolves — transforms, or hands off to a real, credible moment",
            "CTA",
        ],
        optional_beats=["A second grounding detail if the duration allows"],
        prohibited_patterns=[
            "a decorative device that never actually maps onto the real claimed benefit",
            "the metaphor never being grounded in any concrete, given product fact",
        ],
    ),
    "pure_demonstration": Architecture(
        key="pure_demonstration",
        name="Pure Product Demonstration",
        creative_purpose=(
            "Build tactile/sensory trust by showing exactly what the product looks, feels, sounds, or "
            "behaves like — no character, no problem/solution arc, just a clean, continuous reveal."
        ),
        when_to_use=(
            "Texture/format/appearance is a genuine purchase hesitation (what does this actually look/"
            "feel like), or the objective is mid-funnel trust-building for an audience that already has "
            "some interest, not cold-hook attention-grabbing."
        ),
        when_not_to_use=(
            "Cold top-of-funnel attention-grabbing (this format has no hook mechanism of its own beyond "
            "the product itself) or when the product's real edge is emotional/insight-led rather than "
            "physical/sensory."
        ),
        hook_pattern="A persistent, plain claim caption paired with the physical action itself (unwrapping, pouring, applying) — no spoken hook needed.",
        beats=[
            "The physical reveal action begins (unwrapping/opening/pouring/applying).",
            "The product itself is shown clearly, continuously, in genuine detail.",
            "The final state (poured, applied, worn, used) is shown as the payoff.",
        ],
        product_reveal_logic="Immediate and total — the product is the entire piece from frame one.",
        proof_mechanism="Purely visual/textural — no claims beyond a persistent caption line.",
        emotional_progression="Curiosity about the physical object -> calm satisfaction at the reveal — intentionally minimal range.",
        cta_style="Often none needed within the piece itself — can be a plain caption or omitted if the piece is meant to run as a supporting asset.",
        required_inputs=["a real, specific physical/sensory detail worth showing"],
        failure_conditions=[
            "A problem/solution narrative or character gets bolted on, diluting the show-don't-tell purity.",
            "The piece is used as a cold-open hook when it has no actual hook mechanism.",
        ],
        required_beats=[
            "Visual problem or point of curiosity (what does this actually look/feel like)",
            "Demonstration — the physical reveal action itself",
            "Observation — the product shown clearly, continuously, in genuine detail",
            "Product mechanism — how it actually works/behaves, shown not narrated",
            "Result/payoff — the final state",
        ],
        optional_beats=["A plain closing caption, if the piece needs a standalone CTA"],
        prohibited_patterns=[
            "a bolted-on problem/solution narrative or character diluting the show-don't-tell purity",
            "being used as a cold-open attention hook with no actual hook mechanism of its own",
        ],
    ),
}


def architecture_catalog_prompt_block() -> str:
    """Short listing (name + purpose + when-to-use) for a selection prompt —
    NOT the full detail block, which is only rendered for the one chosen
    architecture via Architecture.prompt_block()."""
    lines = []
    for arch in ARCHITECTURES.values():
        lines.append(f'- "{arch.key}" — {arch.name}: {arch.creative_purpose} WHEN TO USE: {arch.when_to_use} WHEN NOT: {arch.when_not_to_use}')
    return "\n".join(lines)


def get_architecture(key: str) -> Architecture | None:
    return ARCHITECTURES.get(key)


DEFAULT_ARCHITECTURE_KEY = "objection_handling_interview"


_SELECTION_SYSTEM_PROMPT = """You are a creative director choosing which structural architecture best
fits a given ad brief, from a fixed library. You are NOT writing the ad — only selecting the engine
it should run on, based on what proof/objections/tone are actually available.

Pick the architecture whose WHEN TO USE conditions are genuinely satisfied by the given brief, and
whose WHEN NOT TO USE conditions are NOT triggered. Never pick an architecture that requires proof,
evidence, or a contradiction the brief doesn't actually supply — an architecture that needs a real
statistic or real photographed evidence must not be chosen if none is available; one that needs a
real behavioral contradiction must not be chosen if none exists.

Do not default to the same architecture out of habit — actually weigh the brief against each
architecture's WHEN TO USE/WHEN NOT conditions before choosing.

Return ONLY this JSON, no prose, no markdown fences. Keep "reasoning" to ONE short sentence (under
20 words) — this field exists for a debug log, not an essay, and a long reasoning field risks
truncating the response:
{"architecture_key": string, "reasoning": string}
"architecture_key" must be exactly one of the keys listed below, nothing else."""


_ARCHITECTURE_KEY_REGEX = re.compile(r'"architecture_key"\s*:\s*"([a-z_]+)"')


def _extract_architecture_key(text: str) -> str:
    """Tries strict JSON first, then falls back to a direct regex pull of
    just the architecture_key field — the ONLY field that actually matters
    here. Makes selection resilient to a truncated/malformed "reasoning"
    field (the observed real failure mode: a long reasoning string cut off
    mid-word by the token budget, breaking json.loads() even though
    architecture_key itself was written first and complete)."""
    try:
        data = json.loads(text)
        return str(data.get("architecture_key") or "").strip().lower()
    except (json.JSONDecodeError, TypeError):
        match = _ARCHITECTURE_KEY_REGEX.search(text)
        return match.group(1).strip().lower() if match else ""


def select_architecture(
    *,
    product_category: str,
    target_audience: str,
    objective: str,
    available_proof: str,
    tone: str,
    platform: str,
    insight_statement: str = "",
) -> Architecture:
    """LLM-assisted selection with a deterministic, always-safe fallback —
    never raises. Falls back to DEFAULT_ARCHITECTURE_KEY (a broadly
    applicable, low-risk architecture) on any failure so a caller can always
    proceed."""
    fallback = ARCHITECTURES[DEFAULT_ARCHITECTURE_KEY]
    try:
        user_msg = (
            f"Product category: {product_category}\n"
            f"Target audience: {target_audience}\n"
            f"Objective: {objective or 'drive consideration/purchase'}\n"
            f"Available proof/evidence: {available_proof or 'none specifically given — assume only named product facts, no statistics, no real photographed evidence'}\n"
            f"Tone: {tone or 'unspecified'}\n"
            f"Platform: {platform or 'short-form video'}\n"
            f"Human insight already discovered: {insight_statement or 'none discovered — pick an architecture that does not strictly require one'}\n\n"
            f"Architecture library:\n{architecture_catalog_prompt_block()}"
        )
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SELECTION_SYSTEM_PROMPT,
                contents=[user_msg],
                model=settings.openrouter_text_model,
                max_output_tokens=500,
                json_mode=True,
            ),
            label="architecture_selection",
        )
        key = _extract_architecture_key(text)
        if key:
            return ARCHITECTURES.get(key, fallback)
        return fallback
    except Exception as e:
        logger.warning("Architecture selection failed, falling back to default: %s", e)
        return fallback
