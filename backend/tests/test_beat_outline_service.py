"""Tests for Beat Outline generation & validation — the actual enforcement
upgrade that makes architecture selection constrain the script rather than
merely advise it."""

from unittest.mock import patch

from app.services import beat_outline_service as outline_svc
from app.services.creative_architecture import ARCHITECTURES


DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]  # required_beats has 7 entries, "very late" reveal
PURE_DEMO = ARCHITECTURES["pure_demonstration"]  # required_beats has 5 entries, "Immediate and total" reveal


def _outline(beats_count=7, reveal_beat=6, proof_beat=6, payoff_beat=6, cta_beat=7):
    beats = [
        outline_svc.BeatOutlineItem(beat_number=i + 1, purpose=f"p{i}", content=f"content {i}", emotional_state="x")
        for i in range(beats_count)
    ]
    return outline_svc.BeatOutline(
        architecture="dialogue_trap", hook="test hook", human_insight="test insight",
        beats=beats, product_reveal_beat=reveal_beat, proof_beat=proof_beat,
        payoff_beat=payoff_beat, cta_beat=cta_beat,
    )


# --- expected_reveal_fraction (deterministic band parsing) ------------------


def test_expected_reveal_fraction_very_late():
    lo, hi = outline_svc.expected_reveal_fraction(DIALOGUE_TRAP)
    assert lo >= 0.5  # "very late" architecture


def test_expected_reveal_fraction_immediate_total():
    lo, hi = outline_svc.expected_reveal_fraction(PURE_DEMO)
    assert hi <= 0.25  # "Immediate and total" architecture


def test_expected_reveal_fraction_unspecified_has_no_constraint():
    import dataclasses

    fake = dataclasses.replace(DIALOGUE_TRAP, product_reveal_logic="no timing keyword here at all")
    assert outline_svc.expected_reveal_fraction(fake) == (0.0, 1.0)


# --- validate_outline_deterministic ------------------------------------------


def test_validate_outline_deterministic_passes_a_well_formed_late_reveal_outline():
    outline = _outline(beats_count=7, reveal_beat=6, proof_beat=6, payoff_beat=6, cta_beat=7)
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP)
    assert "outline_cta_not_final_beat" not in issues
    assert "outline_product_reveal_timing_off" not in issues


def test_validate_outline_deterministic_flags_cta_not_final_beat():
    outline = _outline(beats_count=7, reveal_beat=6, cta_beat=3)
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP)
    assert "outline_cta_not_final_beat" in issues


def test_validate_outline_deterministic_flags_reveal_too_early_for_very_late_architecture():
    outline = _outline(beats_count=7, reveal_beat=1, proof_beat=6, payoff_beat=6, cta_beat=7)
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP)
    assert "outline_product_reveal_timing_off" in issues


def test_validate_outline_deterministic_flags_missing_required_beats():
    outline = _outline(beats_count=2, reveal_beat=1, proof_beat=1, payoff_beat=2, cta_beat=2)
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP)  # requires 7 beats
    assert "outline_missing_required_beats" in issues


def test_validate_outline_deterministic_flags_empty_outline():
    empty = outline_svc.BeatOutline(
        architecture="x", hook="", human_insight="", beats=[],
        product_reveal_beat=0, proof_beat=0, payoff_beat=0, cta_beat=0,
    )
    assert outline_svc.validate_outline_deterministic(empty, DIALOGUE_TRAP) == ["outline_empty"]


def test_validate_outline_deterministic_flags_duplicate_beats():
    beats = [
        outline_svc.BeatOutlineItem(beat_number=1, purpose="a", content="same content here", emotional_state="x"),
        outline_svc.BeatOutlineItem(beat_number=2, purpose="b", content="same content here", emotional_state="y"),
        outline_svc.BeatOutlineItem(beat_number=3, purpose="c", content="different", emotional_state="z"),
        outline_svc.BeatOutlineItem(beat_number=4, purpose="d", content="another", emotional_state="w"),
        outline_svc.BeatOutlineItem(beat_number=5, purpose="e", content="fifth", emotional_state="v"),
        outline_svc.BeatOutlineItem(beat_number=6, purpose="f", content="sixth", emotional_state="u"),
        outline_svc.BeatOutlineItem(beat_number=7, purpose="g", content="seventh", emotional_state="t"),
    ]
    outline = outline_svc.BeatOutline(
        architecture="x", hook="h", human_insight="i", beats=beats,
        product_reveal_beat=6, proof_beat=6, payoff_beat=6, cta_beat=7,
    )
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP)
    assert "outline_duplicate_beats" in issues


# --- generate_and_validate_outline (LLM orchestration + retry) --------------

