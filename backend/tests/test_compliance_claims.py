"""Layer 1 (deterministic) tests — pure regex, no network calls.

Covers the false-positive suite (creative taglines that must NOT be flagged)
and the real-violation suite (guaranteed/medical/quantified/authority claims
that must always be caught) from the Compliance V2 spec.
"""

from app.services.compliance_claims import find_deterministic_violations

# --- False positives: ordinary creative/marketing language must not trip
# the deterministic layer just because it contains an adjacent word. ---
CREATIVE_LINES = [
    "New strength, new finish line.",
    "Show up stronger for the moments that matter.",
    "Your everyday wellness, your way.",
    "Make room for better habits.",
    "Feel ready for your day.",
    "Own your routine.",
    "Find your everyday glow.",
    "Built for an active lifestyle.",
    "Start your stronger routine.",
    "Your next chapter starts here.",
    "New energy for your everyday.",
    "Feel stronger every day.",
    "Everyone thinks I gave up running. The truth? I changed my routine.",
]


def test_creative_taglines_produce_no_deterministic_findings():
    for line in CREATIVE_LINES:
        findings = find_deterministic_violations(line)
        assert findings == [], f"false positive on creative line: {line!r} -> {findings}"


# --- Real violations: must always be caught, deterministically. ---
VIOLATION_LINES = {
    "Guaranteed to increase stamina.": "GUARANTEED_OUTCOME",
    "100% effective.": "QUANTIFIED_CLAIM",
    "Cures fatigue.": "MEDICAL_CLAIM",
    "Eliminates dark spots completely.": "ABSOLUTE_OUTCOME",
    "Works instantly.": "ABSOLUTE_OUTCOME",
    "Clinically proven to work in 7 days.": "QUANTIFIED_CLAIM",
    "Doctors recommend this product.": "AUTHORITY_CLAIM",
    "FDA approved.": "AUTHORITY_CLAIM",
    "Lose 10 kg in 7 days.": "QUANTIFIED_CLAIM",
    "Guaranteed results.": "GUARANTEED_OUTCOME",
    "Prevents disease.": "MEDICAL_CLAIM",
    "Reverses aging.": "MEDICAL_CLAIM",
    "2x more strength guaranteed.": "GUARANTEED_OUTCOME",
}


def test_real_violations_are_blocked_deterministically():
    for line, expected_type in VIOLATION_LINES.items():
        findings = find_deterministic_violations(line)
        assert findings, f"missed a real violation: {line!r}"
        assert all(f.severity == "blocker" for f in findings)
        assert any(f.claim_type == expected_type for f in findings), (
            f"{line!r} matched {[f.claim_type for f in findings]}, expected {expected_type} among them"
        )


def test_context_changes_classification():
    # Same "finish line" / "strength" vocabulary, but the second sentence
    # makes an explicit guaranteed-performance promise.
    aspirational = "New strength, new finish line."
    explicit_claim = (
        "Our Men's Strength & Vitality Kit guarantees stronger performance and a faster finish."
    )
    assert find_deterministic_violations(aspirational) == []
    hits = find_deterministic_violations(explicit_claim)
    assert any(f.claim_type == "GUARANTEED_OUTCOME" for f in hits)


def test_overlapping_patterns_collapse_to_one_finding():
    # "clinically proven" alone AND the longer "clinically proven to work in
    # N days" pattern both match the same span — should not double-report.
    findings = find_deterministic_violations("Clinically proven to work in 7 days.")
    assert len(findings) == 1
    assert findings[0].claim_type == "QUANTIFIED_CLAIM"


def test_no_findings_on_empty_text():
    assert find_deterministic_violations("") == []


# =============================================================================
# V2.1 hardening pass — slogans/aspirational/Hinglish/testimonial/comparative
# =============================================================================

