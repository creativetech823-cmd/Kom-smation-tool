"""AyushWellness Product Library tests — service layer, against the real
dev SQLite DB (no separate test-DB plumbing exists in this project yet).
Every row created here is tagged with a ZZTEST_ marker and removed in a
fixture teardown, so a normal test run leaves no trace in the dev database
even though it isn't sandboxed in its own transaction.
"""

import pytest

from app.db import SessionLocal
from app.db_models import AyushProduct, Hook, ProductAsset, ProductCreativeAngle, ProductReferenceScript
from app.services import library_service
from app.services import product_library_service as svc

MARKER = "ZZTEST_PRODUCT_LIBRARY"


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        # Teardown: remove every row this test session created, regardless
        # of which test created it — keeps the dev DB clean even on failure.
        session.rollback()
        product_ids = [p.id for p in session.query(AyushProduct).filter(AyushProduct.name.like(f"{MARKER}%")).all()]
        if product_ids:
            session.query(ProductAsset).filter(ProductAsset.product_id.in_(product_ids)).delete(synchronize_session=False)
            session.query(ProductReferenceScript).filter(
                ProductReferenceScript.product_id.in_(product_ids)
            ).delete(synchronize_session=False)
            session.query(ProductCreativeAngle).filter(
                ProductCreativeAngle.product_id.in_(product_ids)
            ).delete(synchronize_session=False)
            session.query(Hook).filter(Hook.product_id.in_(product_ids)).delete(synchronize_session=False)
            session.query(AyushProduct).filter(AyushProduct.id.in_(product_ids)).delete(synchronize_session=False)
            session.commit()
        session.close()


def _make_product(db, name_suffix="", **overrides):
    payload = {
        "name": f"{MARKER} Herbal Masala {name_suffix}".strip(),
        "category": "herbal_health",
        "short_description": "A tobacco-free herbal masala alternative.",
        "ingredients": ["fennel", "cardamom"],
        "benefits": ["tobacco-free"],
        "approved_claims": ["tobacco-free herbal alternative"],
        "prohibited_claims": ["cures addiction"],
    }
    payload.update(overrides)
    return svc.create_product(db, payload)


# --- 1. create product ---
def test_create_product(db):
    product = _make_product(db)
    assert product.id
    assert product.name.startswith(MARKER)
    assert product.slug  # auto-generated
    assert product.status == "active"


# --- 2. category validation (service level: category is stored, extensible string) ---
def test_category_is_stored_as_given_and_extensible():
    db = SessionLocal()
    try:
        product = _make_product(db, "cat", category="nutraceuticals")
        assert product.category == "nutraceuticals"
        # A brand-new category value is accepted (extensible by design — no
        # DB-level enum constraint), matching the "extensible for future
        # categories" requirement.
        product2 = _make_product(db, "cat2", category="ayurvedic_skincare")
        assert product2.category == "ayurvedic_skincare"
    finally:
        db.query(AyushProduct).filter(AyushProduct.name.like(f"{MARKER}%")).delete(synchronize_session=False)
        db.commit()
        db.close()