_GOOD_OUTLINE_JSON = """{
  "beats": [
    {"beat_number": 1, "purpose": "situation", "content": "a", "emotional_state": "neutral", "must_include": []},
    {"beat_number": 2, "purpose": "confession", "content": "b", "emotional_state": "defensive", "must_include": []},
    {"beat_number": 3, "purpose": "challenge", "content": "c", "emotional_state": "challenged", "must_include": []},
    {"beat_number": 4, "purpose": "helplessness", "content": "d", "emotional_state": "stuck", "must_include": []},
    {"beat_number": 5, "purpose": "product enters", "content": "e", "emotional_state": "hopeful", "must_include": []},
    {"beat_number": 6, "purpose": "proof", "content": "f", "emotional_state": "relieved", "must_include": []},
    {"beat_number": 7, "purpose": "cta", "content": "g", "emotional_state": "confident", "must_include": []}
  ],
  "product_reveal_beat": 5,
  "proof_beat": 6,
  "payoff_beat": 6,
  "cta_beat": 7
}"""

_BAD_OUTLINE_JSON = """{
  "beats": [
    {"beat_number": 1, "purpose": "product", "content": "product shown first", "emotional_state": "neutral", "must_include": []},
    {"beat_number": 2, "purpose": "cta", "content": "buy now", "emotional_state": "neutral", "must_include": []}
  ],
  "product_reveal_beat": 1,
  "proof_beat": 0,
  "payoff_beat": 0,
  "cta_beat": 2
}"""


def test_generate_and_validate_outline_accepts_good_outline_on_first_try():
    with patch.object(outline_svc, "call_openrouter_with_retry", return_value=_GOOD_OUTLINE_JSON) as mock_call, \
         patch.object(outline_svc, "validate_outline_llm", return_value=[]):
        outline, issues = outline_svc.generate_and_validate_outline(
            architecture=DIALOGUE_TRAP, hook="test hook", human_insight="test insight",
            product_name="X", category="y", target_audience="z", target_duration_bucket="30s",
        )
    assert mock_call.call_count == 1
    assert outline is not None
    assert issues == []
    assert len(outline.beats) == 7


def test_generate_and_validate_outline_retries_once_then_gives_up_at_max_attempts():
    with patch.object(outline_svc, "call_openrouter_with_retry", side_effect=[_BAD_OUTLINE_JSON, _BAD_OUTLINE_JSON]) as mock_call:
        outline, issues = outline_svc.generate_and_validate_outline(
            architecture=DIALOGUE_TRAP, hook="test hook", human_insight="test insight",
            product_name="X", category="y", target_audience="z", target_duration_bucket="30s",
        )
    assert mock_call.call_count == outline_svc.MAX_OUTLINE_ATTEMPTS
    assert outline is not None  # still returns the last attempt, never blocks generation
    assert len(issues) > 0  # but honestly reports it didn't pass


def test_generate_and_validate_outline_recovers_on_second_attempt():
    with patch.object(outline_svc, "call_openrouter_with_retry", side_effect=[_BAD_OUTLINE_JSON, _GOOD_OUTLINE_JSON]) as mock_call, \
         patch.object(outline_svc, "validate_outline_llm", return_value=[]):
        outline, issues = outline_svc.generate_and_validate_outline(
            architecture=DIALOGUE_TRAP, hook="test hook", human_insight="test insight",
            product_name="X", category="y", target_audience="z", target_duration_bucket="30s",
        )
    assert mock_call.call_count == 2
    assert issues == []
    assert len(outline.beats) == 7


def test_generate_and_validate_outline_threads_premise_into_prompt():
    from app.services.creative_premise_service import CreativePremise

    premise = CreativePremise(
        statement="A specific reveal", creative_device="reversal", situation="a kitchen argument",
        why_curious="curiosity", why_not_swappable="specific",
    )
    with patch.object(outline_svc, "call_openrouter_with_retry", return_value=_GOOD_OUTLINE_JSON), \
         patch.object(outline_svc, "validate_outline_llm", return_value=[]):
        outline_svc.generate_and_validate_outline(
            architecture=DIALOGUE_TRAP, hook="test hook", human_insight="test insight",
            product_name="X", category="y", target_audience="z", target_duration_bucket="30s",
            premise=premise,
        )
    msg = outline_svc._outline_user_message(
        DIALOGUE_TRAP, "test hook", "test insight", "X", "y", "z", "30s", premise=premise,
    )
    assert premise.statement in msg


def test_outline_system_prompt_requires_premise_execution_not_reinvention():
    assert "premise" in outline_svc._OUTLINE_SYSTEM_PROMPT.lower()


def test_llm_validation_prompt_lists_premise_diluted_code():
    assert "premise_diluted" in outline_svc._LLM_VALIDATION_SYSTEM_PROMPT


def test_generate_and_validate_outline_never_raises_on_total_failure():
    with patch.object(outline_svc, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        outline, issues = outline_svc.generate_and_validate_outline(
            architecture=DIALOGUE_TRAP, hook="test hook", human_insight="test insight",
            product_name="X", category="y", target_audience="z", target_duration_bucket="30s",
        )
    assert outline is None
    assert issues == []


def test_beat_outline_prompt_block_contains_hard_constraints():
    outline = _outline()
    block = outline.prompt_block()
    for phrase in ("remove beats", "reorder beats", "invent a different architecture", "introduce the product earlier", "filler to reach length"):
        assert phrase in block
