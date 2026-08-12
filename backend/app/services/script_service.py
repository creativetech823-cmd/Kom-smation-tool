import json

from anthropic import Anthropic

from app.config import settings
from app.models.product import GeneratedScript, ScriptGenerationInput
from app.services.claude_utils import extract_json_text
from app.services.compliance_rules import rules_for_category

_client = Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM_PROMPT = """You are a short-form video ad director for a content factory pipeline. You do NOT
invent the creative — you are given ONE specific, already-chosen story situation (a persona, a
conflict, an emotional arc) and your job is to write the complete cinematic script that brings that
exact situation to life. Stay faithful to the given persona, emotion, and marketing angle throughout.

Structure: a Hook that opens directly on the situation's conflict/tension, then 2-5 sequential Scenes
(the "body") that escalate and resolve it, then a CTA that lands the situation's marketing angle.
Choose the number of scenes to fit the given estimated length (roughly one scene per 8-12 seconds).

For every single line (hook, each scene, and the CTA) produce:
- "text": the spoken/on-screen line, under the given character limit (for on-screen subtitle fit)
- "visual_tags": concrete, literal visual search tags — phrases that would actually return relevant
  results on a stock photo/video site like Pexels or Pixabay. Abstract or poetic phrasing is useless;
  tags must describe a literal, photographable scene or object (e.g. "green cardamom pods closeup",
  "worried father looking at phone", not "a wave of realization"). 1-3 tags per line.
- "scene_label": "Hook", "Scene 1", "Scene 2", ... or "CTA"
- "visual_direction": a director's note on blocking/action/framing for this line — richer prose than
  visual_tags, describing what happens on screen (e.g. "Father sits at the kitchen table, phone face
  down, staring at it for a long beat before picking it up"). Keep visual_tags and visual_direction
  distinct: visual_tags are literal stock-search phrases, visual_direction is cinematic direction.
- "camera_angle": a concrete shot type (e.g. "close-up", "over-the-shoulder", "wide establishing shot")
- "emotion": the emotional beat of this specific line

Also produce one top-level "bgm_suggestion": a short direction for background music (mood/genre/tempo)
that fits the situation's emotional arc across the whole ad.

You MUST NOT make claims outside the approved category rules given to you — you are the first of two
guardrail passes, so be conservative. If ingredient/USP data is missing, write generically rather than
inventing specifics.

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{
  "hook": {"text": string, "visual_tags": [string], "scene_label": string, "visual_direction": string, "camera_angle": string, "emotion": string},
  "body": [{"text": string, "visual_tags": [string], "scene_label": string, "visual_direction": string, "camera_angle": string, "emotion": string}],
  "cta": {"text": string, "visual_tags": [string], "scene_label": string, "visual_direction": string, "camera_angle": string, "emotion": string},
  "bgm_suggestion": string
}
"""


def _build_user_message(payload: ScriptGenerationInput) -> str:
    p = payload.structured_product
    s = payload.selected_situation
    rules = rules_for_category(payload.product_category)
    rules_block = "\n".join(f"- {r}" for r in rules)

    winners_block = (
        "\n".join(f"- {w}" for w in payload.similar_past_winners)
        if payload.similar_past_winners
        else "(none available yet)"
    )

    return (
        f"Chosen story situation (the creative brief — bring THIS to life):\n"
        f"Title: {s.title}\n"
        f"Description: {s.description}\n"
        f"Emotion: {s.emotion}\n"
        f"Persona: {s.persona}\n"
        f"Marketing angle: {s.marketing_angle}\n"
        f"Category: {s.category}\n"
        f"Estimated length: {s.estimated_length}\n\n"
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
    """Stage 6 — chosen story situation -> full cinematic script + visual search tags."""

    response = _client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=2560,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload)}],
    )

    data = json.loads(extract_json_text(response.content))
    return GeneratedScript(**data, situation=payload.selected_situation)
