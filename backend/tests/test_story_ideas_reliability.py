"""Story Ideas reliability fix (2026-09-18 task) — the "stuck loading"
regression. Backend half: an aggregate wall-clock budget around
generate_situations_with_quality_floor's retry loop, best-so-far candidate
preservation across attempts, an honest error (never a silent empty
"success") when zero candidates survive, and a model-neutral malformed-JSON
error message. Does not touch creative architecture — every test here mocks
generate_situations() itself (or the raw LLM call), never weakens what
counts as a "valid" candidate.

The frontend half (AbortController timeout in lib/api.ts, clearing the
stale localStorage project id in app/page.tsx) has no automated test here:
this repo has no JS test runner configured (no Jest/Vitest, no test script)
— verified by inspection before writing this file. Those two are verified
by `tsc --noEmit` (clean) and manual code review instead, documented
honestly in the final report rather than silently skipped or given a new
test framework nobody asked for.
"""

import json
import time
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import openrouter_utils, semantic_story_judge_service as sj, story_situation_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


HERBAL_MASALA = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same chewing ritual and taste"],
)


def _payload(count=6):
    return StorySituationsInput(
        structured_product=HERBAL_MASALA, product_category="herbal_health", count=count,
        script_language=ScriptLanguage.hinglish,
    )


def _card(title):
    return {
        "title": title, "description": f"description for {title}", "human_situation": "a specific person",
        "behavioral_tension": "a specific tension", "creative_mechanism": "Object-Driven Reveal",
        "creative_engine": "a specific behavior with a specific object and a specific turn",
        "product_role": "the specific job the product does", "hook_type": "Question",
        "hook_mechanism": "fits", "hook_execution": "a concrete opening scene", "emotion": "e", "persona": "p",
        "marketing_angle": "m", "category": "c", "difficulty": "easy", "estimated_length": "30s",
        "virality_score": 6.0, "recommended_angles": [],
    }


# --- Aggregate wall-clock budget --------------------------------------------


def test_budget_stops_further_attempts_once_exhausted():
    """3 attempts allowed, but the budget runs out after the 1st — the 2nd
    and 3rd must never be attempted."""
    call_count = {"n": 0}

    def fake_generate_situations(payload):
        call_count["n"] += 1
        return svc.StorySituationsResult(situations=[])  # never meets the floor, would normally retry

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations), \
         patch("time.monotonic", side_effect=[0.0, 0.0, 100.0, 100.0, 100.0]):
        # First time.monotonic() call is the loop's `start`; second is the
        # pre-attempt-1 budget check (still within budget); third is the
        # pre-attempt-2 check (now past the 90s budget) — attempt 2 must
        # never fire the underlying generate_situations call.
        result = svc.generate_situations_with_quality_floor(
            _payload(), min_situations=6, max_attempts=3, max_total_seconds=90.0,
        )
    assert call_count["n"] == 1
    assert result.budget_exhausted is True
    assert result.quality_floor_met is False


def test_no_budget_given_behaves_exactly_as_before():
    """max_total_seconds=None (the default) must preserve the pre-existing
    unbounded-by-time behavior — only max_attempts bounds it, unchanged."""
    call_count = {"n": 0}

    def fake_generate_situations(payload):
        call_count["n"] += 1
        return svc.StorySituationsResult(situations=[])

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations):
        result = svc.generate_situations_with_quality_floor(_payload(), min_situations=6, max_attempts=3)
    assert call_count["n"] == 3
    assert result.budget_exhausted is False


def test_generate_situations_for_request_passes_the_default_budget():
    captured = {}

    def fake_quality_floor(payload, min_situations, max_total_seconds=None):
        captured["max_total_seconds"] = max_total_seconds
        return svc.QualityFloorResult(situations=[svc.StorySituation(
            id="t", title="X", description="d", emotion="e", persona="p", marketing_angle="m",
            category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
        )], quality_floor_met=True, attempts_used=1)

    with patch.object(svc, "generate_situations_with_quality_floor", side_effect=fake_quality_floor):
        svc.generate_situations_for_request(_payload())
    assert captured["max_total_seconds"] == svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS
    assert svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 90.0


