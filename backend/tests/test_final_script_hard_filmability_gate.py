"""Final hard gate — enforce filmable video structure (2026-09-18 task,
follow-up to the filmable-format prompt/schema task). Gap being closed: a
script with scene labels and dialogue but NO action/reaction/visual_
direction anywhere (an explanation dressed as scenes) previously passed
every check. This adds one new, deliberately structural Layer-1 check —
`not_filmable_video` — that trusts the action/reaction/visual_direction
fields as the PRIMARY filmability signal rather than a second abstract-
language denylist, and feeds into the exact same existing single-rewrite
mechanism as every other issue code. Nothing else changed: no new retry
system, no model/timeout/claim-safety change."""

from unittest.mock import patch

from app.config import settings
from app.models.product import ContentType, ScriptLine
from app.services import architecture_validation_service as arch_val
from app.services import openrouter_utils
from app.services import script_quality as sq
from app.services import script_service as svc
from app.services import semantic_story_judge_service as sj
from app.services import story_situation_service as story_svc


def _payload_stub(content_type=ContentType.video):
    return type("P", (), {"content_type": content_type})()


# --- 1: old scripts without action/reaction still deserialize --------------


def test_old_script_line_without_action_reaction_still_deserializes():
    line = ScriptLine(text="An old stored line with no action/reaction fields at all.")
    assert line.action is None
    assert line.reaction is None


def test_old_script_line_dict_from_a_pre_existing_db_record_still_loads():
    """Simulates a historical DB record's raw dict — no "action"/"reaction"
    keys present at all (not even as null)."""
    raw = {"text": "hi", "on_screen_text": "", "visual_tags": [], "scene_label": "Scene 1"}
    line = ScriptLine(**raw)
    assert line.text == "hi"
    assert line.action is None


# --- helpers for constructing body fixtures ---------------------------------


def _line(text="", action="", reaction="", visual_direction="", scene_label="", section="story"):
    return {
        "text": text, "action": action, "reaction": reaction, "visual_direction": visual_direction,
        "scene_label": scene_label, "section": section,
    }


def _script(body, hook_text="A strong specific hook.", cta_text="A closing line.", mechanism="mini_story"):
    return {
        "hook": {"text": hook_text, "section": "hook"},
        "body": body,
        "cta": {"text": cta_text, "section": "cta"},
        "creative_mechanism": mechanism,
    }


# --- 2: meaningful visual/action/dialogue passes ----------------------------


