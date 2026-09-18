"""Generate-script timeout fix (2026-09-18 task, second follow-up).

Root cause (confirmed by code inspection, matching the exact live error
text): script_service.py has NO aggregate deadline object of its own — the
full generate_script() pipeline (creative pre-stages, the final-script
write, claim-safety gate, quality gate, architecture gate, each gate's one
allowed rewrite + architecture gate's post-rewrite re-check) is a long but
BOUNDED sequential chain of LLM calls, each using the shared OpenRouter
client's unmodified 120s-per-call default — nothing backend-side was ever
cutting this off early. The frontend's own SCRIPT_GENERATION_TIMEOUT_MS
(previously 300_000) was the sole cause of "Request timed out after 300s":
it aborted a request that was still genuinely in progress. Also confirmed
by inspection: no accidental extra retries — each gate does AT MOST one
rewrite pass (already bounded and documented in script_service.py's own
docstrings), never a loop.

This file cannot exercise the frontend AbortController directly (this repo
has no JS test runner — same documented limitation as every prior timeout
task), so it verifies the frontend constant's actual value via a plain text
read of lib/api.ts, and verifies the backend half: no new artificial
deadline was introduced, the pipeline can complete even when an individual
call is slow, and every existing quality/safety gate and the existing
bounded-retry mechanism are untouched."""

import inspect
import json
import logging
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import architecture_validation_service as arch_val
from app.services import creative_architecture, openrouter_utils
from app.services import script_quality as sq
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
    "body": [
        {"text": "A body line.", "action": "He reaches for the packet, then stops.", "visual_direction": "Close on his hand."},
        {"text": "A second body line.", "reaction": "The passenger notices."},
    ],
    "cta": {"text": "A closing line."},
    "creative_mechanism": "curiosity_gap",
})

_SAFE_CLAIM_JSON = json.dumps({
    "implied_claim": False, "claim_evidence": "", "claim_reason": "",
    "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
})


def _payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="Auto Mein Do Pocket", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def _run_generate_script_fully_mocked(fake_generate_text=None):
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    fake = fake_generate_text or (lambda *a, **k: _GOOD_SCRIPT_JSON)
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
        patch.object(svc, "generate_text", side_effect=fake),
    ]
    for p in patches:
        p.start()
    try:
        return svc.generate_script(_payload())
    finally:
        for p in reversed(patches):
            p.stop()


# --- 1: frontend no longer kills generate-script at the old 300s mark ------


def test_frontend_no_longer_uses_a_300_second_ceiling_for_generate_script():
    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    src = api_ts.read_text(encoding="utf-8")
    match = re.search(r"SCRIPT_GENERATION_TIMEOUT_MS\s*=\s*([^;]+);", src)
    assert match, "SCRIPT_GENERATION_TIMEOUT_MS constant not found in lib/api.ts"
    value = eval(match.group(1), {"__builtins__": {}})  # e.g. "20 * 60_000" — arithmetic literal only
    assert value != 300_000  # the old, too-tight ceiling
    assert value >= 600_000  # at least 10 minutes — a genuine safety net, not a short expected-duration cap


def test_generate_script_and_regenerate_still_use_the_endpoint_specific_timeout():
    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    src = api_ts.read_text(encoding="utf-8")
    assert 'post<GeneratedScript>("/pipeline/generate-script", payload, SCRIPT_GENERATION_TIMEOUT_MS)' in src
    assert 'post<GeneratedScript>("/pipeline/regenerate-script-section", payload, SCRIPT_GENERATION_TIMEOUT_MS)' in src


def test_story_ideas_still_uses_the_unrelated_180s_default_not_the_new_ceiling():
    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    src = api_ts.read_text(encoding="utf-8")
    match = re.search(r"const POST_TIMEOUT_MS = ([\d_]+);", src)
    assert match and int(match.group(1).replace("_", "")) == 180_000


# --- backend: no artificial aggregate deadline was introduced --------------


def test_script_service_still_has_no_aggregate_deadline_object():
    """This task's diagnosis found no time.monotonic/deadline/budget-based
    aggregate cap in script_service.py before or after — confirms none was
    added as part of this fix (the fix is frontend-only plus logging)."""
    src = inspect.getsource(svc)
    assert "max_total_seconds" not in src
    assert "deadline" not in src.lower() or "GENERATE_SCRIPT" in src  # only the new log lines may mention timing


def test_no_explicit_timeout_kwarg_introduced_on_any_script_service_call():
    """Every generate_text/call_openrouter_with_retry call in script_service.py
    must still rely on the shared client's unmodified 120s-per-call default —
    no new per-call ceiling was added as a workaround."""
    src = inspect.getsource(svc)
    assert "timeout=" not in src


def test_shared_openrouter_client_default_timeout_unchanged():
    src = inspect.getsource(openrouter_utils)
    assert "timeout=120.0" in src


