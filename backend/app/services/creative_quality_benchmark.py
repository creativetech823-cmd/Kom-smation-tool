"""Creative Quality Benchmark — Phase 3 Part D. A thin aggregation/reporting
layer, NOT a new validator: it reuses product_context_validator.py's
deterministic detector and semantic_story_judge_service.py's batched judge
directly, and turns their combined output into the 10 structured dimensions
+ aggregate percentages this task asks for. No LLM call exists in this file
that isn't already in one of those two modules.

Used two ways:
1. Unit-testable against a small deterministic fixture set (see
   tests/fixtures/creative_quality_benchmark_fixtures.py), with the judge
   mocked — no live calls required for the regression suite.
2. A live runner (scripts run ad hoc, not part of the test suite) that
   calls evaluate_candidates() against real generate_situations() output to
   produce the before/after comparison and live metrics table.
"""

from dataclasses import dataclass, field

from app.services import architecture_validation_service as av
from app.services.product_context_service import ProductCreativeContract
from app.services.product_context_validator import detect_category_drift_signal
from app.services.semantic_story_judge_service import SemanticJudgment, dedupe_by_cluster, judge_story_situations

# Phase 3C, Part 19 — the story-execution dimension names reported by the
# benchmark, reusing architecture_validation_service.evaluate_script_execution's
# "scores" object directly (no second LLM call, no separate scoring schema).
SCRIPT_EXECUTION_SCORE_KEYS = [
    "story_execution", "title_integrity", "premise_integrity", "narrative_device_integrity",
    "dramatic_event", "human_tension", "visual_potential", "memorability", "product_integration",
    "hook_quality", "payoff_quality", "creative_concept_strength",
]

# Above this genericness_risk, a candidate counts toward the "generic" rate
# in aggregate reporting (Part H) — a reporting threshold only, never used
# to reject a candidate (genericness is a score, not a gate — Part A4/A5).
GENERICNESS_REPORTING_THRESHOLD = 0.6
# Below this claim_safety, a candidate is flagged as a claim-safety concern
# in aggregate reporting.
CLAIM_SAFETY_REPORTING_THRESHOLD = 0.6


@dataclass
class BenchmarkCandidateResult:
    index: int
    title: str
    deterministic_category_drift: bool
    deterministic_evidence: str
    semantic_judgment: SemanticJudgment | None  # None = judge unavailable/never ran for this candidate
    decision: str  # "kept" | "rejected_deterministic" | "rejected_semantic_drift" | "rejected_uncertain" | "rejected_duplicate"


@dataclass
class BenchmarkReport:
    product_name: str
    total_candidates: int
    kept_count: int
    product_correct_pct: float          # kept / total
    category_drift_pct: float           # (deterministic OR semantic drift) / total
    semantic_duplicate_pct: float       # rejected as a duplicate cluster member / total
    genericness_rate_pct: float         # judged candidates with genericness_risk > threshold / judged
    avg_creative_potential: float       # over judged candidates only
    territory_adherence_pct: float | None  # None when no territory was given
    claim_safety_issue_count: int
    semantic_judge_available: bool      # False if the judge call failed for this evaluation
    results: list[BenchmarkCandidateResult] = field(default_factory=list)


