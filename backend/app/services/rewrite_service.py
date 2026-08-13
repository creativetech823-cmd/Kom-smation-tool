from anthropic import Anthropic

from app.config import settings
from app.models.product import RewriteDirective, RewriteLineInput, RewriteLineResult

_client = Anthropic(api_key=settings.anthropic_api_key)

_DIRECTIVE_GUIDANCE: dict[RewriteDirective, str] = {
    RewriteDirective.improve: "Tighten and sharpen this line — better rhythm, clearer meaning, "
    "no wasted words. Keep the same intent and claims, just make it read better.",
    RewriteDirective.make_viral: "Rewrite this line to be more scroll-stopping and shareable — "
    "punchier, more surprising, more likely to make someone stop scrolling. Keep it truthful "
    "to the original meaning, don't add claims that weren't there.",
    RewriteDirective.make_emotional: "Rewrite this line to hit harder emotionally — lean into "
    "the feeling underneath it (relief, pride, hope, worry, etc.) without becoming melodramatic "
    "or adding claims that weren't in the original.",
    RewriteDirective.increase_conversion: "Rewrite this line to be more persuasive and "
    "action-driving, as if written by a direct-response copywriter — sharper benefit framing, "
    "more urgency where appropriate. Do not add guarantees or claims the original didn't make.",
    RewriteDirective.rewrite: "Write a fresh alternative take on this line — same core idea and "
    "intent, different words and phrasing than the original.",
}

_SYSTEM_PROMPT = """You are a script-line editor for a short-form video ad content factory.
You rewrite exactly ONE line of dialogue/on-screen text at a time, according to a given
directive. You MUST preserve the line's original meaning, claims, and any product facts it
contains — you are a rewrite pass, not a new-claim generator, and this feeds a
compliance-sensitive pipeline. Never introduce a claim, statistic, or promise that wasn't
already in the original line.

If a maximum character count is given, the rewritten line must fit within it.

Return ONLY the rewritten line of text — no prose, no quotes, no markdown, no explanation."""


def _build_user_message(payload: RewriteLineInput) -> str:
    guidance = _DIRECTIVE_GUIDANCE[payload.directive]
    char_limit = f"\nMax characters: {payload.max_chars}" if payload.max_chars else ""
    return f"Directive: {guidance}\n\nOriginal line:\n{payload.text}{char_limit}"


def rewrite_line(payload: RewriteLineInput) -> RewriteLineResult:
    """AI quick-action — rewrite one script line's text per a directive, nothing else."""

    response = _client.messages.create(
        model=settings.claude_compliance_model,
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(payload)}],
        # Extended thinking is on by default and its tokens count against
        # max_tokens — disabled so tiny-budget calls don't get starved.
        extra_body={"thinking": {"type": "disabled"}},
    )

    text_block = next(b for b in response.content if b.type == "text")
    rewritten = text_block.text.strip().strip('"')
    return RewriteLineResult(text=rewritten)
