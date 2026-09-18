import base64
import contextvars
import json
import logging
import time
from typing import Callable, TypeVar

import httpx

from app.config import settings

logger = logging.getLogger("openrouter_utils")
usage_logger = logging.getLogger("llm_usage")
diagnostics_logger = logging.getLogger("llm_diagnostics")

_BASE_URL = "https://openrouter.ai/api/v1"


# --- Structured error types --------------------------------------------------
# Phase 2: replaces "everything is a bare RuntimeError/ValueError string" with
# typed, diagnosable failures. Each carries `.retryable` (used by
# call_openrouter_with_retry instead of re-guessing from the message text)
# and `.diagnostics` (a small, secret-free dict — never the prompt or a key —
# logged alongside every failure so the NEXT occurrence is diagnosable rather
# than guessed at, per the exact root cause found in Phase 2: an HTTP-200
# response with real completion_tokens but empty message.content was being
# raised as a bare RuntimeError, misclassified as non-transient (it matched
# none of the string-based transient checks), and then never even reached by
# script_service._generate_with_recovery's own except clause — so the
# "existing retry+repair mechanism" was never actually exercised for this
# failure shape at all.
class OpenRouterError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class EmptyResponseError(OpenRouterError):
    """HTTP success, but message.content is empty/missing. Often a transient
    provider-side hiccup (observed live: real completion_tokens billed with
    no visible content returned) — retryable."""
    retryable = True


class MalformedResponseError(OpenRouterError):
    """HTTP success, but the response body doesn't match the expected shape
    (no choices, no message, or the body itself isn't valid JSON) —
    retryable, same transient-glitch profile as EmptyResponseError."""
    retryable = True


class ProviderError(OpenRouterError):
    """The response carries an explicit provider/model-side error field, or
    an HTTP 5xx not otherwise a recognized timeout — retryable."""
    retryable = True


class ContentFilterError(OpenRouterError):
    """finish_reason indicates content was filtered. Retrying the identical
    request is very unlikely to produce a different outcome — NOT retryable
    by default (a caller may still choose to alter the request and try
    again, but blind retry here just burns credits for the same result)."""
    retryable = False


class RateLimitError(OpenRouterError):
    retryable = True


class RequestTimeoutError(OpenRouterError):
    retryable = True


class AuthenticationError(OpenRouterError):
    retryable = False


class ModelUnavailableError(OpenRouterError):
    """The specific model is temporarily unavailable/overloaded (e.g. a 503
    naming the model) — retryable, a different attempt may route to healthy
    capacity."""
    retryable = True

# Best-effort, approximate USD-per-1M-token pricing for COST OBSERVABILITY
# only — this is NOT authoritative billing data, is not fetched live, and may
# be stale. Used only to estimate a rough order-of-magnitude cost per call
# when OpenRouter itself doesn't report one; every value computed from this
# table is labeled "estimated" wherever it's surfaced. A model missing here
# simply skips cost estimation rather than guessing.
_APPROX_PRICE_PER_1M_USD: dict[str, tuple[float, float]] = {
    "google/gemini-2.5-flash": (0.30, 2.50),
    "google/gemini-2.5-pro": (1.25, 10.00),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "google/gemini-2.5-flash-image": (0.30, 2.50),
    # GPT-5.6 Luna cost-experiment (2026-09-18 task) — pricing per
    # https://openrouter.ai/openai/gpt-5.6-luna-20260709, given directly by
    # the task, not fetched live. Only used when OpenRouter itself doesn't
    # report usage.cost on the response (see _record_usage below).
    "openai/gpt-5.6-luna": (0.20, 1.20),
}

# --- Credit-protection circuit breaker ---------------------------------------
# Section 16: "same stage, same model, repeated transient failure -> stop
# retrying" — scoped to the SAME usage-tracking context as cost observability
# (one script generation), not a global/cross-request breaker, so one
# product's bad luck can never suppress retries for an unrelated concurrent
# request. Reset whenever start_usage_tracking() starts a fresh context.
_CIRCUIT_BREAKER_THRESHOLD = 3  # consecutive transient response-shape failures for the same (stage, model)
_failure_counts_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("openrouter_failure_counts_ctx", default=None)


def _circuit_key(stage: str, model: str) -> str:
    return f"{stage or 'unlabeled'}::{model}"


def _record_transient_failure(stage: str, model: str) -> int:
    counts = _failure_counts_ctx.get()
    if counts is None:
        return 0  # no tracked context active — breaker is a no-op outside a tracked generation
    key = _circuit_key(stage, model)
    counts[key] = counts.get(key, 0) + 1
    return counts[key]


def _circuit_is_open(stage: str, model: str) -> bool:
    counts = _failure_counts_ctx.get()
    if counts is None:
        return False
    return counts.get(_circuit_key(stage, model), 0) >= _CIRCUIT_BREAKER_THRESHOLD


