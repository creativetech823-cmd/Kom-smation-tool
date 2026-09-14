"""Persistence layer for the AyushWellness Product Library — AyushProduct,
ProductAsset, ProductReferenceScript. Mirrors library_service.py's shape:
plain ORM CRUD plus JSON (de)serialization for the array-shaped Text columns,
one function per operation, a `*_to_out` serializer per resource.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models import AyushProduct, Hook, ProductAsset, ProductCreativeAngle, ProductReferenceScript


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dumps_list(items: Optional[list]) -> Optional[str]:
    if items is None:
        return None
    return json.dumps(list(items))


def _loads_list(text: Optional[str]) -> list:
    if not text:
        return []
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _slugify(name: str, existing_id: Optional[str] = None) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "product"
    return slug[:300]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

_LIST_FIELDS = (
    "ingredients",
    "benefits",
    "approved_claims",
    "prohibited_claims",
    "pain_points",
    "emotional_triggers",
    "advertising_angles",
    "winning_hooks",
    "marketplace_urls",
    "customer_objections",
    "buying_triggers",
    "words_to_use",
    "words_to_avoid",
)


def _unique_slug(db: Session, base_slug: str, exclude_id: Optional[str] = None) -> str:
    slug = base_slug
    suffix = 2
    while True:
        query = db.query(AyushProduct).filter(AyushProduct.slug == slug)
        if exclude_id:
            query = query.filter(AyushProduct.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def create_product(db: Session, payload: dict) -> AyushProduct:
    fields = dict(payload)
    for key in _LIST_FIELDS:
        if key in fields:
            fields[key] = _dumps_list(fields[key])
    base_slug = _slugify(fields.get("name", "product"))
    fields["slug"] = _unique_slug(db, base_slug)
    product = AyushProduct(**fields)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_products(
    db: Session,
    category: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> list[AyushProduct]:
    query = db.query(AyushProduct)
    if category:
        query = query.filter(AyushProduct.category == category)
    if status:
        query = query.filter(AyushProduct.status == status)
    else:
        # Archived products are opt-in only — a bare listing should feel like
        # "my active catalog", not clutter with everything ever created.
        query = query.filter(AyushProduct.status != "archived")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(AyushProduct.name.like(like), AyushProduct.short_description.like(like)))
    return query.order_by(AyushProduct.updated_at.desc()).all()


def get_product(db: Session, product_id: str) -> Optional[AyushProduct]:
    return db.get(AyushProduct, product_id)


def update_product(db: Session, product_id: str, fields: dict) -> Optional[AyushProduct]:
    product = db.get(AyushProduct, product_id)
    if product is None:
        return None
    fields = dict(fields)
    if "name" in fields and fields["name"]:
        fields["slug"] = _unique_slug(db, _slugify(fields["name"]), exclude_id=product_id)
    for key in _LIST_FIELDS:
        if key in fields:
            fields[key] = _dumps_list(fields[key])
    for key, value in fields.items():
        if value is not None:
            setattr(product, key, value)
    product.updated_at = _now()
    db.commit()
    db.refresh(product)
    return product


def archive_product(db: Session, product_id: str) -> Optional[AyushProduct]:
    return update_product(db, product_id, {"status": "archived"})


def restore_product(db: Session, product_id: str) -> Optional[AyushProduct]:
    return update_product(db, product_id, {"status": "active"})


def _primary_asset(db: Session, product_id: str) -> Optional[ProductAsset]:
    # A URL-only reference asset (no file_path) can never stand in as the
    # product's primary image — that slot is reserved for a real, renderable
    # uploaded photo (what Assets/Render actually display).
    return (
        db.query(ProductAsset)
        .filter(
            ProductAsset.product_id == product_id,
            ProductAsset.is_active.is_(True),
            ProductAsset.file_path.isnot(None),
        )
        .order_by(ProductAsset.is_primary.desc(), ProductAsset.sort_order.asc(), ProductAsset.created_at.asc())
        .first()
    )


def product_to_out(db: Session, product: AyushProduct) -> dict:
    primary = _primary_asset(db, product.id)
    asset_count = (
        db.query(ProductAsset)
        .filter(ProductAsset.product_id == product.id, ProductAsset.is_active.is_(True))
        .count()
    )
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "category": product.category,
        "status": product.status,
        "short_description": product.short_description or "",
        "description": product.description or "",
        "product_url": product.product_url,
        "price": product.price,
        "display_name": product.display_name or "",
        "subcategory": product.subcategory or "",
        "brand": product.brand or "",
        "sku": product.sku or "",
        "marketplace_urls": _loads_list(product.marketplace_urls),
        "landing_page_url": product.landing_page_url,
        "target_audience": product.target_audience or "",
        "primary_problem": product.primary_problem or "",
        "positioning": product.positioning or "",
        "usp": product.usp or "",
        "ingredients": _loads_list(product.ingredients),
        "benefits": _loads_list(product.benefits),
        "usage": product.usage or "",
        "how_it_works": product.how_it_works or "",
        "who_is_it_for": product.who_is_it_for or "",
        "cautions": product.cautions or "",
        "approved_claims": _loads_list(product.approved_claims),
        "prohibited_claims": _loads_list(product.prohibited_claims),
        "mandatory_wording": product.mandatory_wording or "",
        "never_say": product.never_say or "",
        "secondary_target_audience": product.secondary_target_audience or "",
        "customer_objections": _loads_list(product.customer_objections),
        "buying_triggers": _loads_list(product.buying_triggers),
        "awareness_level": product.awareness_level or "",
        "pain_points": _loads_list(product.pain_points),
        "emotional_triggers": _loads_list(product.emotional_triggers),
        "advertising_angles": _loads_list(product.advertising_angles),
        "preferred_tone": product.preferred_tone or "",
        "preferred_language": product.preferred_language or "",
        "cta_text": product.cta_text or "",
        "winning_hooks": _loads_list(product.winning_hooks),
        "creative_notes": product.creative_notes or "",
        "brand_personality": product.brand_personality or "",
        "words_to_use": _loads_list(product.words_to_use),
        "words_to_avoid": _loads_list(product.words_to_avoid),
        "visual_style": product.visual_style or "",
        "visual_exclusions": product.visual_exclusions or "",
        "primary_asset": asset_to_out(primary) if primary else None,
        "asset_count": asset_count,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


# ---------------------------------------------------------------------------
# Product assets
# ---------------------------------------------------------------------------


def create_asset(
    db: Session,
    product_id: str,
    asset_type: str,
    file_path: str,
    thumbnail_path: Optional[str] = None,
    title: str = "",
    description: str = "",
    tags: Optional[list[str]] = None,
    reference_state: Optional[str] = None,
    learning_notes: str = "",
    style_notes: str = "",
) -> ProductAsset:
    is_first = db.query(ProductAsset).filter(ProductAsset.product_id == product_id).count() == 0
    asset = ProductAsset(
        product_id=product_id,
        asset_type=asset_type,
        file_path=file_path,
        thumbnail_path=thumbnail_path,
        title=title,
        description=description,
        tags=_dumps_list(tags or []),
        reference_state=reference_state,
        learning_notes=learning_notes,
        style_notes=style_notes,
        is_primary=is_first,  # the first uploaded asset becomes primary by default
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_asset_link(
    db: Session,
    product_id: str,
    asset_type: str,
    source_url: str,
    title: str = "",
    description: str = "",
    tags: Optional[list[str]] = None,
    reference_state: Optional[str] = None,
    learning_notes: str = "",
    style_notes: str = "",
) -> ProductAsset:
    """A URL-only reference asset (advertisement/reference_video with no
    uploaded file) — never becomes the product's primary image, since a
    primary asset must be a real, renderable product photo."""
    asset = ProductAsset(
        product_id=product_id,
        asset_type=asset_type,
        file_path=None,
        source_url=source_url,
        title=title,
        description=description,
        tags=_dumps_list(tags or []),
        reference_state=reference_state,
        learning_notes=learning_notes,
        style_notes=style_notes,
        is_primary=False,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_assets(
    db: Session,
    product_id: str,
    asset_type: Optional[str] = None,
    active_only: bool = True,
) -> list[ProductAsset]:
    query = db.query(ProductAsset).filter(ProductAsset.product_id == product_id)
    if asset_type:
        query = query.filter(ProductAsset.asset_type == asset_type)
    if active_only:
        query = query.filter(ProductAsset.is_active.is_(True))
    return query.order_by(ProductAsset.is_primary.desc(), ProductAsset.sort_order.asc(), ProductAsset.created_at.desc()).all()


def get_asset(db: Session, asset_id: str) -> Optional[ProductAsset]:
    return db.get(ProductAsset, asset_id)


def update_asset(db: Session, asset_id: str, fields: dict) -> Optional[ProductAsset]:
    asset = db.get(ProductAsset, asset_id)
    if asset is None:
        return None
    fields = dict(fields)
    if "tags" in fields:
        fields["tags"] = _dumps_list(fields.pop("tags"))
    make_primary = fields.pop("is_primary", None)
    for key, value in fields.items():
        if value is not None:
            setattr(asset, key, value)
    if make_primary:
        # Exactly one primary asset per product — demote any current holder.
        db.query(ProductAsset).filter(
            ProductAsset.product_id == asset.product_id, ProductAsset.id != asset.id
        ).update({"is_primary": False})
        asset.is_primary = True
    elif make_primary is False:
        asset.is_primary = False
    asset.updated_at = _now()
    db.commit()
    db.refresh(asset)
    return asset


def deactivate_asset(db: Session, asset_id: str) -> Optional[ProductAsset]:
    return update_asset(db, asset_id, {"is_active": False, "is_primary": False})


def asset_to_out(asset: ProductAsset) -> dict:
    return {
        "id": asset.id,
        "product_id": asset.product_id,
        "asset_type": asset.asset_type.value if hasattr(asset.asset_type, "value") else asset.asset_type,
        "file_path": asset.file_path,
        "thumbnail_path": asset.thumbnail_path,
        "title": asset.title or "",
        "description": asset.description or "",
        "tags": _loads_list(asset.tags),
        "reference_state": asset.reference_state,
        "source_url": asset.source_url,
        "learning_notes": asset.learning_notes or "",
        "style_notes": asset.style_notes or "",
        "sort_order": asset.sort_order or 0,
        "is_primary": bool(asset.is_primary),
        "is_active": bool(asset.is_active),
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


# ---------------------------------------------------------------------------
# Product reference scripts
# ---------------------------------------------------------------------------


def create_reference_script(db: Session, product_id: str, payload: dict) -> ProductReferenceScript:
    script = ProductReferenceScript(product_id=product_id, **payload)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def list_reference_scripts(db: Session, product_id: str, approved_only: bool = False) -> list[ProductReferenceScript]:
    query = db.query(ProductReferenceScript).filter(ProductReferenceScript.product_id == product_id)
    if approved_only:
        query = query.filter(ProductReferenceScript.is_approved.is_(True))
    return query.order_by(ProductReferenceScript.created_at.desc()).all()


def get_reference_script(db: Session, script_id: str) -> Optional[ProductReferenceScript]:
    return db.get(ProductReferenceScript, script_id)


def update_reference_script(db: Session, script_id: str, fields: dict) -> Optional[ProductReferenceScript]:
    script = db.get(ProductReferenceScript, script_id)
    if script is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(script, key, value)
    script.updated_at = _now()
    db.commit()
    db.refresh(script)
    return script


def delete_reference_script(db: Session, script_id: str) -> bool:
    script = db.get(ProductReferenceScript, script_id)
    if script is None:
        return False
    db.delete(script)
    db.commit()
    return True


def reference_script_to_out(script: ProductReferenceScript) -> dict:
    return {
        "id": script.id,
        "product_id": script.product_id,
        "title": script.title or "",
        "script_text": script.script_text,
        "format": script.format,
        "notes": script.notes or "",
        "is_approved": bool(script.is_approved),
        "created_at": script.created_at,
        "updated_at": script.updated_at,
    }


# ---------------------------------------------------------------------------
# Product creative angles
# ---------------------------------------------------------------------------


def create_creative_angle(db: Session, product_id: str, payload: dict) -> ProductCreativeAngle:
    sort_order = db.query(ProductCreativeAngle).filter(ProductCreativeAngle.product_id == product_id).count()
    angle = ProductCreativeAngle(product_id=product_id, sort_order=sort_order, **payload)
    db.add(angle)
    db.commit()
    db.refresh(angle)
    return angle


def list_creative_angles(db: Session, product_id: str) -> list[ProductCreativeAngle]:
    return (
        db.query(ProductCreativeAngle)
        .filter(ProductCreativeAngle.product_id == product_id)
        .order_by(ProductCreativeAngle.sort_order.asc(), ProductCreativeAngle.created_at.asc())
        .all()
    )


def get_creative_angle(db: Session, angle_id: str) -> Optional[ProductCreativeAngle]:
    return db.get(ProductCreativeAngle, angle_id)


def update_creative_angle(db: Session, angle_id: str, fields: dict) -> Optional[ProductCreativeAngle]:
    angle = db.get(ProductCreativeAngle, angle_id)
    if angle is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(angle, key, value)
    angle.updated_at = _now()
    db.commit()
    db.refresh(angle)
    return angle


def delete_creative_angle(db: Session, angle_id: str) -> bool:
    angle = db.get(ProductCreativeAngle, angle_id)
    if angle is None:
        return False
    db.delete(angle)
    db.commit()
    return True


def creative_angle_to_out(angle: ProductCreativeAngle) -> dict:
    return {
        "id": angle.id,
        "product_id": angle.product_id,
        "name": angle.name,
        "description": angle.description or "",
        "target_audience": angle.target_audience or "",
        "emotional_direction": angle.emotional_direction or "",
        "approved_messaging": angle.approved_messaging or "",
        "restricted_messaging": angle.restricted_messaging or "",
        "visual_direction": angle.visual_direction or "",
        "cta_direction": angle.cta_direction or "",
        "sort_order": angle.sort_order or 0,
        "created_at": angle.created_at,
        "updated_at": angle.updated_at,
    }


# ---------------------------------------------------------------------------
# Pipeline-facing product context
# ---------------------------------------------------------------------------


def build_product_context(db: Session, product_id: str, max_reference_excerpts: int = 2) -> Optional[dict]:
    """The compact representation threaded into Script generation / Asset
    Sourcing — see ProductContext in models/product_library.py. Only
    APPROVED reference scripts are eligible, and only a short excerpt of
    each (never the full text) to avoid ballooning the prompt or inviting
    verbatim copying. Creative angles and product-specific hooks are
    similarly compacted to short lines — the full angle/hook records stay in
    the DB for the UI, only enough to steer creative direction goes here."""
    product = db.get(AyushProduct, product_id)
    if product is None:
        return None
    primary = _primary_asset(db, product_id)
    approved_scripts = (
        db.query(ProductReferenceScript)
        .filter(ProductReferenceScript.product_id == product_id, ProductReferenceScript.is_approved.is_(True))
        .order_by(ProductReferenceScript.updated_at.desc())
        .limit(max_reference_excerpts)
        .all()
    )
    excerpts = [s.script_text[:400] for s in approved_scripts]

    angles = list_creative_angles(db, product_id)
    angle_lines = [f"{a.name}: {a.description}" if a.description else a.name for a in angles]

    product_hooks = (
        db.query(Hook)
        .filter(Hook.product_id == product_id)
        .order_by(Hook.usage_count.desc(), Hook.created_at.desc())
        .limit(8)
        .all()
    )
    hook_lines = [h.text for h in product_hooks]

    return {
        "product_id": product.id,
        "name": product.name,
        "category": product.category,
        "short_description": product.short_description or "",
        "usp": product.usp or "",
        "target_audience": product.target_audience or "",
        "primary_problem": product.primary_problem or "",
        "positioning": product.positioning or "",
        "ingredients": _loads_list(product.ingredients),
        "benefits": _loads_list(product.benefits),
        "approved_claims": _loads_list(product.approved_claims),
        "prohibited_claims": _loads_list(product.prohibited_claims),
        "mandatory_wording": product.mandatory_wording or "",
        "preferred_tone": product.preferred_tone or "",
        "preferred_language": product.preferred_language or "",
        "cta_text": product.cta_text or "",
        "winning_hooks": _loads_list(product.winning_hooks),
        "reference_script_excerpts": excerpts,
        "primary_asset_url": f"/product-uploads/{primary.file_path}" if primary else None,
        "never_say": product.never_say or "",
        "preferred_visual_style": product.visual_style or "",
        "visual_exclusions": product.visual_exclusions or "",
        "words_to_use": _loads_list(product.words_to_use),
        "words_to_avoid": _loads_list(product.words_to_avoid),
        "creative_angles": angle_lines,
        "approved_hooks": hook_lines,
        "has_real_product_asset": primary is not None,
    }