def test_video_body_with_visual_action_dialogue_reaction_passes():
    body = [
        _line(
            visual_direction="The driver's hand moves toward his left pocket.",
            action="He stops halfway and looks at the passenger.",
            text='Passenger: "Bhaiya?"',
            reaction="The driver quickly moves his hand to the other pocket.",
            scene_label="SCENE 1 — AUTO RICKSHAW",
        ),
        _line(
            visual_direction="The passenger leans forward.",
            action="He watches the driver's hand switch pockets.",
            text='Passenger: "Naya wala?"',
            scene_label="SCENE 2 — AUTO RICKSHAW",
        ),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


# --- 3: scene labels alone do not make a script filmable -------------------


def test_scene_labels_alone_without_action_reaction_visual_still_fails():
    body = [
        _line(text='Driver: "Changing habits is important."', scene_label="SCENE 1 — AUTO", visual_direction="Driver sits in the auto."),
        _line(text='Passenger: "Aayush is a better choice."', scene_label="SCENE 2"),
        _line(text='Driver: "We should all make new choices."', scene_label="SCENE 3"),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" in issues


# --- 4: explanation-heavy scripts trigger the new issue ---------------------


def test_explanation_heavy_script_with_scene_labels_triggers_the_issue():
    body = [
        _line(text="Worker looks at him.", scene_label="SCENE 1 — OFFICE"),
        _line(text="Aadat sirf packet nahi; woh reach, break aur familiar taste ka poora ritual hai.", scene_label="SCENE 2"),
        _line(text="Haath purana soche, choice nayi ho.", scene_label="SCENE 3"),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    # The two checks are complementary, not mutually exclusive — either or
    # both may fire on a script this explanation-heavy; this test's focus
    # is specifically the new structural check.
    assert "not_filmable_video" in issues


def test_not_filmable_video_never_fires_for_static_content():
    body = [
        _line(text="Headline copy."),
        _line(text="Supporting copy."),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub(content_type=ContentType.static))
    assert "not_filmable_video" not in issues


# --- 5: action/reaction fields count as genuine filmability evidence -------


def test_action_field_alone_is_sufficient_evidence_even_with_generic_text():
    """The exact scenario from the task: action: "His hand moves toward the
    old packet, then stops." is strong evidence even if the word isn't in
    `text` at all."""
    body = [
        _line(text="", action="His hand moves toward the old packet, then stops."),
        _line(text="", reaction="The passenger notices and looks at his other pocket."),
        _line(text='Driver: "Naya try karo."'),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


def test_reaction_field_alone_counts_as_visual_storytelling_evidence():
    body = [
        _line(text="", visual_direction="Wide shot of the break room."),
        _line(text="", reaction="Coworkers exchange a quiet glance."),
        _line(text="", action="He puts the packet back in his bag."),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


# --- 6 & 7: creative mechanism demonstrated vs only explained --------------


def test_mechanism_demonstrated_through_behavior_passes():
    """"Auto Mein Do Pocket" — the stronger output from the task's own
    example: the two-pocket mechanism is physically dramatized."""
    body = [
        _line(action="His hand moves toward one pocket.", visual_direction="Close on his hand hovering."),
        _line(action="He stops.", reaction=""),
        _line(action="He reaches into the other pocket instead.", reaction="The passenger notices."),
    ]
    data = _script(body, mechanism="pattern_interrupt")
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


def test_mechanism_only_explained_in_dialogue_fails():
    """The weak output from the task's own example: "The driver explains
    that he keeps two choices" — mechanism named, never dramatized."""
    body = [
        _line(text='Driver: "Main do choices rakhta hoon, ek purani ek nayi."'),
        _line(text='Passenger: "Interesting."'),
        _line(text='Driver: "Yahi mera tarika hai."'),
    ]
    data = _script(body, mechanism="pattern_interrupt")
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" in issues


# --- 9: does not over-reject a body with a couple of dialogue-only lines ---


def test_does_not_over_reject_a_mostly_concrete_body_with_one_plain_dialogue_line():
    body = [
        _line(action="The boss freezes.", visual_direction="Close on his face."),
        _line(text='Worker: "Sir... aapka?"'),  # plain dialogue line, no action/reaction — should not sink the ratio alone
        _line(action="He slowly takes the packet out and places it on the table.", reaction="Everyone looks at him."),
    ]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


def test_a_single_plain_dialogue_line_does_not_trigger_on_its_own():
    """A body with only one substantive line is too short to judge — fails
    open (no issue), matching "do not over-reject" for brief scripts."""
    body = [_line(text="Worker: \"Sir?\"")]
    data = _script(body)
    issues = sq.deterministic_issues(data, _payload_stub())
    assert "not_filmable_video" not in issues


# --- 8: rewrite instruction wording, and feeds into the existing gate ------


def test_not_filmable_video_has_the_exact_specified_rewrite_instruction():
    instruction = sq._ISSUE_INSTRUCTIONS["not_filmable_video"]
    assert "Rewrite the actual story into filmable scenes." in instruction
    assert "observable action, reaction, dialogue, visual behavior and concrete beats" in instruction
    assert "Preserve the approved concept, hook and product truth." in instruction
    assert "Do not change the creative mechanism merely to avoid the issue." in instruction


def test_rewrite_reason_includes_the_filmability_instruction():
    reason = sq.rewrite_reason(["not_filmable_video"])
    assert "filmable scenes" in reason


def test_quality_gate_triggers_the_existing_single_rewrite_for_a_non_filmable_script():
    bad_draft = _script([
        _line(text='Driver: "Changing habits is important."'),
        _line(text='Passenger: "Aayush is a better choice."'),
        _line(text='Driver: "We should all make new choices."'),
    ])
    rewritten = _script([_line(action="A clean rewrite with real behavior.", visual_direction="A real scene.")])
    called = {"rewrite": False}

    def fake_rewrite(data, payload, target_duration, target_word_count, reason, content_type, context):
        called["rewrite"] = True
        assert "filmable scenes" in reason
        return rewritten

    payload = _payload_stub()
    with patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite):
        result = svc._apply_quality_gate(bad_draft, payload, "30s", None, ContentType.video, run_semantic_check=False)
    assert called["rewrite"] is True
    assert result == rewritten


# --- 7 (cont'd): existing checks are preserved, not removed ----------------


def test_explanatory_language_overuse_check_still_exists():
    assert hasattr(sq, "_detect_explanatory_language_overuse")
    assert "explanatory_language_overuse" in sq._ISSUE_INSTRUCTIONS


def test_explains_instead_of_shows_still_in_the_llm_gate_prompt():
    assert '"explains_instead_of_shows"' in sq._EVAL_SYSTEM_PROMPT


def test_claim_safety_text_detection_unchanged():
    issues = sq.text_issues("Yeh cravings ko 2 hafton mein 90% kam kar deta hai.")
    assert "unsupported_claim" in issues


def test_no_new_retry_system_introduced_max_attempts_untouched():
    import inspect
    sig = inspect.signature(openrouter_utils.call_openrouter_with_retry)
    assert sig.parameters["max_attempts"].default == 4


# --- 10: existing format-specific structures remain valid ------------------


def test_existing_format_specific_structure_blocks_still_present_and_distinct():
    from app.services import content_formats
    formats = ["podcast", "cinematic", "ugc_talking_head", "animation", "product_showcase", "educational_video"]
    blocks = {f: content_formats.video_structure_block(f, "") for f in formats}
    assert all(blocks.values())
    assert len(set(blocks.values())) == len(formats)


# --- 11, 12, 13: model routing / timeouts / image generation untouched -----


def test_model_routing_unchanged_by_the_hard_filmability_gate():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_story_ideas_and_judge_timeout_constants_unchanged():
    assert story_svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0
    assert story_svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0
    assert sj._JUDGE_CALL_TIMEOUT_SECONDS == 40.0


def test_shared_openrouter_client_default_timeout_unchanged():
    import inspect
    src = inspect.getsource(openrouter_utils)
    assert "timeout=120.0" in src


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False


def test_architecture_validation_service_untouched_by_this_task():
    """Sanity check — this task deliberately did not touch
    architecture_validation_service.py; confirm its existing Phase 3C
    issue codes are still intact and unmodified."""
    import inspect
    src = inspect.getsource(arch_val)
    assert '"metaphor_not_embodied"' in src
    assert '"no_concrete_event"' in src
    assert '"announcement_mode"' in src
