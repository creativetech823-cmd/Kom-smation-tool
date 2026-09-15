"""AyushWellness Product Library — REST API.

Additive to the existing pipeline: nothing here is called by the 7-step
Content Pipeline directly except the read-only `/context` endpoint (used to
thread a selected product's knowledge into Script generation / Asset
Sourcing). Mirrors routers/library.py's structure.
"""

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import httpx

from app.config import settings
from app.db import get_db
from app.models.product_library import (
    ProductAssetImportUrlCreate,
    ProductAssetLinkCreate,
    ProductAssetOut,
    ProductAssetUpdate,
    ProductContext,
    ProductCreate,
    ProductCreativeAngleCreate,
    ProductCreativeAngleOut,
    ProductCreativeAngleUpdate,
    ProductImportRequest,
    ProductImportResult,
    ProductOut,
    ProductReferenceScriptCreate,
    ProductReferenceScriptOut,
    ProductReferenceScriptUpdate,
    ProductUpdate,
)
from app.services import product_import_service, product_library_service as svc
from app.services.content_extraction_service import ExtractionError

logger = logging.getLogger("product_library")

router = APIRouter(prefix="/product-library", tags=["product-library"])

_CHUNK_SIZE = 1024 * 1024
_MAX_BYTES = settings.max_product_upload_mb * 1024 * 1024
_ALLOWED_EXTENSIONS = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".gif": "image",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
}


class ExtractionError(Exception):
    pass


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/products", response_model=list[ProductOut])
def list_products(
    category: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    return [svc.product_to_out(db, p) for p in svc.list_products(db, category, status, q)]


@router.post("/products", response_model=ProductOut)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> dict:
    # Strong signal: the same product page (by normalized URL) already has an
    # active product record — reuse it instead of creating a near-duplicate.
    # Covers the double-click / resubmit-after-refresh / re-import-with-
    # tracking-params cases without a hard DB unique constraint.
    if payload.product_url:
        existing = svc.find_by_normalized_url(db, payload.product_url)
        if existing is not None:
            out = svc.product_to_out(db, existing)
            out["is_existing"] = True
            return out

    product = svc.create_product(db, payload.model_dump())
    out = svc.product_to_out(db, product)

    # Weak signal: same name + category, no URL to match on (or a different
    # URL) — never blocks creation, just a heads-up for the caller.
    possible_dup = svc.find_possible_duplicate_by_name(db, payload.name, payload.category, exclude_id=product.id)
    if possible_dup is not None:
        out["possible_duplicate"] = {"id": possible_dup.id, "name": possible_dup.name}

    return out


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)) -> dict:
    product = svc.get_product(db, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return svc.product_to_out(db, product)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdate, db: Session = Depends(get_db)) -> dict:
    product = svc.update_product(db, product_id, payload.model_dump(exclude_unset=True))
    if product is None:
        raise HTTPException(404, "Product not found")
    return svc.product_to_out(db, product)