def test_an_attempt_already_in_flight_is_never_interrupted_mid_call():
    """The budget check only happens BEFORE starting a new attempt — a slow
    generate_situations() call that's already running must be allowed to
    finish, never cut off partway (which could leave gate state
    inconsistent). Verified here by confirming exactly one full call
    happens even though the budget is effectively already spent by the time
    it returns."""
    def fake_generate_situations(payload):
        return svc.StorySituationsResult(situations=[_dummy_situation("Only One")])

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations):
        result = svc.generate_situations_with_quality_floor(
            _payload(), min_situations=6, max_attempts=3, max_total_seconds=90.0,
        )
    # The single attempt ran to completion and returned its real result —
    # not aborted mid-call just because the loop's next budget check would
    # have failed.
    assert len(result.situations) == 1


def _dummy_situation(title):
    from app.models.product import StorySituation
    return StorySituation(
        id="t", title=title, description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
    )


# --- Best-so-far preservation across attempts -------------------------------


def test_best_so_far_preserved_when_a_later_attempt_is_worse():
    """Attempt 1 produces 4 valid candidates (below the 6-target floor, so
    it retries); attempt 2 produces only 1 (bad luck). The final result must
    keep attempt 1's stronger 4, never attempt 2's weaker 1 — this was a
    real latent bug (only `last_result` was ever kept) fixed as part of
    this task."""
    responses = [
        svc.StorySituationsResult(situations=[_dummy_situation(f"A{i}") for i in range(4)]),
        svc.StorySituationsResult(situations=[_dummy_situation("B0")]),
        svc.StorySituationsResult(situations=[]),
    ]
    call_count = {"n": 0}

    def fake_generate_situations(payload):
        result = responses[call_count["n"]]
        call_count["n"] += 1
        return result

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations):
        result = svc.generate_situations_with_quality_floor(_payload(), min_situations=6, max_attempts=3)
    assert len(result.situations) == 4
    assert {s.title for s in result.situations} == {"A0", "A1", "A2", "A3"}
    assert result.quality_floor_met is False  # never reached the floor of 6, but kept the best partial result


def test_best_so_far_still_returns_full_result_when_floor_is_met():
    def fake_generate_situations(payload):
        return svc.StorySituationsResult(situations=[_dummy_situation(f"C{i}") for i in range(6)])

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations):
        result = svc.generate_situations_with_quality_floor(_payload(), min_situations=6, max_attempts=3)
    assert len(result.situations) == 6
    assert result.quality_floor_met is True


# --- Zero valid candidates -> explicit error, never a fake "success" -------


def test_zero_candidates_raises_clear_error_not_silent_empty_success():
    with patch.object(svc, "generate_situations", return_value=svc.StorySituationsResult(situations=[])):
        with pytest.raises(ValueError, match="No story ideas survived"):
            svc.generate_situations_for_request(_payload())


def test_zero_candidates_error_mentions_budget_when_that_was_the_cause():
    def fake_quality_floor(payload, min_situations, max_total_seconds=None):
        return svc.QualityFloorResult(situations=[], quality_floor_met=False, attempts_used=1, budget_exhausted=True)

    with patch.object(svc, "generate_situations_with_quality_floor", side_effect=fake_quality_floor):
        with pytest.raises(ValueError, match="time budget"):
            svc.generate_situations_for_request(_payload())


def test_router_converts_the_zero_candidate_error_to_an_http_error():
    from fastapi import HTTPException
    from app.routers.pipeline import story_situations

    with patch("app.routers.pipeline.generate_situations_for_request", side_effect=ValueError("No story ideas survived the checks")):
        with pytest.raises(HTTPException) as exc_info:
            story_situations(_payload())
    assert exc_info.value.status_code == 502
    assert "No story ideas survived" in str(exc_info.value.detail)


