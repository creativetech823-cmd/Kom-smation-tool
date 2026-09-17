"""Tests for the Product Creative Contract — the fixed factual grounding
that establishes PRODUCT TRUTH before any creative generation starts."""

from app.services.product_context_service import (
    ROLE_RISK_FOOD_OR_COOKING_INGREDIENT,
    build_product_creative_contract,
)


def test_herbal_masala_gets_gutka_category_from_brief_not_name():
    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala",
        category="herbal_health",  # deliberately generic — the real signal is the brief text
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        usp="a 0% tobacco, 0% supari herbal chew",
        benefits=["same chewing ritual and mouth-freshening taste"],
    )
    assert "gutka" in contract.canonical_category.lower() or "tobacco" in contract.canonical_category.lower()
    assert contract.category_confidence == "high"
    assert ROLE_RISK_FOOD_OR_COOKING_INGREDIENT in contract.role_risk_keys
    assert "cooking" in " ".join(contract.forbidden_contexts).lower() or "recipe" in " ".join(contract.forbidden_contexts).lower()


def test_herbal_masala_contract_never_says_cooking_ingredient_in_allowed_contexts():
    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and tobacco chewers", usp="tobacco-free alternative",
    )
    allowed_text = " ".join(contract.allowed_contexts).lower()
    assert "cooking" not in allowed_text
    assert "recipe" not in allowed_text
    assert "curry" not in allowed_text


def test_generic_product_gets_no_role_risk_keys():
    """A product whose brief has nothing to do with tobacco/gutka must never
    inherit Herbal Masala's forbidden-context list — the risk keys must be
    empty, not just differently worded."""
    contract = build_product_creative_contract(
        product_name="AayushWellness Glow Face Serum", category="skincare",
        target_audience="working women with dull, tired-looking skin",
        usp="a lightweight daily serum", benefits=["brighter skin"],
    )
    assert contract.role_risk_keys == []
    assert contract.category_confidence != "high" or "gutka" not in contract.canonical_category.lower()


def test_generic_product_does_not_invent_specific_use_case():
    """Nothing should be hallucinated for a product with a thin brief —
    fields should reflect only what was actually given."""
    contract = build_product_creative_contract(
        product_name="Some New Product", category="", target_audience="",
    )
    assert contract.category_confidence in ("low", "unknown")
    assert contract.forbidden_contexts == []
    assert contract.role_risk_keys == []


def test_contract_pulls_claims_from_product_context_when_given():
    class FakeProductContext:
        brand = "AayushWellness"
        approved_claims = ["supports daily immunity"]
        prohibited_claims = ["cures illness"]
        never_say = "clinically proven"
        positioning = "a simple daily immunity routine"

    contract = build_product_creative_contract(
        product_name="Immune Care Tablets", category="nutraceuticals",
        target_audience="mothers", usp="", benefits=[],
        product_context=FakeProductContext(),
    )
    assert contract.brand == "AayushWellness"
    assert "supports daily immunity" in contract.supported_claims
    assert "cures illness" in contract.unsupported_claims
    assert "clinically proven" in contract.unsupported_claims


def test_prompt_block_states_immutability_rule():
    contract = build_product_creative_contract(
        product_name="X", category="skincare", target_audience="Y",
    )
    block = contract.prompt_block()
    assert "immutable" in block.lower()
    assert "never" in block.lower()
    assert contract.product_name in block


def test_prompt_block_marks_low_confidence_fields_as_unresolved_not_invented():
    contract = build_product_creative_contract(product_name="X", category="", target_audience="")
    block = contract.prompt_block()
    assert "not reliably determined" in block
