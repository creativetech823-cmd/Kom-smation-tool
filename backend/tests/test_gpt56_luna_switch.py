"""GPT-5.6 Luna cost-experiment (2026-09-18 task) — verifies the model
SWITCH itself: OpenRouter remains the sole gateway, creative/final-script
stages resolve to openai/gpt-5.6-luna, no direct OpenAI SDK was introduced,
and no stage can silently fall back to a different model.

Follow-up pre-commit fix (same day): validation stays on
google/gemini-2.5-flash-lite (Claim Safety semantic check, Semantic Story
Judge, quality-gate semantic check, product-context validator) — an
EXPLICIT, intentional exception, not a leftover/silent Gemini fallback (see
OPENROUTER_VALIDATION_MODEL in .env, now active rather than commented out).
Tests below assert this split deliberately, not "everything is Luna".

Does NOT re-test creative-system behavior itself (claim safety logic, hook
tactic logic, Creative Director scoring, etc.) — that's already covered by
their own dedicated test files, all still green after this switch since none
of that logic changed, only which model string is configured."""

import re
from pathlib import Path

from app.config import Settings, settings
from app.services import (
    architecture_validation_service as arch_val,
    claim_safety_service as css,
    hook_generation_service as hooksvc,
    openrouter_utils as oru,
    semantic_story_judge_service as sj,
    story_situation_service as svc,
)

APP_DIR = Path(__file__).parent.parent / "app"


# --- 1. Active model is exactly openai/gpt-5.6-luna -------------------------


def test_active_text_model_is_exactly_gpt56_luna():
    assert settings.openrouter_text_model == "openai/gpt-5.6-luna"


def test_creative_and_final_script_resolve_to_luna_validation_stays_gemini_flash_lite():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_settings_class_explicit_split_config_resolves_correctly():
    """The general resolution mechanism (not just the live .env) supports
    creative/final_script explicitly pinned to Luna while validation is
    explicitly pinned to a different model — proves this isn't a coincidence
    of what happens to be in .env right now."""
    s = Settings(
        openrouter_text_model="openai/gpt-5.6-luna",
        openrouter_creative_model="openai/gpt-5.6-luna",
        openrouter_final_script_model="openai/gpt-5.6-luna",
        openrouter_validation_model="google/gemini-2.5-flash-lite",
    )
    assert s.creative_model == "openai/gpt-5.6-luna"
    assert s.final_script_model == "openai/gpt-5.6-luna"
    assert s.validation_model == "google/gemini-2.5-flash-lite"


# --- 2/5. Active provider remains OpenRouter, auth via OPENROUTER_API_KEY --


def test_openrouter_client_still_uses_openrouter_api_key_header():
    oru.reset_openrouter_client()
    try:
        client = oru.get_openrouter_client()
        auth_header = client.headers.get("authorization", "")
        assert auth_header.startswith("Bearer ")
    finally:
        oru.reset_openrouter_client()


def test_openrouter_base_url_unchanged():
    assert oru._BASE_URL == "https://openrouter.ai/api/v1"


def test_settings_has_no_openai_api_key_field():
    assert not hasattr(settings, "openai_api_key")


# --- 3. No active Gemini text model is selected ------------------------------


def test_no_gemini_model_string_in_luna_pinned_routing():
    """Creative/final-script/base-text must have no Gemini string — the
    validation stage is the one EXPLICIT, intentional exception (checked
    separately below), not a gap in this assertion."""
    for value in (settings.openrouter_text_model, settings.creative_model, settings.final_script_model):
        assert "gemini" not in value.lower()


