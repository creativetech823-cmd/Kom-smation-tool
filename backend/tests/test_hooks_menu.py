"""Hooks Menu integration (2026-09-18 task) — a hook has two SEPARATE
layers (HOOK TACTIC = how attention is captured; CREATIVE MECHANISM = what
the idea is), stored and reasoned about separately end to end: Story Idea
generation -> hook_generation_service (script-writing time) -> the Creative
Director gate's hook-execution check."""

import json
from unittest.mock import patch

import pytest

from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import architecture_validation_service as av
from app.services import hook_generation_service as hooksvc
from app.services import hook_tactic_catalog as tactics
from app.services import openrouter_utils, semantic_story_judge_service as sj
from app.services import story_situation_service as svc
from app.services.creative_architecture import ARCHITECTURES

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]

HERBAL_MASALA = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same chewing ritual and taste"],
)


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _payload(count=6):
    return StorySituationsInput(
        structured_product=HERBAL_MASALA, product_category="herbal_health", count=count,
        script_language=ScriptLanguage.hinglish,
    )


def _candidate(title, hook_type="Question", **overrides):
    base = {
        "title": title, "description": f"description for {title}", "human_situation": "a specific person",
        "behavioral_tension": "a specific tension", "creative_mechanism": "Object-Driven Reveal",
        "creative_engine": "a specific behavior with a specific object and a specific turn",
        "product_role": "the specific job the product does",
        "hook_type": hook_type, "hook_mechanism": "fits because it creates curiosity here",
        "hook_execution": "a concrete opening scene the viewer sees", "emotion": "e", "persona": "p",
        "marketing_angle": "m", "category": "c", "difficulty": "easy", "estimated_length": "30s",
        "virality_score": 6.0, "recommended_angles": [],
    }
    base.update(overrides)
    return base


def _judgment_for(index, **overrides):
    raw = {
        "candidate_index": index, "semantic_category_drift": False, "product_role_alignment": 0.9,
        "creative_potential": 0.8, "genericness_risk": 0.2, "cluster_id": f"cluster_{index}",
    }
    raw.update(overrides)
    return sj._parse_judgment(raw)


# --- Hook tactic catalog -----------------------------------------------------


def test_catalog_has_all_18_named_tactics():
    labels = {t["label"] for t in tactics.HOOK_TACTICS}
    for expected in (
        "Dramatize the Problem", "Motion Tricks", "Podcast", "Reminder", "The Absurd Alternative",
        "In Real Life", "Reaction in Action", "Question", "Evolution", "Shocking Effect",
        "On Trend / FOMO", "Teaser Hook", "Emphasize the Solution", "Negative Hook", "Make Me Laugh",
        "Satisfying Intro", "Destroy / Toss & Burn", "Skeptical Voice",
    ):
        assert expected in labels, expected
    assert len(tactics.HOOK_TACTICS) == 18


def test_valid_hook_tactic_label_canonicalizes():
    assert tactics.valid_hook_tactic_label("  question  ") == "Question"
    assert tactics.valid_hook_tactic_label("Nonsense Invented Tactic") in labels_set()


def labels_set():
    return {t["label"] for t in tactics.HOOK_TACTICS}


# --- Story Idea generation: hook fields, prompt, quality filter, diversity -


def test_system_prompt_distinguishes_tactic_from_mechanism():
    prompt = svc._system_prompt(ScriptLanguage.hinglish)
    assert "HOOKS MENU" in prompt
    assert "hook_type" in prompt
    assert "never confuse them" in prompt.lower() or "never the same thing" in prompt.lower() or "different thing" in prompt.lower()


