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
  "industry": string,
  "pain_points": [string],
  "marketing_angle": string,
  "key_emotions": [string],
  "keywords": [string],
  "missing_fields": [string],
  "confidence": number between 0 and 1
}

Field notes:
- "industry": a short, specific industry/category label this product actually belongs to
  (e.g. "Sports Nutrition", "Herbal Beverages"), inferred from the product name/description —
  not a generic label like "Consumer Goods" unless nothing more specific is determinable.
- "pain_points": problems or frustrations this product's audience plausibly has that the product
  addresses, grounded in the input (not invented use-cases the input never implies).
- "marketing_angle": the single strongest strategic angle this product should sell on, in a
  few words (e.g. "transformation", "expert authority", "everyday convenience").
- "key_emotions": 2-4 emotions this product's marketing should evoke, grounded in its real
  benefits/USP (e.g. a stress-relief tea implies "calm", "relief" — not invented feelings).
- "keywords": short searchable phrases someone might use to describe or search for this product.

Rules:
- "missing_fields" lists which of ingredients/usp/tone/key_benefits/industry/pain_points/
  marketing_angle/key_emotions/keywords could not be determined from the input (empty list if
  everything was determinable).
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
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload, raw_text)}],
        # Extended thinking is on by default and its tokens count against
        # max_tokens — disabled so JSON generation gets the full budget.
        extra_body={"thinking": {"type": "disabled"}},
    )

    try:
        data = json.loads(extract_json_text(response.content))
    except json.JSONDecodeError as e:
        raise ValueError(
            "Claude returned malformed JSON while structuring the product — the response may "
            "have been truncated. Try again, or shorten the product description."
        ) from e

    return StructuredProduct(
        product_name=payload.product_name,
        target_audience=payload.target_audience,
        ingredients=data.get("ingredients", []),
        usp=data.get("usp", ""),
        tone=data.get("tone", ""),
        key_benefits=data.get("key_benefits", []),
        industry=data.get("industry", ""),
        pain_points=data.get("pain_points", []),
        marketing_angle=data.get("marketing_angle", ""),
        key_emotions=data.get("key_emotions", []),
        keywords=data.get("keywords", []),
        missing_fields=data.get("missing_fields", []),
        confidence=data.get("confidence", 0.0),
    )
