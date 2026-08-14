import time
from typing import Callable, TypeVar

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OverloadedError,
    RateLimitError,
)

_TRANSIENT_ANTHROPIC_ERRORS = (
    OverloadedError,
    RateLimitError,
    InternalServerError,
    APIConnectionError,
    APITimeoutError,
)

T = TypeVar("T")


def call_claude_with_retry(fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    """Retry a Claude call through transient overload/rate-limit/connection
    errors with backoff. The Anthropic SDK already retries a couple of times
    internally with a short backoff, but that's not always enough during a
    sustained overload spike (HTTP 529) — this adds a few more attempts with
    longer backoff before giving up with a clean, user-facing message."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except _TRANSIENT_ANTHROPIC_ERRORS as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(min(2**attempt, 10))
    raise ValueError(
        f"Claude is currently overloaded and didn't respond after {max_attempts} attempts — please try again in a moment."
    ) from last_error


def extract_json_text(content_blocks) -> str:
    """Pull the text block out of a Claude response (skipping thinking blocks)
    and strip markdown code fences if the model wrapped its JSON in one."""

    text_block = next(b for b in content_blocks if b.type == "text")
    raw = text_block.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw
