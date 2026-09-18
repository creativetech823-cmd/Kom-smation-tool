"""Live production timeout fix (2026-09-18 task) — the frontend was still
hitting its 90s AbortController timeout after the pool-generation and
semantic-judge fixes, even with no OpenRouter errors at all. Root cause:
generate_situations() makes THREE sequential OpenRouter calls per attempt
(pool generation, semantic judge, angle enrichment), each independently
allowed up to _STORY_IDEAS_CALL_TIMEOUT_SECONDS x _STORY_IDEAS_MAX_ATTEMPTS,
and the 90s aggregate budget in generate_situations_with_quality_floor was
only ever checked BETWEEN outer attempts — never inside one. A single
attempt's three calls could therefore blow well past 90s before the budget
check got a chance to run.

The fix: one absolute time.monotonic() deadline, computed once per request
and threaded unchanged through every attempt and every one of the three
inner calls. Each call's own timeout shrinks to whatever's actually left of
that shared deadline (never more than its existing per-call ceiling), and a
call that would start with too little time left is skipped outright rather
than attempted and left to time out. These tests exercise that behavior
directly, without depending on real wall-clock timing."""

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


def _pool_response(n=12):
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


def _judge_response(n=12):
    return json.dumps({"judgments": [_judgment(i) for i in range(n)]})


def _enrichment_response(n=6):
    return json.dumps({"angles": [{"index": i, "recommended_angles": ["Relatable / Slice-of-life"]} for i in range(n)]})


def _fake_generate_text(captured_timeouts, pool_n=12, judge_n=None, call_log=None):
    judge_n = judge_n if judge_n is not None else pool_n

    def fake(**kwargs):
        label = kwargs.get("label")
        captured_timeouts[label] = kwargs.get("timeout")
        if call_log is not None:
            call_log.append(label)
        if label == "story_situations":
            return _pool_response(pool_n)
        if label == "semantic_story_judge":
            return _judge_response(judge_n)
        if label == "story_situations_angle_enrichment":
            return _enrichment_response(min(6, judge_n))
        raise AssertionError(f"unexpected label: {label}")

    return fake


# --- No deadline given: exact pre-fix behavior, unchanged ------------------


def test_no_deadline_every_call_gets_the_full_fixed_ceiling():
    captured = {}
    with patch.object(svc, "generate_text", side_effect=_fake_generate_text(captured)), \
         patch.object(sj, "generate_text", side_effect=_fake_generate_text(captured)):
        result = svc.generate_situations(_payload())
    # Emergency demo fix (2026-09-18 same-day follow-up): pool-gen/enrichment
    # share _STORY_IDEAS_CALL_TIMEOUT_SECONDS, raised 40s -> 120s. The
    # judge's own _JUDGE_CALL_TIMEOUT_SECONDS was deliberately left at 40s —
    # Gemini Flash-Lite isn't the bottleneck this fix addresses.
    assert captured["story_situations"] == 120.0
    assert captured["semantic_story_judge"] == 40.0
    assert captured["story_situations_angle_enrichment"] == 120.0
    assert len(result.situations) <= svc.MAX_STORY_IDEAS_PER_GENERATION


# --- Shared deadline shrinks each call's own timeout ------------------------


def test_shared_deadline_shrinks_a_later_calls_timeout_after_an_earlier_one_ran_long():
    """Simulates pool generation actually consuming 28 of a 40s shared
    budget (by advancing a fake clock as a side effect of the mocked call
    itself) — the judge call that follows must get a timeout bounded by
    the ~12s actually left, not a fresh 40s ceiling."""
    state = {"t": 0.0}

    def clock():
        return state["t"]

    captured = {}

    def fake(**kwargs):
        label = kwargs.get("label")
        captured[label] = kwargs.get("timeout")
        if label == "story_situations":
            state["t"] += 28.0  # pretend the HTTP call itself took 28s
            return _pool_response(3)
        if label == "semantic_story_judge":
            return _judge_response(3)
        if label == "story_situations_angle_enrichment":
            return _enrichment_response(3)
        raise AssertionError(label)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.monotonic", side_effect=clock):
        deadline = 40.0  # clock starts at 0.0, so this is a 40s shared budget
        svc.generate_situations(_payload(), deadline=deadline)

    assert captured["story_situations"] == 40.0  # first call: full budget still available
    assert 0 < captured["semantic_story_judge"] <= 12.0  # bounded by what's actually left, not the 40s ceiling
    assert captured["semantic_story_judge"] < captured["story_situations"]


# --- No work continuing unnecessarily after the deadline --------------------


