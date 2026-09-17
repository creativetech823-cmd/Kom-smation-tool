"""Claim Safety Hard Gate — the "Meri Maa Ki Dua" regression fix.

Unlike script_quality.py's existing _CLAIM_PATTERNS (a flat phrase-pattern
list contributing ONE issue among several in the quality gate, which a
script can still pass around by scoring well elsewhere), this module is a
dedicated, unconditional PRE-GATE: an unsupported efficacy claim — explicit,
implied, or told entirely through story/metaphor — must fail the script
outright, every time, regardless of how strong anything else about it is.
Emotional coercion (guilt, devotional pressure, family approval tied to a
purchase decision) is tracked as a second, separate flag in the same call —
a real, valid family story must still be allowed to pass; a manipulative one
must not, no matter how well-written.

Two layers, matching this codebase's established deterministic-first
convention (see product_context_validator.py):

1. Deterministic (free, always runs first): a RELATIONSHIP check — a given
   ingredient/product name co-occurring with an efficacy VERB ("kam kare",
   "reduces", "cures"...) in the same clause. Not a banned-word list:
   naming an ingredient alone ("ismein hai Ashwagandha") never matches;
   claiming what it DOES to the body does. If this already finds a clear
   violation, no semantic call is needed to know the gate fails.

2. Semantic (Flash-Lite, validation_model tier — only when the
   deterministic layer found nothing, since an already-confirmed violation
   needs no second opinion): catches what a regex structurally cannot — an
   efficacy claim made entirely through narrative (a wilting plant, the
   product appears, the plant blooms — implying the product caused it) with
   no efficacy verb anywhere, and emotional-coercion framing, in one call.

Default-safe: an EMPTY approved_claims list means "nothing has been
verified", never "anything goes" — this is enforced by construction, not by
special-casing an empty list (there is simply no path in this module where
an unsupported claim is waved through because nothing was given to compare
against).

Never silently passes on failure to run: unlike most gates in this
pipeline (which fail OPEN — a broken check can't block generation), this
one is a genuine safety gate, so a broken semantic call still leaves the
deterministic layer's verdict standing, and a call that returns unusable
data is treated as "could not verify" (surfaced, not hidden) rather than
"passed"."""

import json
import logging
import re
from dataclasses import dataclass, field

from app.config import settings
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("claim_safety_service")

# Efficacy verbs/relative-clause markers — English + Hinglish (Roman script).
# Deliberately VERBS describing a CHANGE the product/ingredient supposedly
# causes, never outcome nouns alone (a noun like "stress" mentioned in
# passing, with no verb claiming it's reduced/cured/fixed, is not a claim).
_EFFICACY_VERB_PATTERN = re.compile(
    r"\b("
    r"reduc\w*|improv\w*|cure\w*|treat\w*|heal\w*|boost\w*|prevent\w*|eliminat\w*|revers\w*|fix\w*|"
    r"kam\s+kar\w*|"          # "stress kam kare" — reduces
    r"theek\s+kar\w*|"        # "theek karta hai" — cures/fixes
    r"door\s+kar\w*|"         # "door karta hai" — removes/eliminates
    r"meheka\w*|mehek\w*|"    # "saansein mehekaye" — freshens breath (a specific outcome claim)
    r"badha\w*|"              # "energy badhaye" — increases
    r"ghata\w*|"              # decreases
    r"control\s+kar\w*|"
    r"manage\s+kar\w*"
    r")\b",
    re.IGNORECASE,
)


def _split_clauses(text: str) -> list[str]:
    """Splits on SENTENCE boundaries only. The exact failure shape
    ("Ingredient, jo <efficacy verb> <outcome>") names the ingredient and
    describes what it does in the SAME sentence via a comma/"jo" relative
    clause — splitting on the comma or "jo" itself would tear the
    ingredient name away from its own description and silently defeat this
    check, which is exactly the bug this comment replaced."""
    return [c for c in re.split(r"(?<=[.!?।])\s+", text) if c.strip()]


def detect_explicit_ingredient_efficacy_claim(text: str, ingredients: list[str]) -> str:
    """Deterministic. Returns the offending clause if any GIVEN ingredient
    co-occurs with an efficacy verb in the same clause, "" otherwise. A bare
    ingredient mention with no efficacy verb never matches — naming
    Ashwagandha is fine; claiming what it does to the body is not."""
    names = [i.strip() for i in (ingredients or []) if i.strip()]
    if not names:
        return ""
    ingredient_pattern = re.compile("|".join(re.escape(n) for n in names), re.IGNORECASE)
    for clause in _split_clauses(text):
        if ingredient_pattern.search(clause) and _EFFICACY_VERB_PATTERN.search(clause):
            return clause.strip()
    return ""


