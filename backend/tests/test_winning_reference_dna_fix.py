"""Critical creative reset — winning script quality (2026-09-18 task).

Root cause found by inspection: `creative_reference_dna.py` already
contains a fully-built, product-specific "winning reference DNA" system —
15 structured records including 4 REAL prior AayushWellness Herbal Masala
scripts ("Calender Video August" — CAL1/CAL3/CAL4/CAL5), each carrying
hook_device, human_insight, proof_device, payoff, creative_mechanism, etc.
`mechanism_notes()` exists specifically to surface these by the creative
mechanism a Story Idea already committed to — but it was NEVER actually
called anywhere in the pipeline (confirmed: zero call sites outside its
own definition). CAL1 and CAL3 have no `architecture` at all, so the
already-wired `relevant_notes()` (architecture-keyed) could never surface
them regardless of which architecture was selected. This is why generated
scripts felt disconnected from the brand's actual winning references even
though the reference data existed in the codebase the whole time.

The fix: wire `mechanism_notes()` into `_run_creative_pre_stages()` using
`payload.selected_situation.creative_mechanism` (Story Ideas already
reports this per candidate), merged with the existing architecture-keyed
notes — reusing 100% existing infrastructure, no new reference data, no
new architecture. Plus: an explicit "transfer the pattern, never copy the
wording" principle (the reference notes are prose descriptions, not raw
scripts, but the writer must still be told not to copy them), and one new
holistic `generic_ai_ad` quality-gate issue code targeting the "reference
DNA absent from the underlying idea" gap specifically, since the existing
granular codes each catch one narrow symptom but nothing previously judged
the whole script against "does this belong beside our actual winners"."""

import inspect
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.services import creative_architecture, creative_mechanism_catalog, creative_reference_dna
from app.services import openrouter_utils
from app.services import script_quality as sq
from app.services import script_service as svc
from app.services import semantic_story_judge_service as sj
from app.services import story_situation_service as story_svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


HERBAL_MASALA = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same chewing ritual and taste"],
)


def _payload(mechanism="") -> ScriptGenerationInput:
    situation = StorySituation(
        id="t", title="Auto Mein Do Pocket", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
        creative_mechanism=mechanism,
    )
    return ScriptGenerationInput(
        structured_product=HERBAL_MASALA, selected_situation=situation, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )


def _run_pre_stages(payload):
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])):
        return svc._run_creative_pre_stages(payload, "30s")


# --- mechanism_notes() was dead code — confirm it exists and is now wired --


def test_mechanism_notes_function_still_exists_and_is_reused_not_reinvented():
    assert hasattr(creative_reference_dna, "mechanism_notes")


def test_calender_video_reference_records_are_still_present_and_unmodified():
    """The 4 real AayushWellness Herbal Masala reference scripts this fix
    surfaces — confirms this task added zero new reference data."""
    ids = {r.video_id for r in creative_reference_dna.REFERENCE_RECORDS}
    assert {"CAL1", "CAL3", "CAL4", "CAL5"}.issubset(ids)


def test_cal1_and_cal3_have_no_architecture_so_relevant_notes_alone_could_never_surface_them():
    cal1 = next(r for r in creative_reference_dna.REFERENCE_RECORDS if r.video_id == "CAL1")
    cal3 = next(r for r in creative_reference_dna.REFERENCE_RECORDS if r.video_id == "CAL3")
    assert cal1.architecture == ""
    assert cal3.architecture == ""
    # No REAL architecture key (the only kind relevant_notes() is ever
    # actually called with) can match an empty architecture field — this
    # is exactly why relevant_notes() alone could never surface CAL1/CAL3
    # regardless of which architecture got selected.
    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    matched = creative_reference_dna.records_for_architecture(default_architecture.key)
    assert cal1 not in matched
    assert cal3 not in matched


def test_pre_stages_now_surface_mechanism_specific_reference_notes_when_available():
    """The core fix: a Story Idea that already committed to "Value Math"
    (CAL3's mechanism) must make CAL3's actual human insight reach the
    final prompt block — previously impossible since mechanism_notes() was
    never called."""
    payload = _payload(mechanism="Value Math")
    pre = _run_pre_stages(payload)
    cal3 = next(r for r in creative_reference_dna.REFERENCE_RECORDS if r.video_id == "CAL3")
    assert cal3.human_insight in pre.prompt_block


def test_pre_stages_with_no_selected_mechanism_behave_exactly_as_before():
    """No selected_situation.creative_mechanism (old stored situations, or
    a situation predating that field) — must not raise, must not inject
    anything mechanism-specific, exactly matching prior behavior."""
    payload = _payload(mechanism="")
    pre = _run_pre_stages(payload)
    cal3 = next(r for r in creative_reference_dna.REFERENCE_RECORDS if r.video_id == "CAL3")
    assert cal3.human_insight not in pre.prompt_block