# --- Rule 19: false-positive suite (English + Hinglish slogans, aspirational
# copy, and mild personal experience) — none of these are claims. ---
V2_1_FALSE_POSITIVES = [
    "New strength, new finish line.",
    "Own your morning.",
    "Feel ready for what's next.",
    "Find your everyday glow.",
    "Support your active lifestyle.",
    "Helps support your daily routine.",
    "Feel more energetic.",
    "Stay active and consistent.",
    "Your everyday wellness companion.",
    "Start your wellness journey.",
    "Feel confident in your routine.",
    "Roz active feel karo.",
    "Apni routine ko better banao.",
    "Har din apna best do.",
    "Energy ke saath din start karo.",
]


def test_v2_1_slogans_and_hinglish_motivational_copy_pass():
    for line in V2_1_FALSE_POSITIVES:
        findings = find_deterministic_violations(line)
        assert findings == [], f"false positive on: {line!r} -> {findings}"


# --- Rule 21: testimonial suite — mild first-person experience passes;
# testimonials that stack a specific/absolute/time-bound outcome are caught. ---
TESTIMONIAL_PASSES = [
    "I felt more energetic after adding it to my routine.",
    "I personally enjoyed using it.",
    "It became part of my morning routine.",
    "I felt more confident during my workouts.",
]


def test_testimonials_without_a_stacked_outcome_produce_no_deterministic_findings():
    for line in TESTIMONIAL_PASSES:
        findings = find_deterministic_violations(line)
        assert findings == [], f"false positive on personal-experience line: {line!r} -> {findings}"


def test_testimonial_with_absolute_intensifier_is_caught_deterministically():
    # A first-person story becomes deterministically catchable once it pairs
    # a resolution verb with "completely"/"permanently" — the same claim
    # shape as the non-testimonial case, regardless of the story wrapper.
    findings = find_deterministic_violations(
        "I used it for 7 days and my fatigue completely disappeared."
    )
    assert any(f.claim_type == "ABSOLUTE_OUTCOME" for f in findings)

    findings = find_deterministic_violations(
        "I used it for one week and my hair fall stopped completely."
    )
    assert any(f.claim_type == "ABSOLUTE_OUTCOME" for f in findings)


# --- Rule 20: additional real-violation coverage — Hinglish medical/quantified
# claims and comparative claims, on top of the original English suite above. ---
V2_1_VIOLATIONS = {
    "Prevents hair fall completely.": "ABSOLUTE_OUTCOME",
    "Never feel tired again.": "ABSOLUTE_OUTCOME",
    "7 din mein pigmentation gayab.": "MEDICAL_CLAIM",
    "Thakaan poori tarah theek ho gayi in 7 days.": "MEDICAL_CLAIM",
    "Stamina double ho gaya.": "QUANTIFIED_CLAIM",
    "Hair fall bilkul ruk gaya.": "MEDICAL_CLAIM",
    "Doctor recommend karte hain.": "AUTHORITY_CLAIM",
    "Better than every other product.": "MISLEADING_COMPARATIVE_CLAIM",
    "India's #1 wellness product.": "MISLEADING_COMPARATIVE_CLAIM",
    "Best product in the market.": "MISLEADING_COMPARATIVE_CLAIM",
    "Works faster than all competitors.": "MISLEADING_COMPARATIVE_CLAIM",
    "10x stronger.": "MISLEADING_COMPARATIVE_CLAIM",
}


def test_v2_1_hinglish_and_comparative_violations_are_blocked_deterministically():
    for line, expected_type in V2_1_VIOLATIONS.items():
        findings = find_deterministic_violations(line)
        assert findings, f"missed a real violation: {line!r}"
        assert all(f.severity == "blocker" for f in findings)
        assert any(f.claim_type == expected_type for f in findings), (
            f"{line!r} matched {[f.claim_type for f in findings]}, expected {expected_type} among them"
        )


def test_harmless_numbers_and_marathon_aspiration_left_to_contextual_layer():
    # A number alone (Rule 14), and a context-dependent performance claim
    # that isn't unambiguous by shape alone (Rule 23/25), are deliberately
    # NOT deterministic — they're exactly what Layer 2 exists for.
    assert find_deterministic_violations("Available in 3 flavors.") == []
    assert find_deterministic_violations("Finish every marathon with this product.") == []
    assert find_deterministic_violations("Har marathon easily complete ho jayega.") == []
