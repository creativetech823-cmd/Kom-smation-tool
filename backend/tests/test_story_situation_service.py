"""Phase 2B — tests for product-grounded story-situation ("Choose Your
Story") generation. Regression coverage for the exact reported failure:
Herbal Masala cards like "Chef ka Secret Ingredient" and "Corporate Stress,
Healthy Meals" positioning the product as a cooking ingredient."""

import json
from unittest.mock import patch

import pytest

from app.config import settings
from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import openrouter_utils, story_situation_service as svc
from app.services.product_context_service import build_product_creative_contract


@pytest.fixture(autouse=True)
def block_all_live_openrouter_calls():
    """Hard safety net: semantic_story_judge_service.py has its OWN
    generate_text binding, separate from story_situation_service.py's —
    patching one does not patch the other. A test that only mocks
    svc.generate_text and forgets this will otherwise make a real,
    unintended live call the moment a role-risk product reaches the
    semantic-judge stage. Fail loudly instead."""
    def _forbidden(*args, **kwargs):
        raise AssertionError("A real OpenRouter HTTP call was attempted in a test that must stay fully offline.")

    with patch.object(openrouter_utils, "get_openrouter_client", side_effect=_forbidden):
        yield


@pytest.fixture(autouse=True)
def default_semantic_judge_unavailable():
    """By default, every test in this file runs with the semantic judge
    reporting "unavailable" (None) — the safe, documented fallback path,
    which keeps every pre-existing Phase 2B test's deterministic-only
    expectations valid unchanged. Tests that specifically exercise the
    semantic judge override this patch within their own body."""
    with patch("app.services.story_situation_service.judge_story_situations", return_value=None):
        yield

HERBAL_MASALA = StructuredProduct(
    product_name="Aayush Herbal Masala",
    target_audience="adult gutka and pan masala chewers, 20s-40s, trying to switch away from tobacco",
    ingredients=["Mulethi", "Amla"], usp="a 0% tobacco, 0% supari herbal chew",
    key_benefits=["same chewing ritual and taste"],
)
IMMUNE_CARE = StructuredProduct(
    product_name="AayushWellness Immune Care Tablets",
    target_audience="mothers of school-age children", ingredients=["Amla", "Giloy"],
    usp="a simple daily chewable immunity tablet", key_benefits=["kids take it without a fight"],
)

# The exact reported failure cards (Phase 2B report), used verbatim as regression input.
DRIFTED_CARDS = [
    {
        "title": "Chef ka Secret Ingredient", "description": "A chef adds Aayush Herbal Masala as a cooking seasoning to his signature curry.",
        "emotion": "pride", "persona": "chef", "marketing_angle": "expert authority", "category": "Educational",
        "difficulty": "medium", "estimated_length": "30s", "virality_score": 6.0, "recommended_angles": [],
    },
    {
        "title": "Corporate Stress, Healthy Meals", "description": "A stressed office worker mixes Aayush Herbal Masala into her healthy home-cooked dinner.",
        "emotion": "relief", "persona": "office worker", "marketing_angle": "everyday wellness", "category": "Lifestyle",
        "difficulty": "easy", "estimated_length": "30s", "virality_score": 5.5, "recommended_angles": [],
    },
]
CLEAN_CARDS = [
    {
        "title": "The Automatic Reach", "description": "A man instinctively reaches for the pocket where his old gutka packet used to be, and finds something new there instead.",
        "emotion": "surprise", "persona": "gutka user trying to switch", "marketing_angle": "habit replacement", "category": "Emotional",
        "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    },
    {
        "title": "Friend Notices the Change", "description": "A friend notices someone has quietly changed their usual chewing routine and asks about it.",
        "emotion": "curiosity", "persona": "peer/friend", "marketing_angle": "social proof", "category": "Social",
        "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.5, "recommended_angles": [],
    },
]


def _payload(product, category, count=4):
    return StorySituationsInput(structured_product=product, product_category=category, count=count, script_language=ScriptLanguage.hinglish)


# --- Contract grounding is actually threaded into the prompt ----------------


def test_system_prompt_instructs_product_truth_before_creative_freedom():
    prompt = svc._system_prompt(ScriptLanguage.hinglish)
    assert "PRODUCT CREATIVE CONTRACT" in prompt
    assert "ambiguous word" in prompt.lower()
    assert "PRODUCT TRUTH" in prompt


def test_user_message_includes_contract_block():
    msg = svc._build_user_message(_payload(HERBAL_MASALA, "herbal_health"), "PRODUCT CREATIVE CONTRACT MARKER TEXT", 4)
    assert "PRODUCT CREATIVE CONTRACT MARKER TEXT" in msg


def test_generate_situations_uses_creative_model():
    payload_json = json.dumps({"situations": []})
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return payload_json

    with patch.object(svc, "generate_text", side_effect=fake):
        svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health"))
    assert captured["model"] == settings.creative_model


# --- Regression: exact reported drifted cards are filtered -------------------


def test_drifted_herbal_masala_cards_are_filtered_out():
    response = json.dumps({"situations": DRIFTED_CARDS + CLEAN_CARDS})
    with patch.object(svc, "generate_text", return_value=response):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=4))
    titles = [s.title for s in result.situations]
    assert "Chef ka Secret Ingredient" not in titles
    assert "Corporate Stress, Healthy Meals" not in titles
    assert "The Automatic Reach" in titles
    assert "Friend Notices the Change" in titles


