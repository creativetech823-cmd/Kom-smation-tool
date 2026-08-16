import json
import uuid

from typing import Optional

from app.config import settings
from app.models.product import (
    GeneratedScript,
    ScriptSuggestionCategory,
    SmartScriptSuggestionsResult,
    StructuredProduct,
)
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

_VALID_CATEGORIES = {c.value for c in ScriptSuggestionCategory}
_CATEGORY_FALLBACK = ScriptSuggestionCategory.clarity.value

_SYSTEM_PROMPT = """You are a professional short-form video ad script editor — the kind a serious
D2C brand hires to punch up a script before it ships — reviewing a finished script line by line.
You evaluate against these lenses: does the hook create real curiosity in the first 2 seconds
(HOOK)? does the opening line earn a continue-watching decision (OPENING_LINE)? does the viewer
feel something (EMOTIONAL_IMPACT)? is every line easy to instantly follow (CLARITY)? does each line
lead logically into the next (FLOW)? is the story concrete and human, not generic (STORYTELLING)?
does the product feel naturally woven in rather than bolted on (PRODUCT_INTEGRATION)? does the
close create a clear, memorable action (CTA)? is anything said twice without adding value
(REPETITION)? does the length match the target duration (LENGTH)? does it sound like natural
spoken Hinglish/Hindi/English rather than written or translated (NATURAL_HINGLISH)? is the brand
name mentioned naturally at least once, if not already (BRAND_MENTION)? does it speak in the
target audience's real voice (AUDIENCE_RELEVANCE)? would a real viewer actually share or rewatch
this (VIRALITY).

Find the 3-6 highest-value, most concrete improvements — never generic advice like "make it
better." Every suggestion must be GROUNDED in the actual script given below: quote the real current
line and write out the exact improved replacement line, not a description of what to change. Keep
the replacement in the same language/register as the original line (see script language below) —
never translate it into a different language, and never invent a claim, statistic, or promise that
wasn't already there.

For product/brand-mention suggestions, pick the single best existing line to naturally weave the
mention into (immediately after the problem is introduced is usually strongest) and write the full
replacement line with the mention added — do not just describe where it could go. Write out the
LITERAL product/brand name given below directly in "suggested_text" — never a bracketed placeholder
like "[brand]" or "[product name]", and never a different/invented name. If no product info is
given below, do not fabricate a brand name and do not use a placeholder either; skip
brand_mention/product_integration suggestions entirely in that case.

Each suggestion targets exactly ONE existing line by its id (hook, body_0, body_1, ..., or cta) —
pick the single most representative line even for a script-wide issue like repetition or pacing
(e.g. for repetition, target the specific line that repeats an idea already said elsewhere and
rewrite it to stop repeating). Only when a fix genuinely cannot be expressed as one line's
before/after (e.g. the whole script badly overshoots the target duration) should you instead leave
current_text/suggested_text null and set suggested_scope to one of: full, hook, cta, science,
story, product_explanation, emotional_tone, length, plus a short "instruction" describing the fix
— use this fallback sparingly, it triggers a full AI regeneration pass instead of an instant fix.

Also set:
- "status": "strong" if the script is already in good shape (few or no real problems — a handful of
  optional polish ideas is fine even when status is "strong"), otherwise "needs_work".
- "headline": one short sentence for the panel's top banner — e.g. "Found 3 opportunities to
  improve." when needs_work, or "Your script is ready to go." when strong and cards is empty, or a
  status like "Script looks strong — a few optional polish ideas below." when strong but you still
  have optional_ideas.
- "optional_ideas": 2-4 short (under 10 words) optional next-step phrases ONLY when status is
  "strong" (e.g. "Try a stronger first 2 seconds", "Make the product mention more natural", "Add a
  stronger emotional payoff", "Make the CTA more memorable") — empty list when status is
  "needs_work" (the cards already cover it).

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{"status": "strong"|"needs_work", "headline": string, "cards": [{"category": string, "title": string, "why": string, "line_id": string|null, "current_text": string|null, "suggested_text": string|null, "suggested_scope": string|null, "instruction": string|null}], "optional_ideas": [string]}

"category" must be one of: hook, opening_line, emotional_impact, clarity, flow, storytelling,
product_integration, cta, repetition, length, natural_hinglish, brand_mention, audience_relevance,
virality."""


def _flatten(script: GeneratedScript) -> list[dict]:
    lines = [{"id": "hook", "role": "hook", **script.hook.model_dump()}]
    lines += [{"id": f"body_{i}", "role": "body", **line.model_dump()} for i, line in enumerate(script.body)]
    lines.append({"id": "cta", "role": "cta", **script.cta.model_dump()})
    return lines


def _build_user_message(script: GeneratedScript, target_duration: str, product: Optional[StructuredProduct]) -> str:
    lines = _flatten(script)
    lines_block = "\n".join(f"- id={l['id']} section={l.get('section')}: {l['text']}" for l in lines)
    words = sum(len(l["text"].split()) for l in lines)
    product_block = (
        f"Product / brand name: {product.product_name}\n"
        f"USP: {product.usp or 'unknown'}\n"
        f"Key benefits: {', '.join(product.key_benefits) or 'unknown'}\n"
        f"Target audience: {product.target_audience}\n"
        if product
        else "Product info: not provided — do not invent a brand/product name.\n"
    )
    return (
        f"{product_block}"
        f"Script language (write every suggested_text in this exact register): {script.script_language.value}\n"
        f"Target duration: {target_duration or script.target_duration or 'unspecified'}\n"
        f"Current estimated word count: {words}\n"
        f"Creative angle: {script.creative_angle or 'none specified'}\n\n"
        f"Script lines:\n{lines_block}"
    )


def suggest_script_improvements(
    script: GeneratedScript, target_duration: str, structured_product: Optional[StructuredProduct] = None
) -> SmartScriptSuggestionsResult:
    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_build_user_message(script, target_duration, structured_product)],
            model=settings.openrouter_text_model,
            max_output_tokens=6144,
            json_mode=True,
        ),
        label="suggest_script_improvements",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("The AI returned malformed JSON while generating suggestions.") from e

    valid_line_ids = {l["id"] for l in _flatten(script)}
    valid_scopes = {"full", "hook", "cta", "science", "story", "product_explanation", "emotional_tone", "length"}

    cards = []
    for item in data.get("cards", []):
        line_id = item.get("line_id")
        if line_id not in valid_line_ids:
            line_id = None
        suggested_scope = item.get("suggested_scope")
        if suggested_scope not in valid_scopes:
            suggested_scope = None
        # A card with neither a real line to patch nor a fallback scope can't
        # actually be applied — drop it rather than showing a dead "Apply".
        if line_id is None and suggested_scope is None:
            continue
        category = item.get("category")
        if category not in _VALID_CATEGORIES:
            category = _CATEGORY_FALLBACK
        cards.append(
            {
                **item,
                "id": uuid.uuid4().hex[:10],
                "category": category,
                "line_id": line_id,
                "suggested_scope": suggested_scope,
            }
        )

    return SmartScriptSuggestionsResult(
        status=data.get("status") or "needs_work",
        headline=data.get("headline") or "",
        cards=cards,
        optional_ideas=data.get("optional_ideas") or [],
    )
