"""Tests for the category-drift validator — the reusable, semantic (not
keyword-blacklist) check answering "does this treat the product according
to its real use case, or has it been reinterpreted?" Includes the exact
regression cases for the reported Herbal Masala failure."""

import json
from unittest.mock import patch

from app.services import product_context_validator as pcv
from app.services.product_context_service import (
    ROLE_RISK_FOOD_OR_COOKING_INGREDIENT,
    build_product_creative_contract,
)

HERBAL_MASALA_CONTRACT = build_product_creative_contract(
    product_name="Aayush Herbal Masala", category="herbal_health",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    usp="a 0% tobacco, 0% supari herbal chew that keeps the same ritual and taste",
    benefits=["same chewing ritual and mouth-freshening taste", "no tobacco or supari"],
)

SKINCARE_CONTRACT = build_product_creative_contract(
    product_name="AayushWellness Glow Face Serum", category="skincare",
    target_audience="working women with dull, tired-looking skin",
    usp="a lightweight daily serum", benefits=["brighter skin"],
)


# --- deterministic detector: exact regression cases from the failure report -


NEGATIVE_CASES = [  # must be detected as drift
    "What if main family ke favourite chicken curry mein yeh herbal masala daal doon, aur kisi ko pata bhi na chale?",
    "Sprinkle Aayush Herbal Masala into dal.",
    "Tonight I used it as a cooking seasoning.",
    "Two bowls of curry, one with Aayush Herbal Masala.",
    "Chef uses Aayush Herbal Masala in a recipe.",
]

POSITIVE_CASES = [  # must NOT be flagged — legitimate, category-correct
    "A person instinctively reaches for the place where their old gutka packet used to be.",
    "A friend notices someone has changed their usual chewing routine.",
    "A visual metaphor shows an old habit disappearing.",
    "A character is confronted with the familiar packet-versus-alternative choice.",
    "A humorous social situation revolves around someone trying to move away from their old gutka routine.",
]


def test_regression_reported_failure_cases_are_detected():
    for text in NEGATIVE_CASES:
        evidence = pcv.detect_category_drift_signal(text, HERBAL_MASALA_CONTRACT)
        assert evidence, f"expected drift signal for: {text!r}"


def test_regression_legitimate_cases_are_not_flagged():
    for text in POSITIVE_CASES:
        evidence = pcv.detect_category_drift_signal(text, HERBAL_MASALA_CONTRACT)
        assert evidence == "", f"unexpected drift flagged for legitimate text: {text!r} -> {evidence!r}"


def test_full_reported_script_text_is_detected_even_with_indirect_later_lines():
    full_script = (
        "What if main family ke favourite chicken curry mein yeh herbal masala daal doon, aur kisi ko "
        "pata bhi na chale? Dinner table par do bowls rakhe — 'A' aur 'B'. Bowl B..."
    )
    assert pcv.detect_category_drift_signal(full_script, HERBAL_MASALA_CONTRACT)


def test_mere_mention_of_family_dinner_or_kitchen_words_alone_does_not_trigger():
    """The detector checks a RELATIONSHIP (a cooking action/role), not a
    keyword list — 'family', 'dinner', 'kitchen', 'taste', 'masala' appearing
    without the product being given a food-preparation role must pass."""
    text = "Family dinner ke baad, kitchen mein baithe hue, usne apni purani habit ke baare mein socha — taste yaad aaya."
    assert pcv.detect_category_drift_signal(text, HERBAL_MASALA_CONTRACT) == ""


# --- registry gating: no role_risk_keys = detector never runs ---------------


def test_detector_never_runs_for_product_with_no_role_risk_keys():
    cooking_shaped_text = "Add this serum to your curry and cook it in the dal."
    assert pcv.detect_category_drift_signal(cooking_shaped_text, SKINCARE_CONTRACT) == ""


def test_detector_returns_empty_for_none_contract():
    assert pcv.detect_category_drift_signal("anything at all", None) == ""


# --- overcorrection guard: unrelated products aren't affected ---------------


def test_skincare_product_unaffected_by_food_detector_even_with_food_words():
    text = "She applies the serum every morning before breakfast, next to her coffee and kitchen counter."
    result = pcv.validate_category_alignment(text, SKINCARE_CONTRACT)
    assert result.passed is True
    assert result.category_drift is False


# --- combined validate_category_alignment: escalation + severity ------------


def test_validate_category_alignment_skips_llm_when_deterministic_clean():
    with patch.object(pcv, "call_openrouter_with_retry") as mock_call:
        result = pcv.validate_category_alignment("A person reaches for the familiar packet.", HERBAL_MASALA_CONTRACT)
    mock_call.assert_not_called()
    assert result.passed is True


def test_validate_category_alignment_escalates_to_llm_when_deterministic_fires():
    with patch.object(pcv, "call_openrouter_with_retry", return_value=json.dumps({
        "category_drift": True, "reason": "used as a cooking ingredient", "violations": ["added to curry"],
    })):
        result = pcv.validate_category_alignment(NEGATIVE_CASES[0], HERBAL_MASALA_CONTRACT)
    assert result.category_drift is True
    assert result.severity == "critical"
    assert result.passed is False


def test_validate_category_alignment_force_semantic_check_runs_llm_even_if_deterministic_clean():
    with patch.object(pcv, "call_openrouter_with_retry", return_value='{"category_drift": false, "reason": "", "violations": []}') as mock_call:
        result = pcv.validate_category_alignment(
            "A person reaches for the familiar packet.", HERBAL_MASALA_CONTRACT, force_semantic_check=True,
        )
    mock_call.assert_called_once()
    assert result.passed is True


def test_llm_check_never_raises_on_failure_treats_as_pass():
    with patch.object(pcv, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        result = pcv.llm_category_alignment_check(NEGATIVE_CASES[0], HERBAL_MASALA_CONTRACT)
    assert result.passed is True
    assert result.category_drift is False


def test_llm_check_returns_pass_for_none_contract():
    result = pcv.llm_category_alignment_check("anything", None)
    assert result.passed is True


def test_category_validation_result_as_dict_shape():
    result = pcv.CategoryValidationResult(passed=False, category_drift=True, reason="r", violations=["v"], severity="critical")
    d = result.as_dict()
    assert d == {"passed": False, "category_drift": True, "reason": "r", "violations": ["v"], "severity": "critical"}
