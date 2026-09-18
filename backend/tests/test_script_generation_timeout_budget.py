"""Urgent demo fix (2026-09-18, same-day follow-up) — POST /pipeline/
generate-script was hitting the frontend's shared 180s AbortController
timeout even with no backend/OpenRouter error: this endpoint's long
sequential pipeline (creative insight/territory/architecture/premise/hook/
outline planning, the final-script write, then claim-safety/quality/
architecture-director gates) has no per-endpoint budget of its own and can
legitimately take longer than Story Ideas' pool generation.

Investigation finding (see final report): unlike Story Ideas,
script_service.py has NO existing shared deadline/budget object at all
(confirmed: zero references to time.monotonic/deadline/budget anywhere in
that file before this task) — the reported timeout was entirely the
frontend's shared POST_TIMEOUT_MS aborting a request the backend was still
legitimately processing. The fix is a frontend-only, endpoint-scoped
timeout override (SCRIPT_GENERATION_TIMEOUT_MS = 300_000 in lib/api.ts,
verified separately via `tsc --noEmit` since this repo has no JS test
runner) plus backend observability logging — these tests cover the backend
half: the new [SCRIPT_GENERATION] timing logs, and confirm nothing on the
backend introduces any new timeout/deadline layer or touches Story Ideas'
existing constants, retry architecture, or model routing."""

import json
import logging
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import architecture_validation_service as arch_val
from app.services import creative_architecture, openrouter_utils, script_quality as sq
from app.services import script_service as svc
from app.services import semantic_story_judge_service as sj
from app.services import story_situation_service as story_svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


_GOOD_SCRIPT_JSON = json.dumps({
    "hook": {"text": "A specific hook line."},
    "body": [{"text": "A body line that develops the story."}],
    "cta": {"text": "A closing line."},
    "creative_mechanism": "curiosity_gap",
})

_SAFE_CLAIM_JSON = json.dumps({
    "implied_claim": False, "claim_evidence": "", "claim_reason": "",
    "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
})


def _payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="t", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def _run_generate_script_fully_mocked(caplog=None):
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    patches = [
        patch.object(svc.creative_insight_service, "discover_insight", return_value=None),
        patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None),
        patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture),
        patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None),
        patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None),
        patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])),
        patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'),
        patch.object(svc.claim_safety_service, "generate_text", return_value=_SAFE_CLAIM_JSON),
        patch.object(arch_val, "generate_text", return_value='{"issues": []}'),
        patch.object(svc, "generate_text", return_value=_GOOD_SCRIPT_JSON),
    ]
    for p in patches:
        p.start()
    try:
        return svc.generate_script(_payload())
    finally:
        for p in reversed(patches):
            p.stop()


# --- 8: [SCRIPT_GENERATION] timing logs are present at INFO level ----------


def test_script_generation_stage_timing_logs_are_emitted(caplog):
    with caplog.at_level(logging.INFO, logger="script_service"):
        _run_generate_script_fully_mocked()
    messages = [r.message for r in caplog.records]
    assert any(m.startswith("[SCRIPT_GENERATION] start") for m in messages)
    assert any(m.startswith("[SCRIPT_GENERATION] creative planning complete") for m in messages)
    assert any(m.startswith("[SCRIPT_GENERATION] final script start") for m in messages)
    assert any(m.startswith("[SCRIPT_GENERATION] validation complete") for m in messages)
    assert any(m.startswith("[SCRIPT_GENERATION] complete") for m in messages)


def test_script_generation_logs_never_include_prompt_or_script_content(caplog):
    with caplog.at_level(logging.INFO, logger="script_service"):
        _run_generate_script_fully_mocked()
    for r in caplog.records:
        if r.name != "script_service" or "[SCRIPT_GENERATION]" not in r.message:
            continue
        assert "A specific hook line" not in r.message
        assert "A body line that develops the story" not in r.message


# --- 3 & 4: no backend-side deadline layer was introduced; internal calls --
# --- still use only the pre-existing shared client default -----------------


def test_no_new_backend_deadline_or_timeout_kwarg_was_introduced():
    """This task's investigation found NO existing per-request deadline
    object in script_service.py, and deliberately did not add one (that
    would be an architecture change, explicitly out of scope for a same-day
    timeout-budget fix). Confirms the final script write call still passes
    no explicit `timeout=` override — it relies on the shared OpenRouter
    client's unmodified 120s-per-call default, exactly as before this task."""
    captured = {}

    def fake_generate_text(*args, **kwargs):
        captured.update(kwargs)
        return _GOOD_SCRIPT_JSON

    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "generate_text", return_value=_SAFE_CLAIM_JSON), \
         patch.object(arch_val, "generate_text", return_value='{"issues": []}'), \
         patch.object(svc, "generate_text", side_effect=fake_generate_text):
        svc.generate_script(_payload())
    assert "timeout" not in captured  # falls through to the shared client's own 120s default, unchanged


def test_generate_script_still_returns_a_script_end_to_end():
    result = _run_generate_script_fully_mocked()
    assert result.hook.text == "A specific hook line."
    assert result.body[0].text == "A body line that develops the story."


# --- 5: existing retry/deadline architecture untouched ---------------------


def test_openrouter_shared_client_default_timeout_unchanged():
    """openrouter_utils.py's shared httpx client default (used by every
    generate-script call site) must remain 120s — untouched by this task.
    Reads the module's own source file directly rather than introspecting
    the live function object, since the autouse fixture above replaces
    get_openrouter_client with a MagicMock for the duration of every test
    in this file."""
    import inspect
    src = inspect.getsource(openrouter_utils)
    assert "timeout=120.0" in src


def test_call_openrouter_with_retry_default_max_attempts_unchanged():
    import inspect
    sig = inspect.signature(openrouter_utils.call_openrouter_with_retry)
    assert sig.parameters["max_attempts"].default == 4


# --- 6: Story Ideas timeout values remain exactly what the prior task set --


def test_story_ideas_overall_budget_unchanged_at_180s():
    assert story_svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0


def test_story_ideas_pool_timeout_ceiling_unchanged_at_120s():
    assert story_svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0


def test_story_ideas_max_attempts_and_min_call_seconds_unchanged():
    assert story_svc._STORY_IDEAS_MAX_ATTEMPTS == 2
    assert story_svc._STORY_IDEAS_MIN_CALL_SECONDS == 8.0


def test_judge_call_timeout_ceiling_unchanged_at_40s():
    assert sj._JUDGE_CALL_TIMEOUT_SECONDS == 40.0


# --- 7: model routing / image generation unchanged --------------------------


def test_model_routing_unchanged_by_the_script_generation_timeout_fix():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False
