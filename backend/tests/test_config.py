"""Tests for hybrid model-routing configuration (Option C) — the
creative_model/final_script_model/validation_model properties and their
fallback to openrouter_text_model when a specialized variable isn't set."""

from app.config import Settings


def test_creative_model_falls_back_to_text_model_when_unset():
    s = Settings(openrouter_text_model="google/gemini-2.5-flash", openrouter_creative_model="")
    assert s.creative_model == "google/gemini-2.5-flash"


def test_creative_model_uses_specialized_value_when_set():
    s = Settings(openrouter_text_model="google/gemini-2.5-flash", openrouter_creative_model="google/gemini-2.5-flash")
    assert s.creative_model == "google/gemini-2.5-flash"


def test_final_script_model_falls_back_to_text_model_when_unset():
    s = Settings(openrouter_text_model="google/gemini-2.5-flash", openrouter_final_script_model="")
    assert s.final_script_model == "google/gemini-2.5-flash"


def test_final_script_model_uses_pro_when_configured():
    s = Settings(openrouter_text_model="google/gemini-2.5-flash", openrouter_final_script_model="google/gemini-2.5-pro")
    assert s.final_script_model == "google/gemini-2.5-pro"


def test_validation_model_falls_back_to_text_model_when_unset():
    s = Settings(openrouter_text_model="google/gemini-2.5-flash", openrouter_validation_model="")
    assert s.validation_model == "google/gemini-2.5-flash"


def test_validation_model_uses_flash_lite_when_configured():
    s = Settings(
        openrouter_text_model="google/gemini-2.5-flash",
        openrouter_validation_model="google/gemini-2.5-flash-lite",
    )
    assert s.validation_model == "google/gemini-2.5-flash-lite"


def test_all_three_specialized_models_independently_configurable():
    s = Settings(
        openrouter_text_model="google/gemini-2.5-flash",
        openrouter_creative_model="google/gemini-2.5-flash",
        openrouter_final_script_model="google/gemini-2.5-pro",
        openrouter_validation_model="google/gemini-2.5-flash-lite",
    )
    assert s.creative_model == "google/gemini-2.5-flash"
    assert s.final_script_model == "google/gemini-2.5-pro"
    assert s.validation_model == "google/gemini-2.5-flash-lite"


def test_application_does_not_fail_when_specialized_vars_are_entirely_absent():
    """Simulates a deployment that never configured the new Option C
    variables at all — every property must still resolve to a usable model
    id (the pre-existing default text model), not raise or return empty."""
    s = Settings(openrouter_text_model="google/gemini-2.5-flash")
    assert s.creative_model
    assert s.final_script_model
    assert s.validation_model
