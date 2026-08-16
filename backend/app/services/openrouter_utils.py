import base64
import logging
import time
from typing import Callable, TypeVar

import httpx

from app.config import settings

logger = logging.getLogger("openrouter_utils")

_BASE_URL = "https://openrouter.ai/api/v1"

# A single shared client, built lazily on first real use (mirrors
# gemini_utils.get_gemini_client) so the app can still start before a key
# is configured.
_client: httpx.Client | None = None


def get_openrouter_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key or 'missing-api-key'}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
    return _client


def reset_openrouter_client() -> None:
    """Discards the cached client so the next call builds a fresh one —
    used when the underlying connection was torn down out from under us."""
    global _client
    if _client is not None:
        _client.close()
    _client = None


def classify_error(e: Exception | None) -> str:
    """A short, specific, user-displayable reason — never a generic 'Network
    Error' unless the failure is genuinely a connection-level problem."""
    if e is None:
        return "Unknown error — no attempts were made."
    if not settings.openrouter_api_key:
        return "API key missing — no OPENROUTER_API_KEY configured on the backend."
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        try:
            message = e.response.json().get("error", {}).get("message") or e.response.text
        except Exception:
            message = e.response.text
        if code == 429:
            return f"OpenRouter quota/rate limit exceeded. {message}"[:300]
        if code in (401, 403):
            return f"API key invalid or lacks permission. {message}"[:300]
        if code == 400:
            return f"Invalid request to OpenRouter: {message}"[:300]
        if code >= 500:
            return f"OpenRouter service error (HTTP {code}): {message}"[:300]
        return f"OpenRouter returned HTTP {code}: {message}"[:300]
    name = type(e).__name__
    msg = str(e)
    if "timeout" in name.lower() or "timeout" in msg.lower():
        return "OpenRouter timeout — the request took too long. Try again."
    if any(term in name for term in ("Connect", "DNS", "Network", "Socket")):
        return f"Network error reaching OpenRouter: {msg[:200]}"
    return f"Invalid response from OpenRouter ({name}): {msg[:200]}"


def image_part(data: bytes, mime_type: str = "image/png") -> dict:
    """Builds an OpenAI/OpenRouter-style image content part from raw bytes —
    the OpenRouter equivalent of genai_types.Part.from_bytes(...), for vision
    calls (e.g. scoring a rendered image, picking the best stock asset)."""
    b64 = base64.b64encode(data).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}


def _build_messages(system_instruction: str, contents: list) -> list[dict]:
    user_content = [{"type": "text", "text": item} if isinstance(item, str) else item for item in contents]
    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]


def _extract_text(response_json: dict) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        raise RuntimeError("Invalid response — OpenRouter returned no choices.")
    text = (choices[0].get("message") or {}).get("content")
    if not text:
        raise RuntimeError("Invalid response — OpenRouter didn't return any text.")
    return text


def generate_text(
    system_instruction: str,
    contents: list,
    *,
    model: str,
    max_output_tokens: int,
    json_mode: bool = False,
    temperature: float | None = None,
) -> str:
    """A single OpenRouter chat-completion call — system prompt + content in,
    plain text or raw JSON text out. `contents` may mix plain strings with
    `image_part(...)` dicts for vision calls."""
    body: dict = {
        "model": model,
        "messages": _build_messages(system_instruction, contents),
        "max_tokens": max_output_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if temperature is not None:
        body["temperature"] = temperature

    response = get_openrouter_client().post("/chat/completions", json=body)
    response.raise_for_status()
    return _extract_text(response.json())


def generate_image(
    prompt: str,
    *,
    model: str,
    reference_images: list[bytes] | None = None,
    seed: int | None = None,
) -> bytes:
    """A single OpenRouter image-generation call (text-to-image, or
    image-conditioned edit when `reference_images` is given). Only works with
    OpenRouter models that support image output modalities — not all do."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for img in reference_images or []:
        content.append(image_part(img))

    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }
    if seed is not None:
        # Forwarded to the underlying provider best-effort — not every
        # OpenRouter-routed image model honors an explicit seed.
        body["seed"] = seed
    response = get_openrouter_client().post("/chat/completions", json=body)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Invalid response — OpenRouter returned no choices.")
    images = (choices[0].get("message") or {}).get("images") or []
    if not images:
        raise RuntimeError("Invalid response — OpenRouter didn't return an image.")
    url = (images[0].get("image_url") or {}).get("url", "")
    if not url.startswith("data:"):
        raise RuntimeError("Invalid response — OpenRouter returned a non-data image URL.")
    b64_payload = url.split(",", 1)[1]
    return base64.b64decode(b64_payload)


T = TypeVar("T")


def call_openrouter_with_retry(fn: Callable[[], T], *, label: str = "openrouter", max_attempts: int = 4) -> T:
    """Retries transient failures (quota/server/timeout/closed-client) with
    backoff before giving up — the standard wrapper for every OpenRouter call."""
    last_error: Exception | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
            message = str(e).lower()
            client_closed = "client has been closed" in message
            transient = code in (429, 500, 502, 503) or "timeout" in message or client_closed
            logger.warning("[%s] attempt=%d/%d failed transient=%s error=%s", label, attempt, max_attempts, transient, e)
            if not transient or attempt == max_attempts:
                break
            if client_closed:
                reset_openrouter_client()
            time.sleep(min(2**attempt, 10))

    reason = classify_error(last_error)
    if attempt > 1:
        reason = f"Retry failed after {attempt} attempts. {reason}"
    logger.error("[%s] All attempts failed. Final reason: %s", label, reason)
    raise ValueError(reason)
