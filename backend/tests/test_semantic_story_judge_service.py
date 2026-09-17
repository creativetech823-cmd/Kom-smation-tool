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