def test_request_count_is_padded_when_product_has_role_risk():
    response = json.dumps({"situations": CLEAN_CARDS})
    captured = {}

    def fake(**kwargs):
        captured["user_message"] = kwargs["contents"][0]
        return response

    with patch.object(svc, "generate_text", side_effect=fake):
        svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=4))
    assert f"Generate exactly {4 + svc._DRIFT_FILTER_BUFFER} story situations" in captured["user_message"]


def test_returns_fewer_or_zero_cards_rather_than_falling_back_to_unfiltered_when_everything_drifted():
    """Phase 2C correction: unlike territory/premise selection (which must
    pick something to let an internal pipeline stage proceed), a user-facing
    story card is safer shown as "fewer/zero" than "confirmed wrong" — the
    old fail-open-to-unfiltered behavior would have silently defeated the
    filter in exactly the case that matters most."""
    all_drifted = json.dumps({"situations": DRIFTED_CARDS})
    with patch.object(svc, "generate_text", return_value=all_drifted):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=2))
    assert result.situations == []
    titles = [s.title for s in result.situations]
    for drifted in DRIFTED_CARDS:
        assert drifted["title"] not in titles


# --- Positive regression cases: legitimate settings must survive -----------


def test_legitimate_situations_with_family_or_social_setting_are_not_flagged():
    positive_examples = [
        {
            "title": "A", "description": "A person instinctively reaches for their old gutka packet, out of habit, during a family dinner.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        },
        {
            "title": "B", "description": "A humorous confrontation between two old friends about one of them quietly giving up their old chewing habit.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        },
        {
            "title": "C", "description": "A visual metaphor shows an old habit fading away and being replaced by something new, at a festival gathering.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        },
    ]
    response = json.dumps({"situations": positive_examples})
    with patch.object(svc, "generate_text", return_value=response):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=3))
    assert len(result.situations) == 3  # none of these legitimate cards were filtered


# --- Other products must not be affected (no overcorrection) ---------------


# --- Phase 2C regression: the second reported round of drifted screenshots -


PHASE_2C_DRIFTED_CARDS = [
    {
        "title": "Chef ka Secret Ingredient", "description": "A chef uses Aayush Herbal Masala in his signature dishes.",
        "emotion": "e", "persona": "chef", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.5, "recommended_angles": [],
    },
    {
        "title": "Meri Daadi Maa ka Naya Secret", "description": "Grandmother adds Aayush Herbal Masala into the family's dinner for extra flavor.",
        "emotion": "e", "persona": "grandmother", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 8.3, "recommended_angles": [],
    },
    {
        "title": "Food Blogger ka Next Trend", "description": "A food blogger features Aayush Herbal Masala as a recipe ingredient in her next cooking video.",
        "emotion": "e", "persona": "food blogger", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 9.1, "recommended_angles": [],
    },
    {
        "title": "Fitness Enthusiast ka Secret Weapon", "description": "A gym-goer uses Aayush Herbal Masala as an energy supplement to fuel his workout.",
        "emotion": "e", "persona": "fitness enthusiast", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.8, "recommended_angles": [],
    },
    {
        "title": "Party Host ka Healthy Twist", "description": "A party host mixes Aayush Herbal Masala into the snacks she serves her guests.",
        "emotion": "e", "persona": "party host", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 6.9, "recommended_angles": [],
    },
]

PHASE_2C_POSITIVE_CARDS = [
    {
        "title": "Office Colleague Notices", "description": "In office mein stress ke time Rahul automatically purani gutka pouch ke liye haath badhata hai. Uski colleague use Aayush Herbal Masala offer karti hai.",
        "emotion": "e", "persona": "office colleague", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    },
    {
        "title": "Father-Son Generational Shift", "description": "Ek pita jo saalon se gutka khaate hain, unka beta unhe Aayush Herbal Masala try karne ka challenge deta hai.",
        "emotion": "e", "persona": "father", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 8.0, "recommended_angles": [],
    },
    {
        "title": "Shopkeeper's Wisdom", "description": "An old shopkeeper who has sold gutka for years recommends Aayush Herbal Masala to a skeptical customer.",
        "emotion": "e", "persona": "shopkeeper", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.2, "recommended_angles": [],
    },
    {
        "title": "Travel Companion", "description": "A traveler reaches for his old packet during a stressful train journey, but a co-passenger offers Aayush Herbal Masala instead.",
        "emotion": "e", "persona": "traveler", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 6.8, "recommended_angles": [],
    },
]


def test_phase_2c_drifted_cards_are_all_filtered_out():
    response = json.dumps({"situations": PHASE_2C_DRIFTED_CARDS + PHASE_2C_POSITIVE_CARDS})
    with patch.object(svc, "generate_text", return_value=response):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=9))
    titles = [s.title for s in result.situations]
    for drifted in PHASE_2C_DRIFTED_CARDS:
        assert drifted["title"] not in titles, f"{drifted['title']} should have been filtered"
    for positive in PHASE_2C_POSITIVE_CARDS:
        assert positive["title"] in titles, f"{positive['title']} should NOT have been filtered"


