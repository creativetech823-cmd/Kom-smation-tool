import logging
import time
from typing import Callable, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import settings

logger = logging.getLogger("gemini_utils")

# google-genai's Client validates that the API key is non-empty at
# CONSTRUCTION time (unlike the old Anthropic client), so it can't be built
# eagerly at module import — the app must still start before a key is
# configured. Built lazily on first real use instead; a single client is
# shared across every Gemini-calling service in the app.
_gemini_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key or "missing-api-key")
    return _gemini_client


def reset_gemini_client() -> None:
    """Discards the cached client so the next call builds a fresh one — used
    when the underlying httpx connection was torn down out from under us
    (e.g. a platform restart mid-request), which raises 'client has been
    closed' rather than a normal API error."""
    global _gemini_client
    _gemini_client = None


def classify_error(e: Exception | None) -> str:
    """A short, specific, user-displayable reason — never a generic 'Network
    Error' unless the failure is genuinely a connection-level problem."""
    if e is None:
        return "Unknown error — no attempts were made."
    if not settings.gemini_api_key:
        return "API key missing — no GEMINI_API_KEY configured on the backend."
    if isinstance(e, genai_errors.APIError):
        code = getattr(e, "code", None)
        message = getattr(e, "message", None) or str(e)
        if code == 429:
            return f"Gemini quota exceeded. {message}"[:300]
        if code in (401, 403):
            return f"API key invalid or lacks permission. {message}"[:300]
        if code == 400:
            return f"Invalid request to Gemini: {message}"[:300]
        if code and code >= 500:
            return f"Gemini service error (HTTP {code}): {message}"[:300]
        return f"Gemini returned HTTP {code}: {message}"[:300]
    name = type(e).__name__
    msg = str(e)
    if "timeout" in name.lower() or "timeout" in msg.lower():
        return "Gemini timeout — the request took too long. Try again."
    if any(term in name for term in ("Connect", "DNS", "Network", "Socket")):
        return f"Network error reaching Gemini: {msg[:200]}"
    return f"Invalid response from Gemini ({name}): {msg[:200]}"


def _extract_text(response: genai_types.GenerateContentResponse) -> str:
    """Concatenates the non-thought text parts from the first candidate.
    `response.text` (the SDK's convenience property) can return None even
    when real text exists, if the response was cut short by MAX_TOKENS while
    some of the budget was spent on internal 'thought' parts — so parts are
    read directly instead of relying on it."""
    candidates = response.candidates or []
    if not candidates:
        raise RuntimeError("Invalid response — Gemini returned no candidates.")
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) if content else None
    texts = [p.text for p in (parts or []) if getattr(p, "text", None) and not getattr(p, "thought", False)]
    if not texts:
        raise RuntimeError("Invalid response — Gemini didn't return any text.")
    return "".join(texts)


def generate_text(
    system_instruction: str,
    contents: list,
    *,
    model: str,
    max_output_tokens: int,
    json_mode: bool = False,
    disable_thinking: bool = True,
    temperature: float | None = None,
) -> str:
    """A single Gemini text-generation call — system prompt + content in,
    plain text or raw JSON text out. `contents` may mix plain strings with
    `genai_types.Part.from_bytes(...)` for vision calls. Some models (e.g.
    gemini-pro-latest) can't run with thinking disabled at all — pass
    `disable_thinking=False` for those."""
    config_kwargs: dict = dict(
        system_instruction=system_instruction,
        max_output_tokens=max_output_tokens,
    )
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    if disable_thinking:
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)

    response = get_gemini_client().models.generate_content(
        model=model, contents=contents, config=genai_types.GenerateContentConfig(**config_kwargs)
    )
    return _extract_text(response)


T = TypeVar("T")


def call_gemini_with_retry(fn: Callable[[], T], *, label: str = "gemini", max_attempts: int = 4) -> T:
    """Retries transient failures (quota/server/timeout/closed-client) with
    backoff before giving up — the standard wrapper for every Gemini text
    call in the app."""
    last_error: Exception | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            code = getattr(e, "code", None)
            message = str(e).lower()
            client_closed = "client has been closed" in message
            transient = code in (429, 500, 502, 503) or "timeout" in message or client_closed
            logger.warning("[%s] attempt=%d/%d failed transient=%s error=%s", label, attempt, max_attempts, transient, e)
            if not transient or attempt == max_attempts:
                break
            if client_closed:
                reset_gemini_client()
            time.sleep(min(2**attempt, 10))

    reason = classify_error(last_error)
    if attempt > 1:
        reason = f"Retry failed after {attempt} attempts. {reason}"
    logger.error("[%s] All attempts failed. Final reason: %s", label, reason)
    raise ValueError(reason)
