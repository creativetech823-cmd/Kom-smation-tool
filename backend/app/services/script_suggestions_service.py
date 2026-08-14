import json

from app.config import settings
from app.models.product import GeneratedScript, ScriptSuggestionsResult
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_SYSTEM_PROMPT = """You are a script doctor reviewing a finished short-form video ad script. Give 3-6
concrete, high-value suggestions for improving it — weak hooks, weak CTAs, an overlong or repetitive
line, pacing issues, a line that doesn't fit the target duration. Be specific and actionable, not
generic ("this could be better"). Reference a real line id from the script when a suggestion targets
one specific line; leave line_id/section null for whole-script suggestions (e.g. overall pacing or
duration).

"suggested_scope" must be one of: full, hook, cta, science, story, product_explanation,
emotional_tone, length — whichever best matches what the suggestion is asking to fix (or null if
none fits). "section" must be one of: hook, problem, science, story, product_intro, ingredients,
benefits, objection_handling, cta (or null).

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{"suggestions": [{"line_id": string|null, "section": string|null, "message": string, "action_label": string, "suggested_scope": string|null}]}"""


def _flatten(script: GeneratedScript) -> list[dict]:
    lines = [{"id": "hook", "role": "hook", **script.hook.model_dump()}]
    lines += [{"id": f"body_{i}", "role": "body", **line.model_dump()} for i, line in enumerate(script.body)]
    lines.append({"id": "cta", "role": "cta", **script.cta.model_dump()})
    return lines


def _build_user_message(script: GeneratedScript, target_duration: str) -> str:
    lines = _flatten(script)
    lines_block = "\n".join(f"- id={l['id']} section={l.get('section')}: {l['text']}" for l in lines)
    words = sum(len(l["text"].split()) for l in lines)
    return (
        f"Target duration: {target_duration}\n"
        f"Current estimated word count: {words}\n\n"
        f"Script lines:\n{lines_block}"
    )


def suggest_script_improvements(script: GeneratedScript, target_duration: str) -> ScriptSuggestionsResult:
    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_build_user_message(script, target_duration)],
            model=settings.gemini_text_model,
            max_output_tokens=1536,
            json_mode=True,
        ),
        label="suggest_script_improvements",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("Gemini returned malformed JSON while generating suggestions.") from e

    return ScriptSuggestionsResult(**data)