def test_pool_generation_raises_immediately_without_any_call_when_deadline_already_passed():
    call_log = []

    def fake(**kwargs):
        call_log.append(kwargs.get("label"))
        return _pool_response(3)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch("time.monotonic", return_value=100.0):
        with pytest.raises(ValueError, match="time budget exhausted"):
            svc.generate_situations(_payload(), deadline=100.0)  # 0s remaining
    assert call_log == []  # no OpenRouter call was ever attempted


def test_judge_is_skipped_not_attempted_when_too_little_time_remains():
    state = {"t": 0.0}

    def clock():
        return state["t"]

    call_log = []

    def fake(**kwargs):
        label = kwargs.get("label")
        call_log.append(label)
        if label == "story_situations":
            state["t"] += 37.0  # leaves ~3s — below the judge's own minimum
            return _pool_response(3)
        if label == "story_situations_angle_enrichment":
            return _enrichment_response(3)
        raise AssertionError(f"judge should never have been called, got {label}")

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.monotonic", side_effect=clock):
        result = svc.generate_situations(_payload(), deadline=40.0)

    assert "semantic_story_judge" not in call_log  # skipped, never attempted
    # Judge unavailable -> safe deterministic-only degrade, never an empty/broken result
    assert len(result.situations) == 3


def test_enrichment_is_skipped_not_attempted_when_too_little_time_remains():
    state = {"t": 0.0}

    def clock():
        return state["t"]

    call_log = []

    def fake(**kwargs):
        label = kwargs.get("label")
        call_log.append(label)
        if label == "story_situations":
            state["t"] += 10.0
            return _pool_response(3)
        if label == "semantic_story_judge":
            state["t"] += 27.0  # total 37s used, leaving ~3s for enrichment
            return _judge_response(3)
        raise AssertionError(f"enrichment should never have been called, got {label}")

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake), \
         patch("time.monotonic", side_effect=clock):
        result = svc.generate_situations(_payload(), deadline=40.0)

    assert "story_situations_angle_enrichment" not in call_log
    # Safe fallback: recommended_angles just falls back to its documented default, never blocks the response.
    assert len(result.situations) == 3


# --- One shared absolute deadline across quality-floor retries, not reset --


def test_same_absolute_deadline_passed_unchanged_to_every_quality_floor_attempt():
    captured_deadlines = []

    def fake_generate_situations(payload, deadline=None):
        captured_deadlines.append(deadline)
        return svc.StorySituationsResult(situations=[])  # never meets the floor -> retries

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations), \
         patch("time.monotonic", side_effect=[0.0, 0.0, 10.0, 20.0]):
        svc.generate_situations_with_quality_floor(
            _payload(), min_situations=6, max_attempts=3, max_total_seconds=90.0,
        )
    assert len(captured_deadlines) == 3
    assert len(set(captured_deadlines)) == 1  # the exact same absolute deadline every time, never recomputed


def test_no_deadline_threaded_when_max_total_seconds_is_none():
    captured_deadlines = []

    def fake_generate_situations(payload, deadline=None):
        captured_deadlines.append(deadline)
        return svc.StorySituationsResult(situations=[_mk("Only")])

    with patch.object(svc, "generate_situations", side_effect=fake_generate_situations):
        svc.generate_situations_with_quality_floor(_payload(), min_situations=1, max_attempts=1)
    assert captured_deadlines == [None]


def _mk(title):
    from app.models.product import StorySituation
    return StorySituation(
        id="t", title=title, description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
    )


# --- Successful generation still returns at most 6 with a deadline given ---


def test_successful_generation_with_a_deadline_still_caps_at_six():
    captured = {}
    with patch.object(svc, "generate_text", side_effect=_fake_generate_text(captured, pool_n=12)), \
         patch.object(sj, "generate_text", side_effect=_fake_generate_text(captured, pool_n=12)):
        result = svc.generate_situations(_payload(), deadline=1_000_000.0)  # effectively unlimited
    assert len(result.situations) <= 6


# --- Model routing / feature flags unaffected by this fix ------------------


def test_validation_model_is_still_gemini_flash_lite():
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_creative_model_is_still_luna():
    assert settings.creative_model == "openai/gpt-5.6-luna"


def test_final_script_model_is_still_luna():
    assert settings.final_script_model == "openai/gpt-5.6-luna"


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False


def test_semantic_judge_still_invoked_by_default_not_bypassed():
    """The judge must still run (and be capable of filtering) in the normal
    case — this fix must never quietly turn semantic judging off."""
    captured = {}
    call_log = []
    fake = _fake_generate_text(captured, pool_n=3, call_log=call_log)
    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(sj, "generate_text", side_effect=fake):
        svc.generate_situations(_payload())
    assert "semantic_story_judge" in call_log
