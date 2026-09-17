"""Phase 3C, Part 19 — tests for the Creative Quality Benchmark's script-
execution extension (evaluate_script_execution_quality / compare_before_after),
which wraps architecture_validation_service.evaluate_script_execution with no
new LLM-calling code of its own."""

import json
from unittest.mock import patch

from app.services import architecture_validation_service as av
from app.services import creative_quality_benchmark as bench
from app.services.creative_architecture import ARCHITECTURES

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]


def test_evaluate_script_execution_quality_wraps_architecture_validation_service():
    mocked = json.dumps({
        "issues": ["announcement_mode"],
        "scores": {"story_execution": 2, "creative_concept_strength": 2},
        "announcement_mode": True, "abstract_copy_risk": False,
    })
    with patch.object(av, "call_openrouter_with_retry", return_value=mocked):
        result = bench.evaluate_script_execution_quality(
            "Aayush Herbal Masala", "Doctor ki Advice, Healthy Life",
            {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP,
        )
    assert result.passed is False
    assert result.announcement_mode is True
    assert result.scores["story_execution"] == 2


def test_evaluate_script_execution_quality_never_raises():
    with patch.object(av, "call_openrouter_with_retry", side_effect=RuntimeError("boom")):
        result = bench.evaluate_script_execution_quality(
            "X", "title", {"hook": {"text": "x"}, "body": [], "cta": {"text": "y"}}, None, DIALOGUE_TRAP,
        )
    assert result.passed is True  # empty issues == pass, same fail-open convention
    assert result.scores == {}


def test_compare_before_after_computes_score_deltas():
    before = bench.ScriptExecutionBenchmarkResult(
        product_name="X", title="T", scores={"story_execution": 2, "title_integrity": 1},
        issues=["announcement_mode"], announcement_mode=True, abstract_copy_risk=True, passed=False,
    )
    after = bench.ScriptExecutionBenchmarkResult(
        product_name="X", title="T", scores={"story_execution": 4, "title_integrity": 5},
        issues=[], announcement_mode=False, abstract_copy_risk=False, passed=True,
    )
    comparison = bench.compare_before_after(before, after)
    assert comparison["score_deltas"]["story_execution"] == 2
    assert comparison["score_deltas"]["title_integrity"] == 4
    assert comparison["before_passed"] is False
    assert comparison["after_passed"] is True
    assert comparison["before_announcement_mode"] is True
    assert comparison["after_announcement_mode"] is False
