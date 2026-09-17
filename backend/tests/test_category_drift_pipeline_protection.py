"""Verifies category-drift protection is actually wired into every pipeline
stage it's supposed to reach — territory, premise, beat outline, and the
final architecture/creative-director gate (deterministic + a mocked Pro
response that reinterprets the product as a cooking ingredient)."""

import json
from unittest.mock import patch

from app.services import architecture_validation_service as arch_val
from app.services import beat_outline_service as outline_svc
from app.services import creative_premise_service as premise_svc
from app.services import creative_territory_service as territory_svc
from app.services.creative_architecture import ARCHITECTURES
from app.services.product_context_service import build_product_creative_contract

DIALOGUE_TRAP = ARCHITECTURES["dialogue_trap"]

HERBAL_MASALA_CONTRACT = build_product_creative_contract(
    product_name="Aayush Herbal Masala", category="herbal_health",
    target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
    usp="a 0% tobacco, 0% supari herbal chew", benefits=["same ritual and taste"],
)

COOKING_DRIFT_TEXT = (
    "What if main family ke favourite chicken curry mein yeh herbal masala daal doon? "
    "Dinner table par do bowls rakhe. Bowl B mein zyada swaad hai."
)


# --- Territory stage ---------------------------------------------------------


def test_territory_selection_filters_out_cooking_drifted_candidate():
    from app.services.creative_territory_service import CreativeTerritory

    drifted = CreativeTerritory(
        territory_name="Secret Family Recipe", territory_description="d",
        human_tension=COOKING_DRIFT_TEXT, behavioural_truth="b", creative_question="q",
        emotional_engine="e", possible_story_world="a kitchen", product_role="a cooking spice",
        why_it_fits_product="w", reference_dna_fit="r", novelty_vs_recent_concepts="n",
        distinct_from_other_candidates="d2",
        scores={k: 4 for k in territory_svc._SCORE_KEYS}, total_score=40,
    )
    clean = CreativeTerritory(
        territory_name="The Automatic Reach", territory_description="d",
        human_tension="reaching for the old packet", behavioural_truth="b",
        creative_question="q", emotional_engine="e", possible_story_world="a pocket",
        product_role="the replacement reached for", why_it_fits_product="w",
        reference_dna_fit="r", novelty_vs_recent_concepts="n", distinct_from_other_candidates="d2",
        scores={k: 2 for k in territory_svc._SCORE_KEYS}, total_score=20,
    )
    chosen = territory_svc.select_strongest_territory([drifted, clean], contract=HERBAL_MASALA_CONTRACT)
    assert chosen.territory_name == "The Automatic Reach"


def test_territory_selection_unaffected_for_product_with_no_role_risk():
    from app.services.creative_territory_service import CreativeTerritory
    from app.services.product_context_service import build_product_creative_contract as build

    skincare_contract = build(product_name="Glow Serum", category="skincare", target_audience="women")
    cooking_shaped = CreativeTerritory(
        territory_name="Kitchen Story", territory_description="d",
        human_tension="added to curry with the product", behavioural_truth="b", creative_question="q",
        emotional_engine="e", possible_story_world="w", product_role="r", why_it_fits_product="w",
        reference_dna_fit="r", novelty_vs_recent_concepts="n", distinct_from_other_candidates="d2",
        scores={k: 4 for k in territory_svc._SCORE_KEYS}, total_score=40,
    )
    chosen = territory_svc.select_strongest_territory([cooking_shaped], contract=skincare_contract)
    assert chosen is not None  # never filtered — this product has no role_risk_keys


# --- Premise stage -----------------------------------------------------------


def test_premise_selection_filters_out_cooking_drifted_candidate():
    from app.services.creative_premise_service import CreativePremise

    drifted = premise_svc._parse_candidate({
        "statement": "Secretly add it to the family curry without anyone noticing",
        "creative_device": "reveal", "situation": COOKING_DRIFT_TEXT,
        "why_curious": "c", "why_not_swappable": "n",
        "scores": {k: 5 for k in premise_svc._SCORE_KEYS},
    })
    clean = premise_svc._parse_candidate({
        "statement": "A hand reaches automatically for where the old packet used to be",
        "creative_device": "behavioral reveal", "situation": "a pocket, a habit",
        "why_curious": "c", "why_not_swappable": "n",
        "scores": {k: 3 for k in premise_svc._SCORE_KEYS},
    })
    chosen = premise_svc.select_strongest_premise([drifted, clean], contract=HERBAL_MASALA_CONTRACT)
    assert chosen.statement == clean.statement


