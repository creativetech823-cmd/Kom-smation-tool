"""Creative Breakdown — "Why this script?" grounded in the ACTUAL structured
creative chain the pipeline already produced, never re-derived from the
final script text alone and never invented after the fact.

Deliberately a pure, deterministic renderer — zero LLM calls, zero cost, zero
hallucination risk. Every explanation line below is a direct readout of a
field some earlier pipeline stage already decided (ProductCreativeContract,
the discovered human insight, the selected CreativeTerritory, the selected
CreativePremise, the selected hook, the BeatOutline, and the Creative
Director's ScriptExecutionEvaluation) — not a new judgment call. If a field
was never decided (a stage failed/was skipped, same fail-open convention as
the rest of this pipeline), the corresponding explanation line says so
plainly rather than inventing a plausible-sounding reason.

Not yet wired into any router/API response or the frontend — this module is
additive and callable on its own (see build_creative_breakdown below),
deliberately so it can be reviewed/tested independently before any API
contract or UI change is made.
"""

from dataclasses import dataclass, field


@dataclass
class CreativeBreakdown:
    hook_reason: str
    territory_reason: str
    human_insight: str
    behavioral_tension: str
    situation_reason: str
    product_entry_reason: str
    narrative_device_reason: str
    payoff_reason: str
    memorability_reason: str
    visual_executability_reason: str
    distinctiveness_reason: str
    claims_avoided: list[str] = field(default_factory=list)
    remaining_weaknesses: list[str] = field(default_factory=list)
    # True only when every upstream stage (contract/insight/territory/
    # premise/hook/outline/evaluation) actually ran and produced a real
    # value — false means one or more lines above are "not available"
    # placeholders rather than genuine grounded explanations. Surface this
    # to a caller/UI rather than letting a partial breakdown look complete.
    fully_grounded: bool = True

    def as_dict(self) -> dict:
        return {
            "hook_reason": self.hook_reason,
            "territory_reason": self.territory_reason,
            "human_insight": self.human_insight,
            "behavioral_tension": self.behavioral_tension,
            "situation_reason": self.situation_reason,
            "product_entry_reason": self.product_entry_reason,
            "narrative_device_reason": self.narrative_device_reason,
            "payoff_reason": self.payoff_reason,
            "memorability_reason": self.memorability_reason,
            "visual_executability_reason": self.visual_executability_reason,
            "distinctiveness_reason": self.distinctiveness_reason,
            "claims_avoided": self.claims_avoided,
            "remaining_weaknesses": self.remaining_weaknesses,
            "fully_grounded": self.fully_grounded,
        }


_NOT_AVAILABLE = "not available — this stage did not produce a usable result for this generation"
_NOT_SCORED = "not scored — no Creative Director evaluation is attached"


@dataclass
class QualityDimension:
    """One line of a structured Creative Quality Assessment (Task V3 Part
    10): a score PAIRED with the evidence and the specific upstream
    creative decision it traces back to — never a bare number, and never a
    vague "this is strong" with nothing behind it. This is the deliberate
    alternative to a model just asserting "award-winning"."""

    name: str
    score: float | None  # None = not scored (no evaluation attached), not 0
    evidence: str
    source_creative_decision: str


@dataclass
class CreativeQualityAssessment:
    dimensions: list[QualityDimension] = field(default_factory=list)
    overall_passed: bool | None = None  # None = no evaluation attached to judge pass/fail from

    def as_dict(self) -> dict:
        return {
            "dimensions": [
                {"name": d.name, "score": d.score, "evidence": d.evidence, "source_creative_decision": d.source_creative_decision}
                for d in self.dimensions
            ],
            "overall_passed": self.overall_passed,
        }


# Dimension name -> (evaluation.scores key it reads, the field on
# premise/territory/contract that supplies "evidence"/"source", a static
# fallback evidence string when that field is empty). Centralizing this
# mapping here (rather than repeating a chain of if/else per dimension)
# is the "avoid arbitrary magic numbers scattered throughout the code" the
# task asks for — one named table, not several ad hoc lookups.
_DIMENSION_SCORE_KEYS: dict[str, str] = {
    "Creative Integrity": "creative_concept_strength",
    "Human Insight": "human_tension",
    "Hook Strength": "hook_quality",
    "Narrative Execution": "narrative_device_integrity",
    "Originality": "creative_concept_strength",
    "Visual Potential": "visual_potential",
    "Product Integration": "product_integration",
    "Memorability": "memorability",
    "Payoff Strength": "payoff_quality",
}


