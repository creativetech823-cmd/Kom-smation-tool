"""claim_safety_service — the "Meri Maa Ki Dua" hard-gate fix (Task V4
Part 14, items 1-9 and 13). Deterministic checks are tested directly with
no mocking; semantic-layer checks mock generate_text — never a live call."""

import json
from unittest.mock import patch

import pytest

from app.services import claim_safety_service as css
from app.services import openrouter_utils


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _mock_semantic(implied=False, coercion=False, claim_evidence="", claim_reason="", coercion_evidence="", coercion_reason=""):
    return patch.object(css, "generate_text", return_value=json.dumps({
        "implied_claim": implied, "claim_evidence": claim_evidence, "claim_reason": claim_reason,
        "emotional_coercion": coercion, "coercion_evidence": coercion_evidence, "coercion_reason": coercion_reason,
    }))


# --- 1. Unsupported ingredient efficacy (deterministic, exact regression) ---


def test_unsupported_ingredient_efficacy_ashwagandha():
    text = "Ashwagandha, jo stress kam kare."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness", ingredients=["Ashwagandha", "Mulethi"])
    assert result.passed is False
    assert result.explicit_claim is True
    assert result.unsupported is True
    assert result.claim_type == "explicit_ingredient"
    assert "Ashwagandha" in result.evidence


def test_unsupported_ingredient_efficacy_mulethi():
    text = "Mulethi, saansein mehekaye."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness", ingredients=["Ashwagandha", "Mulethi"])
    assert result.passed is False
    assert result.claim_type == "explicit_ingredient"


# --- 2. Unsupported product efficacy -----------------------------------------


def test_unsupported_product_efficacy():
    text = "Yeh cravings kam kare, roz istemal kariye."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is False
    assert result.claim_type == "explicit_product"


# --- 3. Safe ingredient mention (no efficacy verb) — must NOT be flagged ----


def test_safe_ingredient_mention_passes():
    text = "Ismein hai Ashwagandha aur Mulethi, ek naya taste experience ke saath."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness", ingredients=["Ashwagandha", "Mulethi"])
    assert result.passed is True
    assert result.unsupported is False


# --- 4/5. Metaphorical / implied efficacy claim (semantic layer) ------------


def test_implied_narrative_efficacy_wilting_plant():
    text = "Ek murjhaya hua paudha. Fir Aayush Wellness aaya. Ab paudha khil raha hai."
    with _mock_semantic(implied=True, claim_evidence="wilting plant blooms after product appears", claim_reason="implies the product caused a health transformation"):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is False
    assert result.implied_claim is True
    assert result.claim_type == "implied_narrative"


def test_metaphorical_claim_with_no_health_outcome_is_not_flagged():
    # A metaphor about the PRODUCT'S IDENTITY/taste, no health/efficacy
    # outcome attached — must be allowed (Part 11: "visual metaphors that do
    # not imply unsupported efficacy").
    text = "Jaise subah ki pehli chai, Aayush Wellness bhi ek fresh start hai."
    with _mock_semantic(implied=False):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is True


# --- 6/8. Emotional coercion / devotional guilt framing ----------------------


def test_emotional_coercion_devotional_framing():
    text = "Maa ne dua maangi thi, aur aaj uski dua poori ho gayi — beta ne aakhir switch kar liya."
    with _mock_semantic(coercion=True, coercion_evidence="mother's prayer framed as fulfilled by product use", coercion_reason="devotional/guilt framing ties family approval to the purchase"):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is False
    assert result.emotional_coercion is True


def test_devotional_guilt_framing_child_causes_parent_suffering():
    text = "Beta ki aadat dekh kar maa roz royi thi, jab tak usne product try nahi kiya."
    with _mock_semantic(coercion=True, coercion_evidence="child's habit portrayed as cause of mother's suffering", coercion_reason="guilt used as primary persuasion"):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is False
    assert result.emotional_coercion is True


# --- 7. Legitimate family situation — must NOT be flagged --------------------


def test_legitimate_family_situation_passes():
    text = "Beta ne apni maa ko naya packet dikhaya. Maa ne muskura kar poocha, 'yeh kya hai?' Dono ne saath mein try kiya."
    with _mock_semantic(coercion=False):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is True
    assert result.emotional_coercion is False


# --- 9. Empty approved-claims data = default-safe, never permission --------


def test_empty_approved_claims_does_not_grant_permission():
    text = "Ashwagandha, jo stress kam kare."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(
            text, product_name="Aayush Wellness", ingredients=["Ashwagandha"], approved_claims=[],
        )
    assert result.passed is False  # empty approved_claims must NOT be read as "anything goes"


def test_claim_covered_by_genuinely_matching_approved_claim_passes():
    text = "Ashwagandha, jo stress kam kare."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(
            text, product_name="Aayush Wellness", ingredients=["Ashwagandha"],
            approved_claims=["Ashwagandha helps reduce stress (clinically studied)"],
        )
    assert result.passed is True  # a REAL given approved claim, not an empty default, covers it


# --- 13. Valid non-efficacy metaphor / product positioning ------------------


def test_product_positioning_without_unsupported_outcome_passes():
    text = "Yeh aapke liye best hai. Aaj hi try kariye, apna naya ritual banaiye."
    with _mock_semantic():
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is True


# --- Semantic-call-unavailable behavior (fail state, not silent pass-through)


def test_semantic_check_failure_does_not_crash_and_keeps_deterministic_clean_result():
    text = "Yeh aapke liye best hai."
    with patch.object(css, "generate_text", side_effect=RuntimeError("provider down")):
        result = css.check_claim_safety_and_coercion(text, product_name="Aayush Wellness")
    assert result.passed is True  # deterministic layer was clean; semantic layer genuinely unavailable
    assert result.checked_semantically is False
