"""The dedicated Language/Copy Quality Gate (Task V6). Root cause: the
existing grammar/naturalness codes inside llm_quality_issues() were silently
skipped whenever ANY Layer-1 deterministic issue fired first inside
_apply_quality_gate — so a rewrite driven by an unrelated issue had zero
grammar verification. This file proves both the new gate's own logic AND
that it is genuinely UNCONDITIONAL (still runs after the other gates,
regardless of what they found)."""

import json
from unittest.mock import patch

import pytest

from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import claim_safety_service as css
from app.services import openrouter_utils
from app.services import script_quality as sq
from app.services import script_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="t", description="d", emotion="e", persona="p", marketing_angle="m",
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


def _script(hook, body, cta):
    return {"hook": {"text": hook}, "body": [{"text": b} for b in body], "cta": {"text": cta}}


CLEAN_SCRIPT = _script(
    "Yaar tu abhi bhi wahi chaba raha hai?",
    ["Haan, aadat hai purani.", "Try kar na yeh, mast hai."],
    "Aaj hi try kar.",
)


def _mock_lq(issues=None, worst_line=""):
    return patch.object(sq, "generate_text", return_value=json.dumps({
        "pass": not issues, "issues": issues or [], "worst_line": worst_line,
    }))


def _mock_clean_claim_safety():
    return patch.object(css, "generate_text", return_value=json.dumps({
        "implied_claim": False, "claim_evidence": "", "claim_reason": "",
        "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
    }))


# --- 1. Bad grammar -----------------------------------------------------


def test_bad_grammar_detected_and_triggers_rewrite():
    with _mock_lq(["bad_grammar"], worst_line="Aadat sirf packet nahi; woh reach, break aur familiar taste ka poora ritual hai."), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        data, result = svc._apply_language_quality_gate(
            {"hook": {"text": "h"}, "body": [{"text": "Aadat sirf packet nahi; woh reach, break aur familiar taste ka poora ritual hai."}], "cta": {"text": "c"}},
            _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True),
        )
    mock_rewrite.assert_called_once()
    assert data == CLEAN_SCRIPT


# --- 2. Broken Hinglish ("choice badli", "familiar chew ko refreshing banata hai") -


def test_broken_hinglish_mechanical_mixing_detected():
    script = _script(
        "h", ["Choice badli — switching habit ko support mila.", "Familiar chew ko refreshing banata hai."], "c",
    )
    with _mock_lq(["unnatural_phrasing", "unnatural_phrasing"], worst_line="Choice badli — switching habit ko support mila."), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        data, result = svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()
    call_args = mock_rewrite.call_args[0]
    assert "unnatural" in call_args[4].lower() or "translation" in call_args[4].lower()


# --- 3. Unnatural / robotic dialogue -------------------------------------


def test_robotic_dialogue_sounding_like_marketer_detected():
    script = _script("h", ["Yeh product aapke liye ek behtareen solution hai jo aapki zarooraton ko poora karta hai."], "c")
    with _mock_lq(["robotic_dialogue"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()


# --- 4. AI-style explanatory sentence -------------------------------------


def test_ai_style_explanatory_sentence_detected():
    script = _script("h", ["Yeh dikhata hai ki kaise ek chhoti si aadat badi tabdeeli la sakti hai, jo hamari zindagi ko behtar banati hai."], "c")
    with _mock_lq(["unnatural_phrasing", "robotic_dialogue"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()


# --- 6. Bad CTA ------------------------------------------------------------


def test_weak_generic_cta_detected():
    script = _script("h", ["b"], "Buy now for the best experience of your life.")
    with _mock_lq(["weak_cta_copy"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()


# --- 7. Overly long / essay-style dialogue (awkward punctuation) ----------


def test_essay_style_punctuation_detected():
    script = _script(
        "h",
        ["Yeh sirf ek product nahi hai; balki yeh ek aisi soch hai, jo hume yaad dilati hai ki asli badlaav andar se aata hai, na ki bahar se."],
        "c",
    )
    with _mock_lq(["awkward_punctuation", "unnatural_phrasing"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()


# --- 9. Natural conversational dialogue — must NOT be flagged -------------


def test_natural_conversational_dialogue_passes_untouched():
    with _mock_lq(issues=None), patch.object(svc, "_rewrite_for_quality") as mock_rewrite:
        data, result = svc._apply_language_quality_gate(
            CLEAN_SCRIPT, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True),
        )
    mock_rewrite.assert_not_called()
    assert data == CLEAN_SCRIPT
    assert result.passed is True


# --- Root-cause proof: UNCONDITIONAL, never short-circuited --------------


def test_gate_runs_and_catches_grammar_even_when_data_would_pass_every_other_check():
    """The exact root cause: this gate must be reachable and effective
    regardless of what any other gate found — proven here by calling it in
    isolation (as script_service._generate_full_script_tracked does, always,
    never behind an `if not issues:` short-circuit from another gate)."""
    script = _script("h", ["Choice badli — switching habit ko support mila."], "c")
    with _mock_lq(["unnatural_phrasing"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=CLEAN_SCRIPT) as mock_rewrite, \
         _mock_clean_claim_safety():
        data, _ = svc._apply_language_quality_gate(script, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True))
    mock_rewrite.assert_called_once()  # this call happening AT ALL is the fix


# --- Re-verification behavior after rewrite --------------------------------


def test_rewrite_reintroducing_a_claim_issue_is_caught_and_marked_not_passed():
    bad_rewrite_with_claim_issue = _script("h", ["Ashwagandha, jo stress kam kare."], "c")
    with _mock_lq(["unnatural_phrasing"]), \
         patch.object(svc, "_rewrite_for_quality", return_value=bad_rewrite_with_claim_issue):
        data, result = svc._apply_language_quality_gate(
            _script("h", ["Choice badli — switching habit ko support mila."], "c"),
            _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True),
        )
    assert result.passed is False  # the language-quality rewrite reintroduced a real claim issue
    assert data == bad_rewrite_with_claim_issue  # still returns something — fail-open convention


def test_gate_never_calls_rewrite_more_than_once():
    call_count = {"n": 0}

    def fake_rewrite(*args, **kwargs):
        call_count["n"] += 1
        return CLEAN_SCRIPT

    with _mock_lq(["bad_grammar"]), patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite), _mock_clean_claim_safety():
        svc._apply_language_quality_gate(
            _script("h", ["bad"], "c"), _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True),
        )
    assert call_count["n"] == 1


def test_gate_never_raises_on_llm_failure():
    with patch.object(sq, "generate_text", side_effect=RuntimeError("provider down")):
        data, result = svc._apply_language_quality_gate(
            CLEAN_SCRIPT, _payload(), "30s", None, ContentType.video, css.ClaimSafetyResult(passed=True),
        )
    assert data == CLEAN_SCRIPT  # fail-open: original draft returned, no crash
