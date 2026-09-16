"""Tests for Human Insight Discovery (AHM Creative DNA §3)."""

from unittest.mock import patch

from app.services import creative_insight_service as insight_svc


_STRONG_INSIGHT_JSON = """{
  "target_person": "a mother of a 7-year-old",
  "purchaser": "the mother",
  "user": "her child",
  "situation": "packing the school bag every Monday after a sick weekend",
  "behavior": "she checks the school WhatsApp group for who else is absent before deciding whether to send her child",
  "tension": "she doesn't want to be the parent who sent a sick kid to school, but also can't keep him home every time",
  "unspoken_truth": "she's not actually worried about immunity in the abstract, she's worried about being judged by other parents",
  "why_not_solved_already": "she's tried random supplements before and stopped because she never saw a difference she could point to",
  "insight_statement": "She's not managing her son's immunity, she's managing her own reputation as a parent who has it together, one WhatsApp group check at a time."
}"""

_GENERIC_INSIGHT_JSON = """{
  "target_person": "a mother",
  "purchaser": "the mother",
  "user": "her child",
  "situation": "cough and cold season",
  "behavior": "worrying",
  "tension": "wants her child to be healthy",
  "unspoken_truth": "health is important",
  "why_not_solved_already": "hasn't found the right product",
  "insight_statement": "Mothers worry about their kids' health."
}"""


def test_discover_insight_accepts_specific_statement_on_first_try():
    with patch.object(insight_svc, "call_openrouter_with_retry", return_value=_STRONG_INSIGHT_JSON) as mock_call:
        result = insight_svc.discover_insight(
            product_name="Immune Care Tablets", category="immunity/kids health",
            target_audience="mothers of school-age children", usp="daily immunity support",
            benefits=["supports immunity"], primary_problem="frequent school absences",
        )
    assert mock_call.call_count == 1
    assert result is not None
    assert result.is_specific is True
    assert "WhatsApp" in result.insight_statement


def test_discover_insight_retries_once_on_generic_statement_then_accepts():
    with patch.object(
        insight_svc, "call_openrouter_with_retry",
        side_effect=[_GENERIC_INSIGHT_JSON, _STRONG_INSIGHT_JSON],
    ) as mock_call:
        result = insight_svc.discover_insight(
            product_name="Immune Care Tablets", category="immunity/kids health",
            target_audience="mothers", usp="", benefits=[], primary_problem="",
        )
    assert mock_call.call_count == 2
    assert result.is_specific is True


def test_discover_insight_returns_generic_flagged_result_if_still_generic_after_retry():
    with patch.object(
        insight_svc, "call_openrouter_with_retry",
        side_effect=[_GENERIC_INSIGHT_JSON, _GENERIC_INSIGHT_JSON],
    ):
        result = insight_svc.discover_insight(
            product_name="X", category="y", target_audience="z", usp="", benefits=[], primary_problem="",
        )
    # Never silently drops the result — but is_specific=False lets the caller know.
    assert result is not None
    assert result.is_specific is False


def test_discover_insight_returns_none_on_total_failure_never_raises():
    with patch.object(insight_svc, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        result = insight_svc.discover_insight(
            product_name="X", category="y", target_audience="z", usp="", benefits=[], primary_problem="",
        )
    assert result is None


def test_is_generic_detects_denylisted_phrases():
    assert insight_svc._is_generic("Mothers worry about their kids' health.") is True
    assert insight_svc._is_generic("Every mother wants the best for her family.") is True
    assert insight_svc._is_generic("short") is True  # too short to be specific
    assert insight_svc._is_generic(
        "She checks the school WhatsApp group every Monday before deciding whether to send her sick kid."
    ) is False


def test_human_insight_prompt_block_contains_all_fields():
    insight = insight_svc.HumanInsight(
        target_person="a", purchaser="b", user="c", situation="d", behavior="e",
        tension="f", unspoken_truth="g", why_not_solved_already="h", insight_statement="i", is_specific=True,
    )
    block = insight.prompt_block()
    for value in ("a", "b", "c", "d", "e", "f", "g", "h", "i"):
        assert value in block
