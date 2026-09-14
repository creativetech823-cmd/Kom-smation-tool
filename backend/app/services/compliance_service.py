"""Stage 7 — Compliance Audit V2.

Two independent layers, run in order, cheapest/most-certain first:

Layer 1 (deterministic, free, in compliance_claims.py): regex checks for
claim SHAPES that are unambiguous by their own wording — a guarantee, a
medical/absolute-outcome verb, a quantified result, a fake-authority appeal.
If this layer finds anything, that's already enough to BLOCK, so we skip the
LLM call entirely (no reason to pay for a semantic opinion on "Guaranteed to
cure fatigue in 7 days.").

Layer 2 (contextual, one LLM call, only when Layer 1 found nothing): the
judgment call regex can't make — is this sentence aspirational creative
copy, or does the surrounding context turn it into an actual product-result
claim? This is where "New strength, new finish line." must come back clean
while "Take our Strength Kit and finish every marathon" must not.

This module stays independent from script_quality.py (creative-quality gate)
and from script generation itself — compliance is a separate audit pass over
finished text, same as before.
"""

import json
import logging

from app.config import settings
from app.models.product import ComplianceCheckInput, ComplianceResult, ComplianceViolation
from app.services.compliance_claims import DeterministicFinding, find_deterministic_violations
from app.services.compliance_rules import rules_for_category
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("compliance_service")

# Layer 2 severities, mapped down to the wire severities ("blocker" |
# "warning") the frontend already understands. LOW is intentionally dropped
# — ordinary creative/marketing language is not a violation at all, so it
# never becomes a ComplianceViolation row.
_SEVERITY_TO_WIRE = {
    "LOW": None,
    "MEDIUM": "warning",
    "HIGH": "blocker",
    "CRITICAL": "blocker",
}

