"""Phase 3C — Fix Story-to-Film Execution Quality.

Regression tests for the root-cause fix (premise generation grounded in the
user's chosen Story Situation, via situation_block) and the new Creative
Director story-execution checks (architecture_validation_service REVIEWER
2.5: title_story_mismatch, metaphor_not_embodied, no_concrete_event,
announcement_mode, hook_abstract_not_situational, payoff_repeats_setup).

Detection is semantic/LLM-based by design (the task explicitly forbids a
phrase blacklist), so these tests verify the PLUMBING that is actually
testable offline without a live call: prompt construction actually includes
the chosen situation/format context, response parsing/stripping is correct,
and the existing issue-code -> rewrite-instruction -> gate mechanism
correctly carries the new codes end to end. Whether a live model's judgment
is actually correct for a given script is verified separately by the live
benchmark (not by this file) — these mocked-response tests assume a
correctly-functioning judgment and check the code around it, per Case A-G
below (Part 18 of the task).
"""

import json
from unittest.mock import patch

import pytest

from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import architecture_validation_service as av
from app.services import creative_architecture, creative_premise_service as cps
from app.services import openrouter_utils, script_quality as sq, script_service as svc
from app.services.creative_architecture import ARCHITECTURES

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield

DOCTOR_SITUATION_BLOCK = (
    "Title: Doctor ki Advice, Healthy Life\n"
    "Description: A regular gutka chewer visits a doctor for an unrelated checkup and gets "
    "unexpected advice about switching.\n"
    "Persona: adult tobacco/gutka chewer, 30s\n"
    "Emotion: surprised, reflective\n"
    "Marketing angle: unexpected authority endorsement"
)

MAA_KI_DUA_SITUATION_BLOCK = (
    "Title: Maa Ki Dua, Badla Beta\n"
    "Description: A mother notices her son has quietly changed a long-standing habit and reacts.\n"
    "Persona: adult son, gutka chewer\n"
    "Emotion: pride, relief\n"
    "Marketing angle: family observation"
)


# --- Root-cause fix: premise generation grounded in the chosen situation ----


def test_premise_user_message_includes_chosen_situation_when_given():
    msg = cps._user_message(
        "Aayush Herbal Masala", "herbal_health", "adult chewers", "", [], "insight block",
        "Dialogue Trap", "purpose", "", situation_block=DOCTOR_SITUATION_BLOCK,
    )
    assert "CHOSEN STORY SITUATION" in msg
    assert "Doctor ki Advice, Healthy Life" in msg


def test_premise_user_message_omits_situation_block_when_not_given():
    msg = cps._user_message(
        "X", "Y", "Z", "", [], "insight", "Arch", "purpose", "",
    )
    assert "CHOSEN STORY SITUATION" not in msg


def test_premise_system_prompt_instructs_dramatizing_the_chosen_situation():
    assert "CHOSEN STORY SITUATION" in cps._SYSTEM_PROMPT
    assert "Doctor ki" in cps._SYSTEM_PROMPT  # the exact illustrative example from the task


def test_generate_premises_threads_situation_block_into_the_call():
    captured = {}

    def fake_generate_text(**kwargs):
        captured["contents"] = kwargs["contents"]
        return json.dumps({"candidates": []})

    with patch.object(cps, "call_openrouter_with_retry", side_effect=lambda fn, **kw: fn()), \
         patch.object(cps, "generate_text", side_effect=fake_generate_text):
        cps.generate_premises(
            product_name="X", category="Y", target_audience="Z", situation_block=DOCTOR_SITUATION_BLOCK,
        )
    assert "Doctor ki Advice" in captured["contents"][0]


# --- FILMABLE CONCEPT fields (Part 4) ---------------------------------------


