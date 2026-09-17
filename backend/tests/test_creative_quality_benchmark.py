"""Phase 3 Part F/D — regression tests for the Creative Quality Benchmark
against the small deterministic fixture set. The semantic judge is always
mocked here (never a live call) — each fixture's mocked_judgment is what a
correct judge would say, used to prove evaluate_candidates()'s own
aggregation/decision logic is correct, independent of live model behavior."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fixtures.creative_quality_benchmark_fixtures import (  # noqa: E402
    BEARD_OIL_FIXTURES, HERBAL_MASALA_FIXTURES, IMMUNE_CARE_FIXTURES,
)

from app.services import creative_quality_benchmark as bench
from app.services import openrouter_utils, semantic_story_judge_service as sj
from app.services.product_context_service import build_product_creative_contract

HERBAL_MASALA_CONTRACT = build_product_creative_contract(
    product_name="Aayush Herbal Masala", category="herbal_health",
    target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
    usp="a 0% tobacco, 0% supari herbal chew",
)
IMMUNE_CARE_CONTRACT = build_product_creative_contract(
    product_name="AayushWellness Immune Care Tablets", category="nutraceuticals",
    target_audience="mothers of school-age children",
)
BEARD_OIL_CONTRACT = build_product_creative_contract(
    product_name="AayushWellness Beard Grow Oil", category="personal_care",
    target_audience="college-going young men self-conscious about patchy beard growth",
)


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


def _mocked_judge_for(fixtures: list[dict]):
    """Builds a fake judge_story_situations that returns exactly the
    fixtures' own mocked_judgment values, re-indexed to whatever subset of
    candidates the benchmark actually sends it (deterministic-survivors
    only, matching real pipeline behavior)."""
    by_title = {f["candidate"]["title"]: f for f in fixtures}

    def fake(contract, candidates, territory_block="", label="semantic_story_judge"):
        judgments = []
        for i, c in enumerate(candidates):
            fixture = by_title[c["title"]]
            mj = fixture["mocked_judgment"]
            if mj is None:
                continue  # this candidate was expected to be caught deterministically, never reaches here
            raw = {"candidate_index": i, **mj}
            judgments.append(sj._parse_judgment(raw))
        return judgments
    return fake


def test_herbal_masala_fixtures_classify_correctly():
    candidates = [f["candidate"] for f in HERBAL_MASALA_FIXTURES]
    with patch.object(sj, "judge_story_situations", side_effect=_mocked_judge_for(HERBAL_MASALA_FIXTURES)), \
         patch("app.services.creative_quality_benchmark.judge_story_situations", side_effect=_mocked_judge_for(HERBAL_MASALA_FIXTURES)):
        report = bench.evaluate_candidates("Aayush Herbal Masala", HERBAL_MASALA_CONTRACT, candidates)

    assert report.total_candidates == 12
    results_by_title = {r.title: r for r in report.results}
    for fixture in HERBAL_MASALA_FIXTURES:
        title = fixture["candidate"]["title"]
        r = results_by_title[title]
        if fixture["expected_category_drift"]:
            assert r.decision in ("rejected_deterministic", "rejected_semantic_drift"), f"{title} should be rejected"
        else:
            assert r.decision == "kept", f"{title} should be kept, got {r.decision}"

    # 6 correct / 12 total = 50% product-correct in this fixture set.
    assert report.product_correct_pct == pytest.approx(50.0, abs=0.1)
    assert report.category_drift_pct == pytest.approx(50.0, abs=0.1)


def test_herbal_masala_subtle_drift_caught_only_by_semantic_judge():
    candidates = [f["candidate"] for f in HERBAL_MASALA_FIXTURES]
    with patch("app.services.creative_quality_benchmark.judge_story_situations", side_effect=_mocked_judge_for(HERBAL_MASALA_FIXTURES)):
        report = bench.evaluate_candidates("Aayush Herbal Masala", HERBAL_MASALA_CONTRACT, candidates)
    results_by_title = {r.title: r for r in report.results}
    subtle = results_by_title["Morning Ritual Refresh"]
    assert subtle.deterministic_category_drift is False  # deterministic layer missed it
    assert subtle.decision == "rejected_semantic_drift"  # semantic judge caught it


def test_immune_care_never_invokes_semantic_judge_and_all_kept():
    candidates = [f["candidate"] for f in IMMUNE_CARE_FIXTURES]
    with patch("app.services.creative_quality_benchmark.judge_story_situations") as mock_judge:
        report = bench.evaluate_candidates("AayushWellness Immune Care Tablets", IMMUNE_CARE_CONTRACT, candidates)
    mock_judge.assert_not_called()
    assert report.product_correct_pct == 100.0
    assert report.category_drift_pct == 0.0


def test_beard_oil_never_invokes_semantic_judge_and_all_kept():
    candidates = [f["candidate"] for f in BEARD_OIL_FIXTURES]
    with patch("app.services.creative_quality_benchmark.judge_story_situations") as mock_judge:
        report = bench.evaluate_candidates("AayushWellness Beard Grow Oil", BEARD_OIL_CONTRACT, candidates)
    mock_judge.assert_not_called()
    assert report.product_correct_pct == 100.0
    # Honest, documented gap: story-CARD-level claim safety for a
    # no-role-risk product is NOT checked by this judge (cost-gated on
    # role_risk_keys) — unsupported claims like "Full Beard in 7 Days" are
    # only caught later, at script-write time, by script_quality.py's
    # existing claim-pattern checks. Not silently pretended to be caught here.
    unsupported_claim_card = next(r for r in report.results if r.title == "Full Beard in 7 Days")
    assert unsupported_claim_card.decision == "kept"
    assert unsupported_claim_card.semantic_judgment is None


def test_empty_candidate_list_returns_zeroed_report():
    report = bench.evaluate_candidates("X", HERBAL_MASALA_CONTRACT, [])
    assert report.total_candidates == 0
    assert report.product_correct_pct == 0.0


def test_judge_unavailable_degrades_to_deterministic_only_reporting():
    # A mix: some caught deterministically (never reach the judge either
    # way) plus at least one deterministic-survivor, so the judge call is
    # actually attempted and its unavailability is genuinely exercised.
    deterministic_only = [f["candidate"] for f in HERBAL_MASALA_FIXTURES if f["mocked_judgment"] is None]
    survivor = HERBAL_MASALA_FIXTURES[0]["candidate"]  # "The Automatic Reach" — deterministically clean
    candidates = deterministic_only + [survivor]
    with patch("app.services.creative_quality_benchmark.judge_story_situations", return_value=None) as mock_judge:
        report = bench.evaluate_candidates("Aayush Herbal Masala", HERBAL_MASALA_CONTRACT, candidates)
    mock_judge.assert_called_once()
    assert report.semantic_judge_available is False
    # The deterministically-caught drift cards are still rejected even
    # though the judge never ran — deterministic filtering is independent.
    drift_titles = {"Chef ka Secret Ingredient", "Meri Daadi Maa ka Naya Secret", "Fitness Enthusiast ka Secret Weapon", "Party Host ka Healthy Twist"}
    for r in report.results:
        if r.title in drift_titles:
            assert r.decision == "rejected_deterministic"
    # The deterministic-survivor is conservatively KEPT (fallback to the
    # last known-good state), never silently dropped nor auto-approved
    # against a check that never actually ran.
    survivor_result = next(r for r in report.results if r.title == "The Automatic Reach")
    assert survivor_result.decision == "kept"
