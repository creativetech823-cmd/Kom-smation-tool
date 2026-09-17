"""Phase 2 reliability tests — response parsing, structured error
classification, retry behavior, the circuit breaker, and cost tracking on
failed calls. Root cause under test: an HTTP-200 response with empty
message.content used to raise an unclassified RuntimeError that was never
retried (misclassified as non-transient) and never even reached by
_generate_with_recovery's own except clause. No live network calls."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import openrouter_utils as oru


def _fake_response(status=200, json_body=None, raise_json_error=False):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status.return_value = None
    if raise_json_error:
        resp.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
    else:
        resp.json.return_value = json_body or {}
    return resp


def _fake_client(response):
    client = MagicMock()
    client.post.return_value = response
    return client


@pytest.fixture(autouse=True)
def reset_circuit_state():
    oru.stop_usage_tracking()
    yield
    oru.stop_usage_tracking()


# --- Response parsing: every scenario from Phase 2 §2/§3 --------------------


def test_normal_successful_response_returns_text():
    resp = _fake_response(json_body={"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        text = oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10, label="test")
    assert text == "hello"


def test_empty_content_raises_empty_response_error():
    resp = _fake_response(json_body={"choices": [{"message": {"content": ""}, "finish_reason": "stop"}], "usage": {"completion_tokens": 50, "prompt_tokens": 10}})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.EmptyResponseError) as exc_info:
            oru.generate_text(system_instruction="s", contents=["c"], model="google/gemini-2.5-pro", max_output_tokens=10, label="final_script_write")
    assert exc_info.value.retryable is True
    assert exc_info.value.diagnostics["model"] == "google/gemini-2.5-pro"
    assert exc_info.value.diagnostics["completion_tokens"] == 50


def test_missing_content_key_with_present_message_raises_empty_response_error():
    resp = _fake_response(json_body={"choices": [{"message": {"role": "assistant"}, "finish_reason": "stop"}]})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.EmptyResponseError):
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)


def test_empty_message_object_raises_malformed_response_error():
    """Distinct from a present-but-empty content: the message object itself
    missing/empty is a structural problem, not merely an empty answer."""
    resp = _fake_response(json_body={"choices": [{"message": {}, "finish_reason": "stop"}]})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.MalformedResponseError):
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)


def test_missing_choices_raises_malformed_response_error():
    resp = _fake_response(json_body={"choices": []})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.MalformedResponseError) as exc_info:
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)
    assert exc_info.value.retryable is True


def test_missing_message_raises_malformed_response_error():
    resp = _fake_response(json_body={"choices": [{}]})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.MalformedResponseError):
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)


def test_malformed_json_body_raises_malformed_response_error():
    resp = _fake_response(raise_json_error=True)
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.MalformedResponseError):
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)


def test_content_filter_finish_reason_raises_content_filter_error_not_retryable():
    resp = _fake_response(json_body={"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]})
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.ContentFilterError) as exc_info:
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)
    assert exc_info.value.retryable is False


def test_http_5xx_still_raises_via_httpx_status_error():
    """The existing status-code path (unchanged) must still work for real
    HTTP-level failures — these never reach _extract_text at all."""
    resp = MagicMock()
    resp.status_code = 503
    resp.raise_for_status.side_effect = httpx.HTTPStatusError("boom", request=MagicMock(), response=resp)
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(httpx.HTTPStatusError):
            oru.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)


# --- Usage/cost tracking on failed calls -------------------------------------


def test_usage_is_recorded_even_when_content_is_empty():
    """The exact observed live shape: real completion_tokens billed, but no
    usable content — cost tracking must NOT report this as free."""
    oru.start_usage_tracking()
    resp = _fake_response(json_body={
        "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 1200, "total_tokens": 1700, "cost": 0.015},
    })
    with patch.object(oru, "get_openrouter_client", return_value=_fake_client(resp)):
        with pytest.raises(oru.EmptyResponseError):
            oru.generate_text(system_instruction="s", contents=["c"], model="google/gemini-2.5-pro", max_output_tokens=10, label="final_script_write")
    summary = oru.get_usage_summary()
    oru.stop_usage_tracking()
    assert summary["by_stage"]["final_script_write"]["input_tokens"] == 500
    assert summary["estimated_total_cost_usd"] == 0.015


# --- Retry behavior: retryable vs not, using the new typed errors -----------


def test_call_openrouter_with_retry_retries_empty_response_error():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise oru.EmptyResponseError("empty", diagnostics={"model": "m"})
        return "ok"

    with patch.object(oru, "time") as mock_time:
        result = oru.call_openrouter_with_retry(flaky, label="test_stage", max_attempts=4)
    assert result == "ok"
    assert attempts["n"] == 2  # retried once, then succeeded


def test_call_openrouter_with_retry_does_not_retry_content_filter_error():
    attempts = {"n": 0}

    def always_filtered():
        attempts["n"] += 1
        raise oru.ContentFilterError("filtered", diagnostics={"model": "m"})

    with pytest.raises(ValueError):
        oru.call_openrouter_with_retry(always_filtered, label="test_stage", max_attempts=4)
    assert attempts["n"] == 1  # not retryable — gave up after the first attempt


# --- Circuit breaker: credit protection --------------------------------------


def test_circuit_breaker_stops_retrying_after_threshold_within_one_generation():
    oru.start_usage_tracking()
    attempts = {"n": 0}

    def always_empty():
        attempts["n"] += 1
        raise oru.EmptyResponseError("empty", diagnostics={"model": "google/gemini-2.5-pro"})

    with patch.object(oru, "time"):
        with pytest.raises(ValueError):
            oru.call_openrouter_with_retry(always_empty, label="final_script_write", max_attempts=10)
    oru.stop_usage_tracking()
    # Threshold is 3 — must stop well short of the configured max_attempts=10.
    assert attempts["n"] <= oru._CIRCUIT_BREAKER_THRESHOLD


def test_circuit_breaker_persists_across_separate_call_invocations_in_same_generation():
    """The breaker is scoped to one generation (one usage-tracking context),
    not one call_openrouter_with_retry invocation — a second, independent
    call for the SAME stage+model must inherit the accumulated failure
    count, exactly the cross-call compounding risk Phase 2 needed to bound."""
    oru.start_usage_tracking()

    def always_empty():
        raise oru.EmptyResponseError("empty", diagnostics={"model": "google/gemini-2.5-pro"})

    with patch.object(oru, "time"):
        with pytest.raises(ValueError):
            oru.call_openrouter_with_retry(always_empty, label="final_script_write", max_attempts=3)
        # A second, separate invocation for the same (stage, model) — the
        # circuit should already be open, so this gives up almost immediately.
        attempts = {"n": 0}

        def counting_empty():
            attempts["n"] += 1
            raise oru.EmptyResponseError("empty", diagnostics={"model": "google/gemini-2.5-pro"})

        with pytest.raises(ValueError):
            oru.call_openrouter_with_retry(counting_empty, label="final_script_write", max_attempts=10)
    oru.stop_usage_tracking()
    assert attempts["n"] == 1  # breaker already open — only one attempt before giving up


def test_circuit_breaker_resets_on_success():
    oru.start_usage_tracking()
    attempts = {"n": 0}

    def fails_twice_then_succeeds():
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise oru.EmptyResponseError("empty", diagnostics={"model": "google/gemini-2.5-pro"})
        return "ok"

    with patch.object(oru, "time"):
        result = oru.call_openrouter_with_retry(fails_twice_then_succeeds, label="final_script_write", max_attempts=5)
    assert result == "ok"
    assert oru._circuit_is_open("final_script_write", "google/gemini-2.5-pro") is False
    oru.stop_usage_tracking()


def test_circuit_breaker_is_a_noop_without_active_tracking_context():
    oru.stop_usage_tracking()  # no context active
    attempts = {"n": 0}

    def always_empty():
        attempts["n"] += 1
        raise oru.EmptyResponseError("empty", diagnostics={"model": "google/gemini-2.5-pro"})

    with patch.object(oru, "time"):
        with pytest.raises(ValueError):
            oru.call_openrouter_with_retry(always_empty, label="final_script_write", max_attempts=4)
    assert attempts["n"] == 4  # full budget used — breaker never engages outside a tracked context


# --- classify_error surfaces useful, specific reasons ------------------------


def test_classify_error_names_finish_reason_for_empty_response():
    err = oru.EmptyResponseError("x", diagnostics={"finish_reason": "length", "model": "google/gemini-2.5-pro"})
    reason = oru.classify_error(err)
    assert "length" in reason
    assert "google/gemini-2.5-pro" in reason
