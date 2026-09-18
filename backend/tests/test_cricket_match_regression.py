"""Regression tests for the reported "Cricket Match, Naya Swag" bug report:

1. An unsupported ingredient-efficacy claim ("Ashwagandha... aaram deta hai")
   reached a user unrejected. Root-caused (see test_claim_safety_service.py's
   dedicated regression test for the claim-safety half) to a detector-
   vocabulary gap, now fixed there.

2. The final script "collapsed the cricket concept into generic ad copy".
   Traced to a real wiring gap: _context_block() — the actual prompt every
   script-writing call receives — never included the approved Story Idea's
   creative_mechanism/creative_engine/hook_type/hook_execution fields at
   all; they only reached the writer indirectly (and lossily) via premise
   generation re-deriving them from a side-channel that doesn't even run for
   regenerate_script_section. This file tests the fix: those fields now
   reach the writer's own prompt directly.

Also covers a real, adjacent wiring gap found during this investigation:
regenerate_script_section()'s broad-scope path (Shorten/Extend/"Entire
Script"-with-instruction) never invoked the claim-safety hard gate at all —
only the narrow "pure full regenerate" path (which routes through
_generate_full_script) did. Fixed to invoke it consistently.
"""

import json
from unittest.mock import patch

import pytest

from app.models.product import (
    ContentType, GeneratedScript, ScriptGenerationInput, ScriptLanguage, ScriptLine,
    ScriptRegenerateScope, ScriptSectionRegenerateInput, StorySituation, StructuredProduct,
)
from app.services import openrouter_utils, script_quality as sq, script_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


PRODUCT = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla", "Ashwagandha"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same ritual and taste"],
)

CRICKET_SITUATION = StorySituation(
    id="t", title="Cricket Match, Naya Swag",
    description="Friends watch a cricket match together and one of them has quietly switched.",
    emotion="pride", persona="adult gutka chewer, cricket fan", marketing_angle="peer observation",
    category="Social", difficulty="medium", estimated_length="30s", virality_score=7.0,
    creative_mechanism="Peer Realization",
    creative_engine="During a tense over, a friend notices the familiar packet in his hand has changed — "
    "no words needed, just a raised eyebrow and a nod.",
    human_situation="a group of friends watching a match at home, mid-over tension",
    behavioral_tension="hiding a habit from friends who'd notice immediately",
    product_role="the object his hand reaches for during the tense moment",
    hook_type="Reaction in Action",
    hook_mechanism="the cricket-watching context makes a sudden reaction read as urgent/exciting",
    hook_execution="A wicket falls. Everyone erupts. In the chaos, a friend's eyes flick to the packet in his hand — surprise, not the usual one.",
)


# --- Part 2: writer-prompt fidelity (creative_mechanism/creative_engine/hook) -


def test_approved_concept_block_includes_mechanism_engine_and_hook_execution():
    block = svc._approved_concept_block(CRICKET_SITUATION)
    assert "Peer Realization" in block
    assert "raised eyebrow and a nod" in block
    assert "Reaction in Action" in block
    assert "eyes flick to the packet" in block
    assert "hiding a habit from friends" in block


def test_approved_concept_block_empty_for_situation_missing_these_fields():
    bare = StorySituation(
        id="t", title="T", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="30s", virality_score=5.0,
    )
    assert svc._approved_concept_block(bare) == ""


def test_context_block_writer_prompt_includes_approved_concept_directly():
    """The definitive fix verification: _context_block is the ACTUAL prompt
    text sent to the writer (not a side-channel like pre.situation_block
    that only reaches premise generation) — it must carry the approved
    concept directly."""
    payload = ScriptGenerationInput(
        structured_product=PRODUCT, selected_situation=CRICKET_SITUATION, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )
    block = svc._context_block(payload, "30s")
    assert "Approved creative mechanism: Peer Realization" in block
    assert "raised eyebrow and a nod" in block
    assert "Approved hook tactic: Reaction in Action" in block
    assert "eyes flick to the packet" in block


