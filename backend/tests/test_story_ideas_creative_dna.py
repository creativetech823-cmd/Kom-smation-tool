"""Story Ideas + Creative Quality Upgrade (2026-09-18 task, "Calender Video
August.docx" reference DNA) — tests for the genuinely NEW logic this task
adds: the mechanism catalog, the reference-DNA mechanism records, the pool ->
filter -> mechanism-variety-aware final-six selection, the STRONG CONCEPT
badge, the idea-level claim-safety pre-filter, the 6-card hard cap, and the
shortfall wrapper's router wiring.

Does NOT re-test what already has dedicated coverage elsewhere:
- claim safety / emotional coercion / "Meri Maa Ki Dua" at the SCRIPT level:
  tests/test_claim_safety_service.py, tests/test_meri_maa_ki_dua_regression.py
- Herbal Masala cooking/fitness role-risk rejection at the deterministic
  layer: tests/test_product_context_validator.py, tests/test_category_drift_pipeline_protection.py
- Creative Breakdown / Quality Assessment rendering: tests/test_creative_breakdown_service.py,
  tests/test_creative_breakdown_integration.py
"""

import json
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import creative_mechanism_catalog as mech_catalog
from app.services import creative_reference_dna as dna
from app.services import openrouter_utils, semantic_story_judge_service as sj
from app.services import story_situation_service as svc


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")
    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


HERBAL_MASALA = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same chewing ritual and taste"],
)


def _payload(count=6, **kw):
    return StorySituationsInput(
        structured_product=HERBAL_MASALA, product_category="herbal_health", count=count,
        script_language=ScriptLanguage.hinglish, **kw,
    )


def _candidate(title, mechanism="Object-Driven Reveal", **overrides):
    base = {
        "title": title, "description": f"description for {title}", "human_situation": "a specific person",
        "behavioral_tension": "a specific tension", "creative_mechanism": mechanism,
        "creative_engine": "a specific behavior with a specific object and a specific turn",
        "product_role": "the specific job the product does", "emotion": "e", "persona": "p",
        "marketing_angle": "m", "category": "c", "difficulty": "easy", "estimated_length": "30s",
        "virality_score": 6.0, "recommended_angles": [],
    }
    base.update(overrides)
    return base


def _judgment_for(index, **overrides):
    raw = {
        "candidate_index": index, "semantic_category_drift": False, "product_role_alignment": 0.9,
        "creative_potential": 0.8, "genericness_risk": 0.2, "cluster_id": f"cluster_{index}",
        "product_truth_alignment": 0.9, "audience_alignment": 0.9, "behavior_alignment": 0.9,
    }
    raw.update(overrides)
    return sj._parse_judgment(raw)


# --- Creative mechanism catalog (Part 3/5) ----------------------------------


def test_mechanism_catalog_includes_all_named_primitives_from_the_task():
    labels = {m["label"] for m in mech_catalog.CREATIVE_MECHANISMS}
    for expected in (
        "Object-Driven Reveal", "Ritual Replacement", "Value Math", "Character-as-Proof",
        "Peer Realization", "Behavioral Comedy / Satire", "Before/After Behavioral Contrast",
    ):
        assert expected in labels, expected


def test_valid_mechanism_label_canonicalizes_case_and_whitespace():
    assert mech_catalog.valid_mechanism_label("  object-driven reveal  ") == "Object-Driven Reveal"


def test_valid_mechanism_label_falls_back_for_invented_label():
    assert mech_catalog.valid_mechanism_label("Something The Model Invented") in {m["label"] for m in mech_catalog.CREATIVE_MECHANISMS}


def test_catalog_prompt_block_includes_working_principle_not_just_label():
    block = mech_catalog.catalog_prompt_block()
    assert "Value Math" in block
    assert "accumulates" in block.lower()  # the actual mechanism, not just a name


def test_story_situation_service_system_prompt_includes_mechanism_catalog():
    prompt = svc._system_prompt(ScriptLanguage.hinglish)
    assert "Value Math" in prompt
    assert "Ritual Replacement" in prompt
    assert "do not force the same one or two mechanisms" in prompt.lower()


# --- Reference DNA extraction from the new document (Part 2) ---------------


def test_reference_dna_has_new_mechanism_tagged_records_from_the_document():
    mechanisms = {r.creative_mechanism for r in dna._USABLE_RECORDS if r.creative_mechanism}
    for expected in ("Value Math", "Character-as-Proof", "Peer Realization", "Upgrade / Modernization"):
        assert expected in mechanisms, expected


def test_mechanism_notes_returns_grounded_example_for_value_math():
    notes = dna.mechanism_notes("Value Math", product_category="herbal_health", brief_text="gutka tobacco switch")
    assert "Value Math" in notes
    assert notes  # non-empty, has actual content


def test_mechanism_notes_empty_for_unmapped_mechanism():
    assert dna.mechanism_notes("Social Experiment") == ""  # no record tagged with this one yet


# --- Pool generation (Part 6) ------------------------------------------------