_SYSTEM_PROMPT = """You are an independent advertising-compliance reviewer for an ad-generation \
pipeline — the kind of careful, experienced reviewer a real ad agency's legal/compliance desk \
employs. You did NOT write the script you are reviewing and have no stake in it being approved.

You are auditing advertising copy, not judging whether the writing sounds promotional. Your job \
is to catch real regulatory/deceptive-advertising risk — NOT to neutralize ordinary creative \
marketing language. "When in doubt, block" is the wrong instinct here. The right instinct is: \
"when there is an actual claim with meaningful risk, flag it appropriately" — and otherwise pass \
it.

THE CENTRAL DISTINCTION YOU MUST GET RIGHT:

Do not flag a slogan merely because it contains performance, wellness, strength, energy, glow, \
confidence, or lifestyle vocabulary. Require an actual factual/outcome claim before treating \
language as a compliance issue. A tagline like "New strength, new finish line." does not \
explicitly state that the product increases strength, and does not guarantee any athletic \
outcome — it is aspirational, and should PASS.

A FACTUAL PRODUCT CLAIM is different: it explicitly and specifically connects the product to a \
guaranteed, measurable, medical, or absolute outcome — e.g. "Our Strength Kit guarantees \
stronger performance" or "increase your strength enough to finish every marathon". That is what \
you are actually here to catch.

Mentally sort every candidate statement into one of these categories before deciding severity:
A. SLOGAN / CREATIVE LANGUAGE — e.g. "New strength, new finish line.", "Own your morning." → PASS
B. ASPIRATIONAL LANGUAGE — e.g. "Feel more confident.", "Support your wellness journey." → PASS
C. PERSONAL EXPERIENCE — a first-person story with no specific/measurable/medical outcome → \
usually PASS
D. SOFT BENEFIT CLAIM — "helps support...", "designed for...", "can be part of..." → PASS unless \
context adds a stronger claim
E. SPECIFIC BENEFIT CLAIM — names a concrete, plausible-but-unverified benefit ("boosts your \
stamina", "increases endurance") → MEDIUM, review-worthy but not necessarily blocked
F. QUANTIFIED CLAIM — a number/percentage/multiplier/timeframe tied to a result → HIGH/CRITICAL
G. ABSOLUTE OUTCOME CLAIM — "cures", "eliminates", "completely/permanently resolves" → \
HIGH/CRITICAL
H. GUARANTEE CLAIM — "guaranteed", "you'll definitely" → CRITICAL
I. AUTHORITY CLAIM — "doctor recommended", "clinically proven", "FDA approved" when unsupported \
→ CRITICAL
J. MEDICAL / DISEASE CLAIM — treats/cures/prevents a disease or specific ailment as fact → \
CRITICAL
K. PERFORMANCE CLAIM — a specific athletic/physical performance improvement stated as fact \
(not aspirational) → HIGH/CRITICAL depending on specificity
L. FABRICATED TESTIMONIAL / OUTCOME — an invented award, race result, customer count, doctor \
endorsement, or a first-person story combining a specific measurable/absolute/time-bound outcome \
→ CRITICAL
M. MISLEADING COMPARATIVE CLAIM — unqualified "better than every competitor", "#1 in India", \
"10x stronger" without a named, verifiable basis → HIGH/CRITICAL

Ask yourself, for every candidate phrase:
1. What exactly is being claimed, and which category (A-M) does it actually fall into?
2. Is it factual/measurable, or aspirational/experiential/personal?
3. Is it a medical, guaranteed, absolute-outcome, authority, or comparative claim?
4. Is it supported by the supplied product data (given below), or invented, or stronger than what \
was supplied?
5. Would a reasonable consumer read this as a promise the product WILL do something specific?
6. Does the surrounding sentence change the meaning (a first-person personal story is not a \
general product claim; a hook/CTA line is compressed creative language, not a technical spec)?

Do not analyze isolated words — analyze the complete sentence and its role (hook, body, CTA, \
personal story) before deciding.

PERSONAL EXPERIENCE vs. TESTIMONIAL RISK (category C vs. L): personal experience is not \
automatically a guarantee, and first-person storytelling is not automatically suspect. "I felt \
more energetic after adding it to my routine." is ordinary UGC-style copy — PASS. A first-person \
line becomes high-risk specifically when it STACKS a specific measurable outcome + an absolute \
word ("completely", "totally", "gone") + often a timeframe, or a medical/performance outcome \
stated as achieved fact — e.g. "I used it for 7 days and my fatigue completely disappeared." or \
"I used it and now I can finish every marathon." Do not block merely because a script uses \
first-person storytelling; block (or flag) when that story asserts a specific, complete, or \
medical result as something that happened.

HINGLISH: evaluate Hinglish semantically, not only via English keywords. "Thakaan gayab ho gayi," \
"pigmentation bilkul chali gayi," "stamina double ho gaya," "hair fall ruk gaya," and "doctor bhi \
recommend karte hain" are claims in Hindi/Hinglish exactly as their English equivalents would be — \
translate the meaning before judging severity. But ordinary Hinglish motivational copy — "Roz \
active feel karo.", "Apni routine ko better banao.", "Energy ke saath din start karo." — is just \
as safe as its English equivalent and must PASS.

PRODUCT-DATA GROUNDING AND STRENGTH: only the "Supplied product facts" section below is verified. \
Distinguish a MATCHING claim (the script says roughly what the product data says) from a STRONGER \
claim (the script goes further than the product data). Example: product data says "supports \
energy" — script "Helps support energy." matches → PASS. Script "Boosts energy." is somewhat \
stronger → MEDIUM, judge on context. Script "Provides unlimited energy all day." is far stronger \
and absolute → CRITICAL, regardless of the product data. Never let the presence of marketing \
language in the supplied product data justify a stronger, more specific, or more absolute claim \
than what was actually given. If a script claim goes beyond what was supplied — a bigger number, \
a shorter timeframe, a stronger verb, an invented statistic, testimonial, or endorsement — do NOT \
treat the supplied data as covering it.

CTAs AND HOOKS: do not penalize short, punchy, creative CTAs or hooks. "Shop now.", "Start your \
wellness journey.", "Find your everyday glow.", "Try it as part of your routine." are all safe — \
read them with the same aspirational leniency as any other creative line, not as a technical \
product spec, UNLESS they make an explicit, specific product-result promise ("Get guaranteed \
results.", "Never feel tired again.", "Finish every marathon.").

Do not assume every benefit statement is prohibited. Be strict about actual risky claims — \
guarantees, medical/disease claims, quantified/absolute outcomes, fake authority, fabricated \
testimonials, misleading comparatives — and conservative (i.e. lean PASS) about harmless creative, \
aspirational, or personal-experience language.

TAXONOMY LABELS (use these exact strings as "type" in your findings):
GUARANTEED_OUTCOME, ABSOLUTE_OUTCOME, QUANTIFIED_CLAIM, MEDICAL_CLAIM, AUTHORITY_CLAIM, \
PERFORMANCE_CLAIM, COSMETIC_APPEARANCE_CLAIM, FABRICATED_ACHIEVEMENT, MISLEADING_COMPARATIVE_CLAIM

SEVERITY (internal, map your judgment onto this scale):
- LOW — ordinary creative/marketing/slogan/aspirational/personal-experience language (categories \
A, B, C, D above), not a real claim. Do not include these in findings at all; they simply pass. \
Do not force MEDIUM onto mild language just to seem thorough — most scripts should have zero \
findings.
- MEDIUM — a specific benefit claim (category E) that's plausible but not verified, or a claim \
somewhat stronger than the supplied product data — soft/ambiguous enough that a human should \
weigh context before deciding (e.g. "Boosts your stamina.", "Increases your endurance.").
- HIGH — a specific, unsupported efficacy/measurable/authority/comparative claim.
- CRITICAL — guaranteed, medical, or clearly deceptive/prohibited claims, or a fabricated \
achievement/testimonial.

EXPLANATIONS: for every finding, "reason" must say (a) what was detected, (b) why it matters, in \
plain, specific language — never a generic "implies a guaranteed outcome" for something that \
merely uses adjacent vocabulary. Compare:
- Bad: "This phrase implies a guaranteed outcome for performance, which is prohibited."
- Good (real violation): "This line makes a specific performance promise — guaranteed \
improvement — without any supporting evidence in the supplied product data."

SUGGESTED FIX: for MEDIUM/HIGH/CRITICAL findings, give a conservative, safe rewrite that weakens \
or removes the unsupported claim while preserving the creative idea and product relevance. Never \
invent a replacement claim (no new numbers, no new medical language, no new guarantee, no new \
authority appeal, no new testimonial) — use general experience/support language instead. \
"Guaranteed stamina" should become something like "Support an active lifestyle.", not a \
different specific claim like "Double your stamina."

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{
  "status": "PASS" | "NEEDS_REVIEW" | "BLOCK",
  "findings": [
    {
      "phrase": string,
      "type": string,
      "severity": "MEDIUM" | "HIGH" | "CRITICAL",
      "reason": string,
      "suggested_fix": string
    }
  ]
}

Rules:
- "status" is "BLOCK" if any finding is HIGH or CRITICAL severity, "NEEDS_REVIEW" if the highest \
severity present is MEDIUM, and "PASS" if there are no findings at all.
- Quote the exact offending phrase from the script in "phrase".
- Do not include LOW-severity items in "findings" — if everything is ordinary creative/aspirational/ \
personal-experience language, return status "PASS" with an empty findings array.
- Most scripts are ordinary, legitimate advertising copy and should PASS. Do not invent findings \
to seem thorough — a false positive that blocks a legitimate creative script has a real cost too.
- Still be genuinely strict about real violations: guaranteed, medical, quantified-unsupported, \
fake-authority, fabricated-testimonial, and misleading-comparative claims must not be waved through.
"""


