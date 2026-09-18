"""Tests for structured reference-creative knowledge (AHM Creative DNA §14) —
in particular the category-transfer rule: mechanism only, never surface
content, when the brief's category differs from the reference material's."""

from app.services import creative_reference_dna as dna


def test_every_usable_record_has_a_valid_architecture_key_or_is_mechanism_only():
    from app.services.creative_architecture import ARCHITECTURES

    # 2026-09-18 Creative DNA task added mechanism-only reference records
    # (retrieved by creative_mechanism via mechanism_notes(), not by
    # architecture via relevant_notes()) — architecture="" is legitimate for
    # those specifically, never for any other record.
    for record in dna.REFERENCE_RECORDS:
        if record.is_anti_pattern:
            continue
        if record.architecture == "":
            assert record.creative_mechanism, f"{record.video_id} has no architecture and no mechanism either"
            continue
        assert record.architecture in ARCHITECTURES, record.video_id


def test_v9_is_marked_as_the_one_anti_pattern():
    v9 = next(r for r in dna.REFERENCE_RECORDS if r.video_id == "V9")
    assert v9.is_anti_pattern is True


def test_records_for_architecture_excludes_anti_pattern():
    records = dna.records_for_architecture("none")
    assert records == []  # the anti-pattern's "architecture" key matches nothing real


def test_records_for_architecture_returns_matching_records():
    records = dna.records_for_architecture("objection_handling_interview")
    assert len(records) >= 1
    assert all(r.architecture == "objection_handling_interview" for r in records)


def test_relevant_notes_labels_cross_category_transfer_explicitly():
    notes = dna.relevant_notes("objection_handling_interview", product_category="skincare")
    assert "DIFFERENT product category" in notes
    assert "mechanism" in notes.lower()
    # Must never leak the reference category's literal surface content
    # (gutka/tobacco-specific nouns) into a cross-category prompt block.
    assert "gutka" not in notes.lower()
    assert "tobacco" not in notes.lower()


def test_relevant_notes_same_category_does_not_claim_cross_category():
    notes = dna.relevant_notes(
        "objection_handling_interview",
        product_category="tobacco/gutka habit-replacement",
        reference_category="tobacco/gutka habit-replacement",
    )
    assert "DIFFERENT product category" not in notes


def test_relevant_notes_empty_for_architecture_with_no_records():
    assert dna.relevant_notes("pure_demonstration_but_typo", product_category="x") == ""


def test_relevant_notes_treats_generic_category_as_same_category_when_brief_text_says_tobacco():
    # The real-world bug: Herbal Masala's stored category is the generic
    # "herbal_health" string, but its actual given target audience is
    # gutka/tobacco chewers — brief_text must be enough to recognize that.
    notes = dna.relevant_notes(
        "objection_handling_interview",
        product_category="herbal_health",
        brief_text="adult gutka and pan masala chewers trying to switch",
    )
    assert "DIFFERENT product category" not in notes


def test_relevant_notes_stays_cross_category_when_brief_text_also_unrelated():
    notes = dna.relevant_notes(
        "objection_handling_interview",
        product_category="herbal_health",
        brief_text="mothers of school-age children",
    )
    assert "DIFFERENT product category" in notes


def test_anti_pattern_notes_is_always_safe_and_nonempty():
    notes = dna.anti_pattern_notes()
    assert "DOCUMENTED ANTI-PATTERN" in notes
    assert len(notes) > 20