def test_full_generation_writer_message_actually_contains_the_approved_mechanism():
    """End-to-end: the REAL user_message handed to the final-script LLM call
    (not just _context_block in isolation) contains the approved concept —
    proves the writer is not reconstructing from a thinner summary."""
    from app.services import creative_architecture

    default_architecture = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    captured = {}

    def fake_write(*args, **kwargs):
        captured["user_message"] = kwargs["contents"][0]
        return json.dumps({
            "hook": {"text": "A wicket falls. A friend's eyes flick to a changed packet."},
            "body": [{"text": "No words needed — just a nod."}],
            "cta": {"text": "Try the switch today."},
            "creative_mechanism": "mini_story",
        })

    payload = ScriptGenerationInput(
        structured_product=PRODUCT, selected_situation=CRICKET_SITUATION, product_category="herbal_health",
        platform="instagram_reel", script_language=ScriptLanguage.hinglish, content_type=ContentType.video,
    )
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=default_architecture), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "check_claim_safety_and_coercion", return_value=svc.claim_safety_service.ClaimSafetyResult(passed=True)), \
         patch.object(svc, "generate_text", side_effect=fake_write):
        svc.generate_script(payload)

    assert "Approved creative mechanism: Peer Realization" in captured["user_message"]
    assert "raised eyebrow and a nod" in captured["user_message"]
    assert "Reaction in Action" in captured["user_message"]


# --- Part 1 (wiring half): regenerate_script_section now runs claim safety --


def _current_script() -> GeneratedScript:
    return GeneratedScript(
        hook=ScriptLine(text="old hook"), body=[ScriptLine(text="old body")], cta=ScriptLine(text="old cta"),
        situation=CRICKET_SITUATION, script_language=ScriptLanguage.hinglish,
    )


def test_broad_regenerate_now_invokes_claim_safety_gate():
    """Previously: regenerate_script_section's full/length broad-scope path
    called _apply_quality_gate only, never _apply_claim_safety_gate — a real
    wiring gap found while diagnosing the reported claim. Now fixed."""
    payload = ScriptSectionRegenerateInput(
        structured_product=PRODUCT, selected_situation=CRICKET_SITUATION, product_category="herbal_health",
        current_script=_current_script(), scope=ScriptRegenerateScope.full,
        custom_instruction="make it punchier",  # forces the broad, non-"pure-full" path
        script_language=ScriptLanguage.hinglish,
    )
    with patch.object(svc, "generate_text", return_value=json.dumps({
        "hook": {"text": "h"}, "body": [{"text": "b"}], "cta": {"text": "c"},
    })), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'), \
         patch.object(svc.claim_safety_service, "check_claim_safety_and_coercion") as mock_claim_gate:
        mock_claim_gate.return_value = svc.claim_safety_service.ClaimSafetyResult(passed=True)
        svc.regenerate_script_section(payload)
    mock_claim_gate.assert_called_once()


def test_broad_regenerate_with_unsupported_claim_triggers_rewrite():
    call_count = {"n": 0}

    def fake_write(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps({
                "hook": {"text": "h"},
                "body": [{"text": "Ashwagandha stress mein aaram deta hai."}],
                "cta": {"text": "c"},
            })
        return json.dumps({"hook": {"text": "h"}, "body": [{"text": "safe rewritten body"}], "cta": {"text": "c"}})

    payload = ScriptSectionRegenerateInput(
        structured_product=PRODUCT, selected_situation=CRICKET_SITUATION, product_category="herbal_health",
        current_script=_current_script(), scope=ScriptRegenerateScope.full,
        custom_instruction="make it punchier", script_language=ScriptLanguage.hinglish,
    )
    with patch.object(svc, "generate_text", side_effect=fake_write), \
         patch.object(sq, "generate_text", return_value='{"pass": true, "issues": []}'):
        result = svc.regenerate_script_section(payload)

    # The unsupported claim must not survive into the final result, and the
    # claim-safety gate's rewrite must have actually been attempted (more
    # than just the original write) — the exact total call count also
    # depends on the (separately tested, unrelated) quality gate's own
    # independent checks on this minimal fixture, so it isn't asserted here.
    assert "aaram" not in result.body[0].text.lower()
    assert call_count["n"] >= 2


def test_narrow_regenerate_scope_unaffected_by_this_fix():
    """The narrow scope (single-block edits) deliberately still does not run
    the broad claim-safety gate — out of scope for this fix, unchanged
    behavior, asserted here so a future change doesn't silently alter it."""
    payload = ScriptSectionRegenerateInput(
        structured_product=PRODUCT, selected_situation=CRICKET_SITUATION, product_category="herbal_health",
        current_script=_current_script(), scope=ScriptRegenerateScope.hook,
        script_language=ScriptLanguage.hinglish,
    )
    full_script_response = json.dumps({
        "hook": {"text": "new hook"}, "body": [{"text": "old body"}], "cta": {"text": "old cta"},
    })
    with patch.object(svc, "generate_text", return_value=full_script_response), \
         patch.object(svc.claim_safety_service, "check_claim_safety_and_coercion") as mock_claim_gate:
        svc.regenerate_script_section(payload)
    mock_claim_gate.assert_not_called()
