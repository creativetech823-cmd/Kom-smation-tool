"""Phase 2: verifies _generate_with_recovery actually catches the failure
type call_openrouter_with_retry raises on exhaustion (previously it did not
— this exact gap meant the "existing retry+repair mechanism" was never
reached for an empty-response failure), skips the repair pass when there is
nothing to repair, and — critically — that the Product Creative Contract and
full creative context survive a retry unchanged, per the explicit Phase 2
requirement that category protection must never be lost to a reliability
fix. No live network calls."""

from unittest.mock import patch

import pytest

from app.services import openrouter_utils as oru
from app.services import script_service as svc


# Body sized to land inside the default 30s word-count target (70-100 words)
# so the pre-existing length-correction pass in _generate_with_recovery
# never fires and silently adds an extra call these tests aren't about.
_LONG_BODY_TEXT = " ".join(["word"] * 80)
GOOD_JSON = (
    '{"hook": {"text": "h"}, "body": [{"text": "' + _LONG_BODY_TEXT + '"}], '
    '"cta": {"text": "c"}, "creative_mechanism": "curiosity_gap"}'
)


@pytest.fixture(autouse=True)
def reset_circuit_state():
    oru.stop_usage_tracking()
    yield
    oru.stop_usage_tracking()


def test_empty_response_on_first_attempt_is_caught_and_retried():
    """Regression for the exact Phase 2 root cause: previously this
    ValueError (raised by call_openrouter_with_retry once its own retries
    are exhausted) propagated straight past this function's except clause,
    aborting on attempt 1 without ever trying attempt 2."""
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("Retry failed after 4 attempts. OpenRouter returned no usable text.")
        return GOOD_JSON

    with patch.object(svc, "generate_text", side_effect=flaky):
        data = svc._generate_with_recovery("system", "user message", 1000, "30s")
    assert data["hook"]["text"] == "h"
    assert calls["n"] == 2  # attempt 1 failed, attempt 2 succeeded — no crash on attempt 1


def test_repair_pass_is_skipped_when_nothing_was_ever_returned():
    """Both attempts return no text at all (a pure empty-response failure,
    not malformed-but-present JSON) — the repair pass must be skipped
    entirely rather than asking the model to 'fix' an empty string."""
    calls = {"n": 0}

    def always_empty(*args, **kwargs):
        calls["n"] += 1
        raise ValueError("OpenRouter returned no usable text.")

    with patch.object(svc, "generate_text", side_effect=always_empty):
        with pytest.raises(ValueError, match="no usable content"):
            svc._generate_with_recovery("system", "user message", 1000, "30s")
    # Exactly 2 calls (the two generation attempts) — no third "repair" call.
    assert calls["n"] == 2


def test_repair_pass_still_runs_when_malformed_but_nonempty_text_was_returned():
    """The opposite case must keep working exactly as before: real,
    non-empty (but broken) JSON should still go through the repair pass."""
    calls = {"n": 0}

    def malformed_then_repaired(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return '{"hook": {"text": "h" '  # truncated / invalid JSON, but non-empty
        return GOOD_JSON  # the repair call

    with patch.object(svc, "generate_text", side_effect=malformed_then_repaired):
        data = svc._generate_with_recovery("system", "user message", 1000, "30s")
    assert data["hook"]["text"] == "h"
    assert calls["n"] == 3  # 2 failed generation attempts + 1 repair call


# --- Product Creative Contract / creative context survives a retry ----------


def test_contract_and_creative_context_survive_a_retry_unchanged():
    """The retry reuses the exact same system/user_message — including
    whatever Product Creative Contract, territory, premise, and outline
    blocks it already contains — so a reliability retry can never silently
    drop product grounding. This is the literal mechanism Phase 2 §14 asks
    to be verified."""
    contract_marker = "PRODUCT CREATIVE CONTRACT (immutable factual grounding"
    user_message = (
        f"{contract_marker}\nProduct: Aayush Herbal Masala\n"
        "Actual category/what this product IS: Tobacco/gutka/pan-masala/supari consumption alternative\n"
        "APPROVED CREATIVE TERRITORY: The Automatic Reach\n"
    )
    captured_user_messages = []
    calls = {"n": 0}

    def flaky(system, user_msg, *args, **kwargs):
        captured_user_messages.append(user_msg)
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("OpenRouter returned no usable text.")
        return GOOD_JSON

    with patch.object(svc, "_call_llm", side_effect=flaky):
        svc._generate_with_recovery("system", user_message, 1000, "30s")

    assert len(captured_user_messages) == 2
    for msg in captured_user_messages:
        assert contract_marker in msg
        assert "gutka" in msg.lower()
        assert "The Automatic Reach" in msg


def test_herbal_masala_retry_after_failure_does_not_reintroduce_cooking_context():
    """Mocks a failed Pro response followed by a successful one and verifies
    the successful retry's script still carries correct product grounding —
    the exact scenario Phase 2 §18/§14 requires a regression test for."""
    from app.services.product_context_service import build_product_creative_contract

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        usp="a 0% tobacco, 0% supari herbal chew",
    )
    user_message = f"{contract.prompt_block()}\nProduct: Aayush Herbal Masala\n"
    correct_script_json = (
        '{"hook": {"text": "Jab haath apne aap wahan jaata hai jahan gutka hua karta tha."}, '
        '"body": [{"text": "Ab ussi ritual ke liye Aayush Herbal Masala."}], '
        '"cta": {"text": "Try it today."}, "creative_mechanism": "mini_story"}'
    )
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("OpenRouter returned no usable text.")
        return correct_script_json

    from app.services.product_context_validator import detect_category_drift_signal

    with patch.object(svc, "generate_text", side_effect=flaky):
        data = svc._generate_with_recovery("system", user_message, 1000, "30s")

    combined_text = data["hook"]["text"] + " " + data["body"][0]["text"]
    assert detect_category_drift_signal(combined_text, contract) == ""
    assert "curry" not in combined_text.lower()
    assert "recipe" not in combined_text.lower()


# --- No silent model downgrade -----------------------------------------------


def test_retry_on_failure_never_silently_switches_model():
    """A Pro failure followed by a retry must still use the SAME configured
    model — no silent fallback to Flash unless explicitly configured."""
    from app.config import settings

    captured_models = []

    def flaky(*args, **kwargs):
        captured_models.append(kwargs.get("model"))
        if len(captured_models) == 1:
            raise oru.EmptyResponseError("empty", diagnostics={"model": kwargs.get("model")})
        return GOOD_JSON

    with patch.object(svc, "generate_text", side_effect=flaky):
        svc._generate_with_recovery("system", "user", 1000, "30s", model=settings.final_script_model)

    assert all(m == settings.final_script_model for m in captured_models)
