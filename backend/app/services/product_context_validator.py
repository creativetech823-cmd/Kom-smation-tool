"""Product Context / Category-Drift Validator — answers one question, kept
deliberately separate from creative quality, clichés, and claim safety:
"does this text still treat the product according to its actual defined use
case, or has the creative reinterpreted what the product IS?"

Two layers, matching the rest of this pipeline's deterministic-first
convention:

1. Deterministic role-risk detectors (free, always run): a small registry of
   RELATIONSHIP-based pattern detectors, keyed by the recognized
   ROLE_RISK_* keys a product's ProductCreativeContract can carry. Each
   detector checks a structural relationship (a food-preparation ACTION or
   ROLE co-occurring with the product/a reference to it in the same
   sentence) — not a flat banned-word list — and, critically, only ever
   runs for a product whose contract actually flags that risk. A product
   with no role_risk_keys never has any detector run against it at all, so
   this can never accidentally punish an unrelated product for mentioning
   "kitchen" or "family dinner" in a legitimate scene.

2. LLM semantic check (validation tier — Flash-Lite): the real judgment
   call, given the contract's allowed/forbidden contexts and asked
   explicitly whether the text's PRODUCT ROLE (not its creative quality)
   still matches. Used sparingly: callers should generally only reach for
   this when the deterministic layer flagged something, OR unconditionally
   at the single highest-stakes checkpoint (the final script), matching the
   task's cost-efficiency requirement.

Never raises: any failure here returns a "no drift detected" result rather
than blocking generation — this is a gate for a real defect, not a source of
new failures in itself.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text
from app.services.product_context_service import (
    ROLE_RISK_FITNESS_OR_NUTRITION_SUPPLEMENT,
    ROLE_RISK_FOOD_OR_COOKING_INGREDIENT,
    ProductCreativeContract,
)

logger = logging.getLogger("product_context_validator")


@dataclass
class CategoryValidationResult:
    passed: bool
    category_drift: bool
    reason: str = ""
    violations: list[str] = field(default_factory=list)
    severity: str = "none"  # "none" | "warning" | "critical"

    def as_dict(self) -> dict:
        return {
            "passed": self.passed, "category_drift": self.category_drift, "reason": self.reason,
            "violations": self.violations, "severity": self.severity,
        }


_PASS = CategoryValidationResult(passed=True, category_drift=False, severity="none")


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?।])\s+|\n+", text) if s.strip()]


# --- food_or_cooking_ingredient role-risk detector --------------------------
# The one concrete detector this ships with today — the actual failure mode
# this task exists to fix. A RELATIONSHIP check (a cooking action/role
# co-occurring with a food-dish noun in the same sentence), not a flat
# banned-word list: mentioning "kitchen" or "dinner" alone never triggers
# this; the product being given a food-preparation ROLE does.
_COOKING_ACTION_PATTERNS: list[re.Pattern] = [
    # \w* (not a fixed ed/ing/s suffix list) so "mixes", "mixing", "mixed",
    # "adds", "seasons", "sprinkled" etc. all match uniformly.
    re.compile(r"\b(add\w*|mix\w*|sprinkle\w*|season\w*|cook\w*|simmer\w*|marinate\w*|garnish\w*|stir\w*)\b", re.IGNORECASE),
    re.compile(r"\b(daal(o|un|doon|do|ti|ta|te)?|chhid[ao]k\w*|pakao|pakaya|banaya|mix\s*kar\w*)\b", re.IGNORECASE),
]
_FOOD_ROLE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(ingredient\w*|seasoning|spice mix|cooking spice|recipe\w*)\b", re.IGNORECASE),
]
_FOOD_DISH_NOUNS = re.compile(
    r"\b(curry|dal|daal|sabzi|sabji|biryani|khaana|khana|dish(es)?|meal\w*|bowl(s)?|cooking|recipe\w*|chef|"
    r"dinner|lunch|breakfast|food|snack\w*)\b",
    re.IGNORECASE,
)
# A CONTAINMENT relationship ("a bowl of curry WITH the product", "curry
# containing X") implies the product is playing a food-ingredient role even
# with no explicit cooking verb — the exact "Two bowls of curry, one with
# Aayush Herbal Masala" shape from the reported failure.
_CONTAINMENT_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(with|has|contain(s|ing)?|mixed with|topped with)\b", re.IGNORECASE),
]


def _detect_food_preparation_role_signal(text: str) -> str:
    """Returns a short evidence string if any sentence shows the product
    being given a food-preparation ROLE (a cooking action, an ingredient/
    seasoning role word, or a containment relationship — "bowl with X" —
    co-occurring with a food-dish noun), empty string otherwise. Deliberately
    relationship-based, not a keyword list — a sentence with only a food-dish
    noun and no such relationship (e.g. a character simply sitting at a
    family dinner) does not match."""
    for sentence in _split_sentences(text):
        if not _FOOD_DISH_NOUNS.search(sentence):
            continue
        has_action = any(p.search(sentence) for p in _COOKING_ACTION_PATTERNS)
        has_role = any(p.search(sentence) for p in _FOOD_ROLE_PATTERNS)
        has_containment = any(p.search(sentence) for p in _CONTAINMENT_PATTERNS)
        if has_action or has_role or has_containment:
            return sentence.strip()
    return ""


# Registry: ROLE_RISK_* key -> detector(text) -> evidence string ("" = clean).
# Extending this to a future category's own known risky-role pattern means
# adding one entry here and one ROLE_RISK_* constant in
# product_context_service.py — never a per-product branch anywhere else.
# --- fitness_or_nutrition_supplement role-risk detector ---------------------
# Phase 2C: a second, distinct drift pattern found in live UI review — a
# habit-replacement product reinterpreted as a fitness/energy/nutrition
# supplement ("Fitness Enthusiast ka Secret Weapon"). No food/kitchen words
# involved at all, so this needed its own detector, not a food-list addition.
_FITNESS_ROLE_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(energy (boost|supplement|drink)|pre-?workout|protein (supplement|shake|powder)|"
        r"nutrition(al)? supplement|fitness supplement|workout fuel|performance booster|gym supplement)\b",
        re.IGNORECASE,
    ),
]
_FITNESS_ACTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(boost\w*|fuel\w*|power\w*|energiz\w*|supercharg\w*)\b", re.IGNORECASE),
]
_FITNESS_CONTEXT_NOUNS = re.compile(
    r"\b(energy|workout|gym|fitness|nutrition|protein|performance|exercise|training)\b", re.IGNORECASE
)


def _detect_fitness_nutrition_role_signal(text: str) -> str:
    """Returns evidence if the product is given a fitness/energy/nutrition
    ROLE — either an explicit role phrase ("pre-workout", "energy
    supplement") or an energizing ACTION verb co-occurring with a fitness/
    workout/nutrition context noun in the same sentence. A character simply
    being a "fitness enthusiast" or going to the "gym" with no such role
    assigned to the product does not match on its own."""
    for sentence in _split_sentences(text):
        if any(p.search(sentence) for p in _FITNESS_ROLE_PATTERNS):
            return sentence.strip()
        has_context = bool(_FITNESS_CONTEXT_NOUNS.search(sentence))
        has_action = any(p.search(sentence) for p in _FITNESS_ACTION_PATTERNS)
        if has_context and has_action:
            return sentence.strip()
    return ""


_ROLE_RISK_DETECTORS = {
    ROLE_RISK_FOOD_OR_COOKING_INGREDIENT: _detect_food_preparation_role_signal,
    ROLE_RISK_FITNESS_OR_NUTRITION_SUPPLEMENT: _detect_fitness_nutrition_role_signal,
}


def detect_category_drift_signal(text: str, contract: ProductCreativeContract | None) -> str:
    """Deterministic, free. Returns a short evidence string if any
    registered detector for one of THIS contract's own role_risk_keys
    fires, "" otherwise (including when the contract has no role_risk_keys
    at all — the common case for most products, which never runs any
    detector)."""
    if contract is None or not contract.role_risk_keys:
        return ""
    for key in contract.role_risk_keys:
        detector = _ROLE_RISK_DETECTORS.get(key)
        if detector is None:
            continue
        evidence = detector(text)
        if evidence:
            return evidence
    return ""


_SEMANTIC_SYSTEM_PROMPT = """You check ONE thing about a piece of ad-creative text: does it treat the
product according to its ACTUAL defined commercial use case (given below as a fixed Product Creative
Contract), or has the creative silently reinterpreted what the product IS, who it's for, or how it's
used/consumed?

Do NOT judge creative quality, clichés, claims, or length — those are checked elsewhere. Creative
freedom in storytelling device, metaphor, character, setting, tone, humor, and structure is expected
and fine, even when it doesn't literally restate the product's category. What fails this check is the
product's real-world ROLE being changed — e.g. a product whose real use case is a tobacco/gutka
alternative being shown added to food as a cooking ingredient, or any other contradiction between the
text and the given contract's category/use case/audience/consumption context.

Return ONLY this JSON, no prose, no markdown fences:
{"category_drift": boolean, "reason": string, "violations": [string]}
category_drift=false, reason="", violations=[] when the text is genuinely consistent with the contract's
real use case, even if it never literally restates it."""


def _semantic_user_message(text: str, contract: ProductCreativeContract) -> str:
    return f"{contract.prompt_block()}\nGenerated creative text to check:\n{text}"


def llm_category_alignment_check(text: str, contract: ProductCreativeContract | None, label: str = "category_drift_check") -> CategoryValidationResult:
    """The real semantic judgment call — validation tier (Flash-Lite).
    Never raises: any failure is treated as a pass (fail-open, same
    convention as every other gate in this pipeline) since this is a
    defect-catcher, not a source of new failures."""
    if contract is None:
        return _PASS
    try:
        raw = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SEMANTIC_SYSTEM_PROMPT,
                contents=[_semantic_user_message(text, contract)],
                model=settings.validation_model,
                max_output_tokens=250,
                json_mode=True,
                label=label,
            ),
            label=label,
            max_attempts=2,
        )
        data = json.loads(raw)
        drift = bool(data.get("category_drift"))
        reason = str(data.get("reason") or "")
        violations = [v for v in (data.get("violations") or []) if isinstance(v, str)]
        return CategoryValidationResult(
            passed=not drift, category_drift=drift, reason=reason, violations=violations,
            severity="critical" if drift else "none",
        )
    except Exception as e:
        logger.warning("Category-drift semantic check failed, treating as pass: %s", e)
        return _PASS


def validate_category_alignment(
    text: str,
    contract: ProductCreativeContract | None,
    *,
    force_semantic_check: bool = False,
    label: str = "category_drift_check",
) -> CategoryValidationResult:
    """The combined entry point most callers should use: runs the free
    deterministic detector first; escalates to the LLM semantic check only
    if the deterministic layer found evidence OR the caller explicitly
    forces it (e.g. the single unconditional final-script checkpoint) —
    keeps the common case (no drift, no LLM call) genuinely free."""
    if contract is None:
        return _PASS
    evidence = detect_category_drift_signal(text, contract)
    if not evidence and not force_semantic_check:
        return _PASS
    result = llm_category_alignment_check(text, contract, label=label)
    if evidence and not result.category_drift:
        # The deterministic layer found real structural evidence (a food-
        # prep role co-occurring with the product's context) that the LLM
        # check didn't confirm as drift — surface it as a lower-severity
        # warning rather than silently dropping it, since the relationship
        # pattern itself is real signal even if the LLM judged the overall
        # text as still consistent (e.g. a legitimate contrast/negation).
        return CategoryValidationResult(
            passed=True, category_drift=False,
            reason=f"deterministic pattern flagged but semantic check found no real drift: {evidence}",
            violations=[], severity="none",
        )
    return result