def test_validation_model_is_the_one_explicit_gemini_exception():
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_env_file_has_old_gemini_pro_and_flash_routing_commented_out_not_deleted():
    """Part 4: preserve for rollback — comment out, never delete. Only the
    old CREATIVE(flash)/FINAL_SCRIPT(pro)/TEXT(flash) Gemini routing is
    commented out now — VALIDATION_MODEL's Gemini Flash-Lite line is
    deliberately ACTIVE (the explicit split-model config), not commented."""
    env_text = (Path(__file__).parent.parent / ".env").read_text(encoding="utf-8")
    assert "# OPENROUTER_TEXT_MODEL=google/gemini-2.5-flash" in env_text
    assert "# OPENROUTER_CREATIVE_MODEL=google/gemini-2.5-flash" in env_text
    assert "# OPENROUTER_FINAL_SCRIPT_MODEL=google/gemini-2.5-pro" in env_text
    # And not active (no un-commented duplicate of the same assignment).
    assert not re.search(r"^OPENROUTER_TEXT_MODEL=google/gemini", env_text, re.MULTILINE)
    assert not re.search(r"^OPENROUTER_CREATIVE_MODEL=google/gemini", env_text, re.MULTILINE)
    assert not re.search(r"^OPENROUTER_FINAL_SCRIPT_MODEL=google/gemini", env_text, re.MULTILINE)
    # The validation line IS active and uncommented.
    assert re.search(r"^OPENROUTER_VALIDATION_MODEL=google/gemini-2\.5-flash-lite", env_text, re.MULTILINE)


# --- 4. No direct OpenAI SDK integration introduced --------------------------


def test_no_openai_sdk_import_anywhere_in_app():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^\s*(import openai\b|from openai\b)", text, re.MULTILINE):
            offenders.append(str(path))
    assert offenders == []


def test_openai_not_in_requirements():
    req_path = Path(__file__).parent.parent / "requirements.txt"
    if not req_path.exists():
        return
    text = req_path.read_text(encoding="utf-8").lower()
    assert not re.search(r"^openai\b", text, re.MULTILINE)


# --- 6. All text-generation stages resolve to Luna (via the shared props) --


def test_hook_generation_service_uses_creative_model():
    import inspect
    src = inspect.getsource(hooksvc.generate_and_select_hook)
    assert "settings.creative_model" in inspect.getsource(hooksvc)
    assert settings.creative_model == "openai/gpt-5.6-luna"


def test_claim_safety_service_resolves_to_validation_model_gemini_flash_lite():
    import inspect
    assert "settings.validation_model" in inspect.getsource(css)
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_semantic_story_judge_resolves_to_validation_model_gemini_flash_lite():
    import inspect
    assert "settings.validation_model" in inspect.getsource(sj)
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_creative_director_resolves_to_luna():
    import inspect
    assert "settings.final_script_model" in inspect.getsource(arch_val)
    assert settings.final_script_model == "openai/gpt-5.6-luna"


def test_story_situation_service_resolves_to_luna():
    import inspect
    assert "settings.creative_model" in inspect.getsource(svc)
    assert settings.creative_model == "openai/gpt-5.6-luna"


# --- 11. No silent model fallback --------------------------------------------


def test_call_openrouter_with_retry_never_changes_the_model_across_attempts():
    """The retry wrapper calls the SAME closure every attempt — it has no
    code path that swaps `model` to a different value on failure. Verified
    by construction: fn() is called unmodified up to max_attempts times."""
    from unittest.mock import patch

    calls = []

    def fn():
        calls.append(1)
        raise oru.EmptyResponseError("empty", diagnostics={"model": "openai/gpt-5.6-luna"})

    with patch("time.sleep", return_value=None):
        try:
            oru.call_openrouter_with_retry(fn, label="test_stage", max_attempts=3)
        except ValueError:
            pass
    assert len(calls) == 3  # every attempt was the identical fn — no model substitution anywhere


def test_classify_error_never_suggests_falling_back_to_a_different_model():
    reason = oru.classify_error(oru.EmptyResponseError("x", diagnostics={"model": "openai/gpt-5.6-luna"}))
    assert "gemini" not in reason.lower()
    assert "fallback" not in reason.lower() and "falling back" not in reason.lower()


# --- 13. Image generation remains disabled -----------------------------------


def test_image_generation_still_disabled_during_this_experiment():
    assert settings.image_generation_enabled is False


def test_image_model_routing_untouched_by_the_text_model_switch():
    """openrouter_image_model is a separate config axis from
    openrouter_text_model — the Luna switch must not have touched it."""
    assert settings.openrouter_image_model != settings.openrouter_text_model
    assert "gemini" in settings.openrouter_image_model.lower()  # unchanged, still Gemini image model