# --- 3. retrieve product ---
def test_retrieve_product(db):
    created = _make_product(db)
    fetched = svc.get_product(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    out = svc.product_to_out(db, fetched)
    assert out["ingredients"] == ["fennel", "cardamom"]
    assert out["approved_claims"] == ["tobacco-free herbal alternative"]
    assert out["prohibited_claims"] == ["cures addiction"]


# --- 4. update product ---
def test_update_product(db):
    created = _make_product(db)
    updated = svc.update_product(db, created.id, {"cta_text": "Try it today", "benefits": ["tobacco-free", "refreshing"]})
    assert updated.cta_text == "Try it today"
    out = svc.product_to_out(db, updated)
    assert out["benefits"] == ["tobacco-free", "refreshing"]
    # Slug regenerates safely when name changes, without colliding.
    original_slug = created.slug
    renamed = svc.update_product(db, created.id, {"name": f"{MARKER} Renamed"})
    assert renamed.slug != original_slug


# --- 5. delete/deactivate product ---
def test_archive_and_restore_product(db):
    created = _make_product(db)
    archived = svc.archive_product(db, created.id)
    assert archived.status == "archived"
    # Archived products are excluded from the default (no-status-filter) listing.
    active_listing = svc.list_products(db, category="herbal_health")
    assert created.id not in [p.id for p in active_listing]
    restored = svc.restore_product(db, created.id)
    assert restored.status == "active"


# --- 6. attach asset to product ---
def test_attach_asset_to_product(db):
    product = _make_product(db)
    asset = svc.create_asset(db, product.id, "product_packshot", "fake/path.png", title="Test packshot")
    assert asset.product_id == product.id
    assert asset.is_primary is True  # first asset for a product becomes primary automatically


# --- 7. classify asset ---
def test_classify_asset(db):
    product = _make_product(db)
    asset = svc.create_asset(db, product.id, "other", "fake/path.png")
    updated = svc.update_asset(db, asset.id, {"asset_type": "product_lifestyle", "tags": ["hero", "lifestyle"]})
    assert updated.asset_type.value == "product_lifestyle"
    out = svc.asset_to_out(updated)
    assert out["tags"] == ["hero", "lifestyle"]


# --- 8. active/inactive asset ---
def test_deactivate_asset(db):
    product = _make_product(db)
    asset = svc.create_asset(db, product.id, "product_image", "fake/path.png")
    deactivated = svc.deactivate_asset(db, asset.id)
    assert deactivated.is_active is False
    assert deactivated.is_primary is False
    active_assets = svc.list_assets(db, product.id)
    assert asset.id not in [a.id for a in active_assets]
    all_assets = svc.list_assets(db, product.id, active_only=False)
    assert asset.id in [a.id for a in all_assets]


# --- 9. product asset selection priority (primary-first ordering) ---
def test_primary_asset_selection_priority(db):
    product = _make_product(db)
    first = svc.create_asset(db, product.id, "product_image", "a.png")
    second = svc.create_asset(db, product.id, "product_packshot", "b.png")
    assert first.is_primary is True
    assert second.is_primary is False
    # Promote the second asset to primary — exactly one primary at a time.
    svc.update_asset(db, second.id, {"is_primary": True})
    db.refresh(first)
    db.refresh(second)
    assert first.is_primary is False
    assert second.is_primary is True
    out = svc.product_to_out(db, product)
    assert out["primary_asset"]["id"] == second.id


# --- reference scripts ---
def test_reference_script_crud_and_approved_filter(db):
    product = _make_product(db)
    draft = svc.create_reference_script(db, product.id, {"title": "Draft", "script_text": "old draft copy", "is_approved": False})
    approved = svc.create_reference_script(
        db, product.id, {"title": "Approved", "script_text": "approved reference copy", "is_approved": True}
    )
    all_scripts = svc.list_reference_scripts(db, product.id)
    assert {s.id for s in all_scripts} == {draft.id, approved.id}
    approved_only = svc.list_reference_scripts(db, product.id, approved_only=True)
    assert [s.id for s in approved_only] == [approved.id]


# --- 10/11. pipeline context reaches Script/Assets: build_product_context ---
def test_build_product_context_includes_only_approved_script_excerpts(db):
    product = _make_product(db)
    svc.create_reference_script(db, product.id, {"title": "Draft", "script_text": "UNAPPROVED_TEXT", "is_approved": False})
    svc.create_reference_script(db, product.id, {"title": "Approved", "script_text": "APPROVED_TEXT", "is_approved": True})
    svc.create_asset(db, product.id, "product_packshot", "real/pack.png")

    context = svc.build_product_context(db, product.id)
    assert context["product_id"] == product.id
    assert context["ingredients"] == ["fennel", "cardamom"]
    assert context["prohibited_claims"] == ["cures addiction"]
    assert any("APPROVED_TEXT" in e for e in context["reference_script_excerpts"])
    assert all("UNAPPROVED_TEXT" not in e for e in context["reference_script_excerpts"])
    assert context["primary_asset_url"] == "/product-uploads/real/pack.png"


def test_build_product_context_missing_product_returns_none(db):
    assert svc.build_product_context(db, "does-not-exist") is None


# --- extended fields (brand/creative-direction/target-customer) round-trip ---
def test_extended_product_fields_persist_and_serialize(db):
    product = _make_product(
        db,
        "extended",
        brand="AyushWellness",
        sku="AWH-001",
        never_say="Never call it a medical cure",
        customer_objections=["too expensive", "does it actually work"],
        buying_triggers=["doctor recommended it"],
        words_to_use=["natural", "herbal"],
        words_to_avoid=["miracle", "instant"],
        visual_style="warm, real Indian home settings",
    )
    out = svc.product_to_out(db, product)
    assert out["brand"] == "AyushWellness"
    assert out["sku"] == "AWH-001"
    assert out["never_say"] == "Never call it a medical cure"
    assert out["customer_objections"] == ["too expensive", "does it actually work"]
    assert out["buying_triggers"] == ["doctor recommended it"]
    assert out["words_to_use"] == ["natural", "herbal"]
    assert out["words_to_avoid"] == ["miracle", "instant"]
    assert out["visual_style"] == "warm, real Indian home settings"


# --- creative angles CRUD ---
def test_creative_angle_crud():
    db = SessionLocal()
    try:
        product = _make_product(db, "angles")
        angle = svc.create_creative_angle(
            db,
            product.id,
            {
                "name": "Tobacco-free alternative",
                "description": "Habit-swap positioning",
                "approved_messaging": "100% tobacco-free herbal blend",
                "restricted_messaging": "Never imply medical cessation efficacy",
            },
        )
        assert angle.product_id == product.id

        angles = svc.list_creative_angles(db, product.id)
        assert [a.id for a in angles] == [angle.id]

        updated = svc.update_creative_angle(db, angle.id, {"description": "Updated positioning"})
        assert updated.description == "Updated positioning"

        out = svc.creative_angle_to_out(updated)
        assert out["name"] == "Tobacco-free alternative"
        assert out["restricted_messaging"] == "Never imply medical cessation efficacy"

        assert svc.delete_creative_angle(db, angle.id) is True
        assert svc.list_creative_angles(db, product.id) == []
        assert svc.delete_creative_angle(db, "does-not-exist") is False
    finally:
        db.rollback()
        db.query(ProductCreativeAngle).filter(ProductCreativeAngle.product_id.in_(
            [p.id for p in db.query(AyushProduct).filter(AyushProduct.name.like(f"{MARKER}%")).all()]
        )).delete(synchronize_session=False)
        db.query(AyushProduct).filter(AyushProduct.name.like(f"{MARKER}%")).delete(synchronize_session=False)
        db.commit()
        db.close()


# --- product context includes creative angles, product hooks, and the
# has_real_product_asset flag ---
def test_build_product_context_includes_angles_and_hooks_and_asset_flag(db):
    product = _make_product(db, "context-extras")
    svc.create_creative_angle(db, product.id, {"name": "Daily habit reset", "description": "Morning ritual framing"})

    hook = Hook(text=f"{MARKER} Still reaching for tobacco out of habit?", category="question", product_id=product.id)
    db.add(hook)
    db.commit()

    context_no_asset = svc.build_product_context(db, product.id)
    assert context_no_asset["has_real_product_asset"] is False
    assert context_no_asset["creative_angles"] == ["Daily habit reset: Morning ritual framing"]
    assert context_no_asset["approved_hooks"] == [f"{MARKER} Still reaching for tobacco out of habit?"]

    svc.create_asset(db, product.id, "product_packshot", "real/pack.png")
    context_with_asset = svc.build_product_context(db, product.id)
    assert context_with_asset["has_real_product_asset"] is True

    db.delete(hook)
    db.commit()


# --- a URL-only reference asset (advertisement/reference_video link) never
# becomes the product's primary image, and file_path is genuinely optional ---
def test_url_only_reference_asset_is_not_primary(db):
    product = _make_product(db, "reference-link")
    real_asset = svc.create_asset(db, product.id, "product_packshot", "real/pack.png")
    assert real_asset.is_primary is True

    link = svc.create_asset_link(
        db,
        product.id,
        asset_type="advertisement",
        source_url="https://example.com/reference-ad",
        learning_notes="Strong hook-first structure",
    )
    assert link.is_primary is False
    assert link.file_path is None

    out = svc.asset_to_out(link)
    assert out["file_path"] is None
    assert out["source_url"] == "https://example.com/reference-ad"
    assert out["learning_notes"] == "Strong hook-first structure"

    context = svc.build_product_context(db, product.id)
    assert context["primary_asset_url"] == "/product-uploads/real/pack.png"


# --- Real Product Asset vs Reference Material classification (Product Asset
# Architecture fix) ---


def test_reference_asset_never_becomes_primary_automatically(db):
    """Uploading a reference-type asset FIRST for a brand-new product must
    NOT make it primary — only a genuine product photo auto-promotes. Before
    this fix, "first asset of any type" became primary."""
    product = _make_product(db, "ref-not-auto-primary")
    ad = svc.create_asset(db, product.id, "advertisement", "ad.jpg")
    assert ad.is_primary is False
    out = svc.product_to_out(db, product)
    assert out["primary_asset"] is None  # no real product asset exists yet

    ref_img = svc.create_asset(db, product.id, "reference_image", "style-ref.jpg")
    assert ref_img.is_primary is False

    video = svc.create_asset(db, product.id, "reference_video", "clip.mp4")
    assert video.is_primary is False

    other = svc.create_asset(db, product.id, "other", "misc.jpg")
    assert other.is_primary is False

    # Now the first REAL product photo shows up — it, and only it, auto-primaries.
    real = svc.create_asset(db, product.id, "product_image", "real.jpg")
    assert real.is_primary is True
    out = svc.product_to_out(db, product)
    assert out["primary_asset"]["id"] == real.id


def test_update_asset_rejects_making_reference_material_primary(db):
    product = _make_product(db, "ref-reject-primary")
    ad = svc.create_asset(db, product.id, "advertisement", "ad.jpg")
    with pytest.raises(ValueError):
        svc.update_asset(db, ad.id, {"is_primary": True})
    db.refresh(ad)
    assert ad.is_primary is False  # the rejected attempt left it untouched


def test_update_asset_rejects_primary_without_file(db):
    product = _make_product(db, "no-file-reject-primary")
    link = svc.create_asset_link(db, product.id, asset_type="product_image", source_url="https://example.com/x.jpg")
    assert link.file_path is None
    with pytest.raises(ValueError):
        svc.update_asset(db, link.id, {"is_primary": True})


def test_reference_asset_excluded_from_primary_even_if_manually_flagged(db):
    """Defense in depth: even if a row somehow has is_primary=True on a
    reference type (e.g. legacy data from before this fix), _primary_asset
    must never surface it — verified through the public product_to_out API."""
    product = _make_product(db, "legacy-bad-primary")
    ad = svc.create_asset(db, product.id, "advertisement", "ad.jpg")
    # Simulate stale/legacy data bypassing the update_asset guard entirely.
    ad.is_primary = True
    db.commit()

    out = svc.product_to_out(db, product)
    assert out["primary_asset"] is None

    real = svc.create_asset(db, product.id, "product_packshot", "real.jpg")
    out = svc.product_to_out(db, product)
    assert out["primary_asset"]["id"] == real.id


def test_deactivating_primary_promotes_next_best_real_asset(db):
    product = _make_product(db, "auto-promote")
    first = svc.create_asset(db, product.id, "product_image", "a.jpg")
    second = svc.create_asset(db, product.id, "product_packshot", "b.jpg")
    assert first.is_primary is True
    assert second.is_primary is False

    svc.deactivate_asset(db, first.id)
    db.refresh(second)
    assert second.is_primary is True
    out = svc.product_to_out(db, product)
    assert out["primary_asset"]["id"] == second.id


def test_deactivating_primary_never_promotes_a_reference_asset(db):
    product = _make_product(db, "no-promote-reference")
    real = svc.create_asset(db, product.id, "product_image", "a.jpg")
    svc.create_asset(db, product.id, "advertisement", "ad.jpg")
    svc.create_asset(db, product.id, "reference_video", "clip.mp4")
    assert real.is_primary is True

    svc.deactivate_asset(db, real.id)
    out = svc.product_to_out(db, product)
    # No real product asset remains — primary must be null, never a reference asset.
    assert out["primary_asset"] is None


def test_asset_to_out_reports_is_real_product_asset(db):
    product = _make_product(db, "is-real-flag")
    real = svc.create_asset(db, product.id, "product_lifestyle", "a.jpg")
    ref = svc.create_asset(db, product.id, "reference_image", "b.jpg")
    assert svc.asset_to_out(real)["is_real_product_asset"] is True
    assert svc.asset_to_out(ref)["is_real_product_asset"] is False


# --- create_hook (Hook Studio) with an optional product association ---
def test_create_hook_with_and_without_product(db):
    product = _make_product(db, "hook-create")
    product_hook = library_service.create_hook(db, "Still reaching for tobacco out of habit?", tone="empathetic", product_id=product.id)
    global_hook = library_service.create_hook(db, "A hook with no product")

    assert product_hook.product_id == product.id
    assert global_hook.product_id is None

    product_only, total = library_service.list_hooks(db, product_id=product.id)
    assert [h.id for h in product_only] == [product_hook.id]
    assert total == 1

    with pytest.raises(ValueError):
        library_service.create_hook(db, "   ")

    db.delete(product_hook)
    db.delete(global_hook)
    db.commit()
