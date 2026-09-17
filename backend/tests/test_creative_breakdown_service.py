"""creative_breakdown_service is a pure deterministic renderer — no LLM
calls, so these tests construct fixture objects directly rather than mocking
generate_text. The point being tested: every line traces to a specific
field, and a missing upstream stage produces an honest "not available"
placeholder (never an invented explanation) with fully_grounded=False."""

from app.services.creative_breakdown_service import build_creative_breakdown, build_creative_quality_assessment
from app.services.creative_premise_service import CreativePremise
from app.services.creative_territory_service import CreativeTerritory
from app.services.product_context_service import ProductCreativeContract
from app.services.architecture_validation_service import ScriptExecutionEvaluation
from app.services.creative_architecture import ARCHITECTURES


def _territory() -> CreativeTerritory:
    return CreativeTerritory(
        territory_name="The Ghost of Habits Past",
        territory_description="Muscle-memory reach for an old habit.",
        human_tension="Residual urge even after deciding to change.",
        behavioural_truth="Hands act before the mind decides.",
        creative_question="What happens when the hand remembers but the person has moved on?",
        emotional_engine="quiet relief",
        possible_story_world="a quiet desk, an empty drawer",
        product_role="the new answer the hand finds instead",
        why_it_fits_product="Herbal Masala replaces the exact reach-for-it moment, not just the product.",
        reference_dna_fit="matches the late-reveal mechanism seen in the reference set",
        novelty_vs_recent_concepts="Distinct from the last 3 generations, which used a confrontation device.",
        distinct_from_other_candidates="Unlike the other candidates, this one has no second character at all.",
    )


def _premise() -> CreativePremise:
    return CreativePremise(
        statement="A hand reaches for an empty pouch out of habit, then finds the new packet instead.",
        creative_device="visual metaphor",
        situation="A quiet desk moment, days after quitting.",
        why_curious="The viewer wonders what the hand will find.",
        why_not_swappable="The empty-pouch device is specific to a real gutka/tobacco habit, not swappable to a generic wellness product.",
        visual_device="close-up on a hand diverting from an old dusty pouch to a bright new packet",
        emotional_engine="quiet relief",
        product_role="the thing the hand finds instead of the old habit",
        payoff="the hand's motion completes on the new packet, not the old one",
        narrative_device="visual metaphor / muscle memory",
        who="a person mid-recovery from a gutka habit",
        concrete_event="the hand's autopilot reach is interrupted and redirected",
        human_tension="residual urge after deciding to change",
        what_changes="the automatic reach now lands on the new product, not the old habit",
    )


def _contract() -> ProductCreativeContract:
    return ProductCreativeContract(
        product_name="Aayush Wellness Herbal Masala",
        canonical_category="Tobacco/gutka/pan-masala alternative",
        category_confidence="high",
        core_problem_or_tension="the pull of an existing habit vs. the desire to switch",
        unsupported_claims=["cures addiction", "medically proven"],
    )


def test_fully_grounded_when_every_stage_present():
    evaluation = ScriptExecutionEvaluation(issues=[], scores={"memorability": 4}, announcement_mode=False)
    result = build_creative_breakdown(
        contract=_contract(),
        insight_statement="People miss the ritual, not just the substance.",
        territory=_territory(),
        premise=_premise(),
        selected_hook_text="Jab haath apne aap purane khaali dabbe ki taraf jaaye...",
        architecture=ARCHITECTURES["visual_metaphor_device"],
        evaluation=evaluation,
    )
    assert result.fully_grounded is True
    assert "Ghost of Habits Past" in result.territory_reason
    assert result.human_insight == "People miss the ritual, not just the substance."
    assert "empty pouch" not in result.hook_reason  # hook line quotes the hook, not the premise
    assert "visual metaphor" in result.hook_reason or "visual metaphor" in result.narrative_device_reason
    assert result.memorability_reason == "Creative Director memorability score: 4/5."
    assert result.claims_avoided == ["cures addiction", "medically proven"]
    assert result.remaining_weaknesses == []


def test_missing_stages_produce_honest_not_available_not_invented_text():
    result = build_creative_breakdown()
    assert result.fully_grounded is False
    assert "not available" in result.hook_reason
    assert "not available" in result.human_insight
    assert result.claims_avoided == []
    assert result.remaining_weaknesses == []
    # No territory object at all still gets a real (not "not available") line
    # explaining the absence, since that IS the grounded truth in this case.
    assert "No creative territory was selected" in result.territory_reason


def test_remaining_weaknesses_reflects_actual_unresolved_evaluation_issues():
    evaluation = ScriptExecutionEvaluation(issues=["announcement_mode", "payoff_repeats_setup"], scores={})
    result = build_creative_breakdown(evaluation=evaluation)
    assert result.remaining_weaknesses == ["announcement_mode", "payoff_repeats_setup"]
    # Not invented commentary — the exact issue codes the real gate produced.


def test_behavioral_tension_falls_back_through_territory_then_premise_then_contract():
    # No territory -> falls back to premise.human_tension
    result = build_creative_breakdown(premise=_premise())
    assert result.behavioral_tension == "residual urge after deciding to change"

    # Neither territory nor premise -> falls back to contract
    result2 = build_creative_breakdown(contract=_contract())
    assert result2.behavioral_tension == "the pull of an existing habit vs. the desire to switch"


# --- CreativeQualityAssessment (Task V3 Part 10) -----------------------------


def test_quality_assessment_every_score_traces_to_the_real_evaluation_scores_dict():
    evaluation = ScriptExecutionEvaluation(
        issues=[], announcement_mode=False, abstract_copy_risk=False,
        scores={"creative_concept_strength": 4, "hook_quality": 5, "memorability": 3, "product_integration": 4,
                "visual_potential": 4, "payoff_quality": 4, "narrative_device_integrity": 4, "human_tension": 4},
    )
    result = build_creative_quality_assessment(contract=_contract(), premise=_premise(), evaluation=evaluation)
    by_name = {d.name: d for d in result.dimensions}
    assert by_name["Hook Strength"].score == 5
    assert "5/5" in by_name["Hook Strength"].evidence
    assert by_name["Memorability"].score == 3
    assert result.overall_passed is True
    # No dimension is a bare number — every one carries a traceable source.
    assert all(d.source_creative_decision for d in result.dimensions)


def test_quality_assessment_never_fabricates_a_score_when_no_evaluation_attached():
    result = build_creative_quality_assessment()
    assert result.overall_passed is None
    for d in result.dimensions:
        assert d.score is None, f"{d.name} should not have a fabricated score with no evaluation attached"
        if d.name not in ("Claim Safety", "Genericness Risk"):
            assert "not scored" in d.evidence
            assert "not available" in d.source_creative_decision


def test_quality_assessment_claim_safety_lists_actual_contract_claims_not_invented_ones():
    evaluation = ScriptExecutionEvaluation(issues=[], scores={})
    result = build_creative_quality_assessment(contract=_contract(), evaluation=evaluation)
    claim_safety = next(d for d in result.dimensions if d.name == "Claim Safety")
    assert "cures addiction" in claim_safety.source_creative_decision
    assert "medically proven" in claim_safety.source_creative_decision


def test_quality_assessment_genericness_risk_reflects_announcement_mode_flag():
    generic_eval = ScriptExecutionEvaluation(issues=["announcement_mode"], announcement_mode=True, scores={})
    result = build_creative_quality_assessment(evaluation=generic_eval)
    genericness = next(d for d in result.dimensions if d.name == "Genericness Risk")
    assert genericness.score == 0.0
    assert "Flagged" in genericness.evidence
