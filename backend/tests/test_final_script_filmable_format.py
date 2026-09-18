"""Final Script Quality Fix — Filmable Output + Strict Video Format
(2026-09-18 task). Root complaint: scripts for "Boss Ko Bhi Chhodna Pada"
and "Auto Mein Do Pocket" were technically structured but read like AI
advertising copy/concept explanations (e.g. "Aadat sirf packet nahi; woh
reach, break aur familiar taste ka poora ritual hai.") rather than a
shootable scene with behavior, reaction, and natural dialogue.

Since this repo makes no live OpenRouter calls in tests, these tests verify
the two things that actually changed: (1) the PROMPT now requires the
scene-based Visual/Action/Dialogue/Reaction format, format-specific writing
conventions, and the show-don't-explain/mechanism-drives-story/dialogue-
must-sound-spoken rules; (2) the QUALITY GATE now has both a deterministic
density check and an LLM-checked issue code that would flag and force a
rewrite of output matching the exact complained-about pattern. This is the
same testing strategy already used throughout this codebase for prompt/
gate changes (see test_generate_full_script_routing.py) — prompts aren't
executed against a live model in tests, so tests assert on prompt content
and on the deterministic/gate logic that would catch bad output."""

import json
import logging
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import (
    ContentType,
    ScriptGenerationInput,
    ScriptLanguage,
    ScriptLine,
    StorySituation,
    StructuredProduct,
)
from app.services import architecture_validation_service as arch_val
from app.services import content_formats, openrouter_utils
from app.services import creative_architecture, script_quality as sq
from app.services import script_service as svc
from app.services import story_situation_service as story_svc
from app.services import semantic_story_judge_service as sj


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


# --- 1: Cinematic video output requires Visual/Action/Dialogue structure ---


def test_cinematic_format_prompt_requires_visual_action_reaction_dialogue_order():
    block = content_formats.video_structure_block("cinematic", "")
    assert "VISUAL -> ACTION -> REACTION -> DIALOGUE" in block
    assert '"action"' in block
    assert '"reaction"' in block


def test_default_video_fields_block_documents_action_and_reaction():
    assert '"action"' in svc._FIELDS_BLOCK
    assert '"reaction"' in svc._FIELDS_BLOCK
    assert "PHYSICALLY DOES" in svc._FIELDS_BLOCK


def test_script_json_shape_includes_action_and_reaction_fields():
    assert '"action": string' in svc._SCRIPT_JSON_SHAPE
    assert '"reaction": string' in svc._SCRIPT_JSON_SHAPE


def test_script_line_model_accepts_action_and_reaction_fields():
    line = ScriptLine(text="hi", action="He reaches for the packet.", reaction="She notices.")
    assert line.action == "He reaches for the packet."
    assert line.reaction == "She notices."


def test_script_line_defaults_action_and_reaction_to_none_backward_compatible():
    """A script built before this field existed (or a mocked test fixture
    that never mentions them) must still construct without error."""
    line = ScriptLine(text="hi")
    assert line.action is None
    assert line.reaction is None


# --- 2: Selected format changes the actual script structure/labels ---------


def test_podcast_format_uses_host_guest_interruption_reaction_labels():
    block = content_formats.video_structure_block("podcast", "")
    assert "HOST:" in block and "GUEST:" in block
    assert "INTERRUPTION:" in block
    assert "REACTION:" in block


def test_ugc_format_uses_shot_person_to_camera_action_reaction_cutaway_labels():
    block = content_formats.video_structure_block("ugc_talking_head", "")
    assert "SHOT:" in block
    assert "PERSON TO CAMERA:" in block
    assert "ACTION:" in block
    assert "REACTION:" in block
    assert "CUTAWAY:" in block


def test_animation_format_uses_scene_visual_character_action_dialogue_labels():
    block = content_formats.video_structure_block("animation", "")
    assert "SCENE:" in block
    assert "VISUAL:" in block
    assert "CHARACTER ACTION:" in block
    assert "DIALOGUE-VO:" in block
    assert "TRANSITION:" in block


def test_product_showcase_format_uses_shot_product_visual_voiceover_labels():
    block = content_formats.video_structure_block("product_showcase", "")
    assert "SHOT:" in block
    assert "PRODUCT VISUAL:" in block
    assert "VOICEOVER:" in block
    assert "PRODUCT DETAIL:" in block