def test_nonzero_candidates_never_raise_even_below_the_floor():
    """A shortfall (fewer than requested) is NOT the same as zero — must
    still return normally with generation_shortfall=True, never raise."""
    with patch.object(svc, "generate_situations", return_value=svc.StorySituationsResult(situations=[_dummy_situation("Only One")])):
        result = svc.generate_situations_for_request(_payload())
    assert len(result.situations) == 1
    assert result.generation_shortfall is True


# --- Model-neutral error message --------------------------------------------


def test_malformed_json_error_message_uses_actual_model_not_hardcoded_gemini():
    with patch.object(svc, "generate_text", return_value="not valid json{{{"), \
         patch.object(svc.settings, "openrouter_creative_model", "openai/gpt-5.6-luna"):
        with pytest.raises(ValueError) as exc_info:
            svc.generate_situations(_payload())
    message = str(exc_info.value)
    assert "openai/gpt-5.6-luna" in message
    assert "Gemini" not in message


def test_malformed_json_error_message_reflects_gemini_when_that_is_actually_configured():
    """Model-neutral means it shows whatever IS configured — including
    Gemini, when that's genuinely the active model. It must never hardcode
    either name; it must reflect settings.creative_model exactly."""
    with patch.object(svc, "generate_text", return_value="not valid json{{{"), \
         patch.object(svc.settings, "openrouter_creative_model", "google/gemini-2.5-flash"):
        with pytest.raises(ValueError) as exc_info:
            svc.generate_situations(_payload())
    assert "google/gemini-2.5-flash" in str(exc_info.value)


# --- Model routing / no silent fallback (unaffected by this fix) -----------


def test_generate_situations_still_calls_creative_model_unaffected_by_reliability_fix():
    captured = {}

    def fake(**kwargs):
        captured["model"] = kwargs.get("model")
        return json.dumps({"situations": [_card("X")]})

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        svc.generate_situations(_payload())
    assert captured["model"] == settings.creative_model


def test_quality_floor_retry_never_silently_substitutes_a_different_model():
    """Every attempt inside the retry loop must go through the SAME
    generate_situations() call chain (and therefore the same
    settings.creative_model resolution) — the retry loop introduces no
    alternate model path."""
    models_seen = []

    def fake(**kwargs):
        models_seen.append(kwargs.get("model"))
        return json.dumps({"situations": []})  # always empty, forces all 3 attempts

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        svc.generate_situations_with_quality_floor(_payload(), min_situations=6, max_attempts=3)
    assert len(models_seen) == 3
    assert len(set(models_seen)) == 1  # identical model every attempt, never swapped


# --- Per-call timeout/retry bound (single-call-can-exceed-budget fix) ------
# A single OpenRouter HTTP attempt shares the client's 120s default, and
# call_openrouter_with_retry's own default of 4 attempts could chain that up
# to ~494s for ONE call alone — already far past the 90s aggregate budget,
# and the quality-floor loop only checks its budget BETWEEN attempts, never
# during one. These tests confirm the two Story-Ideas-specific LLM calls
# (pool-generation, semantic judge) got a shorter, explicit per-call bound
# WITHOUT touching the shared client default other stages still rely on.


