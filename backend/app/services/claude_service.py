import json

from anthropic import Anthropic

from app.config import settings
from app.models.product import ProductInput, StructuredProduct
from app.services.claude_utils import extract_json_text

_client = Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM_PROMPT = """You are a product-data structuring engine for an ad-generation pipeline.
You will receive raw product information (scraped website text, a free-typed description, or
manually entered fields) plus a product name and target audience.

Your job: extract a clean, structured product profile. Do not invent facts that are not present
or reasonably implied in the input — this feeds a compliance-sensitive ad pipeline, so
hallucinated ingredients or claims are unacceptable.

Return ONLY valid JSON matching this exact shape, no prose, no markdown fences:
{
  "ingredients": [string],
  "usp": string,
  "tone": string,
  "key_benefits": [string],
  "missing_fields": [string],
  "confidence": number between 0 and 1
}

Rules:
- "missing_fields" lists which of ingredients/usp/tone/key_benefits could not be determined
  from the input (empty list if everything was determinable).
- "confidence" reflects how much of the profile came from solid input vs. guesswork.
- If the raw input is empty or near-empty, return low confidence and populate missing_fields
  accordingly rather than fabricating content.
"""


def _build_user_message(payload: ProductInput, raw_text: str) -> str:
    return (
        f"Product name: {payload.product_name}\n"
        f"Target audience: {payload.target_audience}\n"
        f"Manual ingredients (if provided): {payload.manual_ingredients or 'none'}\n"
        f"Manual USP (if provided): {payload.manual_usp or 'none'}\n\n"
        f"Raw input:\n{raw_text or '(no additional raw input provided)'}"
    )


def structure_product(payload: ProductInput, raw_text: str = "") -> StructuredProduct:
    """Stage 3 — turn raw input into a StructuredProduct via Claude."""

    response = _client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload, raw_text)}],
    )

    data = json.loads(extract_json_text(response.content))

    return StructuredProduct(
        product_name=payload.product_name,
        target_audience=payload.target_audience,
        ingredients=data.get("ingredients", []),
        usp=data.get("usp", ""),
        tone=data.get("tone", ""),
        key_benefits=data.get("key_benefits", []),
        missing_fields=data.get("missing_fields", []),
        confidence=data.get("confidence", 0.0),
    )