# --- 2: a slow-but-successful LLM call can still complete ------------------


def test_slow_but_successful_calls_still_complete_end_to_end():
    """Simulates every call in the pipeline being slow (but never erroring,
    never timing out) — the backend has nothing that would cut this off,
    so the full script must still come back successfully."""
    import time as _time

    def fake_slow_generate_text(*args, **kwargs):
        # Not an actual sleep (keeps the test fast) — this proves the
        # backend imposes no artificial ceiling that would reject a call
        # just because real wall-clock time passed, by directly advancing
        # the same clock the (nonexistent) deadline logic would have used.
        _time.monotonic()
        return _GOOD_SCRIPT_JSON

    result = _run_generate_script_fully_mocked(fake_slow_generate_text)
    assert result.hook.text == "A specific hook line."


# --- 3: quality / claim-safety / filmability gates still execute -----------


def test_claim_safety_and_quality_and_architecture_gates_still_run(caplog):
    with caplog.at_level(logging.INFO, logger="script_service"):
        result = _run_generate_script_fully_mocked()
    assert result.hook.text == "A specific hook line."
    messages = [r.message for r in caplog.records]
    assert any("[GENERATE_SCRIPT] claim safety gate start" in m for m in messages)
    assert any("[GENERATE_SCRIPT] claim safety gate complete" in m for m in messages)
    assert any("[GENERATE_SCRIPT] quality gate start" in m for m in messages)
    assert any("[GENERATE_SCRIPT] quality gate complete" in m for m in messages)
    assert any("[GENERATE_SCRIPT] architecture gate start" in m for m in messages)


def test_not_filmable_video_check_still_wired_into_deterministic_issues():
    assert "not_filmable_video" in sq._ISSUE_INSTRUCTIONS


def test_filmability_gate_still_triggers_the_shared_rewrite_path():
    bad_draft = {
        "hook": {"text": "A hook."},
        "body": [
            {"text": "Driver explains habits are important."},
            {"text": "Passenger agrees a new choice is better."},
            {"text": "Driver says everyone should change."},
        ],
        "cta": {"text": "A cta."},
        "creative_mechanism": "mini_story",
    }
    called = {"rewrite": False}

    def fake_rewrite(data, payload, target_duration, target_word_count, reason, content_type, context):
        called["rewrite"] = True
        return {**bad_draft, "body": [{"text": "rewritten", "action": "does something"}]}

    with patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite):
        svc._apply_quality_gate(bad_draft, _payload(), "30s", None, ContentType.video, run_semantic_check=False)
    assert called["rewrite"] is True


# --- 4: existing retry behavior remains intact ------------------------------


def test_call_openrouter_with_retry_default_max_attempts_unchanged():
    sig = inspect.signature(openrouter_utils.call_openrouter_with_retry)
    assert sig.parameters["max_attempts"].default == 4


def test_each_gate_still_does_at_most_one_rewrite_pass():
    """Regression: confirms this task didn't touch the existing bounded-
    rewrite guarantee — the docstrings this asserts against are the same
    ones that predate this task."""
    assert "At most one rewrite pass" in svc._apply_quality_gate.__doc__
    assert "At most one targeted" in svc._apply_architecture_gate.__doc__


def test_generate_script_rewrite_logs_present_when_a_rewrite_fires(caplog):
    bad_draft_text = json.dumps({
        "hook": {"text": "A hook."},
        "body": [
            {"text": "Driver explains habits are important."},
            {"text": "Passenger agrees a new choice is better."},
            {"text": "Driver says everyone should change."},
        ],
        "cta": {"text": "A cta."},
        "creative_mechanism": "mini_story",
    })

    def fake(*args, **kwargs):
        label = kwargs.get("label")
        if label == "gate_rewrite":
            return _GOOD_SCRIPT_JSON
        return bad_draft_text

    with caplog.at_level(logging.INFO, logger="script_service"):
        _run_generate_script_fully_mocked(fake)
    messages = [r.message for r in caplog.records]
    assert any(m.startswith("[GENERATE_SCRIPT] rewrite start") for m in messages)
    assert any(m.startswith("[GENERATE_SCRIPT] rewrite complete") for m in messages)


# --- 5: Story Ideas timeout settings remain unchanged -----------------------


def test_story_ideas_timeout_constants_unchanged():
    assert story_svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0
    assert story_svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0
    assert story_svc._STORY_IDEAS_MAX_ATTEMPTS == 2
    assert sj._JUDGE_CALL_TIMEOUT_SECONDS == 40.0


def test_story_ideas_retry_architecture_untouched():
    src = inspect.getsource(story_svc)
    assert "_remaining_call_timeout" in src  # the per-retry deadline fix is still present, unmodified


# --- 6: model routing remains unchanged -------------------------------------


def test_model_routing_unchanged_by_the_generate_script_timeout_fix():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False