def test_phase_2c_high_score_does_not_rescue_a_drifted_card():
    """Section 7: a beautifully-scored but fundamentally wrong concept must
    still be rejected outright — score is never a substitute for role
    alignment. The 9.1-scored food-blogger card must not survive filtering."""
    response = json.dumps({"situations": PHASE_2C_DRIFTED_CARDS})
    with patch.object(svc, "generate_text", return_value=response):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=5))
    high_score_titles = [s.title for s in result.situations if s.virality_score >= 9.0]
    assert "Food Blogger ka Next Trend" not in high_score_titles
    assert not any(s.title == "Food Blogger ka Next Trend" for s in result.situations)


def test_fitness_nutrition_role_detector_directly():
    from app.services.product_context_validator import detect_category_drift_signal

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        usp="a 0% tobacco, 0% supari herbal chew",
    )
    assert detect_category_drift_signal(
        "A gym-goer uses it as a pre-workout energy supplement to fuel his training.", contract,
    )
    assert detect_category_drift_signal(
        "He takes it before the gym because it boosts his energy for the workout.", contract,
    )


def test_fitness_context_alone_without_product_role_is_not_flagged():
    """A fitness ENTHUSIAST as a character is fine — only the product being
    given a fitness/energy ROLE is the actual drift."""
    from app.services.product_context_validator import detect_category_drift_signal

    contract = build_product_creative_contract(
        product_name="Aayush Herbal Masala", category="herbal_health",
        target_audience="adult gutka and pan masala chewers trying to switch away from tobacco",
        usp="a 0% tobacco, 0% supari herbal chew",
    )
    text = "A fitness enthusiast who used to chew gutka before every gym session now reaches for Aayush Herbal Masala instead."
    assert detect_category_drift_signal(text, contract) == ""


