import json

from anthropic import Anthropic

from app.config import settings
from app.models.product import GeneratedScript, ScriptSuggestionsResult
from app.services.claude_utils import extract_json_text

_client = Anthropic(api_key=settings.anthropic_api_key)

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
    response = _client.messages.create(
        model=settings.claude_compliance_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(script, target_duration)}],
        extra_body={"thinking": {"type": "disabled"}},
    )

    try:
        data = json.loads(extract_json_text(response.content))
    except json.JSONDecodeError as e:
        raise ValueError("Claude returned malformed JSON while generating suggestions.") from e

    return ScriptSuggestionsResult(**data)