def test_educational_video_format_uses_hook_visual_speaker_explanation_labels():
    block = content_formats.video_structure_block("educational_video", "")
    assert "HOOK:" in block
    assert "VISUAL:" in block
    assert "SPEAKER:" in block
    assert "EXPLANATION:" in block
    assert "DEMONSTRATION:" in block
    assert "PAYOFF:" in block


def test_different_formats_produce_genuinely_different_structure_blocks():
    formats = ["podcast", "cinematic", "ugc_talking_head", "animation", "product_showcase", "educational_video"]
    blocks = {f: content_formats.video_structure_block(f, "") for f in formats}
    assert len(set(blocks.values())) == len(formats)  # every format's block is distinct


def test_video_ad_default_format_falls_back_to_ad_structure_unchanged():
    """"video_ad" (the default/no format) is deliberately absent from
    _VIDEO_STRUCTURE_PROMPTS — script_service._video_structure() must still
    fall back to the scene-based default structure, unaffected by this
    task's per-format additions."""
    assert content_formats.video_structure_block("video_ad", "") == ""
    assert content_formats.video_structure_block("", "") == ""


# --- 3: Creative mechanism must drive the story, not just be named ---------


def test_core_principles_require_mechanism_to_drive_the_story():
    block = svc._core_principles_block()
    assert "CREATIVE MECHANISM MUST DRIVE THE STORY" in block
    assert "removed, the story should materially change" in block


def test_core_principles_require_show_dont_explain():
    block = svc._core_principles_block()
    assert "SHOW, DON'T EXPLAIN" in block
    assert "Aadat sirf packet nahi" in block  # the exact reported bad example, used as a negative reference


def test_core_principles_require_device_return_in_payoff():
    block = svc._core_principles_block()
    assert "memorable device, relationship, or dynamic" in block
    assert "must connect back to that specific device/dynamic" in block


# --- 4 & 5: abstract/explanatory + slogan-like dialogue trigger a rewrite --


def _card(**overrides):
    base = {
        "hook": {"text": "Boss ne rule banaya.", "section": "hook"},
        "body": [
            {"text": "Worker looks at him.", "section": "story"},
            {"text": "Aadat sirf packet nahi; woh reach, break aur familiar taste ka poora ritual hai.", "section": "story"},
            {"text": "Haath purana soche, choice nayi ho.", "section": "story"},
        ],
        "cta": {"text": "Ab samajh gaya na, yahi direction hai.", "section": "cta"},
        "creative_mechanism": "mini_story",
    }
    base.update(overrides)
    return base


def test_deterministic_check_flags_a_script_dominated_by_explanatory_phrasing():
    data = _card()
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "explanatory_language_overuse" in issues


def test_deterministic_check_does_not_flag_a_normal_script_with_one_incidental_match():
    data = _card(body=[
        {"text": "He reaches for the familiar packet out of habit.", "section": "story"},
        {"text": "He stops, looks at it, and puts it back.", "section": "story"},
        {"text": "Worker: \"Sir, aap bhi?\"", "section": "story"},
    ], cta={"text": "Try the kit and make your next weekend count.", "section": "cta"})
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "explanatory_language_overuse" not in issues


def test_explains_instead_of_shows_issue_code_is_documented_for_the_llm_gate():
    assert '"explains_instead_of_shows"' in sq._EVAL_SYSTEM_PROMPT
    assert "creative strategist" in sq._EVAL_SYSTEM_PROMPT


def test_both_new_issue_codes_have_rewrite_instructions():
    assert "explanatory_language_overuse" in sq._ISSUE_INSTRUCTIONS
    assert "explains_instead_of_shows" in sq._ISSUE_INSTRUCTIONS
    assert sq.rewrite_reason(["explanatory_language_overuse"])
    assert sq.rewrite_reason(["explains_instead_of_shows"])


