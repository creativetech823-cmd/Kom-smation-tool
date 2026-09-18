"""Per-retry shared-deadline fix (2026-09-18 live production task) — the
read-only investigation found that pool generation's (and the semantic
judge's) timeout was computed ONCE, before call_openrouter_with_retry() ran,
then captured by the retry closure and reused UNCHANGED for every attempt —
so a second attempt got a stale, un-shrunk budget instead of whatever was
actually left of the shared 90s deadline. That's a separate, more specific
bug than test_story_ideas_shared_deadline.py's cross-stage coverage (pool ->
judge -> enrichment): this file proves the fix WITHIN a single call's own
retry loop — attempt 2 must see less time than attempt 1 left it, and a
retry must never fire at all once the shared deadline is already gone."""

import json
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


def _card(title, **overrides):
    base = {
        "title": title, "description": f"description for {title}", "human_situation": "a specific person",
        "behavioral_tension": "a specific tension", "creative_mechanism": "Object-Driven Reveal",
        "creative_engine": "a specific behavior with a specific object and a specific turn",
        "product_role": "the specific job the product does", "hook_type": "Question",
        "hook_mechanism": "fits", "hook_execution": "a concrete opening scene", "emotion": "e", "persona": "p",
        "marketing_angle": "m", "category": "c", "difficulty": "easy", "estimated_length": "30s",
        "virality_score": 6.0,
    }
    base.update(overrides)
    return base


def _pool_response(n=3):
    return json.dumps({"situations": [_card(f"Card {i}") for i in range(n)]})


def _judgment(index, **overrides):
    base = {
        "candidate_index": index, "semantic_category_drift": False, "reason": "ok",
        "product_truth_alignment": 0.9, "audience_alignment": 0.9, "behavior_alignment": 0.9,
        "product_role_alignment": 0.9, "creative_potential": 0.8, "memorability": 0.7,
        "visual_potential": 0.7, "genericness_risk": 0.1, "claim_safety": 1.0,
        "territory_alignment": None, "cluster_id": f"c{index}",
        "implied_claim": False, "emotional_coercion": False,
    }
    base.update(overrides)
    return base


def _judge_response(n=3):
    return json.dumps({"judgments": [_judgment(i) for i in range(n)]})


def _enrichment_response(n=3):
    return json.dumps({"angles": [{"index": i, "recommended_angles": ["Relatable / Slice-of-life"]} for i in range(n)]})


# --- 1 & 2 & 3: retry recomputes the deadline, second attempt gets less time


def test_pool_generation_second_attempt_gets_a_smaller_timeout_than_the_first():
    """Attempt 1 fails transiently after consuming 15s of a 40s shared
    budget; attempt 2 must see a timeout bounded by what's ACTUALLY left
    (~25s), never the original ~40s value attempt 1 started with."""
    state = {"t": 0.0}

    def clock():
        return state["t"]

    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        if kwargs.get("label") != "story_situations":
            return _judge_response(3) if kwargs.get("label") == "semantic_story_judge" else _enrichment_response(3)
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        state["t"] += 15.0  # this attempt itself "took" 15s of wall time
        if call_n["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": settings.creative_model})
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None), \
         patch("time.monotonic", side_effect=clock):
        svc.generate_situations(_payload(), deadline=40.0)

    assert len(captured) == 2  # both attempts actually ran
    assert captured[0] == 40.0  # attempt 1: full ceiling, nothing consumed yet
    assert captured[1] < captured[0]  # attempt 2: strictly less — never the stale original value
    assert captured[1] == pytest.approx(25.0, abs=0.01)  # 40s budget - 15s already spent


def test_second_attempt_never_receives_the_first_attempts_exact_stale_value():
    """Direct regression for the reported bug: assert the two captured
    per-attempt timeouts are NOT equal when time has elapsed between them —
    equality would mean the closure captured one stale value instead of
    recomputing fresh."""
    state = {"t": 0.0}

    def clock():
        return state["t"]

    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        if kwargs.get("label") != "story_situations":
            return _judge_response(3) if kwargs.get("label") == "semantic_story_judge" else _enrichment_response(3)
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        state["t"] += 20.0
        if call_n["n"] == 1:
            raise openrouter_utils.ProviderError("server error", diagnostics={"model": settings.creative_model})
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None), \
         patch("time.monotonic", side_effect=clock):
        svc.generate_situations(_payload(), deadline=40.0)

    assert captured[0] != captured[1]


# --- 4: no OpenRouter request when the deadline is already expired ---------


def test_pool_generation_makes_zero_calls_when_deadline_already_expired():
    call_log = []

    def fake(**kwargs):
        call_log.append(kwargs.get("label"))
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch("time.monotonic", return_value=500.0):
        with pytest.raises(ValueError, match="time budget exhausted"):
            svc.generate_situations(_payload(), deadline=500.0)  # 0s remaining
    assert call_log == []


def test_judge_makes_zero_calls_when_deadline_already_expired():
    from app.services.product_context_service import build_product_creative_contract

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers", usp="0% tobacco",
    )
    call_log = []

    def fake(**kwargs):
        call_log.append(kwargs.get("label"))
        return _judge_response(3)

    with patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.monotonic", return_value=500.0):
        result = sj.judge_story_situations(contract, [{"title": "t"}], deadline=500.0)
    assert call_log == []
    assert result is None  # documented "unavailable" contract, never a fabricated pass


