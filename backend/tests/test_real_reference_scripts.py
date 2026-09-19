"""Real AayushWellness reference scripts (2026-09-19).

`product_reference_scripts` was empty: nothing ever imported
"Calender Video August.docx" (committed at backend/), and the DB is
gitignored/per-environment. These tests use the REAL document and a REAL
(in-memory SQLite) database built from the app's own schema — reference
content is never mocked, so every retrieval test fails if the importer
imports nothing or the DB is empty."""

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main  # imported at module level: main.py calls logging.basicConfig(force=True) on import, which would wipe caplog's handler if first imported mid-test
from app.config import Settings
from app.db import Base
from app.db_models import AyushProduct, ProductReferenceScript
from app.models.product import ContentType, ScriptGenerationInput, ScriptLanguage, StorySituation, StructuredProduct
from app.models.product_library import ProductContext
from app.services import product_library_service, reference_script_service as rss
from app.services import script_service as svc

# Phrases that exist verbatim in the real document — one per script.
REAL_PHRASES = {
    1: "India upgrade kar raha hai phones smart ho gaye",
    2: "Pet mein jalan, Daant Peele Padna",
    3: "Roz ka sirf ₹20",
    4: "Be smart. Be like Harsh.",
    5: "Yeh hai Gutka Paglu",
}


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    # StaticPool-equivalent for in-memory: one shared connection
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db(session_factory):
    with session_factory() as s:
        yield s


def _product(db, name="Aayush Wellness Herbal Masala", slug=None, category="herbal_health"):
    p = AyushProduct(name=name, slug=slug or name.lower().replace(" ", "-"), category=category)
    db.add(p)
    db.commit()
    return p


# --- the source document itself ---------------------------------------------


def test_the_real_document_exists_in_the_repo():
    assert rss.DEFAULT_DOCUMENT_PATH.exists(), "Calender Video August.docx must be committed under backend/"


def test_document_parses_into_the_five_real_scripts_with_actual_text():
    refs = rss.parse_calender_document()
    assert [r.number for r in refs] == [1, 2, 3, 4, 5]
    for r in refs:
        assert REAL_PHRASES[r.number] in r.script_text, f"script {r.number} lost its real wording"
        assert len(r.script_text) > 300


def test_analysis_notes_header_is_not_imported_as_a_script():
    for r in rss.parse_calender_document():
        assert "Sales Ad Script analyze Points" not in r.script_text
        assert "3000 chemicals" not in r.script_text


def test_directions_and_mechanisms_match_the_existing_reference_dna_records():
    from app.services import creative_reference_dna as dna
    by_key = {r.reference_key: r for r in rss.parse_calender_document()}
    for rec in dna.REFERENCE_RECORDS:
        if rec.video_id.startswith("CAL") and rec.video_id in by_key:
            assert by_key[rec.video_id].mechanism == rec.creative_mechanism
    assert {r.direction for r in by_key.values()} == {
        "Premium / Upgrade", "Problem → Solution", "Money / Value", "Funny / Sarcastic", "Character / Persona",
    }


# --- import: created, idempotent, preserved, scoped -------------------------


def test_import_creates_all_five_references_for_herbal_masala(db):
    p = _product(db)
    result = rss.import_calender_references(db)
    assert result.created == 5 and result.products_matched == 1
    rows = db.query(ProductReferenceScript).filter_by(product_id=p.id).all()
    assert {r.reference_key for r in rows} == {"CAL1", "CAL2", "CAL3", "CAL4", "CAL5"}
    assert all(r.is_approved and r.source_document == rss.SOURCE_DOCUMENT for r in rows)


def test_import_is_idempotent_running_twice_creates_no_duplicates(db):
    _product(db)
    rss.import_calender_references(db)
    second = rss.import_calender_references(db)
    third = rss.import_calender_references(db)
    assert second.created == 0 and third.created == 0
    assert second.unchanged == 5
    assert db.query(ProductReferenceScript).count() == 5


def test_import_preserves_the_actual_script_text_exactly(db):
    p = _product(db)
    rss.import_calender_references(db)
    parsed = {r.reference_key: r.script_text for r in rss.parse_calender_document()}
    for row in db.query(ProductReferenceScript).filter_by(product_id=p.id):
        assert row.script_text == parsed[row.reference_key]
        assert REAL_PHRASES[int(row.reference_key[3:])] in row.script_text


