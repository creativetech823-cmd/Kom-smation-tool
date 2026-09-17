"""Tests for the OpenRouter usage/cost observability layer (Option C §12-13)
— structured logging of token usage and estimated cost, and the per-request
usage accumulator used for the pipeline cost summary. No live network calls."""

from unittest.mock import MagicMock, patch

from app.services import openrouter_utils as oru


def test_estimate_cost_returns_none_for_unknown_model():
    assert oru._estimate_cost_usd("some/unknown-model", 1000, 1000) is None


def test_estimate_cost_computes_from_known_pricing_table():
    cost = oru._estimate_cost_usd("google/gemini-2.5-pro", 1_000_000, 1_000_000)
    assert cost == 1.25 + 10.00


def test_record_usage_prefers_openrouter_reported_cost_over_estimate():
    oru.start_usage_tracking()
    try:
        oru._record_usage("test_stage", "google/gemini-2.5-pro", {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": 0.0042}
        })
        summary = oru.get_usage_summary()
    finally:
        oru.stop_usage_tracking()
    assert summary["estimated_total_cost_usd"] == 0.0042


def test_record_usage_falls_back_to_estimated_cost_when_not_reported():
    oru.start_usage_tracking()
    try:
        oru._record_usage("test_stage", "google/gemini-2.5-flash", {
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0, "total_tokens": 1_000_000}
        })
        summary = oru.get_usage_summary()
    finally:
        oru.stop_usage_tracking()
    assert summary["estimated_total_cost_usd"] == 0.30


def test_record_usage_is_a_noop_without_active_tracking():
    oru.stop_usage_tracking()  # ensure no tracking context is active
    # Should not raise even though nothing is accumulating.
    oru._record_usage("test_stage", "google/gemini-2.5-flash", {"usage": {"prompt_tokens": 10, "completion_tokens": 5}})


def test_record_usage_never_raises_on_malformed_response():
    oru.start_usage_tracking()
    try:
        oru._record_usage("test_stage", "x", {"usage": "not a dict"})  # malformed on purpose
        summary = oru.get_usage_summary()
    finally:
        oru.stop_usage_tracking()
    assert summary["call_count"] == 0


def test_record_usage_skips_silently_when_no_usage_block_present():
    oru.start_usage_tracking()
    try:
        oru._record_usage("test_stage", "google/gemini-2.5-flash", {})  # OpenRouter didn't return usage
        summary = oru.get_usage_summary()
    finally:
        oru.stop_usage_tracking()
    assert summary["call_count"] == 0


def test_usage_summary_aggregates_by_stage():
    oru.start_usage_tracking()
    try:
        oru._record_usage("insight", "google/gemini-2.5-flash", {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})
        oru._record_usage("insight", "google/gemini-2.5-flash", {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})
        oru._record_usage("final_script_write", "google/gemini-2.5-pro", {"usage": {"prompt_tokens": 500, "completion_tokens": 300, "total_tokens": 800}})
        summary = oru.get_usage_summary()
    finally:
        oru.stop_usage_tracking()
    assert summary["by_stage"]["insight"]["calls"] == 2
    assert summary["by_stage"]["insight"]["input_tokens"] == 200
    assert summary["by_stage"]["final_script_write"]["model"] == "google/gemini-2.5-pro"
    assert summary["total_input_tokens"] == 700
    assert summary["call_count"] == 3


def test_get_usage_summary_returns_zeroed_summary_when_never_started():
    oru.stop_usage_tracking()
    summary = oru.get_usage_summary()
    assert summary["call_count"] == 0
    assert summary["estimated_total_cost_usd"] is None


def test_generate_text_passes_label_through_to_record_usage():
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    fake_response.raise_for_status.return_value = None
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response

    with patch.object(oru, "get_openrouter_client", return_value=fake_client), \
         patch.object(oru, "_record_usage") as mock_record:
        result = oru.generate_text(
            system_instruction="s", contents=["c"], model="google/gemini-2.5-flash",
            max_output_tokens=100, label="my_stage",
        )
    assert result == "hello"
    mock_record.assert_called_once()
    args = mock_record.call_args[0]
    assert args[0] == "my_stage"
    assert args[1] == "google/gemini-2.5-flash"


def test_generate_text_never_sends_label_to_openrouter_request_body():
    """label is for local observability only — must never appear in the
    actual JSON body sent to OpenRouter."""
    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
    fake_response.raise_for_status.return_value = None
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response

    with patch.object(oru, "get_openrouter_client", return_value=fake_client):
        oru.generate_text(
            system_instruction="s", contents=["c"], model="google/gemini-2.5-flash",
            max_output_tokens=100, label="my_stage",
        )
    sent_body = fake_client.post.call_args[1]["json"]
    assert "label" not in sent_body
    assert "my_stage" not in str(sent_body)