def _reset_circuit(stage: str, model: str) -> None:
    counts = _failure_counts_ctx.get()
    if counts is not None:
        counts.pop(_circuit_key(stage, model), None)


# A per-request-context accumulator for the "pipeline cost summary" feature —
# uses a contextvar (not a module-level list) so concurrent requests never
# mix each other's usage records. Off by default (None): _record_usage() is a
# no-op unless something has called start_usage_tracking() first, so normal
# calls outside a tracked pipeline run pay zero extra cost.
_usage_ctx: contextvars.ContextVar[list | None] = contextvars.ContextVar("openrouter_usage_ctx", default=None)


def start_usage_tracking() -> None:
    """Begins accumulating per-call usage records for get_usage_summary() to
    read later in this same logical request/task, and resets the circuit-
    breaker's failure counts for this same context. Safe to call repeatedly —
    each call starts fresh."""
    _usage_ctx.set([])
    _failure_counts_ctx.set({})


def stop_usage_tracking() -> None:
    _usage_ctx.set(None)
    _failure_counts_ctx.set(None)


def get_usage_summary() -> dict:
    """Aggregates whatever usage records were captured since the last
    start_usage_tracking() call in this context. Never raises; returns a
    zeroed summary if tracking was never started or nothing was recorded."""
    records = _usage_ctx.get() or []
    by_stage: dict[str, dict] = {}
    total_input = total_output = total_tokens = 0
    total_cost = 0.0
    any_cost_known = False
    for r in records:
        stage = r["stage"]
        entry = by_stage.setdefault(stage, {"model": r["model"], "input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0})
        entry["calls"] += 1
        entry["input_tokens"] += r["input_tokens"] or 0
        entry["output_tokens"] += r["output_tokens"] or 0
        total_input += r["input_tokens"] or 0
        total_output += r["output_tokens"] or 0
        total_tokens += r["total_tokens"] or 0
        if r["cost_usd"] is not None:
            entry["cost_usd"] += r["cost_usd"]
            total_cost += r["cost_usd"]
            any_cost_known = True
    return {
        "by_stage": by_stage,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "estimated_total_cost_usd": round(total_cost, 6) if any_cost_known else None,
        "call_count": len(records),
    }


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = _APPROX_PRICE_PER_1M_USD.get(model)
    if not prices:
        return None
    price_in, price_out = prices
    return round((input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out, 6)


def _record_usage(stage: str, model: str, response_json: dict) -> None:
    """Logs a structured usage line (stage/model/tokens/cost — never a
    prompt, header, or key) and, if a pipeline usage-tracking context is
    active, appends the same record for get_usage_summary(). Never raises —
    a malformed/missing usage block just means nothing to report."""
    try:
        usage = response_json.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        if input_tokens is None and output_tokens is None:
            return  # OpenRouter didn't return a usage block for this call
        reported_cost = usage.get("cost")
        if reported_cost is not None:
            cost_usd, cost_source = float(reported_cost), "openrouter_reported"
        else:
            cost_usd = _estimate_cost_usd(model, input_tokens or 0, output_tokens or 0)
            cost_source = "estimated" if cost_usd is not None else "unavailable"
        usage_logger.info(
            "stage=%s model=%s input_tokens=%s output_tokens=%s total_tokens=%s cost_usd=%s cost_source=%s",
            stage or "unlabeled", model, input_tokens, output_tokens, total_tokens, cost_usd, cost_source,
        )
        records = _usage_ctx.get()
        if records is not None:
            records.append({
                "stage": stage or "unlabeled", "model": model, "input_tokens": input_tokens,
                "output_tokens": output_tokens, "total_tokens": total_tokens, "cost_usd": cost_usd,
            })
    except Exception as e:
        logger.debug("Usage recording failed (non-fatal): %s", e)

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
    if isinstance(e, OpenRouterError):
        d = e.diagnostics
        if isinstance(e, EmptyResponseError):
            return f"OpenRouter returned no usable text (finish_reason={d.get('finish_reason')}, model={d.get('model')})."
        if isinstance(e, ContentFilterError):
            return f"OpenRouter filtered the response content (model={d.get('model')})."
        if isinstance(e, MalformedResponseError):
            return f"OpenRouter's response didn't match the expected shape (model={d.get('model')})."
        return str(e)
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


def _diagnostics_summary(response_json: dict, *, http_status: int, model: str, stage: str) -> dict:
    """A small, secret-free structural summary of a response — never the
    prompt, never a key, never the full response body — safe to log and to
    attach to a raised error for the next occurrence to be diagnosable
    instead of guessed at."""
    choices = response_json.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    content = message.get("content")
    usage = response_json.get("usage") or {}
    return {
        "stage": stage or "unlabeled",
        "model": model,
        "http_status": http_status,
        "choices": len(choices),
        "message_present": bool(message),
        "content_present": content is not None,
        "content_length": len(content) if isinstance(content, str) else 0,
        "finish_reason": choice.get("finish_reason"),
        "usage_present": bool(usage),
        "completion_tokens": usage.get("completion_tokens"),
        "provider": response_json.get("provider") or usage.get("provider"),
        "error_present": bool(response_json.get("error")),
    }


def _log_diagnostics(diagnostics: dict) -> None:
    diagnostics_logger.warning(
        "llm_response_issue stage=%s model=%s http_status=%s choices=%s message_present=%s "
        "content_present=%s content_length=%s finish_reason=%s usage_present=%s "
        "completion_tokens=%s provider=%s error_present=%s",
        diagnostics.get("stage"), diagnostics.get("model"), diagnostics.get("http_status"),
        diagnostics.get("choices"), diagnostics.get("message_present"), diagnostics.get("content_present"),
        diagnostics.get("content_length"), diagnostics.get("finish_reason"), diagnostics.get("usage_present"),
        diagnostics.get("completion_tokens"), diagnostics.get("provider"), diagnostics.get("error_present"),
    )


def _extract_text(response_json: dict, *, diagnostics: dict) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        _log_diagnostics(diagnostics)
        raise MalformedResponseError("OpenRouter returned no choices.", diagnostics=diagnostics)
    message = choices[0].get("message") or {}
    if not message:
        _log_diagnostics(diagnostics)
        raise MalformedResponseError("OpenRouter returned a choice with no message.", diagnostics=diagnostics)
    content = message.get("content")
    finish_reason = choices[0].get("finish_reason")
    if not content:
        _log_diagnostics(diagnostics)
        if finish_reason == "content_filter":
            raise ContentFilterError(
                f"OpenRouter filtered the content (finish_reason={finish_reason}).", diagnostics=diagnostics,
            )
        raise EmptyResponseError(
            f"OpenRouter returned HTTP 200 with no usable text (finish_reason={finish_reason}).",
            diagnostics=diagnostics,
        )
    return content


def generate_text(
    system_instruction: str,
    contents: list,
    *,
    model: str,
    max_output_tokens: int,
    json_mode: bool = False,
    temperature: float | None = None,
    label: str = "",
    reasoning_effort: str | None = "__default__",
    timeout: float | None = None,
) -> str:
    """A single OpenRouter chat-completion call — system prompt + content in,
    plain text or raw JSON text out. `contents` may mix plain strings with
    `image_part(...)` dicts for vision calls. `label` (e.g. "creative_insight",
    "final_script_write") identifies the pipeline stage purely for the usage/
    cost observability log and diagnostics — it's never sent to OpenRouter.

    reasoning_effort (GPT-5.6 Luna cost experiment, 2026-09-18 task, Part 13):
    OpenRouter's unified `reasoning.effort` field ("high"/"medium"/"low"),
    forwarded as-is to whichever reasoning-capable model is configured — a
    no-op for a model that doesn't support it. The sentinel default
    "__default__" (not None) means "use settings.openrouter_reasoning_effort"
    so every one of this pipeline's ~35 call sites gets a sensible default
    automatically without each one needing to pass it explicitly (avoiding
    "unrelated changes" across every service module); passing reasoning_effort
    explicitly (including None, to omit the field entirely) still overrides
    the default per-call. Never "maximum reasoning on every call" by
    default — settings.openrouter_reasoning_effort defaults to "medium".

    timeout (Story Ideas budget-overshoot fix, 2026-09-18 task): per-call
    override of the shared client's 120s default (httpx supports this on a
    per-request basis without touching the client itself). None (the
    default, every existing call site) means "use the client's 120s" —
    completely unaffected. Only story_situation_service.py's pool-generation
    call and semantic_story_judge_service.py's judge call pass an explicit,
    shorter value, since together they're the two sequential LLM calls
    inside one Story Ideas "attempt" that must collectively fit inside the
    ~90s aggregate budget — every other pipeline stage's timeout is
    deliberately untouched, per the explicit "don't globally reduce it"
    instruction."""
    body: dict = {
        "model": model,
        "messages": _build_messages(system_instruction, contents),
        "max_tokens": max_output_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if temperature is not None:
        body["temperature"] = temperature
    effort = settings.openrouter_reasoning_effort if reasoning_effort == "__default__" else reasoning_effort
    if effort:
        body["reasoning"] = {"effort": effort}

    # Dev visibility (2026-09-18 task, Part 15) — one line per call, logged
    # BEFORE the request so it's visible even if the call fails; never logs
    # the key, the prompt, or any request/response body content.
    logger.info("[LLM] provider=openrouter model=%s stage=%s", model, label or "unlabeled")
    request_kwargs = {"json": body}
    if timeout is not None:
        request_kwargs["timeout"] = timeout
    response = get_openrouter_client().post("/chat/completions", **request_kwargs)
    response.raise_for_status()
    try:
        response_json = response.json()
    except json.JSONDecodeError as e:
        diagnostics = {"stage": label or "unlabeled", "model": model, "http_status": response.status_code, "error_present": True}
        _log_diagnostics(diagnostics)
        raise MalformedResponseError(f"OpenRouter's response body wasn't valid JSON: {e}", diagnostics=diagnostics) from e
    # Usage is recorded even when extraction below fails — a failed call can
    # still have billed real tokens (the exact observed shape: real
    # completion_tokens with empty content), and cost tracking must reflect
    # that rather than silently reporting it as free.
    _record_usage(label, model, response_json)
    diagnostics = _diagnostics_summary(response_json, http_status=response.status_code, model=model, stage=label)
    return _extract_text(response_json, diagnostics=diagnostics)


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
    """Retries transient failures (quota/server/timeout/closed-client/empty-
    or-malformed-response) with backoff before giving up — the standard
    wrapper for every OpenRouter call.

    Retry classification: a typed OpenRouterError (EmptyResponseError,
    MalformedResponseError, ProviderError, RateLimitError, ModelUnavailableError
    -> retryable; ContentFilterError, AuthenticationError -> not) uses its own
    `.retryable` flag directly, fixing the exact Phase 2 root cause — an empty-
    content HTTP-200 response used to raise a bare, unclassified RuntimeError
    that matched none of the string-based transient checks below and so was
    never retried at all, despite max_attempts=4. Anything else (httpx errors,
    generic exceptions) falls back to the original status-code/message
    heuristic, unchanged.

    Circuit breaker (credit protection, Phase 2 §16): when a typed error's
    diagnostics name a model, consecutive transient failures for that exact
    (label, model) pair are counted in the active usage-tracking context
    (see start_usage_tracking). Past _CIRCUIT_BREAKER_THRESHOLD, this stops
    retrying immediately rather than exhausting the full attempt budget —
    scoped to one generation, never a cross-request global breaker. A
    success resets the count for that pair."""
    last_error: Exception | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        try:
            result = fn()
            circuit_model = getattr(last_error, "diagnostics", {}).get("model") if last_error is not None else None
            if circuit_model:
                _reset_circuit(label, circuit_model)
            return result
        except Exception as e:
            last_error = e
            retryable_flag = getattr(e, "retryable", None)
            if retryable_flag is not None:
                transient = retryable_flag
            else:
                code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
                message = str(e).lower()
                client_closed = "client has been closed" in message
                # Bug found and fixed while verifying Story Ideas timeout
                # behavior (2026-09-18 task): httpx's OWN timeout exceptions
                # (ReadTimeout/ConnectTimeout/WriteTimeout/PoolTimeout) say
                # "timed out", not "timeout" — the string literal below never
                # matched them, so a genuine per-call timeout was silently
                # classified as non-transient and got ZERO retries, contrary
                # to this function's documented intent ("Retries transient
                # failures (quota/server/timeout/...)"). Checking the actual
                # exception class (httpx.TimeoutException, the real base
                # class for all four) is correct regardless of message
                # wording — the "timeout" substring check is kept only as a
                # defensive fallback for any other exception type that
                # happens to describe itself that way.
                is_httpx_timeout = isinstance(e, httpx.TimeoutException)
                transient = code in (429, 500, 502, 503) or is_httpx_timeout or "timeout" in message or client_closed
            circuit_model = getattr(e, "diagnostics", {}).get("model") if isinstance(e, OpenRouterError) else None
            breaker_tripped = False
            if transient and circuit_model:
                failure_count = _record_transient_failure(label, circuit_model)
                breaker_tripped = _circuit_is_open(label, circuit_model)
                if breaker_tripped:
                    logger.warning(
                        "[%s] circuit breaker open for model=%s after %d consecutive transient failures — stopping retries",
                        label, circuit_model, failure_count,
                    )
            logger.warning("[%s] attempt=%d/%d failed transient=%s error=%s", label, attempt, max_attempts, transient, e)
            if not transient or breaker_tripped or attempt == max_attempts:
                break
            if "client has been closed" in str(e).lower():
                reset_openrouter_client()
            time.sleep(min(2**attempt, 10))

    reason = classify_error(last_error)
    if attempt > 1:
        reason = f"Retry failed after {attempt} attempts. {reason}"
    logger.error("[%s] All attempts failed. Final reason: %s", label, reason)
    raise ValueError(reason)
