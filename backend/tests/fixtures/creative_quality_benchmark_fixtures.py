"""Phase 3 Part F — a small, deterministic benchmark fixture set. Each entry
pairs a story-situation candidate with the EXPECTED judgment a correct
semantic judge would produce for it — used to mock the LLM response in
regression tests, never to make a live call. expected_* fields are what the
test asserts against; mocked_judgment is what gets fed back as the "model
response" so evaluate_candidates()'s downstream logic (decision policy,
dedup, aggregate metrics) is exercised realistically end to end.
"""

HERBAL_MASALA_FIXTURES = [
    # --- correct, varied situations -----------------------------------
    {
        "id": "hm_01", "candidate": {
            "title": "The Automatic Reach", "description": "A man instinctively reaches for the pocket where his old gutka packet used to be, and finds Aayush Herbal Masala there instead.",
            "emotion": "surprise", "persona": "gutka user switching", "marketing_angle": "habit replacement",
            "category": "Emotional", "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.5, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.95, "audience_alignment": 0.9,
                             "behavior_alignment": 0.9, "product_role_alignment": 0.95, "creative_potential": 0.85,
                             "memorability": 0.8, "visual_potential": 0.85, "genericness_risk": 0.15, "claim_safety": 1.0, "cluster_id": "auto_reach"},
    },
    {
        "id": "hm_02", "candidate": {
            "title": "Friend Notices the Change", "description": "A friend notices someone has quietly changed their usual chewing routine and asks about it at a chai stall.",
            "emotion": "curiosity", "persona": "peer", "marketing_angle": "social proof", "category": "Social",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.5, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.9, "audience_alignment": 0.85,
                             "behavior_alignment": 0.85, "product_role_alignment": 0.9, "creative_potential": 0.6,
                             "memorability": 0.55, "visual_potential": 0.6, "genericness_risk": 0.45, "claim_safety": 1.0, "cluster_id": "friend_notices"},
    },
    {
        "id": "hm_03", "candidate": {
            "title": "Road Trip Ka Saathi", "description": "A driver on a long road trip reaches for his old gutka habit to stay awake; a co-passenger offers Aayush Herbal Masala instead.",
            "emotion": "relief", "persona": "traveler", "marketing_angle": "safer alternative", "category": "Travel",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.2, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.9, "audience_alignment": 0.85,
                             "behavior_alignment": 0.9, "product_role_alignment": 0.9, "creative_potential": 0.75,
                             "memorability": 0.7, "visual_potential": 0.75, "genericness_risk": 0.25, "claim_safety": 1.0, "cluster_id": "travel_companion"},
    },
    {
        "id": "hm_04", "candidate": {
            "title": "Corporate Break Mein", "description": "A stressed office worker heading out for a gutka break sees his family's photo on his desk and reaches for Aayush Herbal Masala instead.",
            "emotion": "peace", "persona": "office worker", "marketing_angle": "family motivation", "category": "Workplace",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.9, "audience_alignment": 0.85,
                             "behavior_alignment": 0.85, "product_role_alignment": 0.9, "creative_potential": 0.6,
                             "memorability": 0.6, "visual_potential": 0.6, "genericness_risk": 0.4, "claim_safety": 1.0, "cluster_id": "workplace_family"},
    },
    {
        "id": "hm_05", "candidate": {
            "title": "Shopkeeper's Wisdom", "description": "An old paan shop owner who has sold gutka for decades recommends Aayush Herbal Masala to a skeptical regular customer.",
            "emotion": "trust", "persona": "shopkeeper", "marketing_angle": "expert endorsement", "category": "Community",
            "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.8, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.92, "audience_alignment": 0.9,
                             "behavior_alignment": 0.9, "product_role_alignment": 0.92, "creative_potential": 0.8,
                             "memorability": 0.75, "visual_potential": 0.7, "genericness_risk": 0.2, "claim_safety": 1.0, "cluster_id": "shopkeeper_wisdom"},
    },
    {
        "id": "hm_06", "candidate": {
            "title": "Wedding Ki Tension", "description": "A groom's best friend reaches for pan masala amid wedding stress; the groom hands him Aayush Herbal Masala with a joke about the big day.",
            "emotion": "humor", "persona": "wedding party", "marketing_angle": "humor", "category": "Social",
            "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.9, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high",
        "mocked_judgment": {"semantic_category_drift": False, "product_truth_alignment": 0.9, "audience_alignment": 0.88,
                             "behavior_alignment": 0.88, "product_role_alignment": 0.9, "creative_potential": 0.82,
                             "memorability": 0.78, "visual_potential": 0.75, "genericness_risk": 0.2, "claim_safety": 1.0, "cluster_id": "wedding_humor"},
    },
    # --- incorrect: deterministic-catchable drift ----------------------
    {
        "id": "hm_07", "candidate": {
            "title": "Chef ka Secret Ingredient", "description": "A chef adds Aayush Herbal Masala as a cooking seasoning to his signature dish.",
            "emotion": "pride", "persona": "chef", "marketing_angle": "expert authority", "category": "Educational",
            "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.5, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "n/a", "expected_behavior_alignment": "low",
        "mocked_judgment": None,  # caught deterministically — never reaches the judge
    },
    {
        "id": "hm_08", "candidate": {
            "title": "Meri Daadi Maa ka Naya Secret", "description": "Grandmother adds Aayush Herbal Masala into the family's dinner for extra flavor.",
            "emotion": "warmth", "persona": "grandmother", "marketing_angle": "tradition", "category": "Familial",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 8.3, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "n/a", "expected_behavior_alignment": "low",
        "mocked_judgment": None,
    },
    {
        "id": "hm_09", "candidate": {
            "title": "Fitness Enthusiast ka Secret Weapon", "description": "A gym-goer uses Aayush Herbal Masala as an energy supplement to fuel his workout.",
            "emotion": "energy", "persona": "fitness enthusiast", "marketing_angle": "performance", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.8, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "n/a", "expected_behavior_alignment": "low",
        "mocked_judgment": None,
    },
    {
        "id": "hm_10", "candidate": {
            "title": "Party Host ka Healthy Twist", "description": "A party host mixes Aayush Herbal Masala into the snacks she serves her guests.",
            "emotion": "hospitality", "persona": "party host", "marketing_angle": "healthy hosting", "category": "Social",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.9, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "n/a", "expected_behavior_alignment": "low",
        "mocked_judgment": None,
    },
    # --- incorrect: subtle drift only the semantic judge should catch --
    {
        "id": "hm_11", "candidate": {
            "title": "Morning Ritual Refresh", "description": "A man gets ready for his morning routine and chooses this before heading out for the day, feeling refreshed and prepared.",
            "emotion": "freshness", "persona": "young professional", "marketing_angle": "daily ritual", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "high", "expected_behavior_alignment": "low",
        "mocked_judgment": {"semantic_category_drift": True, "reason": "generic morning-routine wellness item, not a gutka alternative",
                             "product_truth_alignment": 0.3, "audience_alignment": 0.4, "behavior_alignment": 0.2,
                             "product_role_alignment": 0.2, "creative_potential": 0.3, "memorability": 0.3,
                             "visual_potential": 0.3, "genericness_risk": 0.85, "claim_safety": 1.0, "cluster_id": "morning_refresh"},
    },
    {
        "id": "hm_12", "candidate": {
            "title": "Ghar Ki Khushi", "description": "A family gathers for a warm evening together, enjoying good health and happiness with Aayush Herbal Masala as part of their wellness routine.",
            "emotion": "warmth", "persona": "family", "marketing_angle": "family wellness", "category": "Familial",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.0, "recommended_angles": [],
        },
        "expected_product_alignment": "low", "expected_category_drift": True,
        "expected_genericness_risk_band": "high", "expected_behavior_alignment": "low",
        "mocked_judgment": {"semantic_category_drift": True, "reason": "generic family wellness with no connection to the actual gutka/tobacco-switching behavior",
                             "product_truth_alignment": 0.3, "audience_alignment": 0.3, "behavior_alignment": 0.15,
                             "product_role_alignment": 0.25, "creative_potential": 0.2, "memorability": 0.2,
                             "visual_potential": 0.25, "genericness_risk": 0.9, "claim_safety": 1.0, "cluster_id": "generic_family_wellness"},
    },
]

IMMUNE_CARE_FIXTURES = [
    {
        "id": "ic_01", "candidate": {
            "title": "Breakfast Battle Se Bachao", "description": "A busy mother struggles to get her kids to take their immunity tablet during the morning breakfast rush.",
            "emotion": "relief", "persona": "mother", "marketing_angle": "everyday wellness", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.5, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high",
        "mocked_judgment": None,  # Immune Care carries no role_risk_keys — never reaches the judge
    },
    {
        "id": "ic_02", "candidate": {
            "title": "School Trip Worry Khatam", "description": "A mother anxious about her child's health on an upcoming school trip finds peace of mind with a simple daily immunity routine.",
            "emotion": "peace", "persona": "mother", "marketing_angle": "seasonal wellness", "category": "Emotional",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "ic_03", "candidate": {
            "title": "Grandma Ki Nuskhe Modern Twist", "description": "A grandmother's complicated home remedies for immunity contrasted with a simple daily chewable tablet her grandchild actually enjoys.",
            "emotion": "nostalgia", "persona": "grandmother/grandchild", "marketing_angle": "tradition vs convenience", "category": "Familial",
            "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.5, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "ic_04", "candidate": {
            "title": "Playtime Pe No Compromise", "description": "A child refuses a bitter homemade immunity remedy before playtime, but happily takes the tasty chewable tablet instead.",
            "emotion": "joy", "persona": "child/mother", "marketing_angle": "kid-friendly", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.8, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "ic_05", "candidate": {
            "title": "Seasonal Switch Routine", "description": "As the seasons change, a mother builds a simple new daily immunity habit for her family instead of scrambling when someone falls sick.",
            "emotion": "confidence", "persona": "mother", "marketing_angle": "preventive routine", "category": "Educational",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.2, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
]

BEARD_OIL_FIXTURES = [
    {
        "id": "bo_01", "candidate": {
            "title": "Date Night Confidence", "description": "A college student self-conscious about his patchy beard gains confidence for a date after weeks of using a daily beard oil routine.",
            "emotion": "confidence", "persona": "college student", "marketing_angle": "confidence transformation", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 7.0, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "bo_02", "candidate": {
            "title": "Friends Ki Taunt, Ab Nahi", "description": "A young man's friends playfully tease him about his patchy beard; he starts a grooming routine to fill it in.",
            "emotion": "humor", "persona": "young man", "marketing_angle": "peer social proof", "category": "Social",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.5, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "bo_03", "candidate": {
            "title": "First Job Interview Jitters", "description": "A nervous young man wants a mature, professional look for his first job interview but his patchy beard undermines his confidence.",
            "emotion": "anxiety", "persona": "job seeker", "marketing_angle": "professional appearance", "category": "Emotional",
            "difficulty": "medium", "estimated_length": "30s", "virality_score": 7.2, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "low", "expected_behavior_alignment": "high", "mocked_judgment": None,
    },
    {
        "id": "bo_04", "candidate": {
            "title": "Morning Routine Ka Secret", "description": "A college student seamlessly includes a beard oil routine into his morning grooming habits, showing the simple daily steps.",
            "emotion": "routine", "persona": "college student", "marketing_angle": "daily habit", "category": "Lifestyle",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 6.0, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "high", "expected_behavior_alignment": "medium", "mocked_judgment": None,
    },
    {
        "id": "bo_05_unsupported_claim", "candidate": {
            "title": "Full Beard in 7 Days", "description": "A young man with a completely patchy beard uses the oil and has a full, thick beard in just 7 days, guaranteed.",
            "emotion": "amazement", "persona": "young man", "marketing_angle": "dramatic transformation", "category": "Sales",
            "difficulty": "easy", "estimated_length": "30s", "virality_score": 8.0, "recommended_angles": [],
        },
        "expected_product_alignment": "high", "expected_category_drift": False,
        "expected_genericness_risk_band": "medium", "expected_behavior_alignment": "medium",
        "mocked_judgment": None,  # flagged by claim-safety checks elsewhere in the pipeline (unsupported timeline/guarantee), not category drift
        "expected_claim_safety_flag": True,
    },
]

ALL_FIXTURES = {
    "Herbal Masala": HERBAL_MASALA_FIXTURES,
    "Immune Care": IMMUNE_CARE_FIXTURES,
    "Beard Oil": BEARD_OIL_FIXTURES,
}
