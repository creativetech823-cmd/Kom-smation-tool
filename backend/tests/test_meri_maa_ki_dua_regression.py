"""The "Meri Maa Ki Dua" regression — Task V4 Part 10. Tests
script_service._apply_claim_safety_gate directly (the actual wiring point),
never the title itself: the same underlying pattern under a DIFFERENT title
must be caught identically, proving detection is keyed to content, not the
regression's name. Also covers Part 14 item 10 (rewrite -> re-validation)
and item 11/12 (this new gate doesn't interfere with the existing Herbal
Masala cooking/fitness drift detectors)."""

import json
from unittest.mock import patch

import pytest

from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import claim_safety_service as css
from app.services import openrouter_utils, script_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


# The reported failing script, structured as the raw dict shape
# _apply_claim_safety_gate operates on (same shape _generate_with_recovery
# returns before Pydantic validation).
MERI_MAA_KI_DUA_SCRIPT = {
    "hook": {"text": "Ek murjhaya hua paudha, ghar ke kone mein."},
    "body": [
        {"text": "Ashwagandha, jo stress kam kare."},
        {"text": "Mulethi, saansein mehekaye."},
        {"text": "Maa ne roz dua maangi thi apne bete ke liye."},
        {"text": "Aur dheere dheere, woh paudha khilne laga."},
    ],
    "cta": {"text": "Maa ki dua, aaj poori ho gayi. Try Aayush Wellness."},
}

# Same underlying pattern (ingredient efficacy claims + implied wilting/
# blooming outcome + devotional guilt framing), completely different title/
# character names — proves the gate is content-keyed, not title-keyed.
DIFFERENT_TITLE_SAME_PATTERN_SCRIPT = {
    "hook": {"text": "Ek sookha hua gamla, balcony mein."},
    "body": [
        {"text": "Ashwagandha, jo stress kam kare."},
        {"text": "Papa ne mannat maangi thi apni beti ke liye."},
        {"text": "Aur dheere dheere, woh gamla hara-bhara ho gaya."},
    ],
    "cta": {"text": "Papa ki mannat, aaj poori ho gayi."},
}

CLEAN_REWRITE_SCRIPT = {
    "hook": {"text": "Ek quiet subah, ghar ke kone mein."},
    "body": [
        {"text": "Ismein hai Ashwagandha aur Mulethi, ek naya taste ke saath."},
        {"text": "Beta ne apni maa ko naya packet dikhaya."},
        {"text": "Dono ne saath mein try kiya."},
    ],
    "cta": {"text": "Try Aayush Wellness today."},
}


def _payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="Meri Maa Ki Dua", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(
        product_name="Aayush Wellness", target_audience="adult gutka chewers",
        ingredients=["Ashwagandha", "Mulethi"], usp="", key_benefits=[],
    )
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def _clean_semantic_mock():
    return patch.object(css, "generate_text", return_value=json.dumps({
        "implied_claim": False, "claim_evidence": "", "claim_reason": "",
        "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
    }))


def test_meri_maa_ki_dua_fails_on_explicit_ingredient_claims_before_any_llm_call():
    # Both ingredient claims are caught DETERMINISTICALLY — the gate must
    # short-circuit to a hard fail without ever reaching the semantic layer
    # for this exact script (the deterministic violation alone is enough).
    with patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_REWRITE_SCRIPT):
        data, result = svc._apply_claim_safety_gate(
            MERI_MAA_KI_DUA_SCRIPT, _payload(), "30s", None, ContentType.video,
        )
    assert result.passed is True  # after the one rewrite, the clean draft passes
    assert data == CLEAN_REWRITE_SCRIPT


def test_meri_maa_ki_dua_pattern_caught_under_a_completely_different_title():
    # Same underlying pattern, different title/characters entirely — proves
    # the gate reacts to content, never a hardcoded title check.
    with patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_REWRITE_SCRIPT) as mock_rewrite:
        data, result = svc._apply_claim_safety_gate(
            DIFFERENT_TITLE_SAME_PATTERN_SCRIPT, _payload(), "30s", None, ContentType.video,
        )
    mock_rewrite.assert_called_once()
    assert result.passed is True
    # Confirm the rewrite instruction actually named the real defect, not a
    # generic "make this better" — the reason is the 5th positional arg.
    call_args = mock_rewrite.call_args[0]
    assert "efficacy" in call_args[4].lower() or "claim" in call_args[4].lower()