def evaluate_candidates(
    product_name: str,
    contract: ProductCreativeContract,
    candidates: list[dict],
    territory_block: str = "",
) -> BenchmarkReport:
    """Never raises: a semantic-judge failure degrades to deterministic-only
    reporting (semantic_judge_available=False), same fail-safe convention as
    the production pipeline — this benchmark must never itself become a
    reason to trust an unverified candidate."""
    results: list[BenchmarkCandidateResult] = []
    total = len(candidates)
    if total == 0:
        return BenchmarkReport(
            product_name=product_name, total_candidates=0, kept_count=0,
            product_correct_pct=0.0, category_drift_pct=0.0, semantic_duplicate_pct=0.0,
            genericness_rate_pct=0.0, avg_creative_potential=0.0, territory_adherence_pct=None,
            claim_safety_issue_count=0, semantic_judge_available=True, results=[],
        )

    has_role_risk = bool(contract.role_risk_keys)
    det_evidence = [
        detect_category_drift_signal(
            " ".join(str(c.get(k) or "") for k in ("title", "description", "persona", "marketing_angle")), contract
        ) if has_role_risk else ""
        for c in candidates
    ]
    det_survivor_indices = [i for i, ev in enumerate(det_evidence) if not ev]

    judgments: list[SemanticJudgment] | None = []
    judge_available = True
    if has_role_risk and det_survivor_indices:
        det_survivors = [candidates[i] for i in det_survivor_indices]
        raw_judgments = judge_story_situations(contract, det_survivors, territory_block)
        if raw_judgments is None:
            judge_available = False
            judgments = []
        else:
            # Re-map candidate_index (local to det_survivors) back to the
            # original candidates list index.
            judgments = [
                SemanticJudgment(
                    candidate_index=det_survivor_indices[j.candidate_index], semantic_category_drift=j.semantic_category_drift,
                    reason=j.reason, product_truth_alignment=j.product_truth_alignment,
                    audience_alignment=j.audience_alignment, behavior_alignment=j.behavior_alignment,
                    product_role_alignment=j.product_role_alignment, creative_potential=j.creative_potential,
                    memorability=j.memorability, visual_potential=j.visual_potential,
                    genericness_risk=j.genericness_risk, claim_safety=j.claim_safety,
                    territory_alignment=j.territory_alignment, cluster_id=j.cluster_id,
                )
                for j in raw_judgments if j.candidate_index < len(det_survivor_indices)
            ]

    judgment_by_index = {j.candidate_index: j for j in judgments}
    clear_pass_judgments = [j for j in judgments if j.decision == "clear_pass"]
    keep_indices = dedupe_by_cluster(clear_pass_judgments) if (has_role_risk and judge_available) else set(det_survivor_indices)

    for i, c in enumerate(candidates):
        j = judgment_by_index.get(i)
        if not has_role_risk:
            decision = "kept"
        elif det_evidence[i]:
            decision = "rejected_deterministic"
        elif not judge_available:
            decision = "kept"  # conservative fallback to deterministic-verified state
        elif j is None:
            decision = "rejected_uncertain"  # judge ran but returned nothing for this candidate
        elif j.decision == "clear_drift":
            decision = "rejected_semantic_drift"
        elif j.decision == "uncertain":
            decision = "rejected_uncertain"
        elif i not in keep_indices:
            decision = "rejected_duplicate"
        else:
            decision = "kept"
        results.append(BenchmarkCandidateResult(
            index=i, title=str(c.get("title") or ""), deterministic_category_drift=bool(det_evidence[i]),
            deterministic_evidence=det_evidence[i], semantic_judgment=j, decision=decision,
        ))

    kept = [r for r in results if r.decision == "kept"]
    drifted = [r for r in results if r.decision in ("rejected_deterministic", "rejected_semantic_drift")]
    duplicates = [r for r in results if r.decision == "rejected_duplicate"]
    judged = [r for r in results if r.semantic_judgment is not None]

    genericness_rate = (
        sum(1 for r in judged if r.semantic_judgment.genericness_risk > GENERICNESS_REPORTING_THRESHOLD) / len(judged) * 100
        if judged else 0.0
    )
    avg_creative_potential = sum(r.semantic_judgment.creative_potential for r in judged) / len(judged) if judged else 0.0
    claim_issues = sum(1 for r in judged if r.semantic_judgment.claim_safety < CLAIM_SAFETY_REPORTING_THRESHOLD)
    territory_scores = [r.semantic_judgment.territory_alignment for r in judged if r.semantic_judgment.territory_alignment is not None]
    territory_pct = (
        sum(1 for s in territory_scores if s >= 0.6) / len(territory_scores) * 100 if territory_scores else None
    )

    return BenchmarkReport(
        product_name=product_name, total_candidates=total, kept_count=len(kept),
        product_correct_pct=len(kept) / total * 100,
        category_drift_pct=len(drifted) / total * 100,
        semantic_duplicate_pct=len(duplicates) / total * 100,
        genericness_rate_pct=genericness_rate,
        avg_creative_potential=avg_creative_potential,
        territory_adherence_pct=territory_pct,
        claim_safety_issue_count=claim_issues,
        semantic_judge_available=judge_available,
        results=results,
    )


# --- Phase 3C, Part 19 — Story-to-Film Execution benchmark -------------------
# A second, independent use of this module: instead of scoring Choose-Your-
# Story CARDS (evaluate_candidates above), this scores a full GENERATED
# SCRIPT's story execution, reusing architecture_validation_service's
# Creative Director call directly — no new LLM-calling code, no new scoring
# schema, just a thin wrapper + before/after reporting convenience.


@dataclass
class ScriptExecutionBenchmarkResult:
    product_name: str
    title: str  # the selected story situation's title, for the report table
    scores: dict  # SCRIPT_EXECUTION_SCORE_KEYS -> 1-5, {} if the eval call failed
    issues: list[str]
    announcement_mode: bool
    abstract_copy_risk: bool
    passed: bool  # issues == [] — same pass/fail definition as the production gate


def evaluate_script_execution_quality(
    product_name: str,
    title: str,
    script_data: dict,
    outline,
    architecture,
    reference_dna_notes: str = "",
    territory_block: str = "",
    contract_block: str = "",
    situation_block: str = "",
    content_type: str = "",
    format_value: str = "",
    audience: str = "",
) -> ScriptExecutionBenchmarkResult:
    evaluation = av.evaluate_script_execution(
        script_data, outline, architecture, product_name, audience, reference_dna_notes,
        territory_block, "", contract_block, situation_block, content_type, format_value,
    )
    return ScriptExecutionBenchmarkResult(
        product_name=product_name, title=title, scores=evaluation.scores, issues=evaluation.issues,
        announcement_mode=evaluation.announcement_mode, abstract_copy_risk=evaluation.abstract_copy_risk,
        passed=not evaluation.issues,
    )


def compare_before_after(
    before: ScriptExecutionBenchmarkResult, after: ScriptExecutionBenchmarkResult
) -> dict:
    """Per-dimension score deltas plus pass/fail and announcement_mode
    before/after — the exact "before Creative Quality Gate vs after" table
    Part 19 asks for, computed from two already-run evaluations rather than
    a third LLM call."""
    deltas = {
        key: (after.scores.get(key, 0) - before.scores.get(key, 0))
        for key in SCRIPT_EXECUTION_SCORE_KEYS
        if key in before.scores or key in after.scores
    }
    return {
        "title": before.title,
        "before_passed": before.passed, "after_passed": after.passed,
        "before_announcement_mode": before.announcement_mode, "after_announcement_mode": after.announcement_mode,
        "before_scores": before.scores, "after_scores": after.scores,
        "score_deltas": deltas,
        "before_issues": before.issues, "after_issues": after.issues,
    }
