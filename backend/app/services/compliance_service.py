import json

from app.config import settings
from app.models.product import ComplianceCheckInput, ComplianceResult
from app.services.compliance_rules import rules_for_category
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_SYSTEM_PROMPT = """You are an independent compliance auditor for an ad-generation pipeline.
You did NOT write the script you are reviewing — you have no stake in it being approved.
Your only job is to flag anything that violates the category rules given to you.

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{
  "passed": boolean,
  "violations": [
    {"phrase": string, "reason": string, "severity": "blocker" | "warning"}
  ],
  "notes": string
}

Rules:
- "passed" is false if there is at least one "blocker" severity violation.
- "warning" severity is for borderline phrasing that should be reviewed by a human but
  doesn't outright violate a rule.
- Quote the exact offending phrase from the script in "phrase".
- If nothing is wrong, return passed=true with an empty violations array.
- Be strict — this is the last automated gate before a human review step, and the cost
  of a false negative (missing a real violation) is much higher than a false positive.
"""


def _build_user_message(payload: ComplianceCheckInput) -> str:
    rules = rules_for_category(payload.product_category)
    rules_block = "\n".join(f"- {r}" for r in rules)
    return (
        f"Product: {payload.product_name}\n"
        f"Category: {payload.product_category}\n\n"
        f"Category rules to enforce:\n{rules_block}\n\n"
        f"Script to audit:\n{payload.script_text}"
    )


def audit_script(payload: ComplianceCheckInput) -> ComplianceResult:
    """Stage 7 — independent compliance pass, separate model from Stage 6.
    Uses gemini_compliance_model (a stronger model that can't run with
    thinking disabled) rather than the fast/cheap model used everywhere
    else — preserving the original "independent second opinion" design
    intent, not just a different provider."""

    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_build_user_message(payload)],
            model=settings.gemini_compliance_model,
            max_output_tokens=2048,
            json_mode=True,
            disable_thinking=False,
        ),
        label="audit_script",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "Gemini returned malformed JSON during the compliance audit. Try again."
        ) from e
    return ComplianceResult(**data)