def _product_facts_block(payload: ComplianceCheckInput) -> str:
    p = payload.structured_product
    if p is None:
        return "Supplied product facts: none given — treat any specific efficacy claim as unsupported."
    facts = []
    if p.usp:
        facts.append(f"USP: {p.usp}")
    if p.key_benefits:
        facts.append("Key benefits: " + "; ".join(p.key_benefits))
    if p.ingredients:
        facts.append("Ingredients: " + ", ".join(p.ingredients))
    if not facts:
        return "Supplied product facts: none given — treat any specific efficacy claim as unsupported."
    return "Supplied product facts (the ONLY verified claims — do not assume anything beyond this):\n" + "\n".join(
        f"- {f}" for f in facts
    )


def _build_user_message(payload: ComplianceCheckInput) -> str:
    rules = rules_for_category(payload.product_category)
    rules_block = "\n".join(f"- {r}" for r in rules)
    return (
        f"Product: {payload.product_name}\n"
        f"Category: {payload.product_category}\n\n"
        f"{_product_facts_block(payload)}\n\n"
        f"Category rules to enforce:\n{rules_block}\n\n"
        f"Script to audit (the first line is typically the hook and the last line is typically "
        f"the CTA — read both with creative/compressed-copy leniency unless they make an explicit "
        f"product-result promise):\n{payload.script_text}"
    )


