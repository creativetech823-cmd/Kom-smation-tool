import json

from anthropic import Anthropic

from app.config import settings
from app.models.product import GeneratedScript, ScriptGenerationInput
from app.services.claude_utils import extract_json_text
from app.services.compliance_rules import rules_for_category

_client = Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM_PROMPT = """You are a short-form video ad scriptwriter for a content factory pipeline.
You write hook/body/CTA scripts and, for every single line, you also produce concrete,
literal visual search tags — phrases that would actually return relevant results on a stock
photo/video site like Pexels or Pixabay. Abstract or poetic phrasing in visual_tags is useless;
tags must describe a literal, photographable scene or object (e.g. "green cardamom pods
closeup", "woman drinking tea morning sunlight", not "a burst of freshness").

You MUST NOT make claims outside the approved category rules given to you — you are the
first of two guardrail passes, so be conservative. If ingredient/USP data is missing, write
generically rather than inventing specifics.

Keep every line under the given character limit (for on-screen subtitle fit).

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{
  "hook": {"text": string, "visual_tags": [string]},
  "body": [{"text": string, "visual_tags": [string]}],
  "cta": {"text": string, "visual_tags": [string]}
}

Body should have 2-4 lines. Each line's visual_tags should have 1-3 tags.
"""


def _build_user_message(payload: ScriptGenerationInput) -> str:
    p = payload.structured_product
    rules = rules_for_category(payload.product_category)
    rules_block = "\n".join(f"- {r}" for r in rules)

    winners_block = (
        "\n".join(f"- {w}" for w in payload.similar_past_winners)
        if payload.similar_past_winners
        else "(none available yet)"
    )

    return (
        f"Platform: {payload.platform}\n"
        f"Max characters per line: {payload.max_line_chars}\n\n"
        f"Product: {p.product_name}\n"
        f"Target audience: {p.target_audience}\n"
        f"Ingredients: {', '.join(p.ingredients) or 'unknown'}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Tone: {p.tone or 'unspecified'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n\n"
        f"Category compliance rules (do not violate these):\n{rules_block}\n\n"
        f"Similar past-winning scripts for reference (style/structure inspiration only, "
        f"do not copy claims):\n{winners_block}"
    )


def generate_script(payload: ScriptGenerationInput) -> GeneratedScript:
    """Stage 6 — structured product -> hook/body/CTA + visual search tags."""

    response = _client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=1536,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload)}],
    )

    data = json.loads(extract_json_text(response.content))
    return GeneratedScript(**data)
