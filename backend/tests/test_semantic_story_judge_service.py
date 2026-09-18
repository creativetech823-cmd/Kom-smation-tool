"""Phase 3 — unit tests for the Semantic Story Judge: response parsing,
decision policy (clear_pass/clear_drift/uncertain), dedup-by-cluster, and
failure handling (must never silently pass a candidate on judge failure)."""

import json
from unittest.mock import patch

import pytest

from app.services import openrouter_utils, semantic_story_judge_service as sj
from app.services.product_context_service import build_product_creative_contract

HERBAL_MASALA_CONTRACT = build_product_creative_contract(
    product_name="Aayush Herbal Masala", category="herbal_health",
    target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
    usp="a 0% tobacco, 0% supari herbal chew",
)


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _judgment(**overrides) -> dict:
    base = {
        "candidate_index": 0, "semantic_category_drift": False, "reason": "",
        "product_truth_alignment": 0.9, "audience_alignment": 0.9, "behavior_alignment": 0.9,
        "product_role_alignment": 0.9, "creative_potential": 0.7, "memorability": 0.7,
        "visual_potential": 0.7, "genericness_risk": 0.2, "claim_safety": 1.0,
        "territory_alignment": None, "cluster_id": "c0",
    }
    base.update(overrides)
    return base


# --- decision policy ----------------------------------------------------


def test_decision_clear_pass_when_drift_false_and_role_alignment_high():
    j = sj._parse_judgment(_judgment(product_role_alignment=0.85))
    assert j.decision == "clear_pass"
    assert j.passed is True


def test_decision_clear_drift_when_semantic_drift_true():
    j = sj._parse_judgment(_judgment(semantic_category_drift=True, product_role_alignment=0.9))
    assert j.decision == "clear_drift"
    assert j.passed is False


def test_decision_clear_drift_when_role_alignment_very_low_even_without_drift_flag():
    j = sj._parse_judgment(_judgment(semantic_category_drift=False, product_role_alignment=0.2))
    assert j.decision == "clear_drift"


def test_decision_uncertain_is_never_treated_as_pass():
    j = sj._parse_judgment(_judgment(semantic_category_drift=False, product_role_alignment=0.55))
    assert j.decision == "uncertain"
    assert j.passed is False


# --- parsing robustness ---------------------------------------------------


def test_parse_judgment_handles_missing_optional_fields():
    j = sj._parse_judgment({"candidate_index": 2, "semantic_category_drift": False})
    assert j.candidate_index == 2
    assert j.product_role_alignment == 0.0
    assert j.cluster_id  # always gets a fallback cluster id


def test_parse_judgment_returns_none_for_non_dict():
    assert sj._parse_judgment("not a dict") is None


def test_parse_judgment_returns_none_for_missing_candidate_index():
    assert sj._parse_judgment({"semantic_category_drift": False}) is None


# --- dedupe_by_cluster -----------------------------------------------------


def test_dedupe_keeps_highest_creative_potential_per_cluster():
    judgments = [
        sj._parse_judgment(_judgment(candidate_index=0, cluster_id="A", creative_potential=0.5)),
        sj._parse_judgment(_judgment(candidate_index=1, cluster_id="A", creative_potential=0.9)),
        sj._parse_judgment(_judgment(candidate_index=2, cluster_id="B", creative_potential=0.6)),
    ]
    keep = sj.dedupe_by_cluster(judgments)
    assert keep == {1, 2}


def test_dedupe_breaks_ties_by_lower_genericness_risk():
    judgments = [
        sj._parse_judgment(_judgment(candidate_index=0, cluster_id="A", creative_potential=0.7, genericness_risk=0.6)),
        sj._parse_judgment(_judgment(candidate_index=1, cluster_id="A", creative_potential=0.7, genericness_risk=0.1)),
    ]
    keep = sj.dedupe_by_cluster(judgments)
    assert keep == {1}