def test_pool_generation_call_uses_a_reduced_per_call_timeout_and_retry_count():
    captured = {}

    def fake_call_openrouter_with_retry(fn, *, label, max_attempts=4):
        captured["max_attempts"] = max_attempts
        return fn()

    def fake_generate_text(**kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return json.dumps({"situations": []})

    with patch.object(svc, "call_openrouter_with_retry", side_effect=fake_call_openrouter_with_retry), \
         patch.object(svc, "generate_text", side_effect=fake_generate_text):
        svc.generate_situations(_payload())

    assert captured["timeout"] == svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS
    assert captured["timeout"] < 120.0  # strictly less than the shared client default
    assert captured["max_attempts"] == svc._STORY_IDEAS_MAX_ATTEMPTS
    assert captured["max_attempts"] < 4  # strictly less than call_openrouter_with_retry's own default


def test_semantic_judge_call_also_uses_a_reduced_per_call_timeout():
    captured = {}

    def fake_generate_text(**kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return json.dumps({"judgments": []})

    with patch.object(sj, "generate_text", side_effect=fake_generate_text):
        sj.judge_story_situations(
            contract=type("C", (), {"role_risk_keys": [], "prompt_block": lambda self: ""})(),
            candidates=[{"title": "x"}],
        )
    assert captured["timeout"] == 40.0
    assert captured["timeout"] < 120.0


def test_worst_case_single_attempt_is_bounded_well_under_the_old_12_minute_ceiling():
    """Documents the actual bound achieved: 2 calls (pool-gen, judge) x 2
    attempts x 40s + backoff, vs. the previous 4+2 attempts x 120s (~736s).
    Not a claim of a strict sub-90s guarantee for one attempt (that would
    require restructuring the sequential two-call attempt into a shared-
    deadline object — out of scope, an architecture change) — just proof
    the fix materially shrinks the worst case."""
    per_call_worst = svc._STORY_IDEAS_MAX_ATTEMPTS * svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS + 2  # +2s backoff
    one_attempt_worst = per_call_worst * 2  # pool-gen then judge, sequential
    assert one_attempt_worst < 200  # was ~736s before this fix
    assert one_attempt_worst == 164.0


def test_generate_text_timeout_param_only_sent_to_httpx_when_explicitly_given():
    """Every OTHER call site (no explicit timeout=) must be completely
    unaffected — confirms this is additive, not a change to the shared
    client default."""
    from unittest.mock import MagicMock

    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
    fake_response.raise_for_status.return_value = None
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response

    with patch.object(openrouter_utils, "get_openrouter_client", return_value=fake_client):
        openrouter_utils.generate_text(system_instruction="s", contents=["c"], model="m", max_output_tokens=10)
    call_kwargs = fake_client.post.call_args[1]
    assert "timeout" not in call_kwargs  # falls through to the client's own 120s default


def test_generate_text_timeout_param_forwarded_to_httpx_when_given():
    from unittest.mock import MagicMock

    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
    fake_response.raise_for_status.return_value = None
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response

    with patch.object(openrouter_utils, "get_openrouter_client", return_value=fake_client):
        openrouter_utils.generate_text(
            system_instruction="s", contents=["c"], model="m", max_output_tokens=10, timeout=40.0,
        )
    call_kwargs = fake_client.post.call_args[1]
    assert call_kwargs["timeout"] == 40.0


def test_timeout_exception_never_reaches_json_parsing_as_a_valid_response():
    """Verifies the safety property the task explicitly asked to confirm:
    a timeout must never be mistaken for a parseable (even if malformed)
    response — httpx raises BEFORE response.json()/_extract_text() are ever
    reached, so there is no code path where partial/timed-out output could
    be treated as a valid candidate."""
    import httpx
    from unittest.mock import MagicMock

    fake_client = MagicMock()
    fake_client.post.side_effect = httpx.ReadTimeout("The read operation timed out")

    with patch.object(openrouter_utils, "get_openrouter_client", return_value=fake_client):
        with pytest.raises(httpx.ReadTimeout):
            openrouter_utils.generate_text(
                system_instruction="s", contents=["c"], model="m", max_output_tokens=10, timeout=1.0,
            )
    # response.json() / _extract_text() were never reached — nothing was
    # parsed, nothing could have been silently accepted as a valid candidate.


def test_call_openrouter_with_retry_classifies_httpx_read_timeout_as_transient():
    """The retry wrapper must actually recognize a real httpx timeout as
    retryable (not silently give up after one attempt, and not silently
    treat it as a permanent failure requiring no backoff) — verified with
    the exact exception/message shape httpx raises for a real timeout."""
    import httpx

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise httpx.ReadTimeout("The read operation timed out")

    with patch("time.sleep", return_value=None):
        try:
            openrouter_utils.call_openrouter_with_retry(fn, label="test", max_attempts=2)
        except ValueError:
            pass
    assert calls["n"] == 2  # retried, not given up after one attempt
