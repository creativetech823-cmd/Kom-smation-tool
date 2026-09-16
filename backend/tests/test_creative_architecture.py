"""Tests for the Creative Architecture library (AHM Creative DNA §1)."""

from unittest.mock import patch

from app.services import creative_architecture as ca


def test_every_architecture_has_all_required_fields():
    for key, arch in ca.ARCHITECTURES.items():
        assert arch.key == key
        assert arch.name
        assert arch.creative_purpose
        assert arch.when_to_use
        assert arch.when_not_to_use
        assert arch.hook_pattern
        assert len(arch.beats) >= 3
        assert arch.product_reveal_logic
        assert arch.proof_mechanism
        assert arch.emotional_progression
        assert arch.cta_style
        assert arch.required_inputs
        assert len(arch.failure_conditions) >= 1


def test_prompt_block_contains_key_sections():
    arch = ca.ARCHITECTURES["objection_handling_interview"]
    block = arch.prompt_block()
    assert arch.name in block
    assert "Product reveal logic" in block
    assert "Proof mechanism" in block
    assert "specifically fails when" in block
    for beat in arch.beats:
        assert beat in block


def test_get_architecture_returns_none_for_unknown_key():
    assert ca.get_architecture("not_a_real_architecture") is None
    assert ca.get_architecture("dialogue_trap") is not None


def test_default_architecture_key_is_valid():
    assert ca.DEFAULT_ARCHITECTURE_KEY in ca.ARCHITECTURES


def test_select_architecture_returns_valid_key_from_mocked_llm():
    with patch.object(ca, "call_openrouter_with_retry", return_value='{"architecture_key": "ironic_bit", "reasoning": "test"}'):
        arch = ca.select_architecture(
            product_category="skincare",
            target_audience="young urban women",
            objective="drive purchase",
            available_proof="real customer photos",
            tone="playful",
            platform="instagram_reel",
            insight_statement="test insight",
        )
    assert arch.key == "ironic_bit"


def test_select_architecture_falls_back_on_invalid_key_from_llm():
    with patch.object(ca, "call_openrouter_with_retry", return_value='{"architecture_key": "made_up_architecture", "reasoning": "oops"}'):
        arch = ca.select_architecture(
            product_category="skincare", target_audience="x", objective="y",
            available_proof="z", tone="", platform="", insight_statement="",
        )
    assert arch.key == ca.DEFAULT_ARCHITECTURE_KEY


def test_select_architecture_falls_back_on_llm_failure():
    with patch.object(ca, "call_openrouter_with_retry", side_effect=RuntimeError("network down")):
        arch = ca.select_architecture(
            product_category="x", target_audience="y", objective="z",
            available_proof="", tone="", platform="", insight_statement="",
        )
    assert arch.key == ca.DEFAULT_ARCHITECTURE_KEY


def test_select_architecture_falls_back_on_malformed_json():
    with patch.object(ca, "call_openrouter_with_retry", return_value="not json at all"):
        arch = ca.select_architecture(
            product_category="x", target_audience="y", objective="z",
            available_proof="", tone="", platform="", insight_statement="",
        )
    assert arch.key == ca.DEFAULT_ARCHITECTURE_KEY


def test_select_architecture_recovers_key_from_truncated_json_reasoning_field():
    # The actual observed real-world failure: a long "reasoning" string gets
    # cut off by the token budget mid-word, producing an unterminated
    # string that breaks json.loads() — but architecture_key itself, being
    # written first, is complete and recoverable.
    truncated = '{"architecture_key": "ironic_bit", "reasoning": "because this product has a genuinely fun'
    with patch.object(ca, "call_openrouter_with_retry", return_value=truncated):
        arch = ca.select_architecture(
            product_category="x", target_audience="y", objective="z",
            available_proof="", tone="", platform="", insight_statement="",
        )
    assert arch.key == "ironic_bit"  # recovered, not silently defaulted


def test_extract_architecture_key_handles_valid_json():
    assert ca._extract_architecture_key('{"architecture_key": "pure_demonstration", "reasoning": "x"}') == "pure_demonstration"


def test_extract_architecture_key_handles_truncated_json():
    assert ca._extract_architecture_key('{"architecture_key": "dialogue_trap", "reasoning": "unterminated') == "dialogue_trap"


def test_extract_architecture_key_returns_empty_for_no_match():
    assert ca._extract_architecture_key("complete garbage, no key here") == ""
