"""Tests for the Creative Quality Benchmark runner's concurrency (the
runtime-optimization task) — proves the scheduling change is correct without
ever calling the real pipeline: script_service.generate_script is always
faked here with controlled sleep/failure behavior."""

import threading
import time
from unittest.mock import patch

import pytest

from app.models.product import StructuredProduct
from app.services import creative_benchmark_runner as runner
from app.services import script_service


def _case(i: int, product_label: str = "P") -> runner.BenchmarkCase:
    return runner.BenchmarkCase(
        product_label=product_label, situation_title=f"Situation {i}", situation_description="d",
        situation_emotion="e", situation_marketing_angle="a",
        structured_product=StructuredProduct(product_name="X", target_audience="Y", ingredients=[], usp="", key_benefits=[]),
        product_category="c",
    )


# --- Requirement 1/3: bounded concurrency is actually respected ------------


def test_concurrency_limit_is_respected():
    active = {"count": 0, "max_seen": 0}
    lock = threading.Lock()

    def fake_generate_script(payload):
        with lock:
            active["count"] += 1
            active["max_seen"] = max(active["max_seen"], active["count"])
        time.sleep(0.05)
        with lock:
            active["count"] -= 1
        return None

    cases = [_case(i) for i in range(9)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        runner.run_benchmark_cases(cases, concurrency=3)

    assert active["max_seen"] <= 3
    assert active["max_seen"] > 1  # actually ran concurrently, not accidentally serialized


def test_default_concurrency_comes_from_settings():
    with patch.object(runner.settings, "creative_benchmark_concurrency", 2):
        active = {"count": 0, "max_seen": 0}
        lock = threading.Lock()

        def fake_generate_script(payload):
            with lock:
                active["count"] += 1
                active["max_seen"] = max(active["max_seen"], active["count"])
            time.sleep(0.05)
            with lock:
                active["count"] -= 1
            return None

        cases = [_case(i) for i in range(6)]
        with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
            runner.run_benchmark_cases(cases)  # no explicit concurrency override
    assert active["max_seen"] <= 2


# --- Requirement 1: independent cases actually run concurrently (timing) ---


def test_independent_cases_run_concurrently_not_sequentially():
    def fake_generate_script(payload):
        time.sleep(0.1)
        return None

    cases = [_case(i) for i in range(6)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        t0 = time.time()
        result = runner.run_benchmark_cases(cases, concurrency=3)
        elapsed = time.time() - t0

    # 6 cases at 0.1s each, concurrency=3 -> ~2 batches -> ~0.2s, NOT 0.6s
    # sequential. Generous upper bound for CI/thread-scheduling jitter.
    assert elapsed < 0.45
    assert result.total_cases == 6
    assert len(result.succeeded) == 6


# --- Requirement 2/preserve pipeline ordering: exactly one call per case ---


def test_each_case_calls_generate_script_exactly_once_with_no_reordering_inside():
    calls = []

    def fake_generate_script(payload):
        calls.append(payload.selected_situation.title)
        return None

    cases = [_case(i) for i in range(4)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        runner.run_benchmark_cases(cases, concurrency=2)

    assert sorted(calls) == sorted(c.situation_title for c in cases)
    assert len(calls) == 4  # exactly one call per case, never more


# --- Requirement 5: one failed case does not cancel the run ----------------


def test_one_case_failure_does_not_stop_the_others():
    def fake_generate_script(payload):
        if payload.selected_situation.title == "Situation 2":
            raise RuntimeError("boom")
        return None

    cases = [_case(i) for i in range(5)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases(cases, concurrency=2)

    assert len(result.results) == 5
    failed = [r for r in result.results if r.status == "failure"]
    assert len(failed) == 1
    assert failed[0].case.situation_title == "Situation 2"
    assert "boom" in failed[0].error
    assert len(result.succeeded) == 4


def test_case_result_status_values_are_structured():
    def fake_generate_script(payload):
        return None

    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases([_case(0)], concurrency=1)
    r = result.results[0]
    assert r.status in ("success", "failure", "timeout")
    assert r.duration_s >= 0
    assert isinstance(r.cost_usd, float)


# --- Requirement 4: usage/cost tracking stays isolated per case ------------


def test_usage_and_cost_data_stays_isolated_per_case():
    import logging

    logger = logging.getLogger("script_service")

    def fake_generate_script(payload):
        # Each case logs its OWN distinct pipeline_cost_summary, mirroring
        # exactly what _generate_full_script already does in production.
        cost = 0.01 if payload.selected_situation.title == "Situation 0" else 0.05
        logger.info("pipeline_cost_summary %r", {
            "by_stage": {}, "total_input_tokens": 1, "total_output_tokens": 1,
            "total_tokens": 2, "estimated_total_cost_usd": cost, "call_count": 1,
        })
        time.sleep(0.02)
        return None

    cases = [_case(0), _case(1)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases(cases, concurrency=2)

    by_title = {r.case.situation_title: r for r in result.results}
    assert by_title["Situation 0"].cost_usd == pytest.approx(0.01)
    assert by_title["Situation 1"].cost_usd == pytest.approx(0.05)
    # Neither case's usage_summary leaked the other's cost.
    assert by_title["Situation 0"].usage_summary["estimated_total_cost_usd"] == pytest.approx(0.01)
    assert by_title["Situation 1"].usage_summary["estimated_total_cost_usd"] == pytest.approx(0.05)


def test_retry_and_rewrite_counts_captured_per_case_without_leaking():
    import logging

    svc_logger = logging.getLogger("script_service")
    or_logger = logging.getLogger("openrouter_utils")

    def fake_generate_script(payload):
        if payload.selected_situation.title == "Situation 0":
            or_logger.warning("[final_script_write] attempt=1/4 failed transient=True error=x")
            svc_logger.info("Quality gate flagged ['x'] — attempting one rewrite pass")
        time.sleep(0.02)
        return None

    cases = [_case(0), _case(1)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases(cases, concurrency=2)

    by_title = {r.case.situation_title: r for r in result.results}
    assert by_title["Situation 0"].retry_count == 1
    assert by_title["Situation 0"].rewrite_count == 1
    assert by_title["Situation 1"].retry_count == 0
    assert by_title["Situation 1"].rewrite_count == 0


# --- Requirement 8: results remain correctly associated with their case ----


def test_results_correctly_associated_with_their_own_case_under_concurrency():
    def fake_generate_script(payload):
        time.sleep(0.01 * (hash(payload.selected_situation.title) % 5))
        return None

    cases = [_case(i, product_label=f"Product-{i}") for i in range(8)]
    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases(cases, concurrency=4)

    assert len(result.results) == 8
    seen_titles = {r.case.situation_title for r in result.results}
    assert seen_titles == {c.situation_title for c in cases}
    for r in result.results:
        assert r.case.product_label == f"Product-{r.case.situation_title.split(' ')[1]}"


# --- BenchmarkRunResult aggregate properties --------------------------------


def test_benchmark_run_result_aggregate_properties():
    def fake_generate_script(payload):
        if payload.selected_situation.title == "Situation 1":
            raise RuntimeError("boom")
        return None

    with patch.object(script_service, "generate_script", side_effect=fake_generate_script):
        result = runner.run_benchmark_cases([_case(0), _case(1), _case(2)], concurrency=2)

    assert len(result.succeeded) == 2
    assert len(result.failed) == 1
    assert result.total_cost_usd == 0.0  # fake never logs a cost summary
