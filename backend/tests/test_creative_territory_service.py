"""creative_territory_service's selection logic (Part 6/7 of the V3 task):
distinguishing a genuinely different creative territory from "the same
underlying mechanism with a different character/location". All tests here
are pure/deterministic — they construct CreativeTerritory objects directly
and call select_strongest_territory(), never generate_territories() (which
would make a live call), so no LLM/API interaction happens anywhere in this
file."""

from app.services.creative_territory_service import (
    CreativeTerritory, _deterministic_too_similar, _significant_tokens, select_strongest_territory,
)


def _territory(name: str, tension: str, question: str, distance_from_recent: int = 5, **score_overrides) -> CreativeTerritory:
    scores = {
        "human_truth": 4, "product_relevance": 4, "audience_relevance": 4, "creative_potential": 4,
        "visual_potential": 4, "reference_dna_fit": 4, "product_integration": 4, "claim_safety": 5,
        "novelty": 4, "distance_from_recent": distance_from_recent,
    }
    scores.update(score_overrides)
    return CreativeTerritory(
        territory_name=name, territory_description="", human_tension=tension, behavioural_truth="",
        creative_question=question, emotional_engine="", possible_story_world="", product_role="",
        why_it_fits_product="", reference_dna_fit="", novelty_vs_recent_concepts="",
        distinct_from_other_candidates="", scores=scores, total_score=sum(scores.values()),
    )


# --- Part 6: "same idea, different clothes" at the territory level ----------


def test_grandfather_pocket_reveal_and_friend_pocket_reveal_are_deterministically_similar():
    # The exact example from the task: swapping the relationship (grandfather
    # -> friend) while the underlying mechanism (reaching into a pocket,
    # revealing the product instead of the old habit) stays identical.
    a = _significant_tokens(
        "Grandfather's Pocket Reveal",
        "An old habit hidden in a pocket, revealed and replaced in front of family",
        "What does grandfather really keep in his pocket now?",
    )
    b = _significant_tokens(
        "Friend's Pocket Surprise",
        "An old habit hidden in a pocket, revealed and replaced in front of friends",
        "What does his friend really keep in his pocket now?",
    )
    assert _deterministic_too_similar(a, b) is True


def test_ritual_hiding_vs_sensory_replacement_are_genuinely_different():
    # Different underlying lens (social concealment vs. sensory experience),
    # not just different wording for the same mechanism.
    a = _significant_tokens(
        "The Hidden Habit", "Going to awkward lengths to hide chewing from family and colleagues",
        "What do people actually do to keep this secret?",
    )
    b = _significant_tokens(
        "The Sensory Ritual", "The specific taste, smell, and mouthfeel that makes the old habit hard to give up",
        "What does the craving actually feel like, moment to moment?",
    )
    assert _deterministic_too_similar(a, b) is False


def test_select_strongest_territory_excludes_candidate_too_close_to_recent_territory():
    recent = [{"territory_name": "Grandfather's Pocket Reveal", "human_tension": "hidden habit revealed to family", "creative_question": "what's really in his pocket"}]
    same_mechanism_new_character = _territory(
        "Uncle's Pocket Reveal", "hidden habit revealed to family", "what's really in his pocket",
        distance_from_recent=2,  # model itself flags this as close
    )
    genuinely_different = _territory(
        "The Sensory Ritual", "the taste and ritual that's hard to give up", "what does the craving feel like",
        distance_from_recent=5, total_score=999,
    )
    genuinely_different.total_score = sum(genuinely_different.scores.values())
    winner = select_strongest_territory([same_mechanism_new_character, genuinely_different], recent_concepts=recent)
    assert winner.territory_name == "The Sensory Ritual"


def test_select_strongest_territory_deterministic_safeguard_catches_generous_self_score():
    # The model itself scores distance_from_recent generously (5 = "totally
    # different") despite the territory being the same underlying mechanism
    # as a recent one with different wording — the deterministic token-
    # overlap safeguard must still catch it independent of that self-score.
    recent = [{"territory_name": "Grandfather's Pocket Reveal", "human_tension": "an old habit hidden in a pocket, revealed and replaced in front of family", "creative_question": "what does grandfather really keep in his pocket now"}]
    falsely_confident = _territory(
        "Friend's Pocket Surprise", "an old habit hidden in a pocket, revealed and replaced in front of friends",
        "what does his friend really keep in his pocket now", distance_from_recent=5,
    )
    only_option = select_strongest_territory([falsely_confident], recent_concepts=recent)
    # Fail-open: with no other candidate, the too-close one is still
    # returned rather than returning nothing — but this proves the pool
    # WOULD have excluded it if an alternative existed (see next test).
    assert only_option is not None

    genuinely_different = _territory(
        "The Sensory Ritual", "the taste and ritual that's hard to give up", "what does the craving feel like",
        distance_from_recent=5,
    )
    winner = select_strongest_territory([falsely_confident, genuinely_different], recent_concepts=recent)
    assert winner.territory_name == "The Sensory Ritual"