def _premise(who="", concrete_event="", human_tension="", what_changes="", **overrides):
    p = cps.CreativePremise(
        statement="a premise", creative_device="device", situation="a situation",
        why_curious="curious", why_not_swappable="specific",
        who=who, concrete_event=concrete_event, human_tension=human_tension, what_changes=what_changes,
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def test_filmable_concept_weak_when_fields_unanswered():
    weak = _premise()  # every filmable field empty
    assert cps._is_filmable_concept_weak(weak) is True


def test_filmable_concept_strong_when_fields_concretely_answered():
    strong = _premise(
        who="a 32-year-old gutka chewer visiting a doctor for an unrelated checkup",
        concrete_event="the doctor notices his gums and asks about the habit directly",
        human_tension="hiding a habit from people who are supposed to know his health",
        what_changes="he leaves with a real alternative instead of a lecture",
    )
    assert cps._is_filmable_concept_weak(strong) is False


def test_filmable_concept_placeholder_values_still_count_as_weak():
    weak = _premise(who="N/A", concrete_event="none", human_tension="tbd", what_changes="-")
    assert cps._is_filmable_concept_weak(weak) is True


def test_select_strongest_premise_prefers_filmable_concept_over_weak_metaphor_only():
    weak_metaphor_only = _premise(
        who="", concrete_event="", human_tension="", what_changes="",
        scores={k: 5 for k in cps._SCORE_KEYS},
    )
    weak_metaphor_only.total_score = sum(weak_metaphor_only.scores.values())
    strong_filmable = _premise(
        who="a specific person", concrete_event="a specific event happens",
        human_tension="a specific observable tension", what_changes="a specific before/after",
        scores={k: 3 for k in cps._SCORE_KEYS},
    )
    strong_filmable.total_score = sum(strong_filmable.scores.values())
    chosen = cps.select_strongest_premise([weak_metaphor_only, strong_filmable])
    # Even though the metaphor-only candidate self-scored higher, the
    # deterministic filmable-concept filter runs first and excludes it.
    assert chosen is strong_filmable


def test_select_strongest_premise_falls_back_when_all_candidates_weak():
    only_weak = _premise(scores={k: 3 for k in cps._SCORE_KEYS})
    only_weak.total_score = sum(only_weak.scores.values())
    chosen = cps.select_strongest_premise([only_weak])
    assert chosen is only_weak  # never return None when at least one candidate exists


def test_prompt_block_includes_filmable_concept_fields():
    p = _premise(
        who="a doctor's patient", concrete_event="an unexpected diagnosis conversation",
        human_tension="fear of being judged", what_changes="he finally speaks up",
    )
    block = p.prompt_block()
    assert "a doctor's patient" in block
    assert "an unexpected diagnosis conversation" in block
    assert "fear of being judged" in block
    assert "he finally speaks up" in block


# --- architecture_validation_service: format-aware guidance ----------------


def test_format_guidance_static_is_lenient():
    guidance = av._format_guidance("static", "banner_ad")
    assert "STATIC" in guidance
    assert "no_concrete_event" in guidance


def test_format_guidance_testimonial_is_lenient():
    guidance = av._format_guidance("video", "testimonial")
    assert "testimonial" in guidance.lower()


def test_format_guidance_default_video_is_strict():
    guidance = av._format_guidance("video", "video_ad")
    assert "full strength" in guidance.lower()


def test_format_guidance_cinematic_is_strict():
    guidance = av._format_guidance("video", "cinematic")
    assert "full strength" in guidance.lower()


# --- architecture_validation_service: prompt construction ------------------


def test_eval_prompt_lists_phase3c_issue_codes():
    for code in (
        "title_story_mismatch", "metaphor_not_embodied", "no_concrete_event",
        "announcement_mode", "hook_abstract_not_situational", "payoff_repeats_setup",
    ):
        assert f'"{code}"' in av._EVAL_SYSTEM_PROMPT, code


def test_eval_user_message_includes_situation_block_when_given():
    msg = av._eval_user_message(
        {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
        situation_block=DOCTOR_SITUATION_BLOCK,
    )
    assert "CHOSEN STORY SITUATION" in msg
    assert "Doctor ki Advice, Healthy Life" in msg


def test_eval_user_message_omits_situation_block_when_not_given():
    msg = av._eval_user_message({"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y")
    assert "CHOSEN STORY SITUATION" not in msg


def test_eval_user_message_includes_format_guidance():
    msg = av._eval_user_message(
        {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
        content_type="static", format_value="banner_ad",
    )
    assert "FORMAT NOTE" in msg
    assert "STATIC" in msg


# --- evaluate_script_execution: safety-net stripping + score parsing -------


def test_title_story_mismatch_stripped_when_no_situation_given():
    mocked = json.dumps({"issues": ["title_story_mismatch", "weak_creative_idea"], "scores": {}})
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
            situation_block="",  # no situation given
        )
    assert "title_story_mismatch" not in result.issues
    assert "weak_creative_idea" in result.issues


def test_title_story_mismatch_kept_when_situation_given():
    mocked = json.dumps({"issues": ["title_story_mismatch"], "scores": {}})
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
            situation_block=DOCTOR_SITUATION_BLOCK,
        )
    assert "title_story_mismatch" in result.issues


def test_evaluate_script_execution_parses_scores_and_flags():
    mocked = json.dumps({
        "issues": ["announcement_mode", "metaphor_not_embodied"],
        "scores": {"story_execution": 2, "title_integrity": 1, "creative_concept_strength": 2},
        "announcement_mode": True, "abstract_copy_risk": True,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
            situation_block=DOCTOR_SITUATION_BLOCK,
        )
    assert result.scores["story_execution"] == 2
    assert result.announcement_mode is True
    assert result.abstract_copy_risk is True


def test_evaluate_script_execution_never_raises_on_failure():
    with patch.object(av, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        result = av.evaluate_script_execution(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
        )
    assert result.issues == []
    assert result.scores == {}


def test_llm_architecture_and_creative_director_issues_still_returns_plain_list():
    """Backward-compat wrapper used by _apply_architecture_gate."""
    mocked = json.dumps({"issues": ["no_memorable_device"], "scores": {}})
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        issues = av.llm_architecture_and_creative_director_issues(
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP, "X", "Y",
        )
    assert issues == ["no_memorable_device"]


# --- script_quality: rewrite instructions exist for every new code ---------


def test_all_phase3c_issue_codes_have_rewrite_instructions():
    for code in (
        "title_story_mismatch", "metaphor_not_embodied", "no_concrete_event",
        "announcement_mode", "hook_abstract_not_situational", "payoff_repeats_setup",
    ):
        assert code in sq._ISSUE_INSTRUCTIONS, code
        reason = sq.rewrite_reason([code])
        assert len(reason) > 20


# --- Part 18 regression cases (A-G) — plumbing-level, mocked judgment ------
# Each case supplies a MOCKED model response representing what a correctly-
# functioning Creative Director call should say for that script, and checks
# that evaluate_script_execution's parsing/pass-fail logic carries it through
# correctly end to end (issues list, .passed, format-aware code presence).


def _script(hook: str, body: list[str], cta: str) -> dict:
    return {
        "hook": {"text": hook},
        "body": [{"text": b} for b in body],
        "cta": {"text": cta},
    }


def test_case_a_doctor_title_generic_announcement_fails():
    # The actual reported failure: title promises a doctor scene, script is
    # a generic problem -> product -> ingredients -> lifestyle -> CTA copy
    # with no doctor content and an explained-not-embodied metaphor.
    script = _script(
        hook="Tambaku ki aadat ek be-rang loop jaisi hai.",
        body=[
            "Isi loop ko todne ke liye, main Aayush Wellness Herbal Masala suggest karta hoon.",
            "Yeh ek natural aur non-addictive alternative hai.",
            "Yeh herbal blend aapke overall wellness ko support karta hai.",
        ],
        cta="Apni life mein rang wapas laayein.",
    )
    mocked = json.dumps({
        "issues": ["title_story_mismatch", "metaphor_not_embodied", "announcement_mode", "payoff_repeats_setup"],
        "scores": {"story_execution": 2, "title_integrity": 1, "dramatic_event": 1, "creative_concept_strength": 2},
        "announcement_mode": True, "abstract_copy_risk": True,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            situation_block=DOCTOR_SITUATION_BLOCK, content_type="video", format_value="video_ad",
        )
    assert result.announcement_mode is True
    assert "title_story_mismatch" in result.issues
    assert result.scores["title_integrity"] <= 2
    assert not result.issues == []  # fails the gate


def test_case_b_doctor_title_genuine_doctor_scene_passes():
    script = _script(
        hook="Doctor ne seedha poocha — kab se chaba rahe ho?",
        body=[
            "Checkup ke beech mein, doctor ne uske gums dekhe aur seedha sawaal kiya.",
            "Woh jhijhak gaya, par doctor ne judge nahi kiya — ek switch suggest kiya.",
            "Aayush Herbal Masala — same ritual, bina tambaku ke.",
        ],
        cta="Apne doctor se poochiye — ya khud try kariye.",
    )
    mocked = json.dumps({
        "issues": [],
        "scores": {"story_execution": 4, "title_integrity": 5, "dramatic_event": 4, "creative_concept_strength": 4},
        "announcement_mode": False, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            situation_block=DOCTOR_SITUATION_BLOCK, content_type="video", format_value="video_ad",
        )
    assert result.passed is True
    assert result.scores["title_integrity"] >= 4


def test_case_c_maa_ki_dua_no_mother_son_relationship_fails():
    script = _script(
        hook="Habits change everything.",
        body=["Ek naya switch, ek nayi shuruaat.", "Aayush Herbal Masala try kariye."],
        cta="Switch karein aaj hi.",
    )
    mocked = json.dumps({
        "issues": ["title_story_mismatch", "announcement_mode"],
        "scores": {"title_integrity": 1, "human_tension": 1},
        "announcement_mode": True, "abstract_copy_risk": True,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            situation_block=MAA_KI_DUA_SITUATION_BLOCK, content_type="video", format_value="video_ad",
        )
    assert "title_story_mismatch" in result.issues
    assert result.passed is False


def test_case_d_maa_ki_dua_genuine_mother_son_change_passes():
    script = _script(
        hook="Maa ne kuch nahi kaha — bas dekha.",
        body=[
            "Beta ka packet ab gone tha, dabbe mein Aayush Herbal Masala tha.",
            "Maa ne kuch poocha nahi, bas ek muskaan di.",
        ],
        cta="Apni maa ko bhi ek wajah dijiye muskaane ki.",
    )
    mocked = json.dumps({
        "issues": [],
        "scores": {"title_integrity": 5, "human_tension": 4, "creative_concept_strength": 4},
        "announcement_mode": False, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            situation_block=MAA_KI_DUA_SITUATION_BLOCK, content_type="video", format_value="video_ad",
        )
    assert result.passed is True


def test_case_e_product_announcement_shape_fails_high_genericness():
    script = _script(
        hook="Tambaku chhodna mushkil hai?",
        body=["Aayush Herbal Masala mein hai Mulethi aur Amla.", "Yeh aapko refreshing feel deta hai."],
        cta="Aaj hi try kariye.",
    )
    mocked = json.dumps({
        "issues": ["announcement_mode", "generic_insight"],
        "scores": {"creative_concept_strength": 2, "story_execution": 2},
        "announcement_mode": True, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            content_type="video", format_value="video_ad",
        )
    assert result.announcement_mode is True
    assert result.scores["creative_concept_strength"] <= 2


def test_case_f_strong_visual_metaphor_demonstrated_through_action_passes():
    script = _script(
        hook="Woh roz wahi chair, wahi packet, wahi exit.",
        body=[
            "Aaj kuch alag hua — packet ki jagah Aayush Herbal Masala tha.",
            "Uska chehra pehli baar us routine mein badla.",
        ],
        cta="Apna routine badlo, ek din mein.",
    )
    mocked = json.dumps({
        "issues": [],
        "scores": {"visual_potential": 5, "dramatic_event": 4, "creative_concept_strength": 4},
        "announcement_mode": False, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            content_type="video", format_value="cinematic",
        )
    assert result.passed is True
    assert result.scores["visual_potential"] >= 4


# --- Part 17: bounded re-verification after the one allowed rewrite --------


def _doctor_payload() -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="Doctor ki Advice, Healthy Life",
        description="A regular gutka chewer visits a doctor and gets unexpected advice about switching.",
        emotion="surprised", persona="adult gutka and pan masala chewers trying to switch away from tobacco",
        marketing_angle="unexpected authority endorsement", category="c", difficulty="medium",
        estimated_length="30s", virality_score=5.0, recommended_angles=[],
    )
    product = StructuredProduct(
        product_name="Aayush Herbal Masala",
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
        key_benefits=["same ritual and taste"],
    )
    return ScriptGenerationInput(
        structured_product=product, selected_situation=situation, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


ANNOUNCEMENT_JSON = json.dumps({
    "hook": {"text": "Tambaku ki aadat ek be-rang loop jaisi hai."},
    "body": [{"text": "Main Aayush Herbal Masala suggest karta hoon, ek natural alternative."}],
    "cta": {"text": "Apni life mein rang wapas laayein."},
    "creative_mechanism": "problem_insight",
})
REBUILT_JSON = json.dumps({
    "hook": {"text": "Doctor ne seedha poocha — kab se chaba rahe ho?"},
    "body": [{"text": "Checkup ke beech mein doctor ne switch suggest kiya — Aayush Herbal Masala."}],
    "cta": {"text": "Apne doctor se poochiye."},
    "creative_mechanism": "mini_story",
})


def test_architecture_gate_re_checks_after_the_one_allowed_rewrite_and_does_not_loop():
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    write_call_count = {"n": 0}
    eval_call_count = {"n": 0}

    def fake_write_then_repair(*args, **kwargs):
        write_call_count["n"] += 1
        return ANNOUNCEMENT_JSON if write_call_count["n"] == 1 else REBUILT_JSON

    def fake_arch_eval(*args, **kwargs):
        eval_call_count["n"] += 1
        # First eval (on the announcement draft): flag it. Re-check eval
        # (on the rewritten draft): pass. A third call would mean the gate
        # looped past its bound — asserted against below.
        if eval_call_count["n"] == 1:
            return json.dumps({"issues": ["announcement_mode", "title_story_mismatch"], "scores": {}})
        return json.dumps({"issues": [], "scores": {}})

    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(av, "generate_text", side_effect=fake_arch_eval), \
         patch.object(svc, "generate_text", side_effect=fake_write_then_repair):
        result = svc.generate_script(_doctor_payload())

    # write_call_count is not asserted to an exact value here — _generate_with_
    # recovery may issue its own independent length-correction pass unrelated
    # to the architecture gate, so it isn't a clean proxy for "how many times
    # did the GATE rewrite". eval_call_count is the direct, precise proxy for
    # that: exactly flag-once then re-check-once, never a third (looping) call.
    assert eval_call_count["n"] == 2  # flag, then the bounded re-check — never a third
    assert "doctor" in result.hook.text.lower()


def test_case_g_ugc_testimonial_not_falsely_failed_for_lacking_cinematic_plot():
    script = _script(
        hook="Main pehle bhi try kar chuka tha, honestly kuch kaam nahi aaya.",
        body=["Phir dost ne Aayush Herbal Masala diya.", "Same chewing feel, bina tambaku ke — genuinely surprised tha."],
        cta="Khud try karke dekho.",
    )
    # A correctly-functioning judge, given the FORMAT NOTE for testimonial,
    # should NOT flag no_concrete_event just because there's no dramatized
    # scene — this is the "format-appropriate evaluation" Case G requires.
    mocked = json.dumps({
        "issues": [],
        "scores": {"story_execution": 4, "creative_concept_strength": 3},
        "announcement_mode": False, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = av.evaluate_script_execution(
            script, None, DIALOGUE_TRAP, "Aayush Herbal Masala", "adult gutka chewers",
            content_type="video", format_value="testimonial",
        )
    assert "no_concrete_event" not in result.issues
    assert result.passed is True