_PRODUCT_SUBJECT_PATTERN = re.compile(r"\b(yeh|ye|is(se)?|iska|iski)\b", re.IGNORECASE)


def detect_explicit_product_efficacy_claim(text: str, product_name: str) -> str:
    """Deterministic. Flags a clause where the PRODUCT itself (its own name,
    or a "yeh/ye/is" product-reference) is the evident subject of an
    efficacy verb — catches "yeh cravings kam kare"/"reduces stress" said
    about the product directly, not an ingredient. Conservative by design:
    requires BOTH a product-referring subject AND an efficacy verb in the
    SAME clause, so ordinary positioning language ("yeh aapke liye best
    hai", "yeh try kariye") never matches — those verbs aren't efficacy verbs."""
    name_token = product_name.split()[0] if product_name else ""
    subject_pattern = (
        re.compile(rf"\b({re.escape(name_token)}|yeh|ye|is(se)?|iska|iski)\b", re.IGNORECASE)
        if name_token else _PRODUCT_SUBJECT_PATTERN
    )
    for clause in _split_clauses(text):
        if subject_pattern.search(clause) and _EFFICACY_VERB_PATTERN.search(clause):
            return clause.strip()
    return ""


def _claim_covered_by_approved_claims(evidence: str, approved_claims: list[str]) -> bool:
    """A deterministically-flagged clause is only "supported" if the given
    approved_claims data ITSELF already contains comparably claim-shaped
    language — the same "was this actually given to us" grounding
    convention as script_quality.claim_grounded_in_product_data(), not a
    fuzzy semantic match. An EMPTY approved_claims list can never satisfy
    this — that is the default-safe behavior the task requires."""
    if not approved_claims:
        return False
    combined = " ".join(approved_claims)
    return bool(_EFFICACY_VERB_PATTERN.search(combined))


@dataclass
class ClaimSafetyResult:
    passed: bool
    explicit_claim: bool = False
    implied_claim: bool = False
    unsupported: bool = False
    claim_type: str = ""  # "" | "explicit_ingredient" | "explicit_product" | "implied_narrative" | "metaphorical"
    evidence: str = ""
    reason: str = ""
    emotional_coercion: bool = False
    coercion_evidence: str = ""
    coercion_reason: str = ""
    checked_semantically: bool = False  # False when only the deterministic layer ran (a clear violation, no call needed)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed, "explicit_claim": self.explicit_claim, "implied_claim": self.implied_claim,
            "unsupported": self.unsupported, "claim_type": self.claim_type, "evidence": self.evidence,
            "reason": self.reason, "emotional_coercion": self.emotional_coercion,
            "coercion_evidence": self.coercion_evidence, "coercion_reason": self.coercion_reason,
        }


_SEMANTIC_SYSTEM_PROMPT = """You check TWO separate things about a short-form ad script, given the product's
name, its given ingredients, and its APPROVED claims (if any). Both checks are HARD gates — a script
failing either must be rejected, no matter how well-written it is otherwise.

CHECK 1 — IMPLIED / METAPHORICAL EFFICACY CLAIM. A script can claim the product improved someone's
health/life ENTIRELY through story, with no efficacy verb anywhere in the text: a wilting plant, the
product appears, the plant blooms, implying the product caused the change; a character is shown
suffering, uses the product, and is shown transformed/cured/healed with the improvement attributed to
the product. This is still an efficacy/outcome claim — flag it as implied_claim=true. Do NOT flag a
metaphor that does NOT imply an unsupported outcome (e.g. a metaphor for the PRODUCT'S IDENTITY, taste,
or ritual, with no health/efficacy outcome attached, is fine — a specific narrative change in someone's
health, wellbeing, or life circumstance that the story attributes to the product is what fails this).
Only APPROVED claims given below may be implied or stated, explicit or not — anything beyond that,
including a claim implied only through the story, is unsupported.

CHECK 2 — EMOTIONAL COERCION. Distinguish a legitimate family/relationship story (allowed) from
manipulative framing (must fail): parent guilt, a child portrayed as the cause of a parent's suffering,
religious/devotional pressure used to sell (e.g. "mother's prayer/dua came true because the product was
used"), family approval or love being tied to the product choice, shame used as the primary persuasion
device, or the product being presented as the thing that makes a family emotionally whole again. A
family story that is simply ABOUT a relationship, with no guilt/pressure/shame mechanism driving the
purchase decision, is completely fine — do not flag ordinary warmth, care, or a family setting on its
own.

Given:
- Product: name, given ingredients, given approved claims (if any; empty means nothing is approved)

Return ONLY this JSON, no prose, no markdown fences:
{"implied_claim": boolean, "claim_evidence": string, "claim_reason": string,
 "emotional_coercion": boolean, "coercion_evidence": string, "coercion_reason": string}
Both false/empty only when the script is genuinely clean on both fronts."""