# --- Beat outline stage -------------------------------------------------------


def test_outline_deterministic_validation_flags_category_drift():
    outline = outline_svc.BeatOutline(
        architecture="dialogue_trap", hook="h", human_insight="i",
        beats=[
            outline_svc.BeatOutlineItem(beat_number=1, purpose="p", content=COOKING_DRIFT_TEXT, emotional_state="e"),
            outline_svc.BeatOutlineItem(beat_number=2, purpose="p", content="cta", emotional_state="e"),
        ],
        product_reveal_beat=1, proof_beat=1, payoff_beat=2, cta_beat=2,
    )
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP, HERBAL_MASALA_CONTRACT)
    assert "outline_category_drift" in issues


def test_outline_deterministic_validation_clean_for_legitimate_content():
    outline = outline_svc.BeatOutline(
        architecture="dialogue_trap", hook="h", human_insight="i",
        beats=[
            outline_svc.BeatOutlineItem(beat_number=i, purpose="p", content="a hand reaches for the old habit", emotional_state="e")
            for i in range(1, 8)
        ],
        product_reveal_beat=5, proof_beat=6, payoff_beat=6, cta_beat=7,
    )
    issues = outline_svc.validate_outline_deterministic(outline, DIALOGUE_TRAP, HERBAL_MASALA_CONTRACT)
    assert "outline_category_drift" not in issues


# --- Final script gate (deterministic) ---------------------------------------


def test_architecture_gate_deterministic_flags_category_drift_in_final_script():
    data = {
        "hook": {"text": COOKING_DRIFT_TEXT},
        "body": [{"text": "Ismein hai Mulethi aur Amla."}],
        "cta": {"text": "Try it today."},
    }
    issues = arch_val.validate_script_against_outline_deterministic(data, None, DIALOGUE_TRAP, "Aayush Herbal Masala", HERBAL_MASALA_CONTRACT)
    assert "category_drift" in issues


def test_architecture_gate_deterministic_clean_for_correct_script():
    data = {
        "hook": {"text": "Jab haath apne aap wahan jaata hai jahan gutka hua karta tha."},
        "body": [{"text": "Ab ussi ritual ke liye Aayush Herbal Masala."}],
        "cta": {"text": "Try it today."},
    }
    issues = arch_val.validate_script_against_outline_deterministic(data, None, DIALOGUE_TRAP, "Aayush Herbal Masala", HERBAL_MASALA_CONTRACT)
    assert "category_drift" not in issues


# --- Final Pro creative-director eval: mocked cooking-masala interpretation -


def test_final_creative_director_eval_flags_category_drift_from_mocked_pro_response():
    """Mocks the Pro response as if it genuinely evaluated the reported
    cooking-masala script and concluded it drifted — verifies the issue
    code round-trips correctly, matching the task's required test:
    'Mock the Pro response with a cooking interpretation and verify
    category_drift=true'."""
    mocked_pro_response = json.dumps({
        "issues": ["category_drift", "weak_creative_idea"],
    })
    with patch.object(arch_val, "call_openrouter_with_retry", return_value=mocked_pro_response):
        issues = arch_val.llm_architecture_and_creative_director_issues(
            {"hook": {"text": COOKING_DRIFT_TEXT}, "body": [], "cta": {"text": "y"}},
            None, DIALOGUE_TRAP, "Aayush Herbal Masala", "gutka chewers",
            contract_block=HERBAL_MASALA_CONTRACT.prompt_block(),
        )
    assert "category_drift" in issues


def test_eval_system_prompt_treats_category_alignment_as_prerequisite_not_averaged_score():
    assert '"category_drift"' in arch_val._EVAL_SYSTEM_PROMPT
    assert "PREREQUISITE" in arch_val._EVAL_SYSTEM_PROMPT
    assert "gates it" in arch_val._EVAL_SYSTEM_PROMPT.lower() or "gate" in arch_val._EVAL_SYSTEM_PROMPT.lower()


def test_category_drift_has_a_rewrite_instruction_in_shared_dict():
    from app.services import script_quality as sq

    assert "category_drift" in sq._ISSUE_INSTRUCTIONS
    assert len(sq.rewrite_reason(["category_drift"])) > 20