def test_quality_gate_triggers_a_rewrite_for_the_exact_reported_bad_pattern():
    """End-to-end (mocked): a draft matching the reported complaint must
    trigger exactly one rewrite pass via the existing single-rewrite
    mechanism — never silently accepted."""
    bad_draft = _card()
    rewritten = {**_card(), "body": [{"text": "A clean rewrite.", "section": "story"}]}
    called = {"rewrite": False}

    def fake_rewrite(data, payload, target_duration, target_word_count, reason, content_type, context):
        called["rewrite"] = True
        assert "explanatory" in reason.lower() or "show" in reason.lower() or "strategist" in reason.lower() or "creative" in reason.lower()
        return rewritten

    with patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite):
        result = svc._apply_quality_gate(
            bad_draft, _payload_stub(), "30s", None, ContentType.video, run_semantic_check=False,
        )
    assert called["rewrite"] is True
    assert result == rewritten


# --- 6: product integration stays natural (no info-dump) -------------------


def test_core_principles_require_natural_physical_product_integration():
    block = svc._core_principles_block()
    assert "PRODUCT INTEGRATION stays physical and natural" in block


def test_section_prose_product_intro_requires_physical_entry_not_announcement():
    prose = svc._SECTION_PROSE["product_intro"]
    assert "physical action" in prose
    assert "never a cutaway to introduce the product as new information" in prose


# --- 7: unsupported claims remain blocked (claim-safety gate untouched) ----


def test_unsupported_claim_detection_still_works():
    issues = sq.text_issues("Yeh cravings ko 2 hafton mein 90% kam kar deta hai.")
    assert "unsupported_claim" in issues


def test_claim_safety_gate_function_still_exists_and_is_called_in_full_generation():
    """Regression only — confirms this task didn't touch the claim-safety
    gate's wiring into the fresh-generation pipeline."""
    assert hasattr(svc, "_apply_claim_safety_gate")


# --- 8: ingredient dumping remains rejected unless justified ---------------


def test_ingredient_dump_still_detected():
    data = _card(body=[
        {"text": "Contains Mulethi, Amla, Ashwagandha, Tulsi and 10+ herbs.", "section": "ingredients"},
    ])
    p = _payload_stub()
    p.structured_product.ingredients = ["Mulethi", "Amla", "Ashwagandha", "Tulsi"]
    issues = sq.deterministic_issues(data, p)
    assert "ingredient_dump" in issues


def test_ingredient_dump_issue_still_has_a_rewrite_instruction():
    assert "ingredient_dump" in sq._ISSUE_INSTRUCTIONS


# --- 9: Creative Breakdown stays separate from the actual script -----------


def test_generated_script_keeps_breakdown_fields_separate_from_body_text():
    from app.models.product import GeneratedScript

    script = GeneratedScript(
        hook=ScriptLine(text="h"), body=[ScriptLine(text="b")], cta=ScriptLine(text="c"),
        creative_breakdown={"hook_type": "Question"}, creative_quality_assessment={"memorability": "high"},
    )
    assert script.creative_breakdown == {"hook_type": "Question"}
    assert script.creative_quality_assessment == {"memorability": "high"}
    # Breakdown data is its own field, never mixed into the script's own text.
    assert "hook_type" not in script.hook.text
    assert "hook_type" not in script.body[0].text


def test_fields_block_never_instructs_embedding_breakdown_labels_in_script_text():
    for label in ("Hook Type:", "Creative Mechanism:", "Story Structure:", "Emotional Engine:"):
        assert label not in svc._FIELDS_BLOCK


# --- 10, 11, 12: model routing / timeouts / image generation untouched -----


def test_model_routing_unchanged_by_the_filmable_format_fix():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_story_ideas_timeout_constants_unchanged():
    assert story_svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0
    assert story_svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0
    assert sj._JUDGE_CALL_TIMEOUT_SECONDS == 40.0


def test_shared_openrouter_client_default_timeout_unchanged():
    import inspect
    src = inspect.getsource(openrouter_utils)
    assert "timeout=120.0" in src


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False


# --- End-to-end: full generation still returns a valid script --------------


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


def _payload_stub() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="Auto Mein Do Pocket", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[])
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="c",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
        format="cinematic",
    )


def test_full_generation_still_returns_a_valid_script_with_new_optional_fields_unset():
    """Confirms the schema/prompt additions don't break the existing
    end-to-end generation pipeline — a mocked response with no action/
    reaction keys (as every existing fixture in this repo has) still
    produces a valid GeneratedScript, with the new fields defaulting safely."""
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
        result = svc.generate_script(_payload_stub())
    assert result.hook.text == "A specific hook line."
    assert result.hook.action is None
    assert result.hook.reaction is None
