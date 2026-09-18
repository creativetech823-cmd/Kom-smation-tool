"""generate_situations_with_quality_floor wraps the existing (unmocked-here,
patched-out) generate_situations() with bounded retry — these tests patch
that one function directly rather than mocking the LLM call underneath it,
so no live API calls happen and generate_situations()'s own behavior/tests
are untouched."""

from app.models.product import ScriptLanguage, StorySituation, StorySituationsInput, StorySituationsResult, StructuredProduct
from app.services import story_situation_service as svc


def _payload(exclude=None) -> StorySituationsInput:
    return StorySituationsInput(
        structured_product=StructuredProduct(product_name="Aayush Wellness Herbal Masala", target_audience="adults switching from gutka"),
        product_category="herbal_health",
        count=5,
        exclude_titles=exclude or [],
        script_language=ScriptLanguage.hinglish,
    )


def _situation(title: str) -> StorySituation:
    return StorySituation(
        id="x", title=title, description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="easy", estimated_length="15s", virality_score=5.0,
    )


def test_succeeds_on_first_attempt_when_enough_situations_survive(monkeypatch):
    calls = []

    def fake_generate(payload, deadline=None):
        calls.append(payload)
        return StorySituationsResult(situations=[_situation("A"), _situation("B")])

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=1)
    assert result.quality_floor_met is True
    assert result.attempts_used == 1
    assert len(result.situations) == 2
    assert len(calls) == 1


def test_retries_and_excludes_previously_failed_titles(monkeypatch):
    calls = []

    def fake_generate(payload, deadline=None):
        calls.append(list(payload.exclude_titles))
        if len(calls) < 3:
            return StorySituationsResult(situations=[])  # every candidate drifted/deduped away
        return StorySituationsResult(situations=[_situation("Finally Good")])

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=1, max_attempts=3)
    assert result.quality_floor_met is True
    assert result.attempts_used == 3
    assert len(calls) == 3
    # exclude_titles never shrinks across retries (attempt 1 has none from
    # this run, but never loses what the caller originally passed in)
    assert calls[0] == []


def test_returns_structured_quality_not_met_state_after_bound_exhausted(monkeypatch):
    def fake_generate(payload, deadline=None):
        return StorySituationsResult(situations=[])  # never produces anything usable

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=1, max_attempts=2)
    assert result.quality_floor_met is False
    assert result.attempts_used == 2
    assert result.situations == []
    assert result.dominant_weakness  # a real, non-empty explanation, not silence


def test_never_raises_when_generate_situations_itself_raises(monkeypatch):
    def fake_generate(payload, deadline=None):
        raise ValueError("malformed JSON from model")

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=1, max_attempts=2)
    assert result.quality_floor_met is False
    assert result.situations == []


def test_duplicate_candidate_across_retries_does_not_falsely_satisfy_the_floor(monkeypatch):
    # The model ignores the exclude_titles instruction and returns the exact
    # same (already-insufficient) title again on retry — the wrapper must
    # keep retrying rather than treating attempt 2's identical-to-attempt-1
    # result as if it were newly sufficient just because a retry happened.
    calls = []

    def fake_generate(payload, deadline=None):
        calls.append(payload)
        if len(calls) <= 2:
            return StorySituationsResult(situations=[_situation("Same Stale Idea")])  # below floor of 2, repeated
        return StorySituationsResult(situations=[_situation("Same Stale Idea"), _situation("Genuinely New Idea")])

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=2, max_attempts=3)
    assert result.quality_floor_met is True
    assert result.attempts_used == 3
    assert len(calls) == 3
    # Each retry's exclude_titles keeps accumulating the stale title, even
    # though the model kept ignoring it — the wrapper's own state is correct
    # regardless of whether the model complies.
    assert "Same Stale Idea" in calls[1].exclude_titles
    assert "Same Stale Idea" in calls[2].exclude_titles


def test_no_fail_open_to_known_bad_candidates_when_floor_not_met(monkeypatch):
    # generate_situations() itself already filters out category-drifted/
    # generic candidates before returning — this wrapper must never inflate
    # a below-floor result by falling back to raw/rejected candidates from
    # an earlier attempt. The final situations list is exactly what the
    # LAST attempt's own (already-filtered) result contained, never more.
    def fake_generate(payload, deadline=None):
        # Simulates every candidate this attempt produced failing the
        # deterministic/semantic gates inside generate_situations() itself —
        # it already returns an empty, fully-filtered result, not raw junk.
        return StorySituationsResult(situations=[])

    monkeypatch.setattr(svc, "generate_situations", fake_generate)
    result = svc.generate_situations_with_quality_floor(_payload(), min_situations=1, max_attempts=3)
    assert result.quality_floor_met is False
    assert result.situations == []  # never a fabricated or leaked "known-bad" candidate
    assert result.attempts_used == 3
    assert result.dominant_weakness