def test_pool_size_is_between_12_and_20():
    assert 12 <= svc._pool_size(6) <= 20
    assert 12 <= svc._pool_size(1) <= 20
    assert svc._pool_size(6) >= svc._pool_size(1)


def test_generate_situations_requests_the_pool_not_just_six():
    response = json.dumps({"situations": [_candidate(f"Card {i}") for i in range(3)]})
    captured = {}

    def fake(**kwargs):
        captured["msg"] = kwargs["contents"][0]
        return response

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        svc.generate_situations(_payload(count=6))
    assert f"Generate exactly {svc._pool_size(6)} story situations" in captured["msg"]
    assert svc._pool_size(6) > 6  # genuinely a larger pool, not just six


# --- 6-card hard cap (Part 12) -----------------------------------------------


def test_never_returns_more_than_six_even_if_count_requests_more():
    many_cards = [_candidate(f"Card {i}", mechanism="Everyday Specific Situation") for i in range(10)]
    response = json.dumps({"situations": many_cards})
    judgments = [_judgment_for(i) for i in range(10)]
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(count=50))  # even a wildly over-large request
    assert len(result.situations) <= svc.MAX_STORY_IDEAS_PER_GENERATION


def test_exactly_six_returned_when_at_least_six_survive():
    cards = [_candidate(f"Card {i}", mechanism="Everyday Specific Situation") for i in range(10)]
    response = json.dumps({"situations": cards})
    judgments = [_judgment_for(i) for i in range(10)]
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(count=6))
    assert len(result.situations) == 6


def test_fewer_than_six_shown_when_fewer_survive_never_padded():
    cards = [_candidate(f"Card {i}") for i in range(3)]
    response = json.dumps({"situations": cards})
    judgments = [_judgment_for(i) for i in range(3)]
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(count=6))
    assert len(result.situations) == 3
    titles = {s.title for s in result.situations}
    assert titles == {"Card 0", "Card 1", "Card 2"}  # no fabricated filler card


# --- Mechanism-variety-aware final selection (Part 4/8) ---------------------


def test_final_six_does_not_let_one_mechanism_dominate():
    """9 candidates, all sharing ONE mechanism except 3 with distinct ones —
    the cap (_MAX_PER_MECHANISM_IN_FINAL=3) must keep the dominant mechanism
    from filling all 6 slots when distinct alternatives exist."""
    dominant = [_candidate(f"Dominant {i}", mechanism="Object-Driven Reveal", virality_score=9.0) for i in range(6)]
    distinct = [
        _candidate("Ritual One", mechanism="Ritual Replacement"),
        _candidate("Value One", mechanism="Value Math"),
        _candidate("Peer One", mechanism="Peer Realization"),
    ]
    cards = dominant + distinct
    response = json.dumps({"situations": cards})
    # Dominant candidates score highest so a pure ranking would crowd them all in.
    judgments = (
        [_judgment_for(i, creative_potential=0.95) for i in range(6)]
        + [_judgment_for(i, creative_potential=0.5) for i in range(6, 9)]
    )
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(count=6))
    mechanisms = [s.creative_mechanism for s in result.situations]
    assert mechanisms.count("Object-Driven Reveal") <= svc._MAX_PER_MECHANISM_IN_FINAL
    assert "Ritual Replacement" in mechanisms
    assert "Value Math" in mechanisms
    assert "Peer Realization" in mechanisms


def test_select_final_six_only_considers_actual_survivors_for_mechanism_cap():
    """A non-survivor sharing a popular mechanism must never consume a
    mechanism-cap slot and crowd out an actual survivor."""
    items = [
        {"creative_mechanism": "Object-Driven Reveal"},  # index 0: NOT a survivor
        {"creative_mechanism": "Object-Driven Reveal"},  # index 1: survivor
        {"creative_mechanism": "Object-Driven Reveal"},  # index 2: survivor
        {"creative_mechanism": "Object-Driven Reveal"},  # index 3: survivor
    ]
    judgment_by_index = {i: _judgment_for(i, creative_potential=0.9 - i * 0.01) for i in (1, 2, 3)}
    selected = svc._select_final_six(items, [1, 2, 3], judgment_by_index, limit=3)
    assert 0 not in selected
    assert set(selected) == {1, 2, 3}


# --- STRONG CONCEPT badge (Part 15) -----------------------------------------


def test_strong_concept_requires_all_gates_not_score_alone():
    high_score_but_generic = _judgment_for(0, creative_potential=0.95, genericness_risk=0.9)
    assert svc._is_strong_concept(high_score_but_generic) is False  # 9.5/10-equivalent score alone is not enough

    high_score_but_low_role_alignment = _judgment_for(0, creative_potential=0.95, product_role_alignment=0.5)
    assert svc._is_strong_concept(high_score_but_low_role_alignment) is False

    high_score_with_implied_claim = sj.SemanticJudgment(
        candidate_index=0, semantic_category_drift=False, reason="", product_role_alignment=0.95,
        creative_potential=0.95, genericness_risk=0.1, implied_claim=True,
    )
    assert svc._is_strong_concept(high_score_with_implied_claim) is False

    genuinely_strong = _judgment_for(0, creative_potential=0.9, genericness_risk=0.1, product_role_alignment=0.9)
    assert svc._is_strong_concept(genuinely_strong) is True


