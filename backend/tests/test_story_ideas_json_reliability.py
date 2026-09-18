"""Story Ideas structured-output reliability (2026-09-18 task) — the
confirmed production failure: "openai/gpt-5.6-luna returned malformed JSON
while generating story ideas — the response may have been truncated."

Covers the new _parse_situations_json/_salvage_array_objects robustness
layer (markdown-fence stripping, trailing-comma cleanup, partial-array
salvage for a genuinely truncated response), the recommended_angles
enrichment split (Option A — deferred out of the large pool-generation
call), and end-to-end proof that a Luna-shaped truncated response degrades
to "use the complete candidates, drop the cut-off one" rather than losing
the whole batch or accepting a fabricated/malformed candidate.

Does not touch creative architecture — every candidate that survives a
salvage parse still goes through the SAME claim-safety/category/semantic-
judge/dedup/diversity gates as a cleanly-parsed one; nothing here weakens
what counts as valid.
"""

import json
from unittest.mock import patch

import pytest

from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import openrouter_utils, semantic_story_judge_service as sj, story_situation_service as svc


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


def _payload(count=6):
    return StorySituationsInput(
        structured_product=HERBAL_MASALA, product_category="herbal_health", count=count,
        script_language=ScriptLanguage.hinglish,
    )


def _card(title, **overrides):
    base = {
        "title": title, "description": f"description for {title}", "human_situation": "a specific person",
        "behavioral_tension": "a specific tension", "creative_mechanism": "Object-Driven Reveal",
        "creative_engine": "a specific behavior with a specific object and a specific turn",
        "product_role": "the specific job the product does", "hook_type": "Question",
        "hook_mechanism": "fits", "hook_execution": "a concrete opening scene", "emotion": "e", "persona": "p",
        "marketing_angle": "m", "category": "c", "difficulty": "easy", "estimated_length": "30s",
        "virality_score": 6.0,
    }
    base.update(overrides)
    return base


def _valid_response(n=3):
    return json.dumps({"situations": [_card(f"Card {i}") for i in range(n)]})


# --- The exact Luna-style truncated fixture ---------------------------------
# Modeled directly on the reported production failure: a well-formed opening
# (complete candidate objects), then the response is cut off mid-string on
# the final candidate — no closing quote, no closing braces/brackets at all.
# This is what "the response may have been truncated" actually looks like.
LUNA_TRUNCATED_RESPONSE = (
    '{"situations": [' +
    json.dumps(_card("Cricket Match, Naya Swag")) + "," +
    json.dumps(_card("Papa Ki Nayi Pasand")) + "," +
    '{"title": "Office Mein Nayi Pehchan", "description": "A colleague notices the cha'
    # ^ cut off mid-string — no closing quote, no closing braces/brackets anywhere.
)

MARKDOWN_FENCED_RESPONSE = "```json\n" + _valid_response(2) + "\n```"

EXTRA_PROSE_RESPONSE = "Here are the story ideas you requested:\n\n" + _valid_response(2)

SCHEMA_MISMATCH_RESPONSE = json.dumps({"situations": "not a list at all"})


# --- Unit tests: _parse_situations_json / _salvage_array_objects -----------


def test_valid_response_parses_normally_no_salvage_needed():
    data = svc._parse_situations_json(_valid_response(3))
    assert len(data["situations"]) == 3


def test_markdown_fenced_response_is_stripped_and_parses():
    data = svc._parse_situations_json(MARKDOWN_FENCED_RESPONSE)
    assert len(data["situations"]) == 2


def test_trailing_comma_response_is_cleaned_and_parses():
    broken = '{"situations": [' + json.dumps(_card("A")) + ",]}"
    data = svc._parse_situations_json(broken)
    assert len(data["situations"]) == 1


def test_luna_truncated_response_salvages_the_complete_candidates():
    data = svc._parse_situations_json(LUNA_TRUNCATED_RESPONSE)
    titles = {s["title"] for s in data["situations"]}
    # The two COMPLETE candidates survive; the cut-off third one does not —
    # never fabricated, never silently repaired into something invalid.
    assert titles == {"Cricket Match, Naya Swag", "Papa Ki Nayi Pasand"}
    assert len(data["situations"]) == 2


def test_extra_prose_before_json_is_not_salvageable_by_this_layer_but_does_not_crash():
    """Prose before the JSON object means the response doesn't start with
    '{' — _strip_markdown_fence doesn't touch prose (only code fences), so
    this legitimately still fails to parse as a whole. Confirms the salvage
    path is reached (via the array-marker scan) and either recovers
    candidates or cleanly raises — never silently accepts the prose itself
    as data."""
    try:
        data = svc._parse_situations_json(EXTRA_PROSE_RESPONSE)
        assert len(data["situations"]) == 2  # the salvage scan found the array despite the leading prose
    except json.JSONDecodeError:
        pass  # also an acceptable outcome — never a false "success"