def test_import_attaches_to_every_herbal_masala_row_but_not_other_products(db):
    a = _product(db, slug="a")
    b = _product(db, slug="b")
    other = _product(db, name="Dreamy Sleep Gummies", category="nutraceuticals")
    result = rss.import_calender_references(db)
    assert result.products_matched == 2 and result.created == 10
    assert db.query(ProductReferenceScript).filter_by(product_id=other.id).count() == 0
    assert db.query(ProductReferenceScript).filter_by(product_id=a.id).count() == 5
    assert db.query(ProductReferenceScript).filter_by(product_id=b.id).count() == 5


def test_reimport_does_not_override_a_curators_unapproval(db):
    p = _product(db)
    rss.import_calender_references(db)
    row = db.query(ProductReferenceScript).filter_by(product_id=p.id, reference_key="CAL2").one()
    row.is_approved = False
    db.commit()
    rss.import_calender_references(db)
    db.refresh(row)
    assert row.is_approved is False


def test_imported_rows_are_labeled_creative_material_not_approved_facts(db):
    p = _product(db)
    rss.import_calender_references(db)
    for row in db.query(ProductReferenceScript).filter_by(product_id=p.id):
        assert "NOT approved product facts" in row.notes


# --- retrieval: reference_script_excerpts returns REAL text ------------------


def test_build_product_context_reference_script_excerpts_are_real_reference_text(db):
    """Herbal Masala -> reference_script_excerpts -> non-empty ACTUAL text.
    Starts from an empty reference table: fails if import/retrieval is broken."""
    p = _product(db)
    assert db.query(ProductReferenceScript).count() == 0
    ctx = product_library_service.build_product_context(db, p.id, max_reference_excerpts=5)
    assert ctx["reference_script_excerpts"], "reference_script_excerpts is empty"
    joined = "\n".join(ctx["reference_script_excerpts"])
    for phrase in REAL_PHRASES.values():
        assert phrase in joined
    # full text, not the old 400-char stub
    assert max(len(e) for e in ctx["reference_script_excerpts"]) > 400


def test_a_non_herbal_masala_product_gets_no_reference_excerpts(db):
    """Proves the excerpts come from real imported data, not a fixture."""
    p = _product(db, name="Dreamy Sleep Gummies", category="nutraceuticals")
    ctx = product_library_service.build_product_context(db, p.id)
    assert ctx["reference_script_excerpts"] == []


@pytest.mark.parametrize("mechanism,expected_key", [
    ("Value Math", "CAL3"), ("Peer Realization", "CAL5"),
    ("Character-as-Proof", "CAL4"), ("Upgrade / Modernization", "CAL1"),
])
def test_mechanism_specific_retrieval_puts_the_matching_reference_first(db, mechanism, expected_key):
    p = _product(db)
    rss.import_calender_references(db)
    hits = rss.select_reference_scripts(db, product_id=p.id, mechanism=mechanism)
    assert hits[0].reference_key == expected_key
    assert hits[0].mechanism == mechanism
    assert len(hits) == 3


def test_direction_hint_retrieves_the_problem_to_solution_reference_which_has_no_mechanism(db):
    p = _product(db)
    rss.import_calender_references(db)
    hits = rss.select_reference_scripts(db, product_id=p.id, hint_text="a problem solution style story", limit=5)
    assert hits[0].reference_key == "CAL2"


def test_no_mechanism_still_returns_real_examples_not_nothing(db):
    p = _product(db)
    rss.import_calender_references(db)
    assert len(rss.select_reference_scripts(db, product_id=p.id)) == 3


def test_duplicate_product_rows_do_not_produce_duplicate_hits(db):
    _product(db, slug="a")
    _product(db, slug="b")
    rss.import_calender_references(db)
    hits = rss.select_reference_scripts(db, product_name="Aayush Herbal Masala", limit=10)
    assert sorted(h.reference_key for h in hits) == ["CAL1", "CAL2", "CAL3", "CAL4", "CAL5"]


def test_unapproved_references_are_never_retrieved(db):
    p = _product(db)
    rss.import_calender_references(db)
    for r in db.query(ProductReferenceScript).filter_by(product_id=p.id):
        r.is_approved = False
    db.commit()
    assert rss.select_reference_scripts(db, product_id=p.id) == []