def test_hook_fields_populated_end_to_end():
    card = _candidate("A Real Idea", hook_type="Reaction in Action", hook_mechanism="fits the peer moment", hook_execution="a colleague's face reacts before any explanation")
    response = json.dumps({"situations": [card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    s = result.situations[0]
    assert s.hook_type == "Reaction in Action"
    assert s.hook_mechanism == "fits the peer moment"
    assert "reacts" in s.hook_execution


def test_invalid_hook_type_falls_back_to_default():
    card = _candidate("Idea", hook_type="Something Invented")
    response = json.dumps({"situations": [card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert result.situations[0].hook_type in labels_set()


def test_generic_hook_execution_is_filtered_out():
    bad = _candidate("Bad Hook", hook_execution="Every mother wants the best for her family.")
    good = _candidate("Good Hook", hook_execution="He reaches into his pocket, expecting the old packet.")
    response = json.dumps({"situations": [bad, good]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    titles = {s.title for s in result.situations}
    assert "Bad Hook" not in titles
    assert "Good Hook" in titles


def test_missing_hook_execution_is_not_rejected_fail_open():
    """Absence of hook_execution is NOT itself a rejection reason — only an
    explicit generic-phrase match is (see _hook_quality_prefilter_reason's
    fail-open-on-absence convention)."""
    card = _candidate("No Hook Fields Yet", hook_execution="")
    response = json.dumps({"situations": [card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert len(result.situations) == 1


def test_final_six_gets_hook_tactic_diversity_not_same_2_or_3_tactics():
    # Mechanism varies too, independently of hook_type — realistic (a real
    # pool doesn't repeat mechanism AND hook_type together) and isolates the
    # hook-type cap as the thing actually under test, not the mechanism cap.
    dominant = [_candidate(f"Q{i}", hook_type="Question", creative_mechanism=f"Mech {i}", virality_score=9.0) for i in range(6)]
    distinct = [
        _candidate("Teaser One", hook_type="Teaser Hook", creative_mechanism="Ritual Replacement"),
        _candidate("Reaction One", hook_type="Reaction in Action", creative_mechanism="Value Math"),
        _candidate("Skeptic One", hook_type="Skeptical Voice", creative_mechanism="Peer Realization"),
    ]
    cards = dominant + distinct
    response = json.dumps({"situations": cards})
    judgments = (
        [_judgment_for(i, creative_potential=0.95) for i in range(6)]
        + [_judgment_for(i, creative_potential=0.5) for i in range(6, 9)]
    )
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload())
    hook_types = [s.hook_type for s in result.situations]
    assert hook_types.count("Question") <= svc._MAX_PER_HOOK_TYPE_IN_FINAL
    assert "Teaser Hook" in hook_types
    assert "Reaction in Action" in hook_types
    assert "Skeptical Voice" in hook_types


# --- Semantic judge sees hook fields ----------------------------------------


def test_semantic_judge_candidate_block_includes_hook_fields():
    block = sj._candidate_block(0, {"title": "T", "hook_type": "Question", "hook_execution": "a real scene"})
    assert "hook_type: Question" in block
    assert "a real scene" in block


# --- Script-writing stage: hook_generation_service honors the selected tactic


def test_hook_generation_user_message_includes_approved_tactic():
    msg = hooksvc._user_message(
        "Aayush Herbal Masala", "herbal_health", "adult gutka chewers", "insight", "hook pattern", False,
        "Hinglish", hook_type="Question", hook_mechanism="creates curiosity", hook_execution="he asks his friend a question",
    )
    assert "APPROVED HOOK TACTIC" in msg
    assert "Question" in msg
    assert "he asks his friend a question" in msg


def test_hook_generation_user_message_omits_tactic_block_when_none_given():
    msg = hooksvc._user_message(
        "X", "Y", "Z", "insight", "pattern", False, "Hinglish",
    )
    assert "APPROVED HOOK TACTIC" not in msg


def test_system_prompt_instructs_executing_approved_tactic():
    assert "APPROVED HOOK TACTIC" in hooksvc._SYSTEM_PROMPT


# --- Creative Director gate: hook_tactic_not_executed issue code -----------


def test_eval_prompt_lists_hook_tactic_not_executed_code():
    assert '"hook_tactic_not_executed"' in av._EVAL_SYSTEM_PROMPT


def test_hook_tactic_not_executed_stripped_when_no_tactic_in_situation_block():
    mocked = json.dumps({"issues": ["hook_tactic_not_executed"], "scores": {}})
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
            situation_block="Title: Some Title\nDescription: d",  # no "Approved hook tactic:" line
        )
    assert "hook_tactic_not_executed" not in result.issues


def test_hook_tactic_not_executed_kept_when_tactic_given():
    mocked = json.dumps({"issues": ["hook_tactic_not_executed"], "scores": {}})
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
            situation_block="Title: T\nApproved hook tactic: Question\nWhy this tactic fits: x\nApproved hook execution: y",
        )
    assert "hook_tactic_not_executed" in result.issues


def test_script_service_story_situation_block_includes_hook_tactic():
    from app.services import script_service as ssvc
    from app.models.product import StorySituation

    situation = StorySituation(
        id="t", title="A Title", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
        hook_type="Question", hook_mechanism="fits well", hook_execution="a real question in-scene",
    )
    block = ssvc._story_situation_block(situation)
    assert "Approved hook tactic: Question" in block
    assert "a real question in-scene" in block


def test_script_service_story_situation_block_omits_hook_lines_when_no_hook_type():
    from app.services import script_service as ssvc
    from app.models.product import StorySituation

    situation = StorySituation(
        id="t", title="A Title", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
    )
    block = ssvc._story_situation_block(situation)
    assert "Approved hook tactic" not in block


def test_rewrite_instruction_exists_for_hook_tactic_not_executed():
    from app.services import script_quality as sq
    assert "hook_tactic_not_executed" in sq._ISSUE_INSTRUCTIONS
    assert len(sq.rewrite_reason(["hook_tactic_not_executed"])) > 20