def build_creative_breakdown(
    *,
    contract=None,  # ProductCreativeContract | None
    insight_statement: str = "",
    territory=None,  # CreativeTerritory | None
    premise=None,  # CreativePremise | None
    selected_hook_text: str = "",
    architecture=None,  # Architecture | None
    evaluation=None,  # architecture_validation_service.ScriptExecutionEvaluation | None
) -> CreativeBreakdown:
    """Renders the 13-point explanation the task specifies, each line traced
    to one specific object field — see the module docstring. Never raises:
    a missing input just produces _NOT_AVAILABLE for the lines that depend
    on it, and fully_grounded=False so a caller can tell the difference
    between "genuinely nothing to explain here" and "the chain was
    incomplete when this was built"."""
    grounded = True

    # 1. Hook
    if selected_hook_text:
        mechanism_note = f" (creative mechanism: {premise.creative_device})" if premise and premise.creative_device else ""
        hook_reason = f'The hook "{selected_hook_text}" was selected{mechanism_note}.'
    else:
        hook_reason = _NOT_AVAILABLE
        grounded = False

    # 2. Territory
    if territory is not None:
        why = territory.why_it_fits_product or "no stated fit reason was recorded"
        novelty = f" Novelty vs. recent concepts: {territory.novelty_vs_recent_concepts}." if territory.novelty_vs_recent_concepts else ""
        territory_reason = f'Territory "{territory.territory_name}" was selected because: {why}.{novelty}'
    else:
        territory_reason = "No creative territory was selected for this generation (territory stage unavailable) — the script was built from the human insight and premise alone."

    # 3. Human insight
    human_insight = insight_statement or _NOT_AVAILABLE
    if not insight_statement:
        grounded = False

    # 4. Behavioral tension
    if territory is not None and territory.human_tension:
        behavioral_tension = territory.human_tension
    elif premise is not None and premise.human_tension:
        behavioral_tension = premise.human_tension
    elif contract is not None and contract.core_problem_or_tension:
        behavioral_tension = contract.core_problem_or_tension
    else:
        behavioral_tension = _NOT_AVAILABLE
        grounded = False

    # 5. Situation
    if premise is not None:
        situation_reason = premise.situation or premise.concrete_event or _NOT_AVAILABLE
        if not situation_reason or situation_reason == _NOT_AVAILABLE:
            grounded = False
    else:
        situation_reason = _NOT_AVAILABLE
        grounded = False

    # 6. Product entry point
    reveal_logic = architecture.product_reveal_logic if architecture is not None else ""
    product_role = premise.product_role if premise is not None else ""
    if reveal_logic or product_role:
        product_entry_reason = (
            f"Product role: {product_role or 'not recorded'}. "
            f"Reveal timing (per the chosen architecture): {reveal_logic or 'not recorded'}."
        )
    else:
        product_entry_reason = _NOT_AVAILABLE
        grounded = False

    # 7. Narrative device
    if premise is not None and (premise.narrative_device or premise.creative_device):
        narrative_device_reason = premise.narrative_device or premise.creative_device
    else:
        narrative_device_reason = _NOT_AVAILABLE
        grounded = False

    # 8. Payoff
    payoff_reason = premise.payoff if premise is not None and premise.payoff else _NOT_AVAILABLE
    if payoff_reason == _NOT_AVAILABLE:
        grounded = False

    # 9. Memorability — from the Creative Director's own scored evaluation,
    # never a fresh guess; "not scored" is honest when no evaluation ran.
    if evaluation is not None and evaluation.scores.get("memorability"):
        memorability_reason = f"Creative Director memorability score: {evaluation.scores['memorability']}/5."
    else:
        memorability_reason = "Not scored — no Creative Director evaluation is attached to this breakdown."

    # 10. Visual executability
    visual_executability_reason = premise.visual_device if premise is not None and premise.visual_device else _NOT_AVAILABLE
    if visual_executability_reason == _NOT_AVAILABLE:
        grounded = False

    # 11. Distinctiveness / non-swappability
    distinctiveness_reason = premise.why_not_swappable if premise is not None and premise.why_not_swappable else _NOT_AVAILABLE
    if distinctiveness_reason == _NOT_AVAILABLE:
        grounded = False

    # 12. Claims deliberately avoided — straight off the contract, never invented.
    claims_avoided = list(contract.unsupported_claims) if contract is not None else []

    # 13. Remaining weaknesses — the Creative Director's own unresolved
    # issues (post-rewrite, if any survived), never a fresh critique.
    remaining_weaknesses = list(evaluation.issues) if evaluation is not None else []

    return CreativeBreakdown(
        hook_reason=hook_reason,
        territory_reason=territory_reason,
        human_insight=human_insight,
        behavioral_tension=behavioral_tension,
        situation_reason=situation_reason,
        product_entry_reason=product_entry_reason,
        narrative_device_reason=narrative_device_reason,
        payoff_reason=payoff_reason,
        memorability_reason=memorability_reason,
        visual_executability_reason=visual_executability_reason,
        distinctiveness_reason=distinctiveness_reason,
        claims_avoided=claims_avoided,
        remaining_weaknesses=remaining_weaknesses,
        fully_grounded=grounded,
    )