def test_retrieve_for_generation_self_heals_when_the_table_is_empty(session_factory, monkeypatch):
    with session_factory() as s:
        p = _product(s)
        pid = p.id
    monkeypatch.setattr(rss, "SessionLocal", session_factory)
    hits = rss.retrieve_for_generation(product_id=pid, product_name="Aayush Wellness Herbal Masala", mechanism="Value Math")
    assert hits and hits[0].reference_key == "CAL3"
    assert REAL_PHRASES[3] in hits[0].text


def test_retrieve_for_generation_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(rss, "SessionLocal", boom)
    assert rss.retrieve_for_generation(product_id="x", product_name="y") == []


# --- Language DNA + the writer prompt ---------------------------------------


def test_excerpt_carries_creative_dna_language_dna_and_the_full_real_text(db):
    p = _product(db)
    rss.import_calender_references(db)
    hit = rss.select_reference_scripts(db, product_id=p.id, mechanism="Value Math")[0]
    text = rss.format_reference_excerpt(hit)
    assert "[CAL3] Direction: Money / Value; mechanism: Value Math" in text
    assert "Creative DNA — hook device:" in text
    assert "Language DNA (measured):" in text and "words per spoken sentence" in text
    assert "Roman-script Hinglish" in text
    assert hit.text in text  # full original text preserved


def test_prompt_header_instructs_style_dna_not_copying_and_claim_safety_wins():
    h = rss.REFERENCE_PROMPT_HEADER
    assert "Study the reference examples for patterns and writing DNA." in h
    assert "Transfer the underlying style and principles." in h
    assert "Never copy sentences, phrases, characters, or story wording." in h
    assert "NOT approved product facts" in h and "claim safety always wins" in h


def _payload(ctx, mechanism="Value Math"):
    situation = StorySituation(
        id="t", title="Roz Ka Hisaab", description="d", emotion="e", persona="p", marketing_angle="m",
        category="c", difficulty="medium", estimated_length="30s", virality_score=5.0, recommended_angles=[],
        creative_mechanism=mechanism,
    )
    return ScriptGenerationInput(
        structured_product=StructuredProduct(product_name="Aayush Wellness Herbal Masala", target_audience="gutka users",
                                             ingredients=["Mulethi"], usp="0% tobacco", key_benefits=["same taste"]),
        selected_situation=situation, product_category="herbal_health", platform="instagram_reel",
        script_language=ScriptLanguage.hinglish, content_type=ContentType.video, product_context=ctx,
    )


def _run_pre_stages(payload):
    from unittest.mock import patch
    from app.services import creative_architecture
    arch = creative_architecture.get_architecture(creative_architecture.DEFAULT_ARCHITECTURE_KEY)
    with patch.object(svc.creative_insight_service, "discover_insight", return_value=None), \
         patch.object(svc.creative_territory_service, "generate_and_select_territory", return_value=None), \
         patch.object(svc.creative_architecture, "select_architecture", return_value=arch), \
         patch.object(svc.creative_premise_service, "generate_and_select_premise", return_value=None), \
         patch.object(svc.hook_generation_service, "generate_and_select_hook", return_value=None), \
         patch.object(svc.beat_outline_service, "generate_and_validate_outline", return_value=(None, [])):
        return svc._run_creative_pre_stages(payload, "30s")


def test_real_reference_text_reaches_the_final_writer_prompt_via_product_context(session_factory, monkeypatch, caplog):
    with session_factory() as s:
        p = _product(s)
        raw = product_library_service.build_product_context(s, p.id)
    monkeypatch.setattr(rss, "SessionLocal", session_factory)
    ctx = ProductContext(**raw)
    with caplog.at_level(logging.INFO, logger="reference_dna"), caplog.at_level(logging.INFO, logger="script_service"):
        pre = _run_pre_stages(_payload(ctx, mechanism="Value Math"))
    excerpts = pre.payload.product_context.reference_script_excerpts
    assert excerpts and excerpts[0].startswith("[CAL3]")  # mechanism-ranked
    prompt = svc._context_block(pre.payload, "30s", None)
    assert rss.REFERENCE_PROMPT_HEADER in prompt
    assert REAL_PHRASES[3] in prompt  # the ACTUAL reference wording is in the writer's context
    assert "Never copy sentences, phrases, characters, or story wording." in prompt
    # diagnostics: ids/flags only, never the reference text
    diag = [r.getMessage() for r in caplog.records if "[REFERENCE_DNA] product=" in r.getMessage()]
    assert diag and "references_found=3" in diag[0] and "'CAL3'" in diag[0]
    assert "language_examples_loaded=true" in diag[0] and "creative_examples_loaded=true" in diag[0]
    assert REAL_PHRASES[3] not in diag[0]


