"""Tests for the post-generation creative quality gate, including the AHM
Creative DNA additions: ingredient-dump detection, the expanded generic-
opener denylist, and the new competitor-swappable/interchangeable-beats/
filler-padding/generic-insight issue codes."""

from app.services import script_quality as sq


# --- Anti-overfitting guardrail (§8 — do not overfit to Herbal Masala) ------


def test_category_overfit_flags_gutka_terms_for_unrelated_category():
    terms = sq.category_overfit_terms_present("Roz gutka khane ki aadat chhodo", "immunity/kids health")
    assert "gutka" in terms


def test_category_overfit_allows_tobacco_terms_for_actual_tobacco_category():
    terms = sq.category_overfit_terms_present("Roz gutka khane ki aadat chhodo", "pan masala")
    assert terms == []


def test_category_overfit_empty_when_no_banned_terms_present():
    terms = sq.category_overfit_terms_present("She checks the school WhatsApp group every Monday", "skincare")
    assert terms == []


def test_deterministic_issues_flags_category_overfit_for_skincare_script_with_gutka_language():
    class FakeProduct:
        product_name = "Glow Face Serum"
        ingredients = ["Vitamin C"]
        key_benefits = ["brighter skin"]
        usp = "daily glow"

    class FakePayload:
        structured_product = FakeProduct()
        content_type = "video"
        product_category = "skincare"

    data = {
        "hook": {"text": "Roz gutka khane ki aadat chhodo aur glow pao."},
        "body": [{"text": "Vitamin C helps with brighter skin over time."}],
        "cta": {"text": "Try Glow Face Serum today."},
    }
    issues = sq.deterministic_issues(data, FakePayload())
    assert "category_overfit" in issues


def test_category_overfit_has_rewrite_instruction():
    assert "category_overfit" in sq._ISSUE_INSTRUCTIONS


def test_category_overfit_allows_gutka_terms_when_brief_text_indicates_real_tobacco_audience():
    # The real-world bug: a product like Herbal Masala can be stored under a
    # generic category string ("herbal_health") that says nothing about
    # tobacco/gutka, even though its actual given target audience does.
    terms = sq.category_overfit_terms_present(
        "Roz gutka khane ki aadat chhodo", "herbal_health",
        brief_text="adult gutka and tobacco chewers trying to quit",
    )
    assert terms == []


def test_category_overfit_still_flags_when_neither_category_nor_brief_mentions_tobacco():
    terms = sq.category_overfit_terms_present(
        "Roz gutka khane ki aadat chhodo", "herbal_health", brief_text="mothers of school-age children",
    )
    assert "gutka" in terms


def test_deterministic_issues_uses_target_audience_to_allow_gutka_for_herbal_masala_product():
    class FakeProduct:
        product_name = "Aayush Herbal Masala"
        ingredients = ["Mulethi"]
        key_benefits = ["same ritual, no tobacco"]
        usp = "0% tobacco alternative"
        target_audience = "adult gutka and pan masala chewers trying to switch"

    class FakePayload:
        structured_product = FakeProduct()
        content_type = "video"
        product_category = "herbal_health"

    data = {
        "hook": {"text": "Roz gutka khane ke baad woh 'kuch missing hai' wali feeling."},
        "body": [{"text": "Mulethi jo stress ko manage karne mein support karta hai."}],
        "cta": {"text": "Try Aayush Herbal Masala today."},
    }
    issues = sq.deterministic_issues(data, FakePayload())
    assert "category_overfit" not in issues


# --- product_first_hook -------------------------------------------------


def test_deterministic_issues_flags_product_first_hook():
    class FakeProduct:
        product_name = "Glow Face Serum"
        ingredients = ["Vitamin C"]
        key_benefits = ["brighter skin"]
        usp = "daily glow"
        target_audience = "working women"

    class FakePayload:
        structured_product = FakeProduct()
        content_type = "video"
        product_category = "skincare"

    data = {
        "hook": {"text": "Glow Face Serum is here to change your skincare routine forever."},
        "body": [{"text": "Something happens next."}],
        "cta": {"text": "Try it today."},
    }
    issues = sq.deterministic_issues(data, FakePayload())
    assert "product_first_hook" in issues


def test_deterministic_issues_does_not_flag_product_first_hook_when_product_named_later():
    class FakeProduct:
        product_name = "Glow Face Serum"
        ingredients = ["Vitamin C"]
        key_benefits = ["brighter skin"]
        usp = "daily glow"
        target_audience = "working women"

    class FakePayload:
        structured_product = FakeProduct()
        content_type = "video"
        product_category = "skincare"

    data = {
        "hook": {"text": "Screen time ne meri skin ki chamak cheen li thi."},
        "body": [{"text": "Mili Glow Face Serum, lightweight aur non-greasy."}],
        "cta": {"text": "Try it today."},
    }
    issues = sq.deterministic_issues(data, FakePayload())
    assert "product_first_hook" not in issues


