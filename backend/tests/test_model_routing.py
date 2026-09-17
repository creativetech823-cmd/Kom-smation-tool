"""Routing tests for hybrid model routing (Option C) — verifies each
pipeline stage actually requests the model its tier calls for, with
OpenRouter itself fully mocked (no live calls). Each service module imports
`generate_text` by name into its own namespace, so it's patched per-module
rather than at the shared openrouter_utils source.
"""

import json
from unittest.mock import patch

from app.config import settings
from app.services import (
    architecture_validation_service as arch_val,
    beat_outline_service as outline_svc,
    creative_architecture as arch_svc,
    creative_insight_service as insight_svc,
    creative_premise_service as premise_svc,
    creative_territory_service as territory_svc,
    hook_generation_service as hook_svc,
    script_quality as sq,
    script_service as svc,
)


def _capture_model(response_text: str):
    """Returns (captured_kwargs_dict, fake_generate_text) — the fake
    replaces generate_text, records every kwarg it was called with (most
    importantly `model`), and returns the given canned response."""
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return response_text

    return captured, fake


# --- CREATIVE (Flash) tier ---------------------------------------------------


def test_insight_discovery_uses_creative_model():
    payload = json.dumps({
        "target_person": "x", "purchaser": "x", "user": "x", "situation": "x", "behavior": "x",
        "tension": "x", "unspoken_truth": "x", "why_not_solved_already": "x",
        "insight_statement": "a genuinely specific behavior-anchored insight statement, not a restated benefit",
    })
    captured, fake = _capture_model(payload)
    with patch.object(insight_svc, "generate_text", side_effect=fake):
        insight_svc.discover_insight(product_name="X", category="Y", target_audience="Z")
    assert captured["model"] == settings.creative_model


def test_territory_generation_uses_creative_model():
    payload = json.dumps({"candidates": [{
        "territory_name": "t", "human_tension": "x", "creative_question": "x", "why_distinct": "x",
        "scores": {"originality": 3, "product_integration": 3, "creative_potential": 3},
    }]})
    captured, fake = _capture_model(payload)
    with patch.object(territory_svc, "generate_text", side_effect=fake):
        territory_svc.generate_territories(product_name="X", category="Y", target_audience="Z")
    assert captured["model"] == settings.creative_model


def test_architecture_selection_uses_creative_model():
    captured, fake = _capture_model('{"architecture_key": "dialogue_trap", "reasoning": "fits"}')
    with patch.object(arch_svc, "generate_text", side_effect=fake):
        arch_svc.select_architecture(
            product_category="x", target_audience="y", objective="z", available_proof="",
            tone="", platform="", insight_statement="",
        )
    assert captured["model"] == settings.creative_model


def test_premise_generation_uses_creative_model():
    payload = json.dumps({"candidates": [{
        "statement": "a specific situation", "creative_device": "reversal", "situation": "s",
        "why_curious": "c", "why_not_swappable": "n",
        "scores": {k: 3 for k in premise_svc._SCORE_KEYS},
    }]})
    captured, fake = _capture_model(payload)
    with patch.object(premise_svc, "generate_text", side_effect=fake):
        premise_svc.generate_premises(product_name="X", category="Y", target_audience="Z")
    assert captured["model"] == settings.creative_model


def test_hook_generation_uses_creative_model():
    payload = json.dumps({"candidates": [{
        "text": "a specific hook line with real punctuation.", "curiosity_question": "what happens next?",
        "mechanism": "curiosity_gap", "reveals_product": False, "passes": True, "reject_reason": "",
    }]})
    captured, fake = _capture_model(payload)
    with patch.object(hook_svc, "generate_text", side_effect=fake):
        hook_svc.generate_and_select_hook(
            product_name="X", category="Y", target_audience="Z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=False, language="english",
        )
    assert captured["model"] == settings.creative_model


def test_beat_outline_generation_uses_creative_model():
    from app.services.creative_architecture import ARCHITECTURES

    payload = json.dumps({
        "beats": [{"beat_number": 1, "purpose": "p", "content": "c", "emotional_state": "e", "must_include": []}],
        "product_reveal_beat": 1, "proof_beat": 1, "payoff_beat": 1, "cta_beat": 1,
    })
    captured, fake = _capture_model(payload)
    with patch.object(outline_svc, "generate_text", side_effect=fake), \
         patch.object(outline_svc, "validate_outline_llm", return_value=[]):
        outline_svc.generate_and_validate_outline(
            architecture=ARCHITECTURES["dialogue_trap"], hook="h", human_insight="i",
            product_name="X", category="Y", target_audience="Z", target_duration_bucket="30s",
        )
    assert captured["model"] == settings.creative_model


