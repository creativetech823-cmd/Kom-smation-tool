import json

from app.config import settings
from app.models.product import GenerateAlternativesResult, RewriteLineInput
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_SYSTEM_PROMPT = """You are a script-line editor for a short-form video ad content factory.
Given ONE line of dialogue/on-screen text, write 5 genuinely distinct alternative versions of it —
different angles, phrasing, or rhythm, not near-duplicates of each other. You MUST preserve the
line's original meaning, claims, and any product facts it contains — never introduce a claim,
statistic, or promise that wasn't already in the original line. If a maximum character count is
given, every alternative must fit within it.

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{"alternatives": [string, string, string, string, string]}"""


def _build_user_message(payload: RewriteLineInput) -> str:
    char_limit = f"\nMax characters: {payload.max_chars}" if payload.max_chars else ""
    return f"Original line:\n{payload.text}{char_limit}"


def generate_alternatives(payload: RewriteLineInput) -> GenerateAlternativesResult:
    """AI quick-action — 5 distinct rewrites of one script line, for the user to pick from."""

    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=_SYSTEM_PROMPT,
            contents=[_build_user_message(payload)],
            model=settings.gemini_text_model,
            max_output_tokens=1536,
            json_mode=True,
        ),
        label="generate_alternatives",
    )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("Gemini returned malformed JSON while generating alternatives.") from e

    return GenerateAlternativesResult(**data)
