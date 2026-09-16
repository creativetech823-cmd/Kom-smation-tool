"""Tests for the Creative Premise stage — the missing link between a human
insight (a topic) and a beat outline (a structure)."""

import json
from unittest.mock import patch

from app.services import creative_premise_service as cps


def _candidate(statement="Turn a kitchen argument into a surprising reveal", **score_overrides):
    scores = {k: 3 for k in cps._SCORE_KEYS}
    scores.update(score_overrides)
    return {
        "statement": statement,
        "creative_device": "reversal",
        "situation": "a family dinner argument",
        "why_curious": "viewer wants to know what the reveal is",
        "why_not_swappable": "tied to this exact product's ingredients",
        "scores": scores,
    }


def test_generate_premises_returns_parsed_candidates():
    payload = json.dumps({"candidates": [_candidate(), _candidate("A second, different situation")]})
    with patch.object(cps, "call_openrouter_with_retry", return_value=payload):
        candidates = cps.generate_premises(
            product_name="X", category="Y", target_audience="Z", insight_block="insight",
        )
    assert len(candidates) == 2
    assert candidates[0].statement == "Turn a kitchen argument into a surprising reveal"
    assert candidates[0].total_score == 3 * len(cps._SCORE_KEYS)


def test_generate_premises_returns_empty_list_on_failure_never_raises():
    with patch.object(cps, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        candidates = cps.generate_premises(product_name="X", category="Y", target_audience="Z")
    assert candidates == []


def test_generate_premises_skips_candidates_with_no_statement():
    payload = json.dumps({"candidates": [{"statement": "", "scores": {}}, _candidate()]})
    with patch.object(cps, "call_openrouter_with_retry", return_value=payload):
        candidates = cps.generate_premises(product_name="X", category="Y", target_audience="Z")
    assert len(candidates) == 1


def test_select_strongest_premise_picks_highest_total_score():
    weak = cps._parse_candidate(_candidate("Weak idea", originality=1, curiosity=1))
    strong = cps._parse_candidate(_candidate("Strong idea", originality=5, curiosity=5))
    chosen = cps.select_strongest_premise([weak, strong])
    assert chosen.statement == "Strong idea"


def test_select_strongest_premise_filters_out_restated_insight():
    restated = cps._parse_candidate(_candidate("A mother wants her child to be healthy", originality=5, curiosity=5))
    genuine = cps._parse_candidate(_candidate("A specific kitchen reveal", originality=2, curiosity=2))
    chosen = cps.select_strongest_premise([restated, genuine])
    assert chosen.statement == "A specific kitchen reveal"


def test_select_strongest_premise_falls_back_to_restated_if_nothing_else():
    only_restated = cps._parse_candidate(_candidate("A mother wants her child to be healthy"))
    chosen = cps.select_strongest_premise([only_restated])
    assert chosen is not None  # never return None when at least one candidate exists


def test_select_strongest_premise_returns_none_for_empty_list():
    assert cps.select_strongest_premise([]) is None


def test_generate_and_select_premise_end_to_end():
    payload = json.dumps({"candidates": [_candidate("Idea A", originality=2), _candidate("Idea B", originality=5)]})
    with patch.object(cps, "call_openrouter_with_retry", return_value=payload):
        premise = cps.generate_and_select_premise(product_name="X", category="Y", target_audience="Z")
    assert premise.statement == "Idea B"


def test_generate_and_select_premise_returns_none_when_generation_fails():
    with patch.object(cps, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        premise = cps.generate_and_select_premise(product_name="X", category="Y", target_audience="Z")
    assert premise is None


def test_prompt_block_marks_premise_as_mandatory_and_not_a_topic():
    premise = cps.CreativePremise(
        statement="Turn a kitchen argument into a surprising reveal",
        creative_device="reversal",
        situation="family dinner",
        why_curious="curiosity reason",
        why_not_swappable="specific to this product",
    )
    block = premise.prompt_block()
    assert "mandatory" in block.lower()
    assert premise.statement in block
    assert "not a topic" in block.lower()


def test_system_prompt_requires_distinct_candidates_and_anti_overfit_guidance():
    assert "genuinely different" in cps._SYSTEM_PROMPT
    assert "tobacco/gutka/pan-masala" in cps._SYSTEM_PROMPT.lower() or "tobacco" in cps._SYSTEM_PROMPT.lower()
