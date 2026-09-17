"""End-to-end (fully mocked, no live calls) test of generate_script()
proving the whole Option C routing works together: exploration stages get
short-circuited to their documented fail-open results, and the actual
script-writing call is verified to use the final_script tier — plus that a
pipeline cost summary gets logged."""

import json
import logging
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import architecture_validation_service as arch_val
from app.services import creative_architecture, openrouter_utils, script_quality as sq, script_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    """Hard safety net for this file: if any code path in these tests fails
    to have its own generate_text mocked and falls through to a real HTTP
    call, fail loudly and immediately instead of silently spending real
    OpenRouter credits."""
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")

    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield

_GOOD_SCRIPT_JSON = json.dumps({
    "hook": {"text": "A specific hook line."},
    "body": [{"text": "A body line that develops the story."}],
    "cta": {"text": "A closing line."},
    "creative_mechanism": "curiosity_gap",
})

_SAFE_CLAIM_JSON = json.dumps({
    "implied_claim": False, "claim_evidence": "", "claim_reason": "",
    "emotional_coercion": False, "coercion_evidence": "", "coercion_reason": "",
})


def _payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="t", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def test_generate_script_writes_with_final_script_model_and_logs_cost_summary(caplog):
    captured_models = []

    def fake_generate_text(*args, **kwargs):
        captured_models.append(kwargs.get("model"))
        return _GOOD_SCRIPT_JSON

    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)

    # Every module that owns its own `generate_text` import must be patched
    # individually — a single patch.object(svc, "generate_text", ...) does
    # NOT reach script_quality.py's or architecture_validation_service.py's
    # own bindings, and leaving those live would silently make real
    # OpenRouter calls even in a test meant to be fully offline.
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "generate_text", return_value=_SAFE_CLAIM_JSON), \
         patch.object(arch_val, "generate_text", return_value='{"issues": []}'), \
         patch.object(svc, "generate_text", side_effect=fake_generate_text), \
         caplog.at_level(logging.INFO, logger="script_service"):
        result = svc.generate_script(_payload())

    assert result.hook.text == "A specific hook line."
    # Every call that reached script_service's own generate_text binding
    # (the write, and possibly a length-correction retry — no gates fired
    # since both eval calls above were stubbed to report a clean pass) used
    # the final_script tier, not the cheap exploration tier.
    assert captured_models
    assert all(m == settings.final_script_model for m in captured_models)
    assert any("pipeline_cost_summary" in r.message for r in caplog.records)


def test_generate_script_still_returns_a_script_when_every_exploration_stage_fails():
    """Regression: Option C routing changes must not break the pre-existing
    fail-open guarantee that a script always gets generated even if every
    creative pre-stage (insight/territory/architecture/premise/hook/outline)
    comes back empty."""
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "generate_text", return_value=_SAFE_CLAIM_JSON), \
         patch.object(arch_val, "generate_text", return_value='{"issues": []}'), \
         patch.object(svc, "generate_text", return_value=_GOOD_SCRIPT_JSON):
        result = svc.generate_script(_payload())
    assert result.hook.text == "A specific hook line."
    assert result.body[0].text == "A body line that develops the story."