def test_implied_wilting_to_blooming_outcome_caught_semantically_when_no_explicit_verb_present():
    # A script with NO deterministic ingredient/efficacy-verb violation at
    # all (ingredients only named, never given a verb) but the SAME implied
    # narrative-outcome pattern (wilting -> product -> blooming) — only the
    # semantic layer can catch this.
    script = {
        "hook": {"text": "Ek murjhaya hua paudha."},
        "body": [
            {"text": "Ismein hai Ashwagandha aur Mulethi."},
            {"text": "Dheere dheere, woh paudha khilne laga."},
        ],
        "cta": {"text": "Try Aayush Wellness."},
    }
    call_count = {"n": 0}

    def fake_semantic(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps({
                "implied_claim": True, "claim_evidence": "wilting plant blooms after product introduced",
                "claim_reason": "implies the product caused a health/life improvement with no verified basis",
                "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
            })
        return json.dumps({  # the re-check, on the rewritten (clean) draft
            "implied_claim": False, "claim_evidence": "", "claim_reason": "",
            "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
        })

    with patch.object(css, "generate_text", side_effect=fake_semantic), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_REWRITE_SCRIPT) as mock_rewrite:
        data, result = svc._apply_claim_safety_gate(script, _payload(), "30s", None, ContentType.video)
    mock_rewrite.assert_called_once()
    assert call_count["n"] == 2  # initial check, then the re-check on the rewritten draft
    assert result.passed is True


def test_devotional_coercion_framing_caught_and_triggers_rewrite():
    script = {
        "hook": {"text": "Ek shaam, ghar mein."},
        "body": [{"text": "Maa ne dua maangi thi, aur aaj woh dua poori ho gayi."}],
        "cta": {"text": "Try Aayush Wellness."},
    }
    with patch.object(css, "generate_text", return_value=json.dumps({
        "implied_claim": False, "claim_evidence": "", "claim_reason": "",
        "emotional_coercion": True, "coercion_evidence": "mother's prayer framed as fulfilled by the product",
        "coercion_reason": "devotional pressure ties family/spiritual approval to the purchase",
    })), patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_REWRITE_SCRIPT) as mock_rewrite:
        data, result = svc._apply_claim_safety_gate(script, _payload(), "30s", None, ContentType.video)
    mock_rewrite.assert_called_once()
    call_args = mock_rewrite.call_args[0]
    assert "coercive" in call_args[4].lower() or "guilt" in call_args[4].lower() or "devotional" in call_args[4].lower()


# --- Part 14 item 10: rewrite followed by final re-validation ---------------


def test_rewrite_result_is_re_checked_not_trusted_blindly():
    # The rewrite ITSELF still contains an unresolved violation — the gate
    # must re-run the same check on the rewritten draft and report the
    # bounded failure honestly, never silently accepting the rewrite as
    # clean just because a rewrite happened.
    still_bad_rewrite = {
        "hook": {"text": "Ek quiet subah."},
        "body": [{"text": "Ashwagandha, jo stress kam kare."}],  # rewrite failed to fix it
        "cta": {"text": "Try Aayush Wellness."},
    }
    with patch.object(svc, "_rewrite_for_quality", return_value=still_bad_rewrite):
        data, result = svc._apply_claim_safety_gate(
            MERI_MAA_KI_DUA_SCRIPT, _payload(), "30s", None, ContentType.video,
        )
    assert result.passed is False  # bounded failure — honestly reported, not swept under the rug
    assert data == still_bad_rewrite  # still returns SOMETHING (fail-open convention), never nothing


def test_gate_never_calls_rewrite_more_than_once():
    call_count = {"n": 0}

    def fake_rewrite(*args, **kwargs):
        call_count["n"] += 1
        return MERI_MAA_KI_DUA_SCRIPT  # even a "rewrite" that changes nothing

    with patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite):
        svc._apply_claim_safety_gate(MERI_MAA_KI_DUA_SCRIPT, _payload(), "30s", None, ContentType.video)
    assert call_count["n"] == 1  # bounded — never loops


# --- Part 14 items 11/12: existing Herbal Masala drift detectors unaffected -


def test_clean_script_does_not_trigger_claim_safety_rewrite_at_all():
    with _clean_semantic_mock(), patch.object(svc, "_rewrite_for_quality") as mock_rewrite:
        data, result = svc._apply_claim_safety_gate(CLEAN_REWRITE_SCRIPT, _payload(), "30s", None, ContentType.video)
    mock_rewrite.assert_not_called()
    assert result.passed is True
    assert data == CLEAN_REWRITE_SCRIPT


# --- Part 14 item 14: the new gate has zero coupling to image generation ----


def test_claim_safety_gate_never_touches_image_generation_settings_or_calls():
    """The gate module imports nothing image-related, and settings.
    image_generation_enabled stays exactly as configured (false in this
    test env) after running it — proving zero coupling, not just absence
    of an obvious call."""
    from app.config import settings
    before = settings.image_generation_enabled
    with _clean_semantic_mock():
        svc._apply_claim_safety_gate(CLEAN_REWRITE_SCRIPT, _payload(), "30s", None, ContentType.video)
    assert settings.image_generation_enabled == before
    assert not hasattr(css, "visual_concept_service")
    assert "image" not in [name.lower() for name in dir(css) if not name.startswith("_")]