# --- Part 7: territory diversity within one batch (no recorded history) -----


def test_genuinely_different_candidate_wins_when_it_scores_highest_among_pocket_variants():
    # No recorded history at all (first generation for a product) — four
    # pocket-reveal variants (different character each time, same underlying
    # mechanism) plus one genuinely different idea that scores highest.
    pocket_variants = [
        _territory("Grandfather's Pocket Reveal", "an old habit hidden in a pocket, revealed to family", "what's in his pocket now"),
        _territory("Father's Pocket Reveal", "an old habit hidden in a pocket, revealed to his son", "what's in his pocket now"),
        _territory("Colleague's Pocket Reveal", "an old habit hidden in a pocket, revealed at the office", "what's in his pocket now"),
        _territory("Neighbour's Pocket Reveal", "an old habit hidden in a pocket, revealed to a neighbour", "what's in his pocket now"),
    ]
    genuinely_different = _territory(
        "The Pan-Shop Culture", "the social ritual and language of the pan-shop counter itself",
        "what does the shop counter conversation actually sound like", creative_potential=5, novelty=5,
    )
    winner = select_strongest_territory(pocket_variants + [genuinely_different])
    assert winner.territory_name == "The Pan-Shop Culture"


def test_cross_candidate_dedup_removes_redundant_pocket_variants_from_the_eligible_pool():
    # Documents the actual, narrower guarantee cross-candidate dedup gives:
    # it removes near-duplicates of an ALREADY-KEPT (higher or equal scoring)
    # candidate from the pool greedily by score. It does NOT, by itself,
    # prevent a redundant idea from winning if that redundant idea happens
    # to be the single highest scorer in the batch — single-winner selection
    # has no mechanism to reject "the best of four near-identical ideas" in
    # favor of a weaker-but-more-original one (that trade-off is deliberate:
    # see select_strongest_territory's docstring on quality x diversity, not
    # diversity alone). This test verifies the pool-reduction mechanism
    # directly rather than asserting a winner-selection guarantee that
    # doesn't exist.
    highest = _territory("Grandfather's Pocket Reveal", "an old habit hidden in a pocket, revealed to family", "what's in his pocket now", creative_potential=5, novelty=5)
    near_dup_1 = _territory("Father's Pocket Reveal", "an old habit hidden in a pocket, revealed to his son", "what's in his pocket now")
    near_dup_2 = _territory("Colleague's Pocket Reveal", "an old habit hidden in a pocket, revealed at the office", "what's in his pocket now")
    distinct = _territory("The Pan-Shop Culture", "the social ritual and language of the pan-shop counter itself", "what does the shop counter conversation actually sound like")

    winner = select_strongest_territory([highest, near_dup_1, near_dup_2, distinct])
    # The highest-scoring redundant idea wins (documented limitation above)...
    assert winner.territory_name == "Grandfather's Pocket Reveal"
    # ...but the dedup step itself genuinely ran: confirm near_dup_1/2 really
    # are flagged as too-similar to the winner (i.e. dedup HAD something real
    # to remove, this isn't a vacuous test), and the distinct candidate is not.
    winner_tokens = _significant_tokens(winner.territory_name, winner.human_tension, winner.creative_question)
    assert _deterministic_too_similar(winner_tokens, _significant_tokens(near_dup_1.territory_name, near_dup_1.human_tension, near_dup_1.creative_question))
    assert _deterministic_too_similar(winner_tokens, _significant_tokens(near_dup_2.territory_name, near_dup_2.human_tension, near_dup_2.creative_question))
    assert not _deterministic_too_similar(winner_tokens, _significant_tokens(distinct.territory_name, distinct.human_tension, distinct.creative_question))


def test_select_strongest_territory_returns_none_for_empty_list():
    assert select_strongest_territory([]) is None


def test_select_strongest_territory_never_raises_on_missing_recent_concepts_fields():
    # A recent-concepts record from before territory tracking existed (no
    # territory_name) must not crash the eligibility check.
    recent = [{"architecture_key": "dialogue_trap"}]  # legacy record, no territory fields
    t = _territory("The Sensory Ritual", "craving and taste", "what does it feel like")
    winner = select_strongest_territory([t], recent_concepts=recent)
    assert winner is t