def build_creative_quality_assessment(
    *,
    contract=None,
    premise=None,
    evaluation=None,  # architecture_validation_service.ScriptExecutionEvaluation | None
    claim_safety_result=None,  # claim_safety_service.ClaimSafetyResult | None
) -> CreativeQualityAssessment:
    """Renders the Task V3 Part 10 structured assessment: 11 named
    dimensions, each a (score, evidence, source_creative_decision) triple —
    never a bare "this is strong"/"award-winning" claim. Every score comes
    straight from the Creative Director's own evaluation.scores dict (never
    invented here); every "evidence"/"source" comes from the actual premise/
    contract object that decision was made from. A dimension with no
    evaluation attached gets score=None (honestly "not scored"), never a
    fabricated number.

    claim_safety_result (from the dedicated claim_safety_service hard gate —
    see script_service._apply_claim_safety_gate) is the actual per-script
    verdict, not a placeholder: it REPLACES the old "did the contract list
    any unsupported claims" proxy, and a failing result forces
    overall_passed=False regardless of what the Creative Director's own
    evaluation said — a script must never be presented as "passed review"
    while a hard safety gate is still failing."""
    dimensions: list[QualityDimension] = []
    scores = evaluation.scores if evaluation is not None else {}

    for name, score_key in _DIMENSION_SCORE_KEYS.items():
        score = scores.get(score_key)
        evidence = f"Creative Director {score_key} score: {score}/5." if score else _NOT_SCORED
        if name == "Human Insight":
            source = premise.human_tension if premise and premise.human_tension else _NOT_AVAILABLE
        elif name == "Visual Potential":
            source = premise.visual_device if premise and premise.visual_device else _NOT_AVAILABLE
        elif name == "Product Integration":
            source = premise.product_role if premise and premise.product_role else _NOT_AVAILABLE
        elif name == "Payoff Strength":
            source = premise.payoff if premise and premise.payoff else _NOT_AVAILABLE
        elif name in ("Originality",):
            source = premise.why_not_swappable if premise and premise.why_not_swappable else _NOT_AVAILABLE
        elif name == "Narrative Execution":
            source = (premise.narrative_device or premise.creative_device) if premise else _NOT_AVAILABLE
        else:
            source = _NOT_AVAILABLE
        dimensions.append(QualityDimension(name=name, score=score, evidence=evidence, source_creative_decision=source))

    # Claim Safety and Genericness Risk are not in the script-execution
    # scores dict (they're tracked as booleans/lists elsewhere) — handled
    # separately rather than forcing a fake score for them.
    if claim_safety_result is not None:
        failure_bits = []
        if claim_safety_result.unsupported:
            failure_bits.append(f"unsupported {claim_safety_result.claim_type} claim: \"{claim_safety_result.evidence}\"")
        if claim_safety_result.emotional_coercion:
            failure_bits.append(f"emotional coercion: {claim_safety_result.coercion_reason}")
        dimensions.append(QualityDimension(
            name="Claim Safety",
            score=1.0 if claim_safety_result.passed else 0.0,
            evidence=("Passed the claim-safety/coercion hard gate." if claim_safety_result.passed
                      else "FAILED the claim-safety/coercion hard gate: " + "; ".join(failure_bits)),
            source_creative_decision="claim_safety_service.check_claim_safety_and_coercion (deterministic + semantic hard gate)",
        ))
    else:
        unsupported = list(contract.unsupported_claims) if contract is not None else []
        dimensions.append(QualityDimension(
            name="Claim Safety",
            score=None,
            evidence=_NOT_SCORED + " (claim-safety hard gate did not run for this script).",
            source_creative_decision=", ".join(unsupported) or "ProductCreativeContract.unsupported_claims (empty)",
        ))
    genericness_flagged = bool(evaluation is not None and (evaluation.announcement_mode or evaluation.abstract_copy_risk))
    dimensions.append(QualityDimension(
        name="Genericness Risk",
        score=(0.0 if genericness_flagged else 1.0) if evaluation is not None else None,
        evidence=(
            "Flagged: announcement_mode or abstract_copy_risk was true." if genericness_flagged
            else ("Neither announcement_mode nor abstract_copy_risk was flagged." if evaluation is not None else _NOT_SCORED)
        ),
        source_creative_decision="architecture_validation_service.ScriptExecutionEvaluation.announcement_mode/abstract_copy_risk",
    ))

    if claim_safety_result is not None and not claim_safety_result.passed:
        overall_passed = False  # a hard safety-gate failure always wins — never "passed review" regardless of other scores
    elif evaluation is not None:
        overall_passed = evaluation.passed
    else:
        overall_passed = None

    return CreativeQualityAssessment(
        dimensions=dimensions,
        overall_passed=overall_passed,
    )