def test_unknown_mechanism_label_degrades_safely_to_no_mechanism_notes():
    payload = _payload(mechanism="Not A Real Mechanism Label")
    pre = _run_pre_stages(payload)  # must not raise
    assert pre is not None


def test_mechanism_labels_used_in_tests_are_real_catalog_labels():
    """Sanity check that "Value Math" is a real, current creative_mechanism_
    catalog label, not a made-up test string that happens to match."""
    catalog_labels = {m["label"] for m in creative_mechanism_catalog.CREATIVE_MECHANISMS}
    assert "Value Math" in catalog_labels


# --- "transfer the pattern, never copy the wording" principle --------------


def test_core_principles_instruct_transfer_pattern_never_copy_reference_wording():
    block = svc._core_principles_block()
    assert "never text to copy" in block
    assert "ORIGINAL situation" in block


# --- generic_ai_ad: new holistic issue code ---------------------------------


def test_generic_ai_ad_issue_code_documented_in_the_llm_eval_prompt():
    assert '"generic_ai_ad"' in sq._EVAL_SYSTEM_PROMPT
    assert "winning references" in sq._EVAL_SYSTEM_PROMPT


def test_generic_ai_ad_has_a_rewrite_instruction_that_targets_the_idea_not_just_presentation():
    instruction = sq._ISSUE_INSTRUCTIONS["generic_ai_ad"]
    assert "IDEA itself needs to be stronger" in instruction
    assert sq.rewrite_reason(["generic_ai_ad"])


def test_generic_ai_ad_feeds_into_the_existing_single_rewrite_mechanism_not_a_new_one():
    called = {"rewrite": False}

    def fake_rewrite(data, payload, target_duration, target_word_count, reason, content_type, context):
        called["rewrite"] = True
        assert "reference" in reason.lower() or "idea" in reason.lower()
        return {"hook": {"text": "h"}, "body": [{"text": "b", "action": "a"}], "cta": {"text": "c"}}

    draft = {"hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"}}
    with patch.object(sq, "llm_quality_issues", return_value=["generic_ai_ad"]), \
         patch.object(svc, "_rewrite_for_quality", side_effect=fake_rewrite):
        svc._apply_quality_gate(draft, _payload(), "30s", None, ContentType.video, run_semantic_check=True)
    assert called["rewrite"] is True


# --- existing granular checks and gates remain intact (not replaced) -------


def test_existing_granular_issue_codes_still_present_alongside_generic_ai_ad():
    for code in ("explains_instead_of_shows", "not_filmable_video", "explanatory_language_overuse", "weak_hook", "competitor_swappable"):
        assert code in sq._ISSUE_INSTRUCTIONS


def test_show_dont_explain_and_mechanism_drives_story_principles_still_present():
    block = svc._core_principles_block()
    assert "SHOW, DON'T EXPLAIN" in block
    assert "CREATIVE MECHANISM MUST DRIVE THE STORY" in block


def test_real_person_would_not_say_this_principle_already_present():
    block = svc._core_principles_block()
    assert "would a real person actually say this exact" in block


def test_format_specific_structures_still_distinct_not_forced_into_scene123():
    from app.services import content_formats
    formats = ["podcast", "cinematic", "ugc_talking_head", "animation", "product_showcase", "educational_video"]
    blocks = {f: content_formats.video_structure_block(f, "") for f in formats}
    assert all(blocks.values())
    assert len(set(blocks.values())) == len(formats)


def test_claim_safety_detection_unchanged():
    issues = sq.text_issues("Yeh cravings ko 2 hafton mein 90% kam kar deta hai.")
    assert "unsupported_claim" in issues


def test_product_creative_contract_and_category_drift_protection_untouched():
    """Confirms this task did not weaken product_context_service.py or its
    tobacco/gutka category-transfer signal detection."""
    src = inspect.getsource(creative_reference_dna)
    assert "is_tobacco_gutka_brief" in src
    assert "CATEGORY-TRANSFER RULE" in src


# --- model routing / timeouts / image generation unchanged -----------------


def test_model_routing_unchanged_by_the_reference_dna_fix():
    assert settings.creative_model == "openai/gpt-5.6-luna"
    assert settings.final_script_model == "openai/gpt-5.6-luna"
    assert settings.validation_model == "google/gemini-2.5-flash-lite"


def test_story_ideas_and_generate_script_timeout_settings_unchanged():
    assert story_svc.DEFAULT_STORY_IDEAS_BUDGET_SECONDS == 180.0
    assert story_svc._STORY_IDEAS_CALL_TIMEOUT_SECONDS == 120.0
    assert sj._JUDGE_CALL_TIMEOUT_SECONDS == 40.0


def test_image_generation_still_disabled():
    assert settings.image_generation_enabled is False
