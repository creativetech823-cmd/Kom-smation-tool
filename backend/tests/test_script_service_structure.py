"""Tests for the fix to the structural conflict between the fixed 9-section
writing template and an approved beat outline: when an outline exists, the
system prompt must stop re-deriving its own competing STORY ARC/mechanism
and stop forcing the rigid problem->science->story->... section ordering."""

from app.services import script_service as svc


def test_structure_block_default_forces_fixed_section_order():
    block = svc._structure_block("30s", has_outline=False)
    assert "in order" in block
    assert "do not add any other section" in block


def test_structure_block_with_outline_defers_to_approved_outline():
    block = svc._structure_block("30s", has_outline=True)
    assert "APPROVED BEAT OUTLINE" in block
    assert "do NOT force" in block
    # Must not contain the rigid default-mode instruction that pins the
    # fixed section list as the actual sequence.
    assert "do not add any other section" not in block


def test_creative_direction_block_default_rederives_mechanism_and_arc():
    block = svc._creative_direction_block(has_outline=False)
    assert "STORY ARC" in block
    assert "CREATIVE MECHANISM" in block


def test_creative_direction_block_with_outline_defers_to_premise_and_outline():
    block = svc._creative_direction_block(has_outline=True)
    assert "ALREADY made these decisions" in block
    assert "EXECUTION, not re-invention" in block
    # Must not re-invite the model to re-pick a story arc from scratch.
    assert "STORY ARC — pick the shape" not in block


def test_system_prompt_threads_has_outline_into_structure_and_direction():
    with_outline = svc._system_prompt("30s", has_outline=True)
    without_outline = svc._system_prompt("30s", has_outline=False)
    assert "APPROVED BEAT OUTLINE" in with_outline
    assert "ALREADY made these decisions" in with_outline
    assert "STORY ARC — pick the shape" in without_outline


def test_static_system_prompt_threads_has_outline_into_direction_block():
    with_outline = svc._static_system_prompt("thumbnail", "", "", has_outline=True)
    assert "ALREADY made these decisions" in with_outline


# --- rewrite passes must re-attach the approved premise/outline, not just a reason string --


def test_rewrite_for_quality_includes_creative_context_block_when_given():
    from unittest.mock import patch
    from app.models.product import ScriptGenerationInput, StorySituation, StructuredProduct, ScriptLanguage, ContentType

    situation = StorySituation(
        id="t", title="t", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    payload = ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.english, content_type=ContentType.video,
    )
    captured = {}

    def fake_recovery(system, user_message, *args, **kwargs):
        captured["user_message"] = user_message
        return {"hook": {"text": "h"}, "body": [], "cta": {"text": "c"}}

    with patch.object(svc, "_generate_with_recovery", side_effect=fake_recovery):
        svc._rewrite_for_quality(
            {"hook": {"text": "h"}, "body": [], "cta": {"text": "c"}}, payload, "30s", None,
            "fix it", ContentType.video, creative_context_block="APPROVED BEAT OUTLINE MARKER TEXT",
        )
    assert "APPROVED BEAT OUTLINE MARKER TEXT" in captured["user_message"]
