"""Product Creative Contract — the fixed factual grounding every creative
pipeline stage receives, so a product's real commercial identity (what it
actually is, who uses it, why, and in what context) can never be silently
redefined by an LLM's word association with the product's name.

Root cause this exists to fix: "Herbal Masala" contains the word "masala",
and nothing upstream of the final script writer was ever told, as a fact
rather than a suggestion, that this specific product is NOT a cooking
ingredient — so a sufficiently creative pass could (and did) reinterpret it
as one. The fix is not a banned-word list; it's establishing PRODUCT TRUTH
before creative generation even starts, then keeping every stage anchored to
it:

PRODUCT TRUTH -> AUDIENCE TRUTH -> BEHAVIOURAL TRUTH -> CREATIVE TERRITORY
-> STORYTELLING DEVICE -> SCRIPT

Never a product-name-only guess: the contract is DERIVED from data already
in the system (the given brief, the Product Library's ProductContext when
one is selected, and — the strongest signal available for a product whose
Product Library category is generic — whether the brief's own audience/USP/
benefits text matches a known reference-DNA category, per
creative_reference_dna.is_tobacco_gutka_brief). Nothing here is invented:
where a field genuinely can't be derived, it's left blank/"unknown" rather
than guessed, and category_confidence reflects how much can actually be
trusted.
"""

from dataclasses import dataclass, field

from app.services import creative_reference_dna

# Recognized "risky product role" keys — a small, explicit vocabulary (not
# free text) that both this module and product_context_validator.py key off.
# A contract only includes a key here when there's a genuine, product-
# specific reason to guard against that particular reinterpretation; most
# products carry none of these, and the corresponding detector in
# product_context_validator.py simply never runs for them (see that module's
# docstring) — this is what keeps the mechanism reusable rather than a
# Herbal-Masala-specific global hack.
ROLE_RISK_FOOD_OR_COOKING_INGREDIENT = "food_or_cooking_ingredient"
# Phase 2C: a distinct drift pattern found in live UI review — a habit-
# replacement product reinterpreted as a fitness/energy/nutrition supplement
# ("Fitness Enthusiast ka Secret Weapon"). Different role than the cooking
# one above (no food/kitchen context at all), so it's its own registry key,
# not folded into the food detector.
ROLE_RISK_FITNESS_OR_NUTRITION_SUPPLEMENT = "fitness_or_nutrition_supplement"


@dataclass
class ProductCreativeContract:
    product_name: str
    brand: str = ""
    canonical_category: str = ""
    category_confidence: str = "unknown"  # "high" | "medium" | "low" | "unknown"
    product_type: str = ""
    primary_use_case: str = ""
    primary_audience: str = ""
    consumer_behavior: str = ""
    consumption_context: str = ""
    core_problem_or_tension: str = ""
    product_role: str = ""
    supported_benefits: list[str] = field(default_factory=list)
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    allowed_contexts: list[str] = field(default_factory=list)
    forbidden_contexts: list[str] = field(default_factory=list)
    # Recognized ROLE_RISK_* keys this contract actively guards against —
    # empty for a product with no known risky-reinterpretation pattern.
    role_risk_keys: list[str] = field(default_factory=list)
    reference_derived: bool = False

    def prompt_block(self) -> str:
        benefits_line = ", ".join(self.supported_benefits) or "none given"
        claims_line = ", ".join(self.supported_claims) or "none beyond the benefits above"
        unsupported_line = ", ".join(self.unsupported_claims) or "none flagged"
        allowed_line = "\n".join(f"  - {c}" for c in self.allowed_contexts) or "  (no specific restriction beyond the category above)"
        forbidden_line = "\n".join(f"  - {c}" for c in self.forbidden_contexts) or "  (none specifically flagged)"
        confidence_note = (
            "" if self.category_confidence == "high" else
            f"\n(Category confidence: {self.category_confidence} — where a detail below wasn't reliably "
            "determinable, treat it as unresolved rather than inventing specifics.)"
        )
        return (
            "PRODUCT CREATIVE CONTRACT (immutable factual grounding — read this BEFORE anything else "
            "below; every other block builds inside these facts, never redefines them):\n"
            f"Product: {self.product_name}" + (f" ({self.brand})" if self.brand else "") + "\n"
            f"Actual category/what this product IS: {self.canonical_category or 'not reliably determined'}\n"
            f"Product type: {self.product_type or 'not reliably determined'}\n"
            f"Primary real-world use case: {self.primary_use_case or 'not reliably determined'}\n"
            f"Primary audience: {self.primary_audience or 'not reliably determined'}\n"
            f"Consumer behavior around it: {self.consumer_behavior or 'not reliably determined'}\n"
            f"Consumption/usage context: {self.consumption_context or 'not reliably determined'}\n"
            f"Core problem/tension it sits inside: {self.core_problem_or_tension or 'not reliably determined'}\n"
            f"Product's role in a story: {self.product_role or 'not reliably determined'}\n"
            f"Supported benefits (may be used): {benefits_line}\n"
            f"Supported claims (may be used, reworded but never exceeded): {claims_line}\n"
            f"Unsupported claims (never use, in any wording): {unsupported_line}\n"
            f"Contexts consistent with this product's real use (creative freedom lives HERE):\n{allowed_line}\n"
            f"Contexts that would misrepresent what this product actually is/does — NEVER portray the "
            f"product this way, no matter how creative or unexpected it seems:\n{forbidden_line}\n"
            "RULE: creative experimentation may freely change the narrative device, visual metaphor, "
            "character, setting, tone, humor, or structure — it must NEVER change what the product "
            "fundamentally is, who it's for, or how it's actually used/consumed, unless the brief above "
            "explicitly asks for a different context. Do not reinterpret the product based on an "
            "ambiguous word in its name — treat the facts above as fixed, not a starting point for "
            "association." + confidence_note + "\n"
        )