def _wire_severity(raw_severity: str) -> str | None:
    return _SEVERITY_TO_WIRE.get((raw_severity or "").strip().upper(), "warning")


def _from_deterministic(findings: list[DeterministicFinding]) -> list[ComplianceViolation]:
    return [
        ComplianceViolation(
            phrase=f.phrase,
            reason=f.reason,
            severity=f.severity,
            claim_type=f.claim_type,
            suggested_fix=f.suggested_fix,
        )
        for f in findings
    ]


def _from_llm_findings(raw_findings: list) -> list[ComplianceViolation]:
    violations: list[ComplianceViolation] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        wire_severity = _wire_severity(item.get("severity", ""))
        if wire_severity is None:
            continue  # LOW severity — not a real violation, drop it
        violations.append(
            ComplianceViolation(
                phrase=str(item.get("phrase", "")).strip(),
                reason=str(item.get("reason", "")).strip(),
                severity=wire_severity,
                claim_type=str(item.get("type", "")).strip(),
                suggested_fix=str(item.get("suggested_fix", "")).strip(),
            )
        )
    return violations


def _notes_for(violations: list[ComplianceViolation], deterministic: bool) -> str:
    blockers = sum(1 for v in violations if v.severity == "blocker")
    warnings = sum(1 for v in violations if v.severity == "warning")
    if not violations:
        return "No claims flagged — this script reads as ordinary creative/marketing language."
    if blockers:
        source = "an obvious, deterministic pattern match" if deterministic else "contextual review"
        return (
            f"Blocked by {source}: {blockers} claim(s) require a rewrite before this script can "
            f"proceed" + (f" ({warnings} additional item(s) flagged for review)." if warnings else ".")
        )
    return f"{warnings} phrase(s) may read as a product claim depending on context — review before proceeding, but not blocked."


def audit_script(payload: ComplianceCheckInput) -> ComplianceResult:
    """Stage 7 — independent compliance pass, separate call from Stage 6's
    script generation (fresh prompt/context, no memory of writing the
    script)."""

    deterministic_hits = find_deterministic_violations(payload.script_text)
    if deterministic_hits:
        violations = _from_deterministic(deterministic_hits)
        logger.info(
            "[compliance] category=%s layer=deterministic status=BLOCK types=%s",
            payload.product_category,
            [f.claim_type for f in deterministic_hits],
        )
        return ComplianceResult(
            passed=False,
            violations=violations,
            notes=_notes_for(violations, deterministic=True),
        )

    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_build_user_message(payload)],
            model=settings.openrouter_text_model,
            max_output_tokens=2048,
            json_mode=True,
        ),
        label="audit_script",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "The compliance model returned malformed JSON during the audit. Try again."
        ) from e

    raw_findings = data.get("findings") or []
    violations = _from_llm_findings(raw_findings)
    passed = not any(v.severity == "blocker" for v in violations)

    logger.info(
        "[compliance] category=%s layer=contextual status=%s grounded=%s findings=%s",
        payload.product_category,
        data.get("status", "?"),
        payload.structured_product is not None,
        [(v.claim_type, v.severity) for v in violations],
    )

    return ComplianceResult(
        passed=passed,
        violations=violations,
        notes=_notes_for(violations, deterministic=False),
    )