def test_strong_concept_false_when_no_judgment_available():
    assert svc._is_strong_concept(None) is False


def test_generate_situations_marks_strong_concept_on_surviving_cards():
    card = _candidate("A Genuinely Strong Idea")
    response = json.dumps({"situations": [card]})
    judgment = [_judgment_for(0, creative_potential=0.9, genericness_risk=0.1, product_role_alignment=0.9)]
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgment):
        result = svc.generate_situations(_payload(count=6))
    assert result.situations[0].strong_concept is True


def test_generate_situations_does_not_mark_strong_concept_when_judge_unavailable():
    """No judge data means no basis to award the badge — never guess."""
    card = _candidate("Some Idea")
    response = json.dumps({"situations": [card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload(count=6))
    assert result.situations[0].strong_concept is False


# --- Idea-level claim-safety pre-filter (Part 9/10) -------------------------


def test_explicit_ingredient_efficacy_claim_rejected_before_judge_runs():
    unsafe = _candidate("Mulethi Ka Kamaal", description="Mulethi jo gale ko kam karta hai aur cravings ko reduce karta hai.")
    safe = _candidate("A Clean Idea")
    response = json.dumps({"situations": [unsafe, safe]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None) as mock_judge:
        result = svc.generate_situations(_payload(count=6))
    titles = {s.title for s in result.situations}
    assert "Mulethi Ka Kamaal" not in titles
    assert "A Clean Idea" in titles
    # The judge should only ever see the already-claim-filtered pool.
    judged_candidates = mock_judge.call_args[0][1]
    assert all(c["title"] != "Mulethi Ka Kamaal" for c in judged_candidates)


def test_bare_ingredient_mention_with_no_efficacy_verb_is_not_flagged():
    safe = _candidate("Ismein Hai Mulethi", description="Ismein hai Mulethi aur Amla, same chewing ritual.")
    response = json.dumps({"situations": [safe]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload(count=6))
    assert len(result.situations) == 1


def test_implied_claim_flagged_by_judge_is_rejected():
    card = _candidate("Wilting to Blooming")
    response = json.dumps({"situations": [card]})
    judgment = [_judgment_for(0, creative_potential=0.9)]
    judgment[0].implied_claim = True
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgment):
        result = svc.generate_situations(_payload(count=6))
    assert result.situations == []


def test_emotional_coercion_flagged_by_judge_is_rejected():
    card = _candidate("Meri Maa Ki Dua")
    response = json.dumps({"situations": [card]})
    judgment = [_judgment_for(0, creative_potential=0.9)]
    judgment[0].emotional_coercion = True
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgment):
        result = svc.generate_situations(_payload(count=6))
    assert result.situations == []


# --- New card fields populated end to end -----------------------------------


def test_new_card_fields_are_populated_from_the_model_response():
    card = _candidate(
        "A Real Idea", mechanism="Peer Realization",
        human_situation="a specific office worker", behavioral_tension="hiding a habit from a colleague",
        creative_engine="a colleague notices a changed break-time ritual before being told why",
        product_role="the replacement the colleague offers",
    )
    response = json.dumps({"situations": [card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload(count=6))
    s = result.situations[0]
    assert s.human_situation == "a specific office worker"
    assert s.behavioral_tension == "hiding a habit from a colleague"
    assert s.creative_mechanism == "Peer Realization"
    assert "colleague" in s.creative_engine
    assert s.product_role == "the replacement the colleague offers"


# --- Shortfall wrapper + router wiring (Part 13) ----------------------------


def test_generate_situations_for_request_reports_no_shortfall_when_full_count_survives():
    cards = [_candidate(f"Card {i}") for i in range(6)]
    response = json.dumps({"situations": cards})
    judgments = [_judgment_for(i) for i in range(6)]
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations_for_request(_payload(count=6))
    assert result.generation_shortfall is False
    assert len(result.situations) == 6


def test_generate_situations_for_request_reports_shortfall_after_bounded_retries():
    thin_response = json.dumps({"situations": [_candidate("Only One")]})
    with patch.object(svc, "generate_text", return_value=thin_response), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations_for_request(_payload(count=6))
    assert result.generation_shortfall is True
    assert len(result.situations) == 1  # whatever survived the last attempt, never padded
    assert result.situations[0].title == "Only One"


def test_generate_situations_for_request_never_exceeds_max_attempts_calls():
    call_count = {"n": 0}

    def fake(**kwargs):
        call_count["n"] += 1
        return json.dumps({"situations": [_candidate("Only One")]})

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        svc.generate_situations_for_request(_payload(count=6))
    assert call_count["n"] == svc.MAX_QUALITY_FLOOR_ATTEMPTS
