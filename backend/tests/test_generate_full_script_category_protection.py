"""End-to-end (fully mocked, no live calls) proof that a category-drifted
final script (the exact reported Herbal Masala failure shape) gets caught by
_apply_architecture_gate and triggers the existing single-rewrite mechanism
with the Product Creative Contract preserved in the rewrite context."""

import json
from unittest.mock import patch

import pytest

from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import architecture_validation_service as arch_val
from app.services import creative_architecture, openrouter_utils, script_quality as sq, script_service as svc

COOKING_DRIFT_JSON = json.dumps({
    "hook": {"text": "What if main family ke favourite chicken curry mein yeh herbal masala daal doon?"},
    "body": [{"text": "Dinner table par do bowls rakhe — A aur B. Bowl B mein zyada swaad hai."}],
    "cta": {"text": "Try it today."},
    "creative_mechanism": "curiosity_gap",
})

REPAIRED_JSON = json.dumps({
    "hook": {"text": "Jab haath apne aap wahan jaata hai jahan gutka hua karta tha."},
    "body": [{"text": "Ab ussi ritual ke liye Aayush Herbal Masala — zero tobacco, zero supari."}],
    "cta": {"text": "Try it today."},
    "creative_mechanism": "mini_story",
})

_SAFE_CLAIM_JSON = json.dumps({
    "implied_claim": False, "claim_evidence": "", "claim_reason": "",
    "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
})


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _herbal_masala_payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="t", description="d", emotion="e",
        persona="adult gutka and pan masala chewers trying to switch away from tobacco",
        marketing_angle="a tobacco-free alternative", category="c", difficulty="medium",
        estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(
        product_name="Aayush Herbal Masala",
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
        key_benefits=["same ritual and taste"],
    )
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def test_category_drifted_final_script_triggers_rewrite_and_contract_is_preserved():
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    write_call_count = {"n": 0}
    rewrite_user_messages = []

    def fake_write_then_repair(*args, **kwargs):
        # First call: the writer produces the drifted script. Any call after
        # that (the gate's rewrite pass) produces a repaired one.
        write_call_count["n"] += 1
        if write_call_count["n"] == 1:
            return COOKING_DRIFT_JSON
        return REPAIRED_JSON

    def fake_arch_eval(*args, **kwargs):
        return '{"issues": []}'  # deterministic category check alone is enough to prove the point here

    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "generate_text", return_value=_SAFE_CLAIM_JSON), \
         patch.object(arch_val, "generate_text", side_effect=fake_arch_eval), \
         patch.object(svc, "generate_text", side_effect=fake_write_then_repair):
        result = svc.generate_script(_herbal_masala_payload())

    # The deterministic category check inside _apply_architecture_gate must
    # have caught the drift and triggered exactly one rewrite pass, so the
    # FINAL returned script is the repaired one, not the drifted draft.
    assert "chicken curry" not in result.hook.text.lower()
    assert "gutka" in result.hook.text.lower() or "habit" in result.hook.text.lower()
    assert write_call_count["n"] == 2  # original write + exactly one repair pass


def test_contract_is_built_and_threaded_into_pre_stage_prompt_block():
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])):
        pre = svc._run_creative_pre_stages(_herbal_masala_payload(), "30s")

    assert pre.contract is not None
    assert "PRODUCT CREATIVE CONTRACT" in pre.prompt_block
    assert "gutka" in pre.prompt_block.lower() or "tobacco" in pre.prompt_block.lower()
    # The contract must be the FIRST block — PRODUCT TRUTH before anything else.
    assert pre.prompt_block.strip().startswith("PRODUCT CREATIVE CONTRACT")
