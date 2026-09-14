"""Layer 2 (contextual) + end-to-end audit_script tests. The OpenRouter call
is mocked — these tests never hit the network or spend API credits."""

import json
from unittest.mock import patch

import pytest

from app.models.product import ComplianceCheckInput, StructuredProduct
from app.services import compliance_service


def _input(script_text: str, structured_product: StructuredProduct | None = None) -> ComplianceCheckInput:
    return ComplianceCheckInput(
        script_text=script_text,
        product_category="wellness",
        product_name="Men's Strength & Vitality Kit",
        structured_product=structured_product,
    )


def _mock_llm(response_dict: dict):
    """Patches the OpenRouter call site so audit_script's Layer 2 path
    returns a canned response instead of making a real request."""
    return patch.object(
        compliance_service,
        "call_openrouter_with_retry",
        lambda fn, **kwargs: json.dumps(response_dict),
    )


def test_deterministic_block_never_calls_the_llm():
    """A clear guaranteed-outcome claim should be blocked by Layer 1 alone
    — Layer 2 must not be invoked (no wasted API call)."""
    with patch.object(compliance_service, "call_openrouter_with_retry") as mock_call:
        result = compliance_service.audit_script(_input("Guaranteed to increase stamina."))
    mock_call.assert_not_called()
    assert result.passed is False
    assert any(v.severity == "blocker" for v in result.violations)


def test_creative_tagline_passes_via_contextual_layer():
    """'New strength, new finish line.' has no deterministic hit, so Layer 2
    runs; the (mocked) contextual model correctly reads it as PASS."""
    with _mock_llm({"status": "PASS", "findings": []}):
        result = compliance_service.audit_script(_input("New strength, new finish line."))
    assert result.passed is True
    assert result.violations == []


def test_medium_severity_finding_maps_to_needs_review_not_blocked():
    # "Boosts your stamina." is a specific-but-unverified benefit claim
    # (taxonomy category E) — a defensible MEDIUM, unlike a soft/aspirational
    # phrase such as "Supports your active routine." which the V2.1 prompt
    # now calibrates toward PASS (see test_creative_tagline_passes_via_contextual_layer).
    llm_response = {
        "status": "NEEDS_REVIEW",
        "findings": [
            {
                "phrase": "Boosts your stamina.",
                "type": "PERFORMANCE_CLAIM",
                "severity": "MEDIUM",
                "reason": "A specific benefit claim that's plausible but not verified against supplied product data.",
                "suggested_fix": "Designed to support an active daily routine.",
            }
        ],
    }
    with _mock_llm(llm_response):
        result = compliance_service.audit_script(_input("Boosts your stamina."))
    assert result.passed is True  # NEEDS_REVIEW must not force a block
    assert len(result.violations) == 1
    assert result.violations[0].severity == "warning"
    assert result.violations[0].suggested_fix == "Designed to support an active daily routine."


def test_misleading_comparative_claim_is_caught_deterministically():
    result = compliance_service.audit_script(_input("India's #1 wellness product."))
    assert result.passed is False
    assert any(v.claim_type == "MISLEADING_COMPARATIVE_CLAIM" for v in result.violations)


def test_grounding_strength_stronger_than_supplied_data_still_blocks():
    """Rule 9/10: product data can support a matching claim but must never
    launder a stronger one. 'Provides unlimited energy all day.' goes well
    beyond a supplied 'supports energy' benefit and must stay CRITICAL/blocker
    even though the topic (energy) is grounded."""
    product = StructuredProduct(
        product_name="EnergyBoost",
        target_audience="busy adults",
        key_benefits=["supports energy"],
    )
    llm_response = {
        "status": "BLOCK",
        "findings": [
            {
                "phrase": "Provides unlimited energy all day.",
                "type": "ABSOLUTE_OUTCOME",
                "severity": "CRITICAL",
                "reason": "Claims unlimited, all-day energy — far stronger than the supplied 'supports energy' benefit.",
                "suggested_fix": "Helps support your energy throughout the day.",
            }
        ],
    }
    with _mock_llm(llm_response):
        result = compliance_service.audit_script(_input("Provides unlimited energy all day.", product))
    assert result.passed is False
    assert result.violations[0].severity == "blocker"


def test_high_severity_finding_blocks():
    llm_response = {
        "status": "BLOCK",
        "findings": [
            {
                "phrase": "increase your strength enough to finish every marathon",
                "type": "PERFORMANCE_CLAIM",
                "severity": "HIGH",
                "reason": "Explicitly connects the product to a specific athletic performance outcome without evidence.",
                "suggested_fix": "Designed to support your training routine.",
            }
        ],
    }
    with _mock_llm(llm_response):
        result = compliance_service.audit_script(
            _input("Take Men's Strength & Vitality Kit and increase your strength enough to finish every marathon.")
        )
    assert result.passed is False
    assert result.violations[0].severity == "blocker"


def test_low_severity_findings_are_dropped_entirely():
    llm_response = {
        "status": "PASS",
        "findings": [
            {"phrase": "strength", "type": "ASPIRATIONAL_CREATIVE_LANGUAGE", "severity": "LOW", "reason": "ordinary word"}
        ],
    }
    with _mock_llm(llm_response):
        result = compliance_service.audit_script(_input("New strength, new finish line."))
    assert result.violations == []
    assert result.passed is True


def test_malformed_llm_json_fails_safely_without_crashing():
    with patch.object(compliance_service, "call_openrouter_with_retry", lambda fn, **kwargs: "not json"):
        with pytest.raises(ValueError):
            compliance_service.audit_script(_input("Some ambiguous creative copy."))


def test_product_data_is_included_in_the_grounding_prompt():
    product = StructuredProduct(
        product_name="GlowSerum",
        target_audience="adults with dry skin",
        key_benefits=["supports healthy-looking skin"],
        usp="plant-based hydration",
    )
    message = compliance_service._build_user_message(_input("Helps support healthy-looking skin.", product))
    assert "supports healthy-looking skin" in message
    assert "plant-based hydration" in message
    assert "Supplied product facts" in message


def test_missing_product_data_says_so_in_the_prompt():
    message = compliance_service._build_user_message(_input("Helps support healthy-looking skin."))
    assert "none given" in message