@router.post("/products/{product_id}/archive", response_model=ProductOut)
def archive_product(product_id: str, db: Session = Depends(get_db)) -> dict:
    product = svc.archive_product(db, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return svc.product_to_out(db, product)


@router.post("/products/{product_id}/restore", response_model=ProductOut)
def restore_product(product_id: str, db: Session = Depends(get_db)) -> dict:
    product = svc.restore_product(db, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return svc.product_to_out(db, product)


@router.get("/products/{product_id}/context", response_model=ProductContext)
def get_product_context(product_id: str, db: Session = Depends(get_db)) -> dict:
    """Pipeline-facing: the compact knowledge blob Script generation / Asset
    Sourcing actually consume for this product."""
    context = svc.build_product_context(db, product_id)
    if context is None:
        raise HTTPException(404, "Product not found")
    return context


@router.post("/import-url", response_model=ProductImportResult)
def import_product_url(payload: ProductImportRequest) -> ProductImportResult:
    """Add Product's URL-import step — fetches a public product page and
    returns a best-effort, editable draft. Never saves anything; the
    frontend shows this as a review step before POST /products actually
    creates a product."""
    try:
        return product_import_service.import_product_from_url(payload.url)
    except ExtractionError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        logger.exception("Unhandled error importing product from URL")
        raise HTTPException(502, f"Couldn't import that product page: {e}")


# ---------------------------------------------------------------------------
# Product assets
# ---------------------------------------------------------------------------


def _safe_stored_name(ext: str) -> str:
    # Never use the caller's own filename for the on-disk path — a fresh
    # random id + a whitelisted extension makes path traversal and filename
    # collisions structurally impossible, matching content_extraction_service's
    # reference-upload convention.
    return f"{uuid4().hex[:16]}{ext}"


@router.post("/products/{product_id}/assets", response_model=ProductAssetOut)
async def upload_product_asset(
    product_id: str,
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    reference_state: Optional[str] = Form(None),
    learning_notes: str = Form(""),
    style_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    if svc.get_product(db, product_id) is None:
        raise HTTPException(404, "Product not found")

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext or filename}'. Allowed: images and mp4/mov/webm video.")

    uploads_dir = Path(settings.product_uploads_dir).resolve() / product_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = _safe_stored_name(ext)
    stored_path = uploads_dir / stored_name

    total = 0
    try:
        with open(stored_path, "wb") as out:
            while chunk := await file.read(_CHUNK_SIZE):
                total += len(chunk)
                if total > _MAX_BYTES:
                    out.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(
                        400, f"File is larger than the {settings.max_product_upload_mb}MB limit."
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        stored_path.unlink(missing_ok=True)
        logger.exception("Unhandled error saving product asset upload")
        raise HTTPException(502, f"Couldn't save that file: {e}")

    # Relative path (product_id/filename) — resolved against the
    # /product-uploads static mount by the frontend, never an absolute
    # filesystem path exposed to the client.
    relative_path = f"{product_id}/{stored_name}"
    asset = svc.create_asset(
        db,
        product_id=product_id,
        asset_type=asset_type,
        file_path=relative_path,
        title=title,
        description=description,
        reference_state=reference_state,
        learning_notes=learning_notes,
        style_notes=style_notes,
    )
    return svc.asset_to_out(asset)


@router.post("/products/{product_id}/assets/link", response_model=ProductAssetOut)
def link_product_asset(product_id: str, payload: ProductAssetLinkCreate, db: Session = Depends(get_db)) -> dict:
    """A URL-only reference asset (advertisement/reference_video) — no file
    upload, just an external link plus curator notes on what to learn from
    it. Distinct from the multipart /assets upload route above."""
    if svc.get_product(db, product_id) is None:
        raise HTTPException(404, "Product not found")
    asset = svc.create_asset_link(
        db,
        product_id=product_id,
        asset_type=payload.asset_type,
        source_url=payload.source_url,
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        reference_state=payload.reference_state,
        learning_notes=payload.learning_notes,
        style_notes=payload.style_notes,
    )
    return svc.asset_to_out(asset)


@router.post("/products/{product_id}/assets/import-url", response_model=ProductAssetOut)
def import_product_asset_from_url(
    product_id: str, payload: ProductAssetImportUrlCreate, db: Session = Depends(get_db)
) -> dict:
    """Fetches an externally-hosted image server-side (e.g. one of the URL
    importer's discovered product photos) and stores it exactly like a
    direct upload — a real file_path, eligible to become the primary/real-
    product asset. Distinct from /assets/link, which only stores the URL
    itself for reference material (ads, videos) with no preview file."""
    if svc.get_product(db, product_id) is None:
        raise HTTPException(404, "Product not found")

    clean_path = Path(urlparse(payload.source_url).path)
    ext = clean_path.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported image type '{ext or clean_path.name}'.")

    try:
        with httpx.stream("GET", payload.source_url, timeout=20.0, follow_redirects=True) as resp:
            resp.raise_for_status()
            uploads_dir = Path(settings.product_uploads_dir).resolve() / product_id
            uploads_dir.mkdir(parents=True, exist_ok=True)
            stored_name = _safe_stored_name(ext)
            stored_path = uploads_dir / stored_name
            total = 0
            try:
                with open(stored_path, "wb") as out:
                    for chunk in resp.iter_bytes(_CHUNK_SIZE):
                        total += len(chunk)
                        if total > _MAX_BYTES:
                            out.close()
                            stored_path.unlink(missing_ok=True)
                            raise HTTPException(
                                400, f"Image is larger than the {settings.max_product_upload_mb}MB limit."
                            )
                        out.write(chunk)
            except HTTPException:
                raise
            except Exception:
                stored_path.unlink(missing_ok=True)
                raise
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Couldn't fetch that image: {e}")

    relative_path = f"{product_id}/{stored_name}"
    asset = svc.create_asset(
        db,
        product_id=product_id,
        asset_type=payload.asset_type,
        file_path=relative_path,
        title=payload.title,
        source_url=payload.source_url,
    )
    return svc.asset_to_out(asset)


@router.get("/products/{product_id}/assets", response_model=list[ProductAssetOut])
def list_product_assets(
    product_id: str,
    asset_type: Optional[str] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    assets = svc.list_assets(db, product_id, asset_type, active_only=not include_inactive)
    return [svc.asset_to_out(a) for a in assets]


@router.patch("/assets/{asset_id}", response_model=ProductAssetOut)
def update_product_asset(asset_id: str, payload: ProductAssetUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        asset = svc.update_asset(db, asset_id, payload.model_dump(exclude_unset=True))
    except ValueError as e:
        # Reference material can never become primary — see update_asset's guard.
        raise HTTPException(400, str(e))
    if asset is None:
        raise HTTPException(404, "Asset not found")
    return svc.asset_to_out(asset)


@router.delete("/assets/{asset_id}", status_code=204)
def deactivate_product_asset(asset_id: str, db: Session = Depends(get_db)) -> None:
    """Soft-delete only — matches the project's "detach/deactivate, don't
    destroy" convention (see library_service.delete_project). The file stays
    on disk; the row is marked inactive so it drops out of asset sourcing
    and the UI's default asset list."""
    if svc.deactivate_asset(db, asset_id) is None:
        raise HTTPException(404, "Asset not found")


# ---------------------------------------------------------------------------
# Product reference scripts
# ---------------------------------------------------------------------------


@router.post("/products/{product_id}/reference-scripts", response_model=ProductReferenceScriptOut)
def create_reference_script(
    product_id: str, payload: ProductReferenceScriptCreate, db: Session = Depends(get_db)
) -> dict:
    if svc.get_product(db, product_id) is None:
        raise HTTPException(404, "Product not found")
    script = svc.create_reference_script(db, product_id, payload.model_dump())
    return svc.reference_script_to_out(script)


@router.get("/products/{product_id}/reference-scripts", response_model=list[ProductReferenceScriptOut])
def list_reference_scripts(
    product_id: str, approved_only: bool = False, db: Session = Depends(get_db)
) -> list[dict]:
    return [svc.reference_script_to_out(s) for s in svc.list_reference_scripts(db, product_id, approved_only)]


@router.patch("/reference-scripts/{script_id}", response_model=ProductReferenceScriptOut)
def update_reference_script(
    script_id: str, payload: ProductReferenceScriptUpdate, db: Session = Depends(get_db)
) -> dict:
    script = svc.update_reference_script(db, script_id, payload.model_dump(exclude_unset=True))
    if script is None:
        raise HTTPException(404, "Reference script not found")
    return svc.reference_script_to_out(script)


@router.delete("/reference-scripts/{script_id}", status_code=204)
def delete_reference_script(script_id: str, db: Session = Depends(get_db)) -> None:
    if not svc.delete_reference_script(db, script_id):
        raise HTTPException(404, "Reference script not found")


# ---------------------------------------------------------------------------
# Product creative angles
# ---------------------------------------------------------------------------


@router.post("/products/{product_id}/creative-angles", response_model=ProductCreativeAngleOut)
def create_creative_angle(
    product_id: str, payload: ProductCreativeAngleCreate, db: Session = Depends(get_db)
) -> dict:
    if svc.get_product(db, product_id) is None:
        raise HTTPException(404, "Product not found")
    angle = svc.create_creative_angle(db, product_id, payload.model_dump())
    return svc.creative_angle_to_out(angle)


@router.get("/products/{product_id}/creative-angles", response_model=list[ProductCreativeAngleOut])
def list_creative_angles(product_id: str, db: Session = Depends(get_db)) -> list[dict]:
    return [svc.creative_angle_to_out(a) for a in svc.list_creative_angles(db, product_id)]


@router.patch("/creative-angles/{angle_id}", response_model=ProductCreativeAngleOut)
def update_creative_angle(angle_id: str, payload: ProductCreativeAngleUpdate, db: Session = Depends(get_db)) -> dict:
    angle = svc.update_creative_angle(db, angle_id, payload.model_dump(exclude_unset=True))
    if angle is None:
        raise HTTPException(404, "Creative angle not found")
    return svc.creative_angle_to_out(angle)


@router.delete("/creative-angles/{angle_id}", status_code=204)
def delete_creative_angle(angle_id: str, db: Session = Depends(get_db)) -> None:
    if not svc.delete_creative_angle(db, angle_id):
        raise HTTPException(404, "Creative angle not found")