def test_dedupe_keeps_all_distinct_clusters():
    judgments = [
        sj._parse_judgment(_judgment(candidate_index=i, cluster_id=f"cluster_{i}"))
        for i in range(4)
    ]
    assert sj.dedupe_by_cluster(judgments) == {0, 1, 2, 3}


# --- judge_story_situations: real call shape + failure handling -----------


def test_judge_story_situations_uses_validation_model():
    from app.config import settings

    payload = json.dumps({"judgments": [_judgment(candidate_index=0)]})
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return payload

    with patch.object(sj, "generate_text", side_effect=fake):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert captured["model"] == settings.validation_model
    assert len(result) == 1


def test_judge_story_situations_returns_empty_list_for_empty_candidates():
    assert sj.judge_story_situations(HERBAL_MASALA_CONTRACT, []) == []


def test_judge_story_situations_returns_none_on_malformed_json():
    with patch.object(sj, "generate_text", return_value="not valid json {{{"):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert result is None


def test_judge_story_situations_returns_none_on_empty_response():
    with patch.object(sj, "generate_text", return_value=""):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert result is None


def test_judge_story_situations_returns_none_on_provider_failure():
    with patch.object(sj, "call_openrouter_with_retry", side_effect=oru_provider_error()):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert result is None


def oru_provider_error():
    return ValueError("Retry failed after 2 attempts. OpenRouter service error (HTTP 503).")


def test_judge_story_situations_returns_none_when_judgments_key_missing():
    with patch.object(sj, "generate_text", return_value=json.dumps({"unexpected": "shape"})):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert result is None


def test_judge_story_situations_never_raises_on_unexpected_exception():
    with patch.object(sj, "generate_text", side_effect=RuntimeError("boom")):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert result is None


# --- Live production failure fix (2026-09-18 task): reasoning-token
# truncation on the Gemini Flash-Lite judge call --------------------------


def test_judge_call_explicitly_disables_reasoning_effort():
    """Root-cause fix: generate_text()'s reasoning_effort defaults to
    settings.openrouter_reasoning_effort ("medium") on every call unless
    overridden. Gemini Flash-Lite (this call's model) also honors
    OpenRouter's reasoning.effort field, so leaving it on the default was
    silently spending part of max_output_tokens on hidden reasoning before
    any visible JSON — the exact truncation seen in production. The judge
    call must explicitly pass reasoning_effort=None to opt out."""
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return json.dumps({"judgments": [_judgment(candidate_index=0)]})

    with patch.object(sj, "generate_text", side_effect=fake):
        sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert captured.get("reasoning_effort") is None
    assert "reasoning_effort" in captured  # explicitly passed, not merely absent


def test_judge_call_still_uses_validation_model_not_luna():
    """No accidental routing to Luna — the judge must keep using
    settings.validation_model (google/gemini-2.5-flash-lite), never
    settings.creative_model/final_script_model (openai/gpt-5.6-luna)."""
    from app.config import settings

    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return json.dumps({"judgments": [_judgment(candidate_index=0)]})

    with patch.object(sj, "generate_text", side_effect=fake):
        sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert captured["model"] == settings.validation_model
    assert captured["model"] == "google/gemini-2.5-flash-lite"
    assert captured["model"] != "openai/gpt-5.6-luna"


def test_judge_response_schema_stays_compact_max_output_tokens_unchanged():
    """Prefer schema/verbosity reduction over blindly raising the output
    ceiling — max_output_tokens must stay at 4096, not be bumped up as a
    band-aid for the reasoning-token leak."""
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return json.dumps({"judgments": [_judgment(candidate_index=0)]})

    with patch.object(sj, "generate_text", side_effect=fake):
        sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t", "description": "d"}])
    assert captured["max_output_tokens"] == 4096


def test_judge_prompt_instructs_a_short_reason_field():
    assert "8 words" in sj._SYSTEM_PROMPT


# --- Truncated-response salvage parsing (mirrors the pool-generation fix) -


