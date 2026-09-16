"""Tests for post-script architecture compliance / creative-director /
strengthened competitor-swappable validation (Parts 5-7 of the outline-
enforcement upgrade)."""

from unittest.mock import patch

from app.services import architecture_validation_service as av
from app.services import beat_outline_service as outline_svc
from app.services.creative_architecture import ARCHITECTURES

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]


def _outline(reveal_beat=6, cta_beat=7, beats_count=7):
    beats = [
        outline_svc.BeatOutlineItem(beat_number=i + 1, purpose=f"p{i}", content=f"c{i}", emotional_state="x")
        for i in range(beats_count)
    ]
    return outline_svc.BeatOutline(
        architecture="dialogue_trap", hook="Still going on?", human_insight="test insight",
        beats=beats, product_reveal_beat=reveal_beat, proof_beat=6, payoff_beat=6, cta_beat=cta_beat,
    )


# --- _hook_intact -------------------------------------------------------------


def test_hook_intact_true_for_identical_hook():
    assert av._hook_intact("Still going on?", "Still going on?") is True


def test_hook_intact_true_for_light_localization():
    assert av._hook_intact("Abhi bhi chal raha hai kya, still going on?", "Still going on?") is True


def test_hook_intact_false_for_unrelated_replacement():
    assert av._hook_intact("Introducing our brand new product today!", "Still going on?") is False


def test_hook_intact_true_when_no_approved_hook_given():
    assert av._hook_intact("anything at all", "") is True


# --- _first_product_mention_fraction ------------------------------------------


def test_first_product_mention_fraction_finds_first_occurrence():
    texts = ["a generic opener", "still nothing", "Now we mention Immune Care Tablets here", "closing line"]
    frac = av._first_product_mention_fraction(texts, "Immune Care Tablets")
    assert frac == 2 / 3


def test_first_product_mention_fraction_none_when_never_mentioned():
    texts = ["a", "b", "c"]
    assert av._first_product_mention_fraction(texts, "Immune Care Tablets") is None


# --- validate_script_against_outline_deterministic ---------------------------


def test_deterministic_validation_flags_hook_not_intact():
    data = {
        "hook": {"text": "A completely unrelated generic opener about nothing in particular."},
        "body": [{"text": "some body text mentioning Aayush Herbal Masala here"}],
        "cta": {"text": "buy now"},
    }
    outline = _outline()
    issues = av.validate_script_against_outline_deterministic(data, outline, DIALOGUE_TRAP, "Aayush Herbal Masala")
    assert "hook_not_intact" in issues


def test_deterministic_validation_passes_when_hook_and_reveal_line_up():
    data = {
        "hook": {"text": "Still going on, bro?"},
        "body": [
            {"text": "beat one"}, {"text": "beat two"}, {"text": "beat three"},
            {"text": "beat four"}, {"text": "Here comes Aayush Herbal Masala"},
        ],
        "cta": {"text": "try it today"},
    }
    outline = _outline(reveal_beat=6, cta_beat=7, beats_count=7)
    issues = av.validate_script_against_outline_deterministic(data, outline, DIALOGUE_TRAP, "Aayush Herbal Masala")
    assert "hook_not_intact" not in issues


def test_deterministic_validation_flags_reveal_moved_too_early():
    # Architecture expects a "very late" reveal, but the product is mentioned
    # in the very first body block — enough surrounding blocks that this
    # isolates reveal-timing specifically, rather than also tripping the
    # separate "far fewer blocks than outline beats" check.
    data = {
        "hook": {"text": "Still going on?"},
        "body": [
            {"text": "Aayush Herbal Masala is amazing, buy it now"},
            {"text": "beat two"}, {"text": "beat three"}, {"text": "beat four"}, {"text": "beat five"},
        ],
        "cta": {"text": "buy now"},
    }
    outline = _outline(reveal_beat=6, cta_beat=7, beats_count=7)
    issues = av.validate_script_against_outline_deterministic(data, outline, DIALOGUE_TRAP, "Aayush Herbal Masala")
    assert "product_reveal_moved" in issues


def test_deterministic_validation_flags_missing_beats_when_script_much_shorter_than_outline():
    data = {
        "hook": {"text": "Still going on?"},
        "body": [],
        "cta": {"text": "buy now"},
    }
    outline = _outline(beats_count=7)
    issues = av.validate_script_against_outline_deterministic(data, outline, DIALOGUE_TRAP, "X")
    assert "missing_required_beat" in issues


def test_deterministic_validation_returns_empty_without_outline():
    data = {"hook": {"text": "anything"}, "body": [{"text": "b"}], "cta": {"text": "c"}}
    issues = av.validate_script_against_outline_deterministic(data, None, DIALOGUE_TRAP, "X")
    assert issues == []


# --- llm_architecture_and_creative_director_issues ---------------------------


def test_llm_eval_returns_issues_from_mocked_response():
    with patch.object(av, "call_openrouter_with_retry", return_value='{"issues": ["competitor_swappable", "no_memorable_device"]}'):
        issues = av.llm_architecture_and_creative_director_issues(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y"
        )
    assert issues == ["competitor_swappable", "no_memorable_device"]


def test_llm_eval_returns_empty_on_failure_never_raises():
    with patch.object(av, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        issues = av.llm_architecture_and_creative_director_issues(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y"
        )
    assert issues == []


def test_eval_prompt_lists_exact_issue_codes():
    for code in (
        "missing_required_beat", "architecture_abandoned", "no_emotional_progression",
        "proof_mechanism_missing", "weak_creative_idea", "no_memorable_device",
        "no_curiosity", "story_static", "unearned_cta", "competitor_swappable",
        "missing_turning_point", "missing_payoff", "generic_cta", "product_forced_into_story",
        "reference_dna_mismatch",
    ):
        assert f'"{code}"' in av._EVAL_SYSTEM_PROMPT, code


def test_eval_user_message_includes_reference_dna_notes_when_given():
    msg = av._eval_user_message(
        {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
        reference_dna_notes="Hook device: confrontational question.",
    )
    assert "confrontational question" in msg


def test_eval_user_message_omits_reference_dna_block_when_not_given():
    msg = av._eval_user_message({"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y")
    assert "Reference-DNA notes" not in msg


# --- all new issue codes route through the shared rewrite-reason machinery --


def test_all_new_issue_codes_have_rewrite_instructions():
    from app.services import script_quality as sq

    for code in (
        "missing_required_beat", "architecture_abandoned", "no_emotional_progression",
        "proof_mechanism_missing", "weak_creative_idea", "no_memorable_device",
        "no_curiosity", "story_static", "unearned_cta", "hook_not_intact", "product_reveal_moved",
        "missing_turning_point", "missing_payoff", "generic_cta", "product_forced_into_story",
        "reference_dna_mismatch", "generic_creative_premise", "slogan_as_hook", "product_first_hook",
    ):
        assert code in sq._ISSUE_INSTRUCTIONS, code
        reason = sq.rewrite_reason([code])
        assert len(reason) > 20