# --- 5: judge retries also recalculate remaining deadline ------------------


def test_judge_second_attempt_gets_a_smaller_timeout_than_the_first():
    from app.services.product_context_service import build_product_creative_contract

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers", usp="0% tobacco",
    )
    state = {"t": 0.0}

    def clock():
        return state["t"]

    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        state["t"] += 15.0
        if call_n["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": settings.validation_model})
        return _judge_response(2)

    with patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None), \
         patch("time.monotonic", side_effect=clock):
        result = sj.judge_story_situations(contract, [{"title": "a"}, {"title": "b"}], deadline=40.0)

    assert len(captured) == 2
    assert captured[0] == 40.0
    assert captured[1] < captured[0]
    assert captured[1] == pytest.approx(25.0, abs=0.01)
    assert result is not None
    assert len(result) == 2


# --- 6: deadline=None preserves the exact prior fixed-timeout behavior -----


def test_pool_generation_no_deadline_every_attempt_still_gets_the_full_ceiling():
    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        if kwargs.get("label") != "story_situations":
            return _judge_response(3) if kwargs.get("label") == "semantic_story_judge" else _enrichment_response(3)
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        if call_n["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": settings.creative_model})
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None):
        svc.generate_situations(_payload())  # no deadline given at all

    # Emergency demo fix (2026-09-18 same-day follow-up): pool-gen's ceiling
    # was raised 40s -> 120s to match real observed Luna latency.
    assert captured == [120.0, 120.0]  # both attempts get the unchanged-per-retry fixed ceiling


def test_judge_no_deadline_every_attempt_still_gets_the_full_ceiling():
    from app.services.product_context_service import build_product_creative_contract

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers", usp="0% tobacco",
    )
    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        if call_n["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": settings.validation_model})
        return _judge_response(1)

    with patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None):
        sj.judge_story_situations(contract, [{"title": "a"}])  # no deadline given at all

    assert captured == [40.0, 40.0]


# --- 7, 8, 9: existing quality gates / model routing / image-gen untouched -


def test_successful_generation_still_capped_at_six_after_the_retry_fix():
    def fake(**kwargs):
        label = kwargs.get("label")
        if label == "story_situations":
            return _pool_response(12)
        if label == "semantic_story_judge":
            return _judge_response(12)
        return _enrichment_response(6)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake):
        result = svc.generate_situations(_payload(), deadline=1_000_000.0)
    assert len(result.situations) <= 6


def test_model_routing_unchanged_by_the_retry_fix():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False


def test_semantic_judge_still_runs_by_default():
    call_log = []

    def fake(**kwargs):
        call_log.append(kwargs.get("label"))
        label = kwargs.get("label")
        if label == "story_situations":
            return _pool_response(3)
        if label == "semantic_story_judge":
            return _judge_response(3)
        return _enrichment_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake):
        svc.generate_situations(_payload())
    assert "semantic_story_judge" in call_log


# --- Emergency demo fix (2026-09-18 same-day follow-up): 90s -> 180s budget,
# 40s -> 120s pool-generation ceiling, to accommodate GPT-5.6 Luna's real
# observed ~107s pool-generation latency (a genuine successful completion,
# not an error) ------------------------------------------------------------


def test_overall_story_ideas_budget_is_approximately_180_seconds():
    assert svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0


def test_pool_call_can_use_up_to_approximately_120_seconds_when_time_remains():
    """With a generous shared deadline (much more than 120s left), the pool
    call's own timeout must reflect the new 120s ceiling, not the old 40s
    one — proving a genuinely slow-but-successful ~107s Luna completion now
    fits inside a single attempt's allowed window."""
    captured = {}

    def fake(**kwargs):
        if kwargs.get("label") == "story_situations":
            captured["pool_timeout"] = kwargs.get("timeout")
            return _pool_response(3)
        if kwargs.get("label") == "semantic_story_judge":
            return _judge_response(3)
        return _enrichment_response(3)

    import time as _time

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake):
        svc.generate_situations(_payload(), deadline=_time.monotonic() + 10_000.0)  # far more than 120s left

    assert captured["pool_timeout"] == 120.0
    assert svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0


def test_a_retry_never_exceeds_the_overall_story_ideas_deadline():
    """Even though the per-call CEILING is now 120s, a retry must still be
    bounded by whatever's ACTUALLY left of the overall shared deadline, not
    by the ceiling — proving the larger ceiling never lets a call run past
    the aggregate budget."""
    state = {"t": 0.0}

    def clock():
        return state["t"]

    captured = []
    call_n = {"n": 0}

    def fake(**kwargs):
        if kwargs.get("label") != "story_situations":
            return _judge_response(3) if kwargs.get("label") == "semantic_story_judge" else _enrichment_response(3)
        captured.append(kwargs.get("timeout"))
        call_n["n"] += 1
        state["t"] += 90.0  # attempt 1 consumes 90 of a 180s overall budget
        if call_n["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": settings.creative_model})
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None), \
         patch("time.monotonic", side_effect=clock):
        svc.generate_situations(_payload(), deadline=180.0)

    assert captured[0] == 120.0  # attempt 1: full new ceiling, plenty of the 180s budget available
    assert captured[1] == pytest.approx(90.0, abs=0.01)  # attempt 2: bounded by remaining (180-90), NOT the 120s ceiling
    assert captured[1] < 120.0  # the larger ceiling never overrides what's actually left of the shared deadline
