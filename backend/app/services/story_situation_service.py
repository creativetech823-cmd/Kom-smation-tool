import json
import uuid

from anthropic import Anthropic

from app.config import settings
from app.models.product import StorySituation, StorySituationsInput, StorySituationsResult
from app.services.claude_utils import extract_json_text
from app.services.creative_angles import catalog_prompt_block, valid_angle_labels

_client = Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM_PROMPT = """You are an award-winning creative director at an advertising agency, running an
ideation session — NOT writing a script. Your job is to propose distinct marketing angles ("story
situations") for a product: each one names a person, a problem or context, and an emotional arc
that could become a short-form video ad. A story situation is a premise, never dialogue or scenes.

You must work for ANY industry (FMCG, healthcare, finance, education, SaaS, e-commerce, automotive,
real estate, etc.) — never fall back on a fixed list of personas or categories. Infer the personas,
emotional categories, and marketing angles that make sense for THIS specific product, audience, and
category from the data you're given. Reason about who actually buys/uses/is affected by this product,
what they fear or hope for, and what conflicts or transformations are believable for them.

Maximize diversity across the full set of situations you return. No two situations may share the same
persona archetype, hook angle, emotional core, conflict, or resolution. Vary across multiple thematic
categories in the same batch (for example: emotional/relational stories, inspirational/transformation
stories, educational/expert-authority stories, social/peer-context stories, everyday-lifestyle stories)
— but choose category labels that fit this product rather than reusing a fixed taxonomy.

For each situation produce:
- "title": a punchy 3-7 word title
- "description": 1-3 sentences establishing the person, their situation, and the emotional stakes
- "emotion": the core emotion driving it (e.g. "fear", "pride", "relief", "hope")
- "persona": the protagonist/target character (e.g. "first-time gym-goer", "worried father")
- "marketing_angle": the strategic angle this story sells on (e.g. "myth vs reality", "transformation", "expert authority")
- "category": a short thematic label you choose for this situation (e.g. "Emotional", "Educational")
- "difficulty": "easy", "medium", or "hard" — how complex this would be to actually produce (cast, locations, VFX)
- "estimated_length": a realistic short-form runtime, one of "15s", "30s", "60s"
- "virality_score": a number 0.0-10.0 with one decimal place, your honest calibrated estimate of shareability —
  spread your scores realistically across the batch, do not cluster everything above 9

If a list of already-shown titles is provided, none of your new situations may repeat those titles or
be near-duplicates of their premise — treat them as creatively off-limits.

For every situation, also pick "recommended_angles": 5-8 CREATIVE ANGLES (execution styles — HOW the
story is filmed/told, not the marketing_angle, which is WHY it sells) that genuinely fit THIS
situation's persona, conflict, and production complexity. Choose only from this vocabulary, copying
labels exactly as written — do not invent new ones or reword them:

{angle_catalog}

Pick angles that are actually distinct fits for this specific situation, not a generic default set —
e.g. a father-son story genuinely suits "Father-Son", "Emotional Conversation", or "Meta Glasses POV"
(a father's first-person view), while a factory-workers-quit-together story suits "Social Experiment /
Challenge" or "Documentary" far more than "Doctor Testimonial".

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{{
  "situations": [
    {{
      "title": string,
      "description": string,
      "emotion": string,
      "persona": string,
      "marketing_angle": string,
      "category": string,
      "difficulty": string,
      "estimated_length": string,
      "virality_score": number,
      "recommended_angles": [string]
    }}
  ]
}}
""".format(angle_catalog=catalog_prompt_block())


def _build_user_message(payload: StorySituationsInput) -> str:
    p = payload.structured_product
    exclude_block = (
        "\n".join(f"- {t}" for t in payload.exclude_titles) if payload.exclude_titles else "(none yet)"
    )

    return (
        f"Product: {p.product_name}\n"
        f"Target audience: {p.target_audience}\n"
        f"Product category: {payload.product_category}\n"
        f"Ingredients: {', '.join(p.ingredients) or 'unknown'}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Tone: {p.tone or 'unspecified'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n\n"
        f"Generate exactly {payload.count} story situations.\n\n"
        f"Titles already shown to the user (do not repeat or near-duplicate these):\n{exclude_block}"
    )


def generate_situations(payload: StorySituationsInput) -> StorySituationsResult:
    """Stage 3.5 — structured product -> diverse story-situation options for the user to pick from."""

    response = _client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload)}],
        # Extended thinking is on by default and its tokens count against
        # max_tokens — disabled so JSON generation gets the full budget.
        extra_body={"thinking": {"type": "disabled"}},
    )

    try:
        data = json.loads(extract_json_text(response.content))
    except json.JSONDecodeError as e:
        raise ValueError(
            "Claude returned malformed JSON while generating story ideas — the response may have "
            "been truncated. Try again, or ask for fewer situations."
        ) from e

    situations = []
    for item in data.get("situations", []):
        item = {**item, "recommended_angles": valid_angle_labels(item.get("recommended_angles", []))}
        situations.append(StorySituation(id=uuid.uuid4().hex[:12], **item))
    return StorySituationsResult(situations=situations)