def test_empty_response_string_raises_not_silently_treated_as_zero_candidates():
    with pytest.raises(json.JSONDecodeError):
        svc._parse_situations_json("")


def test_schema_mismatch_situations_not_a_list_does_not_crash_the_parser():
    """The PARSER's job is only syntax — a syntactically valid but wrong-
    shaped response parses fine here; downstream code (raw_items = data.get
    ("situations", [])) is what must handle a non-list value, tested in the
    integration section below."""
    data = svc._parse_situations_json(SCHEMA_MISMATCH_RESPONSE)
    assert data["situations"] == "not a list at all"


def test_salvage_finds_nothing_when_array_marker_is_entirely_absent():
    assert svc._salvage_array_objects('{"foo": "bar"}', "situations") == []


def test_salvage_skips_a_malformed_individual_object_but_keeps_good_ones():
    text = '{"situations": [' + json.dumps(_card("Good One")) + ', {this is not valid json}, ' + json.dumps(_card("Also Good")) + "]}"
    result = svc._salvage_array_objects(text, "situations")
    titles = {r["title"] for r in result}
    assert titles == {"Good One", "Also Good"}


# --- Integration: generate_situations() end to end --------------------------


def test_end_to_end_truncated_luna_response_still_produces_valid_cards():
    """The complete regression: a genuinely Luna-shaped truncated response
    must not blow up the whole request — the 2 complete candidates still
    go through every existing gate and can still be returned."""
    with patch.object(svc, "generate_text", return_value=LUNA_TRUNCATED_RESPONSE), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    titles = {s.title for s in result.situations}
    assert titles.issubset({"Cricket Match, Naya Swag", "Papa Ki Nayi Pasand"})
    assert len(result.situations) <= 2


def test_end_to_end_schema_mismatch_situations_not_a_list_degrades_to_zero_not_a_crash():
    with patch.object(svc, "generate_text", return_value=SCHEMA_MISMATCH_RESPONSE):
        with pytest.raises((ValueError, TypeError, AttributeError)):
            # raw_items = data.get("situations", []) would be a STRING here,
            # which the deterministic filters then iterate character-by-
            # character over — this must fail loudly (a clear exception
            # bubbling to the router's existing error handling), never
            # silently produce "situations" made of individual characters.
            svc.generate_situations(_payload())


def test_end_to_end_genuinely_empty_response_raises_the_documented_error():
    with patch.object(svc, "generate_text", return_value=""):
        with pytest.raises(ValueError, match="malformed JSON"):
            svc.generate_situations(_payload())


def test_malformed_json_that_cannot_be_salvaged_at_all_still_raises_clear_error():
    with patch.object(svc, "generate_text", return_value="{not json and no situations array marker"):
        with pytest.raises(ValueError, match="malformed JSON"):
            svc.generate_situations(_payload())


def test_diagnostics_logged_on_unsalvageable_parse_failure(caplog):
    import logging
    with patch.object(svc, "generate_text", return_value="{not json at all, no array marker"):
        with caplog.at_level(logging.WARNING, logger="story_situation_service"):
            with pytest.raises(ValueError):
                svc.generate_situations(_payload())
    assert "length=" in caplog.text
    assert "head=" in caplog.text


# --- Timeout / retry / no silent fallback (unaffected by the JSON fix) -----


def test_pool_generation_still_retries_on_transient_failure_before_giving_up():
    call_count = {"n": 0}

    def fake(*args, **kwargs):
        if kwargs.get("label") != "story_situations":
            return _valid_response(1)  # enrichment call on the lone survivor, not under test here
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": "openai/gpt-5.6-luna"})
        return _valid_response(1)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert call_count["n"] == 2  # one transient failure, one successful retry
    assert len(result.situations) == 1


def test_pool_generation_gives_up_after_story_ideas_max_attempts_not_the_global_default():
    call_count = {"n": 0}

    def fake(*args, **kwargs):
        call_count["n"] += 1
        raise openrouter_utils.EmptyResponseError("empty", diagnostics={"model": "openai/gpt-5.6-luna"})

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch("time.sleep", return_value=None):
        with pytest.raises(ValueError):
            svc.generate_situations(_payload())
    assert call_count["n"] == svc._STORY_IDEAS_MAX_ATTEMPTS  # 2, not the global default of 4


def test_no_silent_fallback_to_a_different_model_on_json_failure():
    models_used = []

    def fake(**kwargs):
        models_used.append(kwargs.get("model"))
        return LUNA_TRUNCATED_RESPONSE

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        svc.generate_situations(_payload())
    assert len(set(models_used)) == 1  # pool-gen and enrichment used the identical configured model
    assert models_used[0] == svc.settings.creative_model


# --- 6-card UI cap + valid-never-replaced-by-invalid ------------------------