def test_immune_care_unaffected_no_padding_no_filtering_call():
    response = json.dumps({"situations": [
        {
            "title": "Kitchen Chaos", "description": "A mother in her kitchen juggling immunity routines while cooking breakfast for her kids.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        },
    ]})
    captured = {}

    def fake(**kwargs):
        captured["user_message"] = kwargs["contents"][0]
        return response

    with patch.object(svc, "generate_text", side_effect=fake):
        result = svc.generate_situations(_payload(IMMUNE_CARE, "nutraceuticals", count=1))
    # No buffer padding for a product with no role_risk_keys.
    assert "Generate exactly 1 story situations" in captured["user_message"]
    # A kitchen/cooking-adjacent card is fine for THIS product — it's never even checked.
    assert len(result.situations) == 1
    assert result.situations[0].title == "Kitchen Chaos"


def test_immune_care_never_calls_the_semantic_judge():
    """A product with no role_risk_keys must never pay for the semantic
    judge call — same cost-control gate as the deterministic check."""
    response = json.dumps({"situations": [
        {
            "title": "Breakfast Routine", "description": "A mother gives her kids their daily immunity tablet with breakfast.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        },
    ]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch.object(svc, "judge_story_situations") as mock_judge:
        result = svc.generate_situations(_payload(IMMUNE_CARE, "nutraceuticals", count=1))
    mock_judge.assert_not_called()
    assert len(result.situations) == 1


# --- Phase 3: Semantic Story Judge integration ------------------------------


def test_subtle_semantic_drift_with_no_keyword_is_caught_by_the_judge():
    """The exact case deterministic regex cannot catch: no food/fitness
    keyword at all, but the product's role has silently become a generic
    wellness/routine item instead of a gutka/tobacco alternative."""
    subtle_drift_card = {
        "title": "Morning Ritual Refresh", "description": "A man gets ready for his morning routine and chooses this before heading out for the day, feeling refreshed and prepared.",
        "emotion": "e", "persona": "young professional", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    }
    clean_card = {
        "title": "The Automatic Reach", "description": "A man instinctively reaches for the pocket where his old gutka packet used to be.",
        "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    }
    # Deterministic layer would NOT catch the subtle card (no food/fitness
    # keyword) — confirmed directly before asserting the judge catches it.
    from app.services.product_context_validator import detect_category_drift_signal
    contract = build_product_creative_contract(
        product_name=HERBAL_MASALA.product_name, category="herbal_health",
        target_audience=HERBAL_MASALA.target_audience, usp=HERBAL_MASALA.usp,
    )
    assert detect_category_drift_signal(svc._situation_text(subtle_drift_card), contract) == ""

    response = json.dumps({"situations": [subtle_drift_card, clean_card]})
    judge_response = [
        sj_module()._parse_judgment({
            "candidate_index": 0, "semantic_category_drift": True,
            "reason": "positions the product as a generic morning-routine wellness item, not a gutka alternative",
            "product_role_alignment": 0.2, "cluster_id": "a",
        }),
        sj_module()._parse_judgment({
            "candidate_index": 1, "semantic_category_drift": False,
            "product_role_alignment": 0.9, "creative_potential": 0.8, "cluster_id": "b",
        }),
    ]
    with patch.object(svc, "generate_text", return_value=response), \
         patch("app.services.story_situation_service.judge_story_situations", return_value=judge_response):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=2))
    titles = [s.title for s in result.situations]
    assert "Morning Ritual Refresh" not in titles
    assert "The Automatic Reach" in titles


def sj_module():
    from app.services import semantic_story_judge_service
    return semantic_story_judge_service


def test_semantic_duplicates_are_deduplicated_end_to_end():
    cards = [
        {"title": "Friend Notices", "description": "A", "emotion": "e", "persona": "p", "marketing_angle": "m",
         "category": "c", "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.0, "recommended_angles": []},
        {"title": "Friend Asks Why", "description": "B", "emotion": "e", "persona": "p", "marketing_angle": "m",
         "category": "c", "difficulty": "easy", "estimated_length": "30s", "virality_score": 8.0, "recommended_angles": []},
        {"title": "Shopkeeper Story", "description": "C", "emotion": "e", "persona": "p", "marketing_angle": "m",
         "category": "c", "difficulty": "easy", "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": []},
    ]
    sj = sj_module()
    judgments = [
        sj._parse_judgment({"candidate_index": 0, "semantic_category_drift": False, "product_role_alignment": 0.9, "creative_potential": 0.5, "cluster_id": "friend_notices_habit_change"}),
        sj._parse_judgment({"candidate_index": 1, "semantic_category_drift": False, "product_role_alignment": 0.9, "creative_potential": 0.8, "cluster_id": "friend_notices_habit_change"}),
        sj._parse_judgment({"candidate_index": 2, "semantic_category_drift": False, "product_role_alignment": 0.9, "creative_potential": 0.6, "cluster_id": "shopkeeper_trust"}),
    ]
    response = json.dumps({"situations": cards})
    with patch.object(svc, "generate_text", return_value=response), \
         patch("app.services.story_situation_service.judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=3))
    titles = [s.title for s in result.situations]
    # Same cluster -> only the higher creative_potential one survives.
    assert "Friend Asks Why" in titles
    assert "Friend Notices" not in titles
    assert "Shopkeeper Story" in titles


def test_judge_failure_never_reintroduces_a_deterministically_rejected_candidate():
    """The 'no fail-open' guarantee: when the semantic judge is unavailable,
    the fallback is the deterministic-verified state — never the raw,
    unfiltered candidates. A deterministically-rejected candidate must never
    reappear just because the judge call failed."""
    cooking_card = {
        "title": "Chef ka Secret Ingredient", "description": "A chef uses Aayush Herbal Masala as a cooking seasoning in his dishes.",
        "emotion": "e", "persona": "chef", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    }
    clean_card = {
        "title": "The Automatic Reach", "description": "A man reaches for the pocket where his old gutka packet used to be.",
        "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
    }
    response = json.dumps({"situations": [cooking_card, clean_card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch("app.services.story_situation_service.judge_story_situations", return_value=None):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=2))
    titles = [s.title for s in result.situations]
    assert "Chef ka Secret Ingredient" not in titles  # deterministic rejection survives judge unavailability
    assert "The Automatic Reach" in titles


def test_generic_but_product_correct_candidate_is_kept_not_rejected():
    """Genericness is a SCORE, not a rejection reason — the judge must not
    become another form of over-filtering conventional-but-correct ideas."""
    generic_card = {
        "title": "Switching to a Better Option", "description": "A person uses Aayush Herbal Masala instead of gutka.",
        "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
        "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
    }
    sj = sj_module()
    judgments = [sj._parse_judgment({
        "candidate_index": 0, "semantic_category_drift": False, "product_role_alignment": 0.85,
        "creative_potential": 0.2, "genericness_risk": 0.9, "cluster_id": "a",
    })]
    response = json.dumps({"situations": [generic_card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch("app.services.story_situation_service.judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=1))
    assert len(result.situations) == 1
    assert result.situations[0].title == "Switching to a Better Option"


def test_strong_product_correct_creative_candidate_is_kept():
    strong_card = {
        "title": "The Silent Nod", "description": "A shopkeeper who sold him gutka for years silently slides over Aayush Herbal Masala instead — no words needed.",
        "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "medium",
        "estimated_length": "30s", "virality_score": 8.5, "recommended_angles": [],
    }
    sj = sj_module()
    judgments = [sj._parse_judgment({
        "candidate_index": 0, "semantic_category_drift": False, "product_role_alignment": 0.95,
        "creative_potential": 0.9, "memorability": 0.9, "genericness_risk": 0.1, "cluster_id": "a",
    })]
    response = json.dumps({"situations": [strong_card]})
    with patch.object(svc, "generate_text", return_value=response), \
         patch("app.services.story_situation_service.judge_story_situations", return_value=judgments):
        result = svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=1))
    assert result.situations[0].title == "The Silent Nod"


def test_contract_is_built_fresh_and_reaches_both_generation_and_judge():
    captured_gen = {}
    captured_judge = {}

    def fake_gen(**kwargs):
        captured_gen["user_message"] = kwargs["contents"][0]
        # Deterministically clean (no food/fitness keyword) so this reaches
        # the semantic judge stage rather than being dropped before it.
        return json.dumps({"situations": [{
            "title": "The Automatic Reach", "description": "A man reaches for the pocket where his old gutka packet used to be.",
            "emotion": "e", "persona": "p", "marketing_angle": "m", "category": "c", "difficulty": "easy",
            "estimated_length": "30s", "virality_score": 5.0, "recommended_angles": [],
        }]})

    def fake_judge(contract, candidates, *args, **kwargs):
        captured_judge["contract"] = contract
        return []

    with patch.object(svc, "generate_text", side_effect=fake_gen), \
         patch("app.services.story_situation_service.judge_story_situations", side_effect=fake_judge):
        svc.generate_situations(_payload(HERBAL_MASALA, "herbal_health", count=1))
    assert "gutka" in captured_gen["user_message"].lower()
    assert captured_judge["contract"].role_risk_keys  # the same contract-building path reached the judge


def test_choose_your_story_api_response_contract_unchanged():
    """StorySituation must not gain new fields from Phase 3 — internal
    scoring stays internal, per the explicit 'do not change the UI
    unnecessarily' instruction."""
    from app.models.product import StorySituation

    expected_fields = {
        "id", "title", "description", "emotion", "persona", "marketing_angle",
        "category", "difficulty", "estimated_length", "virality_score", "recommended_angles",
    }
    assert set(StorySituation.model_fields.keys()) == expected_fields