def test_reference_text_reaches_the_prompt_even_without_a_product_library_context(session_factory, monkeypatch):
    with session_factory() as s:
        _product(s)
    monkeypatch.setattr(rss, "SessionLocal", session_factory)
    pre = _run_pre_stages(_payload(None, mechanism="Peer Realization"))
    assert rss.REFERENCE_PROMPT_HEADER in pre.prompt_block
    assert REAL_PHRASES[5] in pre.prompt_block


def test_generation_without_any_references_still_works_unchanged(session_factory, monkeypatch):
    monkeypatch.setattr(rss, "SessionLocal", session_factory)  # empty DB, no products
    pre = _run_pre_stages(_payload(None))
    assert rss.REFERENCE_PROMPT_HEADER not in pre.prompt_block


# --- model routing ------------------------------------------------------------

BACKEND = Path(__file__).resolve().parents[1]
LUNA, FLASH_LITE = "openai/gpt-5.6-luna", "google/gemini-2.5-flash-lite"


def test_active_settings_route_creative_and_final_to_luna_and_validation_to_flash_lite():
    from app.config import settings
    assert settings.creative_model == LUNA
    assert settings.final_script_model == LUNA
    assert settings.validation_model == FLASH_LITE
    assert settings.openrouter_text_model == LUNA
    assert settings.image_generation_enabled is False


def test_env_file_resolution_is_independent_of_the_working_directory(tmp_path, monkeypatch):
    from app.config import _ENV_FILE
    assert _ENV_FILE.is_absolute() and _ENV_FILE.parent.name == "backend"
    if not _ENV_FILE.exists():
        pytest.skip("no local .env in this checkout")
    monkeypatch.chdir(tmp_path)  # a directory with no .env
    s = Settings()
    assert s.creative_model == LUNA and s.final_script_model == LUNA and s.validation_model == FLASH_LITE


def test_env_example_activates_luna_split_and_keeps_gemini_only_as_comments():
    active = [ln.strip() for ln in (BACKEND / ".env.example").read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.strip().startswith("#")]
    assert f"OPENROUTER_CREATIVE_MODEL={LUNA}" in active
    assert f"OPENROUTER_FINAL_SCRIPT_MODEL={LUNA}" in active
    assert f"OPENROUTER_VALIDATION_MODEL={FLASH_LITE}" in active
    assert f"OPENROUTER_TEXT_MODEL={LUNA}" in active
    assert not any("gemini-2.5-flash" in ln and "lite" not in ln and "image" not in ln for ln in active)


def test_render_yaml_declares_the_same_split():
    text = (BACKEND.parent / "render.yaml").read_text(encoding="utf-8")
    for key, value in (("OPENROUTER_CREATIVE_MODEL", LUNA), ("OPENROUTER_FINAL_SCRIPT_MODEL", LUNA),
                       ("OPENROUTER_VALIDATION_MODEL", FLASH_LITE), ("OPENROUTER_TEXT_MODEL", LUNA)):
        assert f"key: {key}\n        value: {value}" in text


def test_no_silent_gemini_creative_fallback_when_text_model_is_luna():
    s = Settings(_env_file=None, openrouter_text_model=LUNA)
    assert s.creative_model == LUNA and s.final_script_model == LUNA
    s2 = Settings(_env_file=None, openrouter_text_model=LUNA, openrouter_validation_model=FLASH_LITE)
    assert s2.validation_model == FLASH_LITE


def test_openrouter_is_the_only_gateway_no_direct_openai_sdk():
    for path in (BACKEND / "app").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "import openai" not in src and "from openai" not in src and "api.openai.com" not in src, path
    assert "openai" not in (BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()


def test_startup_warns_loudly_when_a_role_silently_falls_back_to_the_text_model(caplog, monkeypatch):
    monkeypatch.setattr(main.settings, "openrouter_creative_model", "")
    monkeypatch.setattr(main.settings, "openrouter_text_model", "google/gemini-2.5-flash")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        main.log_implicit_model_fallbacks()
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "OPENROUTER_CREATIVE_MODEL is not set" in msgs and "google/gemini-2.5-flash" in msgs


def test_no_warning_when_every_role_is_explicit(caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        main.log_implicit_model_fallbacks()
    assert not [r for r in caplog.records if "falling back" in r.getMessage()]