# Product types whose real commercial role is a tobacco/gutka/pan-masala/
# supari alternative — derived (never hardcoded to one product name) from
# whether the BRIEF's own audience/usp/benefits text matches the reference-
# DNA category, the same signal already used to un-gate reference-DNA
# content and the anti-overfit filter for this exact category.
def _gutka_alternative_contract_fields() -> dict:
    return {
        "canonical_category": "Tobacco/gutka/pan-masala/supari consumption alternative — a switching/habit-replacement product, not a food or cooking product",
        "category_confidence": "high",
        "product_type": "an oral chew/mouth-freshening substitute for gutka, tobacco, or supari",
        "primary_use_case": "reached for in place of gutka/tobacco/supari, in the moments and situations that habit would normally be reached for",
        "consumer_behavior": "habitual chewing/consumption, craving the familiar taste and ritual, considering or actively trying to switch away from tobacco/gutka/supari",
        "consumption_context": "the everyday moments and rituals around the existing gutka/tobacco/supari habit — reaching for the packet, cravings, social consumption situations, the taste/sensory ritual, the habit's smell/spitting/social visibility, wanting an alternative",
        "core_problem_or_tension": "the pull of an existing gutka/tobacco/supari habit versus a genuine desire to switch away from it, without losing the familiar ritual/taste",
        "product_role": "the thing reached for INSTEAD of gutka/tobacco/supari — never an item added to food",
        "allowed_contexts": [
            "reaching automatically for where the old gutka/tobacco packet used to be",
            "a social situation involving a gutka/tobacco/supari user or their peers",
            "the habitual chewing/consumption moment itself",
            "a visual metaphor for the old habit (fading, disappearing, being replaced)",
            "a character trying this as a different option to their usual habit",
            "humor or awkwardness around the old habit or the switching decision",
            "a surprising replacement-ritual reveal",
        ],
        "forbidden_contexts": [
            "used as a cooking ingredient, spice, or food seasoning",
            "added to a dish, curry, dal, sabzi, or any recipe",
            "portrayed as a kitchen/cooking product a family or chef would use in food preparation",
            "positioned as a fitness, energy, or nutrition/workout supplement",
        ],
        "role_risk_keys": [ROLE_RISK_FOOD_OR_COOKING_INGREDIENT, ROLE_RISK_FITNESS_OR_NUTRITION_SUPPLEMENT],
        "reference_derived": True,
    }


def build_product_creative_contract(
    *,
    product_name: str,
    category: str,
    target_audience: str,
    usp: str = "",
    benefits: list[str] | None = None,
    primary_problem: str = "",
    product_context=None,  # ProductContext | None — the richer Product Library record, when selected
) -> ProductCreativeContract:
    """Derives the contract from data already flowing through the pipeline —
    never invents a category/use-case from the product name alone. Never
    raises: falls back to the most conservative (low-confidence, empty
    forbidden/allowed lists) contract rather than guessing."""
    benefits = benefits or []
    brand = getattr(product_context, "brand", "") if product_context else ""
    supported_claims = list(getattr(product_context, "approved_claims", []) or []) if product_context else []
    unsupported_claims = list(getattr(product_context, "prohibited_claims", []) or []) if product_context else []
    never_say = getattr(product_context, "never_say", "") if product_context else ""
    if never_say:
        unsupported_claims = unsupported_claims + [never_say]
    positioning = getattr(product_context, "positioning", "") if product_context else ""

    brief_text = " ".join([product_name, target_audience, usp, primary_problem, " ".join(benefits)])

    if creative_reference_dna.is_tobacco_gutka_brief(brief_text) or creative_reference_dna.is_tobacco_gutka_brief(category):
        derived = _gutka_alternative_contract_fields()
        return ProductCreativeContract(
            product_name=product_name,
            brand=brand,
            primary_audience=target_audience or "not reliably determined",
            supported_benefits=benefits,
            supported_claims=supported_claims,
            unsupported_claims=unsupported_claims,
            **derived,
        )

    # Generic path — no known reference-derived category match. Derive
    # whatever the given brief/context actually states; never invent a
    # specific use-case or a forbidden-context list beyond what's given.
    # category_confidence reflects how concrete the given category string
    # actually is, not a guess about correctness.
    category_clean = (category or "").strip()
    confidence = "medium" if category_clean and category_clean.lower() not in ("", "other", "general", "misc") else "low"
    return ProductCreativeContract(
        product_name=product_name,
        brand=brand,
        canonical_category=category_clean or "",
        category_confidence=confidence,
        product_type=category_clean,
        primary_use_case=usp or positioning or "",
        primary_audience=target_audience or "",
        core_problem_or_tension=primary_problem or "",
        product_role="the product as described in its category/USP above — do not redefine what kind of product this is",
        supported_benefits=benefits,
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        allowed_contexts=[],
        forbidden_contexts=[],
        role_risk_keys=[],
        reference_derived=False,
    )