def test_new_issue_codes_have_rewrite_instructions():
    for code in (
        "generic_creative_premise", "slogan_as_hook", "product_first_hook", "missing_turning_point",
        "missing_payoff", "generic_cta", "product_forced_into_story", "reference_dna_mismatch",
    ):
        assert code in sq._ISSUE_INSTRUCTIONS, code
        assert len(sq.rewrite_reason([code])) > 20


# --- Ingredient dumping (§6) -------------------------------------------------


def test_has_ingredient_dump_detects_contains_list_pattern():
    text = "Contains Amlaki, Elderberry, Echinacea and many natural ingredients."
    assert sq._has_ingredient_dump(text, ["Amlaki", "Elderberry", "Echinacea"]) is True


def test_has_ingredient_dump_detects_crammed_given_ingredients():
    text = "It has Amlaki Elderberry Echinacea Zinc all in one tablet for kids."
    assert sq._has_ingredient_dump(text, ["Amlaki", "Elderberry", "Echinacea", "Zinc"]) is True


def test_has_ingredient_dump_false_for_single_ingredient_mentioned_naturally():
    text = "Ashwagandha is the one ingredient she actually recognized from her grandmother's kitchen."
    assert sq._has_ingredient_dump(text, ["Ashwagandha", "Mulethi", "Amla"]) is False


def test_has_ingredient_dump_false_when_fewer_than_three_given_ingredients():
    text = "Contains Amla and Mulethi and a small amount of honey for taste."
    assert sq._has_ingredient_dump(text, ["Amla", "Mulethi"]) is False


def test_deterministic_issues_flags_ingredient_dump_in_full_script():
    class FakeProduct:
        product_name = "Immune Care Tablets"
        ingredients = ["Amlaki", "Elderberry", "Echinacea", "Zinc"]
        key_benefits = ["supports immunity"]
        usp = "daily immunity support"

    class FakePayload:
        structured_product = FakeProduct()
        content_type = "video"

    data = {
        "hook": {"text": "Every Monday she checks one WhatsApp group before the school bag."},
        "body": [{"text": "Contains Amlaki, Elderberry, Echinacea and Zinc for daily support."}],
        "cta": {"text": "Try Immune Care Tablets today."},
    }
    issues = sq.deterministic_issues(data, FakePayload())
    assert "ingredient_dump" in issues


# --- Expanded generic-opener denylist (§2/§5) --------------------------------


def test_banned_phrases_include_mother_specific_generic_openers():
    for phrase in [
        "every mother wants",
        "we all know health is important",
        "your child's health matters",
        "take care of your family",
        "health is wealth",
        "because your health matters",
    ]:
        assert phrase in sq.BANNED_PHRASES


def test_text_issues_flags_generic_language_for_new_phrases():
    issues = sq.text_issues("Every mother wants the best for her child, always.")
    assert "generic_language" in issues


# --- New LLM-eval issue codes are wired end to end ---------------------------


def test_new_issue_codes_have_rewrite_instructions():
    for code in ("competitor_swappable", "interchangeable_beats", "filler_padding", "generic_insight", "ingredient_dump"):
        assert code in sq._ISSUE_INSTRUCTIONS, code


def test_new_issue_codes_are_documented_in_eval_prompt():
    for code in ("competitor_swappable", "interchangeable_beats", "filler_padding", "generic_insight"):
        assert f'"{code}"' in sq._EVAL_SYSTEM_PROMPT, code


def test_rewrite_reason_combines_multiple_new_issues():
    reason = sq.rewrite_reason(["ingredient_dump", "competitor_swappable"])
    assert "ingredient" in reason.lower()
    assert "competing product" in reason.lower() or "compet" in reason.lower()


# --- Existing behavior must still hold (regression) --------------------------


def test_claim_patterns_still_catch_unsupported_claims():
    issues = sq.text_issues("Clinically proven to cure your cold in 2 days.")
    assert "unsupported_claim" in issues


def test_normalize_creative_mechanism_unaffected_by_new_additions():
    assert sq.normalize_creative_mechanism("curiosity") == "curiosity_gap"
    assert sq.normalize_creative_mechanism("totally-unknown-thing") == sq.DEFAULT_MECHANISM
