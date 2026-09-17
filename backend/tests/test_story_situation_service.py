"""Phase 2B — tests for product-grounded story-situation ("Choose Your
Story") generation. Regression coverage for the exact reported failure:
Herbal Masala cards like "Chef ka Secret Ingredient" and "Corporate Stress,
Healthy Meals" positioning the product as a cooking ingredient."""

import json
from unittest.mock import patch

from app.config import settings
from app.models.product import ScriptLanguage, StorySituationsInput, StructuredProduct
from app.services import story_situation_service as svc
from app.services.product_context_service import build_product_creative_contract

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
