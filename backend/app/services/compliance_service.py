import json

from anthropic import Anthropic

from app.config import settings
from app.models.product import ComplianceCheckInput, ComplianceResult
from app.services.claude_utils import extract_json_text
from app.services.compliance_rules import rules_for_category

_client = Anthropic(api_key=settings.anthropic_api_key)

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
    """Stage 7 — independent compliance pass, separate model from Stage 6."""

    response = _client.messages.create(
        model=settings.claude_compliance_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload)}],
        # Extended thinking is on by default and its tokens count against
        # max_tokens — disabled so JSON generation gets the full budget.
        extra_body={"thinking": {"type": "disabled"}},
    )

    data = json.loads(extract_json_text(response.content))
    return ComplianceResult(**data)
