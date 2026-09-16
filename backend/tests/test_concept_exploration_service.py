"""Tests for multi-concept exploration + the diversity check (AHM Creative
DNA §9 — "if 3 of the 5 concepts follow essentially the same story, flag
that as insufficient creative diversity")."""

from unittest.mock import patch

from app.services import concept_exploration_service as concept_svc


_DIVERSE_JSON = """{
  "concepts": [
    {"creative_territory": "school reputation", "human_insight": "she checks the WhatsApp attendance group before deciding whether to send her sick kid, worried about being judged", "architecture_key": "dialogue_trap", "hook": "h1", "beat_summary": "s1", "must_include": []},
    {"creative_territory": "grandmother comparison", "human_insight": "she secretly compares her parenting to her own mother's generation and feels she is failing at something they did effortlessly", "architecture_key": "documentary_zoom_in", "hook": "h2", "beat_summary": "s2", "must_include": []},
    {"creative_territory": "child's own voice", "human_insight": "the child pretends to feel fine to avoid missing a friend's birthday party, hiding symptoms from the parent", "architecture_key": "visual_metaphor_device", "hook": "h3", "beat_summary": "s3", "must_include": []},
    {"creative_territory": "workplace guilt", "human_insight": "she has already used all her sick leave this quarter and resents having to choose between her job and staying home", "architecture_key": "objection_handling_interview", "hook": "h4", "beat_summary": "s4", "must_include": []},
    {"creative_territory": "sibling contrast", "human_insight": "one child is always sick and the other never is, and she has started to believe it is just luck rather than something she can influence", "architecture_key": "borrowed_format", "hook": "h5", "beat_summary": "s5", "must_include": []}
  ]
}"""

_REPETITIVE_JSON = """{
  "concepts": [
    {"creative_territory": "a", "human_insight": "mother worried about child sick health immunity season school worried", "architecture_key": "dialogue_trap", "hook": "h1", "beat_summary": "s1", "must_include": []},
    {"creative_territory": "b", "human_insight": "mother worried about child sick health immunity season school concerned", "architecture_key": "dialogue_trap", "hook": "h2", "beat_summary": "s2", "must_include": []},
    {"creative_territory": "c", "human_insight": "mother worried about child sick health immunity season school anxious", "architecture_key": "dialogue_trap", "hook": "h3", "beat_summary": "s3", "must_include": []}
  ]
}"""


def test_generate_concept_sketches_returns_five_from_mocked_response():
    with patch.object(concept_svc, "call_openrouter_with_retry", return_value=_DIVERSE_JSON):
        concepts = concept_svc.generate_concept_sketches(
            product_name="Immune Care Tablets", category="immunity/kids health",
            target_audience="mothers", count=5,
        )
    assert len(concepts) == 5
    assert all(c.human_insight for c in concepts)
    assert all(c.architecture_key for c in concepts)


def test_generate_concept_sketches_returns_empty_on_failure_never_raises():
    with patch.object(concept_svc, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        concepts = concept_svc.generate_concept_sketches(
            product_name="X", category="y", target_audience="z",
        )
    assert concepts == []


def test_diversity_check_passes_for_genuinely_different_concepts():
    with patch.object(concept_svc, "call_openrouter_with_retry", return_value=_DIVERSE_JSON):
        concepts = concept_svc.generate_concept_sketches(
            product_name="Immune Care Tablets", category="immunity/kids health",
            target_audience="mothers", count=5,
        )
    issues = concept_svc.diversity_check(concepts)
    assert issues == []


def test_diversity_check_flags_repetitive_concepts():
    with patch.object(concept_svc, "call_openrouter_with_retry", return_value=_REPETITIVE_JSON):
        concepts = concept_svc.generate_concept_sketches(
            product_name="Immune Care Tablets", category="immunity/kids health",
            target_audience="mothers", count=3,
        )
    issues = concept_svc.diversity_check(concepts)
    assert "insufficient_creative_diversity" in issues


def test_diversity_check_flags_no_architectural_diversity():
    with patch.object(concept_svc, "call_openrouter_with_retry", return_value=_REPETITIVE_JSON):
        concepts = concept_svc.generate_concept_sketches(
            product_name="X", category="y", target_audience="z", count=3,
        )
    issues = concept_svc.diversity_check(concepts)
    assert "no_architectural_diversity" in issues