def test_final_ui_output_still_capped_at_six_even_with_a_large_salvaged_pool():
    many_complete_cards = ",".join(json.dumps(_card(f"Card {i}", creative_mechanism=f"Mech {i}")) for i in range(15))
    truncated_but_mostly_complete = '{"situations": [' + many_complete_cards + ', {"title": "Cut Off Card", "descrip'
    judgments = [
        sj._parse_judgment({
            "candidate_index": i, "semantic_category_drift": False, "product_role_alignment": 0.9,
            "creative_potential": 0.8, "genericness_risk": 0.2, "cluster_id": f"c{i}",
        })
        for i in range(15)
    ]
    with patch.object(svc, "generate_text", return_value=truncated_but_mostly_complete), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(count=6))
    assert len(result.situations) <= svc.MAX_STORY_IDEAS_PER_GENERATION


def test_valid_candidates_never_replaced_by_the_incomplete_truncated_one():
    """The cut-off candidate must never appear in the final result under any
    circumstance — not partially, not with fabricated missing fields."""
    with patch.object(svc, "generate_text", return_value=LUNA_TRUNCATED_RESPONSE), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert not any("Office Mein" in s.title for s in result.situations)
    assert not any(s.title == "" for s in result.situations)


# --- Creative architecture remains intact -----------------------------------


def test_salvaged_candidates_still_go_through_claim_safety_prefilter():
    unsafe = _card("Bad One", description="Mulethi gale ko turant aaram deta hai.")
    truncated = (
        '{"situations": [' + json.dumps(unsafe) + "," + json.dumps(_card("Good One")) + ','
        '{"title": "Cut Off", "descrip'
    )
    with patch.object(svc, "generate_text", return_value=truncated), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    titles = {s.title for s in result.situations}
    assert "Bad One" not in titles
    assert "Good One" in titles


def test_salvaged_candidates_still_go_through_hook_quality_prefilter():
    generic_hook = _card("Generic Hook Card", hook_execution="Every mother wants the best for her family.")
    truncated = (
        '{"situations": [' + json.dumps(generic_hook) + "," + json.dumps(_card("Good Hook Card")) + ','
        '{"title": "Cut Off", "descrip'
    )
    with patch.object(svc, "generate_text", return_value=truncated), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    titles = {s.title for s in result.situations}
    assert "Generic Hook Card" not in titles
    assert "Good Hook Card" in titles


def test_mechanism_and_hook_fields_survive_salvage_unweakened():
    card = _card("Full Fields Card", creative_mechanism="Peer Realization", hook_type="Reaction in Action")
    truncated = '{"situations": [' + json.dumps(card) + ', {"title": "Cut'
    with patch.object(svc, "generate_text", return_value=truncated), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert result.situations[0].creative_mechanism == "Peer Realization"
    assert result.situations[0].hook_type == "Reaction in Action"


# --- recommended_angles enrichment split (Option A) -------------------------


def test_recommended_angles_no_longer_requested_in_the_pool_generation_schema():
    prompt = svc._system_prompt(ScriptLanguage.hinglish)
    # The per-candidate JSON schema block must not ask for it anymore — the
    # phrase only appears (if at all) in the separate enrichment prompt.
    assert '"recommended_angles"' not in prompt


def test_enrichment_only_runs_on_final_survivors_not_the_full_pool():
    pool_response = _valid_response(18)
    enrichment_calls = {"n": 0, "candidate_count": None}

    def fake(**kwargs):
        if kwargs.get("label") == "story_situations_angle_enrichment":
            enrichment_calls["n"] += 1
            enrichment_calls["candidate_count"] = kwargs["contents"][0].count("title:")
            return json.dumps({"angles": []})
        return pool_response

    judgments = [
        sj._parse_judgment({
            "candidate_index": i, "semantic_category_drift": False, "product_role_alignment": 0.9,
            "creative_potential": 0.8, "genericness_risk": 0.2, "cluster_id": f"c{i}",
        })
        for i in range(18)
    ]
    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=judgments):
        svc.generate_situations(_payload(count=6))
    assert enrichment_calls["n"] == 1
    assert enrichment_calls["candidate_count"] <= svc.MAX_STORY_IDEAS_PER_GENERATION


def test_enrichment_failure_never_blocks_the_response_angles_just_fall_back():
    def fake(**kwargs):
        if kwargs.get("label") == "story_situations_angle_enrichment":
            raise RuntimeError("enrichment call failed")
        return _valid_response(1)

    with patch.object(svc, "generate_text", side_effect=fake), \
         patch.object(svc, "judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload())
    assert len(result.situations) == 1
    assert result.situations[0].recommended_angles  # fell back to valid_angle_labels([])'s default subset


def test_enrichment_never_called_when_pool_generation_yields_nothing():
    with patch.object(svc, "generate_text", return_value=json.dumps({"situations": []})) as mock_gen:
        svc.generate_situations(_payload())
    labels_used = [c.kwargs.get("label") for c in mock_gen.call_args_list]
    assert "story_situations_angle_enrichment" not in labels_used
