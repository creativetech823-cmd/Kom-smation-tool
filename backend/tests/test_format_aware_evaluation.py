"""Format-aware Creative Director evaluation (Task V3 Part 14) — extends the
format coverage already tested in test_phase3c_story_execution.py (static,
testimonial, default-video-strict, cinematic-strict, and one UGC end-to-end
case) with the remaining formats named in the task: product_demo, podcast,
explainer (the "expert advice" role), product_showcase, educational_video,
whiteboard, and confirms "animation" has no special-cased leniency entry
(intentional — an animated piece can still carry a full narrative, so it
gets the same strict-by-default treatment as any other unlisted format,
rather than silently becoming lenient by accident).

_format_guidance() is a pure function — these are plain unit tests, no
mocking needed for most of them. Two end-to-end mocked cases at the bottom
confirm the guidance text actually reaches the eval prompt for formats other
than the ones already covered elsewhere."""

from unittest.mock import patch

import pytest

from app.services import architecture_validation_service as av, openrouter_utils
from app.services.creative_architecture import ARCHITECTURES

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


@pytest.mark.parametrize("format_value,expected_snippet", [
    ("product_demo", "demonstration itself IS the event"),
    ("podcast", "specific, credible point of view"),
    ("explainer", "concrete, specific example or demonstration"),
    ("product_showcase", "clear, specific presentation"),
    ("educational_video", "credibility and a concrete, specific example"),
    ("whiteboard", "clarity of the concrete idea"),
])
def test_format_guidance_lenient_formats_return_their_own_specific_note(format_value, expected_snippet):
    guidance = av._format_guidance("video", format_value)
    assert expected_snippet in guidance
    assert guidance.startswith("FORMAT NOTE:")


def test_format_guidance_animation_has_no_special_case_and_defaults_to_strict():
    # Intentional, not an oversight: an animated piece can carry a full
    # narrative just like live-action, so it must not silently become
    # lenient just because it's animated — only genuinely non-narrative
    # formats (UGC, testimonial, demo, etc.) get the relaxed guidance.
    guidance = av._format_guidance("video", "animation")
    assert "narrative-driven format" in guidance
    assert "full strength" in guidance
    # Same text a cinematic/unrecognized format gets — confirms no silent
    # animation-specific carve-out exists.
    assert guidance == av._format_guidance("video", "cinematic")


def test_format_guidance_unknown_format_value_also_defaults_to_strict():
    assert "full strength" in av._format_guidance("video", "some_future_format_not_yet_catalogued")


def _script(hook: str, body: list[str], cta: str) -> dict:
    return {"hook": {"text": hook}, "body": [{"text": b} for b in body], "cta": {"text": cta}}


def test_product_demo_format_note_reaches_the_actual_eval_call():
    # End-to-end: confirms the format-specific guidance text is actually
    # threaded into the prompt sent to the model, not just correct in
    # isolation — captures the real call args rather than trusting the
    # unit-level guidance function alone.
    captured = {}

    def _capture(system_instruction, contents, **kwargs):
        captured["prompt"] = contents[0]
        return '{"issues": [], "scores": {}, "announcement_mode": false, "abstract_copy_risk": false}'

    with patch.object(av, "generate_text", side_effect=_capture), \
         patch.object(av, "call_openrouter_with_retry", side_effect=lambda fn, **kw: fn()):
        av.evaluate_script_execution(
            _script("hook", ["body line"], "cta"), None, DIALOGUE_TRAP,
            "Aayush Herbal Masala", "adult gutka chewers",
            content_type="video", format_value="product_demo",
        )
    assert "demonstration itself IS the event" in captured["prompt"]


def test_podcast_format_note_reaches_the_actual_eval_call():
    captured = {}

    def _capture(system_instruction, contents, **kwargs):
        captured["prompt"] = contents[0]
        return '{"issues": [], "scores": {}, "announcement_mode": false, "abstract_copy_risk": false}'

    with patch.object(av, "generate_text", side_effect=_capture), \
         patch.object(av, "call_openrouter_with_retry", side_effect=lambda fn, **kw: fn()):
        av.evaluate_script_execution(
            _script("hook", ["body line"], "cta"), None, DIALOGUE_TRAP,
            "Aayush Herbal Masala", "adult gutka chewers",
            content_type="video", format_value="podcast",
        )
    assert "point of view" in captured["prompt"]