def _judgments_json_prefix(n: int) -> str:
    """A `{"judgments": [...` payload for n complete judgments, deliberately
    left OPEN (no closing `]}`) — modeled on the exact live failure: an
    unterminated string partway through one more trailing object."""
    complete = ",".join(json.dumps(_judgment(candidate_index=i, cluster_id=f"c{i}")) for i in range(n))
    return '{"judgments": [' + complete + ','


def test_valid_judge_json_parses_normally():
    text = json.dumps({"judgments": [_judgment(candidate_index=0), _judgment(candidate_index=1, cluster_id="c1")]})
    with patch.object(sj, "generate_text", return_value=text):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "a"}, {"title": "b"}])
    assert len(result) == 2


def test_multiple_candidate_judgments_all_recovered_when_complete():
    text = json.dumps({"judgments": [_judgment(candidate_index=i, cluster_id=f"c{i}") for i in range(5)]})
    with patch.object(sj, "generate_text", return_value=text):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": f"t{i}"} for i in range(5)])
    assert {j.candidate_index for j in result} == {0, 1, 2, 3, 4}


def test_markdown_fenced_judge_json_is_stripped_and_parses():
    text = "```json\n" + json.dumps({"judgments": [_judgment(candidate_index=0)]}) + "\n```"
    with patch.object(sj, "generate_text", return_value=text):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t"}])
    assert len(result) == 1


def test_trailing_comma_judge_json_is_cleaned_and_parses():
    text = '{"judgments": [' + json.dumps(_judgment(candidate_index=0)) + ',]}'
    with patch.object(sj, "generate_text", return_value=text):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t"}])
    assert len(result) == 1


def test_truncated_judge_response_unterminated_string_salvages_complete_judgments():
    """Mirrors the exact production failure: 'Unterminated string starting
    at: line 190 column 5' — the final judgment object is cut off mid-
    string. Complete earlier judgments must still be recovered instead of
    the whole batch being discarded."""
    truncated = _judgments_json_prefix(3) + '{"candidate_index": 3, "reason": "cut off mid-strin'
    with patch.object(sj, "generate_text", return_value=truncated):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": f"t{i}"} for i in range(4)])
    assert result is not None
    assert {j.candidate_index for j in result} == {0, 1, 2}


def test_partial_final_candidate_never_produces_a_judgment_for_itself():
    truncated = _judgments_json_prefix(2) + '{"candidate_index": 2, "product_role_al'
    with patch.object(sj, "generate_text", return_value=truncated):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": f"t{i}"} for i in range(3)])
    indices = {j.candidate_index for j in result}
    assert 2 not in indices
    assert indices == {0, 1}


def test_unsalvageable_malformed_judge_response_still_returns_none():
    with patch.object(sj, "generate_text", return_value="totally not json and no judgments marker at all"):
        result = sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t"}])
    assert result is None


def test_salvage_diagnostics_are_logged_on_truncated_response(caplog):
    truncated = _judgments_json_prefix(1) + '{"candidate_index": 1, "reason": "cut off mid-strin'
    with patch.object(sj, "generate_text", return_value=truncated):
        with caplog.at_level("WARNING", logger="semantic_story_judge"):
            sj.judge_story_situations(HERBAL_MASALA_CONTRACT, [{"title": "t0"}, {"title": "t1"}])
    assert any("salvaged" in r.message for r in caplog.records)


def test_salvage_helper_finds_nothing_without_the_judgments_marker():
    assert sj._salvage_judgments('{"other_key": [1, 2, 3]') == []


def test_salvage_helper_skips_an_individually_malformed_object():
    text = '{"judgments": [' + json.dumps(_judgment(candidate_index=0)) + ', {not valid json}, ' + json.dumps(_judgment(candidate_index=2, cluster_id="c2")) + ']}'
    salvaged = sj._salvage_judgments(text)
    indices = {o["candidate_index"] for o in salvaged}
    assert indices == {0, 2}
