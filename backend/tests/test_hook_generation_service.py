"""Tests for Hook Generation & Evaluation (AHM Creative DNA §2/§4)."""

from unittest.mock import patch

from app.services import hook_generation_service as hooks_svc


_GOOD_CANDIDATES_JSON = """{
  "candidates": [
    {
      "text": "Every Monday, before packing the school bag, she checks one WhatsApp group first.",
      "curiosity_question": "What is she checking for, and why does it matter more than the bag itself?",
      "mechanism": "social_observation",
      "reveals_product": false,
      "passes": true,
      "reject_reason": ""
    },
    {
      "text": "Every mother wants her child to be healthy.",
      "curiosity_question": "",
      "mechanism": "generic",
      "reveals_product": false,
      "passes": false,
      "reject_reason": "generic opener"
    },
    {
      "text": "Introducing Immune Care Tablets for busy moms.",
      "curiosity_question": "",
      "mechanism": "announcement",
      "reveals_product": true,
      "passes": false,
      "reject_reason": "reveals product immediately"
    }
  ]
}"""

_ALL_GENERIC_JSON = """{
  "candidates": [
    {"text": "Are you tired of feeling low on energy?", "curiosity_question": "", "mechanism": "question", "reveals_product": false, "passes": false, "reject_reason": "generic"},
    {"text": "Did you know most people are deficient?", "curiosity_question": "", "mechanism": "question", "reveals_product": false, "passes": false, "reject_reason": "generic"}
  ]
}"""


def test_generate_and_select_hook_picks_first_passing_candidate():
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=_GOOD_CANDIDATES_JSON):
        result = hooks_svc.generate_and_select_hook(
            product_name="Immune Care Tablets", category="immunity", target_audience="mothers",
            insight_block="", architecture_hook_pattern="mid-scene observation",
            product_reveal_early=False, language="hinglish",
        )
    assert result is not None
    assert result.passes is True
    assert "WhatsApp" in result.text


def test_generate_and_select_hook_rejects_generic_opener_even_if_self_marked_pass():
    # Model marks it "passes": true but the text matches a denylisted phrase —
    # the deterministic re-check must override the model's own grading.
    tricky_json = """{"candidates": [{"text": "Every mother wants her child to be healthy and strong.",
      "curiosity_question": "will she find the answer", "mechanism": "x", "reveals_product": false,
      "passes": true, "reject_reason": ""}]}"""
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=tricky_json):
        result = hooks_svc.generate_and_select_hook(
            product_name="X", category="y", target_audience="z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=False, language="english",
        )
    assert result is None


def test_generate_and_select_hook_rejects_product_name_leak_when_reveal_not_early():
    json_with_leak = """{"candidates": [{"text": "Immune Care Tablets are here to help your child.",
      "curiosity_question": "what will change", "mechanism": "x", "reveals_product": true,
      "passes": true, "reject_reason": ""}]}"""
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=json_with_leak):
        result = hooks_svc.generate_and_select_hook(
            product_name="Immune Care Tablets", category="y", target_audience="z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=False, language="english",
        )
    assert result is None


def test_generate_and_select_hook_allows_product_name_when_architecture_wants_early_reveal():
    json_with_reveal = """{"candidates": [{"text": "Immune Care Tablets, unwrapped for the first time.",
      "curiosity_question": "what does it actually look like", "mechanism": "demonstration",
      "reveals_product": true, "passes": true, "reject_reason": ""}]}"""
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=json_with_reveal):
        result = hooks_svc.generate_and_select_hook(
            product_name="Immune Care Tablets", category="y", target_audience="z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=True, language="english",
        )
    assert result is not None


def test_generate_and_select_hook_returns_none_when_all_candidates_fail():
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=_ALL_GENERIC_JSON):
        result = hooks_svc.generate_and_select_hook(
            product_name="X", category="y", target_audience="z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=False, language="english",
        )
    assert result is None


def test_generate_and_select_hook_returns_none_on_failure_never_raises():
    with patch.object(hooks_svc, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        result = hooks_svc.generate_and_select_hook(
            product_name="X", category="y", target_audience="z", insight_block="",
            architecture_hook_pattern="", product_reveal_early=False, language="english",
        )
    assert result is None


_SLOGAN_SHAPED_JSON = """{
  "candidates": [
    {
      "text": "Mom Ka Superpower",
      "curiosity_question": "what is the superpower",
      "mechanism": "question",
      "reveals_product": false,
      "passes": true,
      "reject_reason": ""
    },
    {
      "text": "Every Monday, before packing the school bag, she checks one WhatsApp group first.",
      "curiosity_question": "What is she checking for, and why does it matter more than the bag itself?",
      "mechanism": "social_observation",
      "reveals_product": false,
      "passes": true,
      "reject_reason": ""
    }
  ]
}"""


def test_generate_and_select_hook_rejects_slogan_shaped_title_even_if_self_marked_pass():
    with patch.object(hooks_svc, "call_openrouter_with_retry", return_value=_SLOGAN_SHAPED_JSON):
        result = hooks_svc.generate_and_select_hook(
            product_name="Immune Care Tablets", category="immunity", target_audience="mothers",
            insight_block="", architecture_hook_pattern="mid-scene observation",
            product_reveal_early=False, language="hinglish",
        )
    assert result is not None
    assert "WhatsApp" in result.text  # the slogan-shaped candidate is skipped, not picked


def test_user_message_includes_premise_block_when_given():
    msg = hooks_svc._user_message(
        "X", "Y", "Z", "insight", "pattern", False, "english", premise_block="PREMISE TEXT HERE",
    )
    assert "PREMISE TEXT HERE" in msg


def test_system_prompt_requires_hooks_to_open_into_given_premise():
    assert "premise" in hooks_svc._SYSTEM_PROMPT.lower()


def test_is_generic_matches_denylist_from_brief():
    for phrase in [
        "Every mother wants the best.",
        "We all know health is important.",
        "Your child's health matters most.",
        "In today's busy life, moms forget themselves.",
        "Take care of your family first.",
        "Health is wealth, after all.",
        "Are you tired of the same routine?",
        "Did you know most kids lack this?",
        "Introducing the newest way to stay healthy.",
        "Say goodbye to sick days forever.",
        "Because your health matters to us.",
    ]:
        assert hooks_svc._is_generic(phrase) is True, phrase
    assert hooks_svc._is_generic("Every Monday she checks one WhatsApp group before packing the bag.") is False