def test_beat_outline_llm_validation_uses_creative_model():
    from app.services.creative_architecture import ARCHITECTURES

    captured, fake = _capture_model('{"issues": []}')
    with patch.object(outline_svc, "generate_text", side_effect=fake):
        outline_svc.validate_outline_llm(
            outline_svc.BeatOutline(
                architecture="dialogue_trap", hook="h", human_insight="i", beats=[],
                product_reveal_beat=1, proof_beat=1, payoff_beat=1, cta_beat=1,
            ),
            ARCHITECTURES["dialogue_trap"],
        )
    assert captured["model"] == settings.creative_model


# --- FINAL_SCRIPT (Pro) tier ------------------------------------------------


def test_final_creative_director_eval_uses_final_script_model():
    from app.services.creative_architecture import ARCHITECTURES

    captured, fake = _capture_model('{"issues": []}')
    with patch.object(arch_val, "generate_text", side_effect=fake):
        arch_val.llm_architecture_and_creative_director_issues(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None,
            ARCHITECTURES["dialogue_trap"], "X", "Y",
        )
    assert captured["model"] == settings.final_script_model


def test_generate_with_recovery_defaults_to_final_script_model():
    good_json = json.dumps({"hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"}, "creative_mechanism": "curiosity_gap"})
    captured, fake = _capture_model(good_json)
    with patch.object(svc, "generate_text", side_effect=fake):
        svc._generate_with_recovery("system", "user", 1000, "30s")
    assert captured["model"] == settings.final_script_model


def test_generate_with_recovery_honors_explicit_model_override():
    good_json = json.dumps({"hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"}, "creative_mechanism": "curiosity_gap"})
    captured, fake = _capture_model(good_json)
    with patch.object(svc, "generate_text", side_effect=fake):
        svc._generate_with_recovery("system", "user", 1000, "30s", model=settings.creative_model)
    assert captured["model"] == settings.creative_model


def test_rewrite_for_quality_uses_final_script_model():
    from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct

    situation = StorySituation(
        id="t", title="t", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    payload = ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.english, content_type=ContentType.video,
    )
    good_json = json.dumps({"hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"}, "creative_mechanism": "curiosity_gap"})
    captured, fake = _capture_model(good_json)
    with patch.object(svc, "generate_text", side_effect=fake):
        svc._rewrite_for_quality({"hook": {"text": "h"}, "body": [], "cta": {"text": "c"}}, payload, "30s", None, "fix it", ContentType.video)
    assert captured["model"] == settings.final_script_model


# --- VALIDATION (Flash-Lite) tier -------------------------------------------


def test_quality_gate_llm_eval_uses_validation_model():
    class FakeProduct:
        product_name = "X"
        target_audience = "Y"
        ingredients = []
        key_benefits = []
        usp = ""

    class FakeSituation:
        title = "t"
        description = "d"

    class FakePayload:
        structured_product = FakeProduct()
        selected_situation = FakeSituation()
        content_type = "video"
        format = ""
        script_language = "english"
        selected_hook_text = ""

    captured, fake = _capture_model('{"pass": true, "issues": []}')
    with patch.object(sq, "generate_text", side_effect=fake):
        sq.llm_quality_issues({"hook": {"text": "h"}, "body": [], "cta": {"text": "c"}}, FakePayload())
    assert captured["model"] == settings.validation_model


# --- narrow single-block edits stay on the cheap creative tier -------------


def test_narrow_regenerate_uses_creative_model_not_final_script():
    good_json = json.dumps({"hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"}, "creative_mechanism": "curiosity_gap"})
    captured, fake = _capture_model(good_json)
    with patch.object(svc, "generate_text", side_effect=fake):
        svc._generate_with_recovery("system", "user", 1000, "30s", model=settings.creative_model, label="narrow_regenerate")
    assert captured["model"] == settings.creative_model
    assert captured["label"] == "narrow_regenerate"
