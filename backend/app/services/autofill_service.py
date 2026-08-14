import json

from app.config import settings
from app.models.product import AutoFillInput, AutoFillSuggestion
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_SYSTEM_PROMPT = """You extract a first-draft product profile from raw scraped/extracted content
(a fetched webpage, an uploaded document, etc.) BEFORE the user has entered anything about the
product manually. This is a draft the user will review and edit, not a final answer.

Return ONLY valid JSON matching this exact shape, no prose, no markdown fences:
{
  "product_name": string,
  "target_audience": string,
  "source_description": string,
  "product_category": string,
  "brand": string,
  "keywords": [string],
  "key_benefits": [string],
  "confidence": number between 0 and 1
}

Field notes:
- "source_description": a clean 2-4 sentence product description distilled from the raw input,
  suitable to prefill a description textarea.
- "product_category": a short category label (e.g. "beverages", "skincare", "sports nutrition").
- "target_audience": your best inference of who this product is for, in a short phrase.

Rules:
- Do not invent facts that aren't present or reasonably implied in the input.
- Leave a field as an empty string / empty list when it isn't determinable rather than guessing.
- "confidence" reflects how much of the profile came from solid input vs. guesswork.
"""


def suggest_product_fields(payload: AutoFillInput) -> AutoFillSuggestion:
    """Pre-Stage-1 — a lightweight Gemini call that guesses editable form
    fields from raw extracted text, run before product_name/target_audience
    exist (structure_product requires those, so it can't do this job)."""

    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            # Kept well under large-request capacity tiers — big payloads
            # (50K+ chars) were consistently hitting sustained overload
            # errors during demand spikes that smaller requests sailed
            # through, even with retries.
            contents=[payload.raw_text[:20_000]],
            model=settings.gemini_text_model,
            max_output_tokens=1536,
            json_mode=True,
        ),
        label="suggest_product_fields",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            "Gemini returned malformed JSON while suggesting product fields — try again."
        ) from e

    return AutoFillSuggestion(
        product_name=data.get("product_name", ""),
        target_audience=data.get("target_audience", ""),
        source_description=data.get("source_description", ""),
        product_category=data.get("product_category", ""),
        brand=data.get("brand", ""),
        keywords=data.get("keywords", []),
        key_benefits=data.get("key_benefits", []),
        confidence=data.get("confidence", 0.0),
    )