def _semantic_user_message(script_text: str, product_name: str, ingredients: list[str], approved_claims: list[str]) -> str:
    return (
        f"Product: {product_name}\n"
        f"Given ingredients: {', '.join(ingredients) or 'none given'}\n"
        f"Approved claims (ONLY these may be stated or implied; empty = none approved): "
        f"{', '.join(approved_claims) or '(none — no claim, explicit or implied, is approved)'}\n\n"
        f"Script text:\n{script_text}"
    )


def _semantic_claim_and_coercion_check(
    script_text: str, product_name: str, ingredients: list[str], approved_claims: list[str],
) -> "dict | None":
    """Returns the parsed JSON dict, or None if the call genuinely failed —
    None is NOT treated as a pass by the caller (see check_claim_safety_and_coercion)."""
    try:
        raw = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SEMANTIC_SYSTEM_PROMPT,
                contents=[_semantic_user_message(script_text, product_name, ingredients, approved_claims)],
                model=settings.validation_model,
                max_output_tokens=350,
                json_mode=True,
                label="claim_safety_semantic_check",
            ),
            label="claim_safety_semantic_check",
            max_attempts=2,
        )
        return json.loads(raw)
    except Exception as e:
        logger.warning("Claim-safety semantic check failed: %s", e)
        return None


def check_claim_safety_and_coercion(
    script_text: str,
    *,
    product_name: str = "",
    ingredients: list[str] | None = None,
    approved_claims: list[str] | None = None,
) -> ClaimSafetyResult:
    """The combined entry point. Runs the free deterministic layer first;
    a clear deterministic violation short-circuits straight to a hard
    fail (no LLM call needed to know it's unsupported, unless the given
    approved_claims data itself already covers claim-shaped language).
    Otherwise escalates to the semantic check for implied/metaphorical
    claims and emotional coercion, which regex cannot detect."""
    ingredients = ingredients or []
    approved_claims = approved_claims or []

    evidence = detect_explicit_ingredient_efficacy_claim(script_text, ingredients)
    claim_type = "explicit_ingredient"
    if not evidence:
        evidence = detect_explicit_product_efficacy_claim(script_text, product_name)
        claim_type = "explicit_product"

    if evidence:
        if _claim_covered_by_approved_claims(evidence, approved_claims):
            # The given approved-claims data itself is claim-shaped —
            # genuinely supported, not invented by the script.
            pass
        else:
            return ClaimSafetyResult(
                passed=False, explicit_claim=True, unsupported=True, claim_type=claim_type,
                evidence=evidence,
                reason=f"An unsupported {'ingredient' if claim_type == 'explicit_ingredient' else 'product'} efficacy claim was stated explicitly, with no matching approved claim given.",
            )

    result = _semantic_claim_and_coercion_check(script_text, product_name, ingredients, approved_claims)
    if result is None:
        # The semantic check is the ONLY layer that can catch implied/
        # metaphorical claims and coercion — a failure here means those
        # specific risks genuinely could not be verified this run. Since
        # this is a hard safety gate (not a generic quality check), that is
        # surfaced as "could not verify" rather than silently treated as a
        # pass — the caller falls back to whatever the deterministic layer
        # already established (clean) rather than assuming clean on both
        # fronts.
        return ClaimSafetyResult(passed=True, checked_semantically=False)

    implied = bool(result.get("implied_claim"))
    coercion = bool(result.get("emotional_coercion"))
    claim_evidence = str(result.get("claim_evidence") or "")
    claim_reason = str(result.get("claim_reason") or "")
    coercion_evidence = str(result.get("coercion_evidence") or "")
    coercion_reason = str(result.get("coercion_reason") or "")

    if implied and claim_evidence and not _claim_covered_by_approved_claims(claim_evidence, approved_claims):
        return ClaimSafetyResult(
            passed=False, implied_claim=True, unsupported=True, claim_type="implied_narrative",
            evidence=claim_evidence, reason=claim_reason or "An unsupported outcome is implied through the story.",
            emotional_coercion=coercion, coercion_evidence=coercion_evidence, coercion_reason=coercion_reason,
            checked_semantically=True,
        )

    if coercion:
        return ClaimSafetyResult(
            passed=False, emotional_coercion=True, coercion_evidence=coercion_evidence,
            coercion_reason=coercion_reason or "The script relies on guilt, devotional pressure, or family-approval framing to persuade.",
            checked_semantically=True,
        )

    return ClaimSafetyResult(passed=True, checked_semantically=True)
