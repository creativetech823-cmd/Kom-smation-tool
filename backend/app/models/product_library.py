"""AyushWellness Product Library — API schemas.

Mirrors the shape of app/models/library.py (Pydantic request/response
contracts; the real persistence layer is the ORM classes in app/db_models.py,
built and serialized by app/services/product_library_service.py). Every
list[str]-shaped field here is stored as JSON text on the ORM side and
(de)serialized in the service layer, matching the ContentAsset/Template
content_json convention.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Only name/category/description are required — everything else can be
    filled in later via ProductUpdate. Category is a plain string (not a
    strict enum) so a third category can be added without a backend change."""

    name: str = Field(..., min_length=1, max_length=300)
    category: str = Field(..., min_length=1, max_length=50)
    short_description: str = ""
    description: str = ""
    product_url: Optional[str] = None
    price: Optional[str] = None

    display_name: str = ""
    subcategory: str = ""
    brand: str = ""
    sku: str = ""
    marketplace_urls: list[str] = Field(default_factory=list)
    landing_page_url: Optional[str] = None

    target_audience: str = ""
    primary_problem: str = ""
    positioning: str = ""
    usp: str = ""
    ingredients: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    usage: str = ""
    how_it_works: str = ""
    who_is_it_for: str = ""
    cautions: str = ""

    approved_claims: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    mandatory_wording: str = ""
    never_say: str = ""

    secondary_target_audience: str = ""
    customer_objections: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    awareness_level: str = ""

    pain_points: list[str] = Field(default_factory=list)
    emotional_triggers: list[str] = Field(default_factory=list)
    advertising_angles: list[str] = Field(default_factory=list)
    preferred_tone: str = ""
    preferred_language: str = ""
    cta_text: str = ""
    winning_hooks: list[str] = Field(default_factory=list)
    creative_notes: str = ""
    brand_personality: str = ""
    words_to_use: list[str] = Field(default_factory=list)
    words_to_avoid: list[str] = Field(default_factory=list)
    visual_style: str = ""
    visual_exclusions: str = ""


class ProductUpdate(BaseModel):
    """All-optional partial update — every field from ProductCreate, unset
    fields left untouched (router calls model_dump(exclude_unset=True))."""

    name: Optional[str] = Field(None, min_length=1, max_length=300)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    product_url: Optional[str] = None
    price: Optional[str] = None

    display_name: Optional[str] = None
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    marketplace_urls: Optional[list[str]] = None
    landing_page_url: Optional[str] = None

    target_audience: Optional[str] = None
    primary_problem: Optional[str] = None
    positioning: Optional[str] = None
    usp: Optional[str] = None
    ingredients: Optional[list[str]] = None
    benefits: Optional[list[str]] = None
    usage: Optional[str] = None
    how_it_works: Optional[str] = None
    who_is_it_for: Optional[str] = None
    cautions: Optional[str] = None

    approved_claims: Optional[list[str]] = None
    prohibited_claims: Optional[list[str]] = None
    mandatory_wording: Optional[str] = None
    never_say: Optional[str] = None

    secondary_target_audience: Optional[str] = None
    customer_objections: Optional[list[str]] = None
    buying_triggers: Optional[list[str]] = None
    awareness_level: Optional[str] = None

    pain_points: Optional[list[str]] = None
    emotional_triggers: Optional[list[str]] = None
    advertising_angles: Optional[list[str]] = None
    preferred_tone: Optional[str] = None
    preferred_language: Optional[str] = None
    cta_text: Optional[str] = None
    winning_hooks: Optional[list[str]] = None
    creative_notes: Optional[str] = None
    brand_personality: Optional[str] = None
    words_to_use: Optional[list[str]] = None
    words_to_avoid: Optional[list[str]] = None
    visual_style: Optional[str] = None
    visual_exclusions: Optional[str] = None


class ProductOut(BaseModel):
    id: str
    name: str
    slug: str
    category: str
    status: str
    short_description: str
    description: str
    product_url: Optional[str] = None
    price: Optional[str] = None

    display_name: str
    subcategory: str
    brand: str
    sku: str
    marketplace_urls: list[str]
    landing_page_url: Optional[str] = None

    target_audience: str
    primary_problem: str
    positioning: str
    usp: str
    ingredients: list[str]
    benefits: list[str]
    usage: str
    how_it_works: str
    who_is_it_for: str
    cautions: str

    approved_claims: list[str]
    prohibited_claims: list[str]
    mandatory_wording: str
    never_say: str

    secondary_target_audience: str
    customer_objections: list[str]
    buying_triggers: list[str]
    awareness_level: str

    pain_points: list[str]
    emotional_triggers: list[str]
    advertising_angles: list[str]
    preferred_tone: str
    preferred_language: str
    cta_text: str
    winning_hooks: list[str]
    creative_notes: str
    brand_personality: str
    words_to_use: list[str]
    words_to_avoid: list[str]
    visual_style: str
    visual_exclusions: str

    primary_asset: Optional["ProductAssetOut"] = None
    asset_count: int = 0

    created_at: datetime
    updated_at: datetime


class ProductAssetCreate(BaseModel):
    """Metadata accompanying a multipart file upload — sent as form fields
    alongside the file, not JSON body (see the /assets/upload route)."""

    asset_type: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    reference_state: Optional[str] = None
    learning_notes: str = ""
    style_notes: str = ""


class ProductAssetLinkCreate(BaseModel):
    """A URL-only reference asset (advertisement/reference_video) with no
    uploaded file — e.g. a competitor ad or YouTube link. See the
    /assets/link route, distinct from the multipart /assets/upload route."""

    asset_type: str
    source_url: str = Field(..., min_length=1)
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    reference_state: Optional[str] = None
    learning_notes: str = ""
    style_notes: str = ""


class ProductAssetUpdate(BaseModel):
    asset_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    reference_state: Optional[str] = None
    sort_order: Optional[int] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    source_url: Optional[str] = None
    learning_notes: Optional[str] = None
    style_notes: Optional[str] = None


class ProductAssetOut(BaseModel):
    id: str
    product_id: str
    asset_type: str
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    title: str
    description: str
    tags: list[str]
    reference_state: Optional[str] = None
    source_url: Optional[str] = None
    learning_notes: str = ""
    style_notes: str = ""
    sort_order: int
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


ProductOut.model_rebuild()


class ProductCreativeAngleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    target_audience: str = ""
    emotional_direction: str = ""
    approved_messaging: str = ""
    restricted_messaging: str = ""
    visual_direction: str = ""
    cta_direction: str = ""


class ProductCreativeAngleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    target_audience: Optional[str] = None
    emotional_direction: Optional[str] = None
    approved_messaging: Optional[str] = None
    restricted_messaging: Optional[str] = None
    visual_direction: Optional[str] = None
    cta_direction: Optional[str] = None
    sort_order: Optional[int] = None


class ProductCreativeAngleOut(BaseModel):
    id: str
    product_id: str
    name: str
    description: str
    target_audience: str
    emotional_direction: str
    approved_messaging: str
    restricted_messaging: str
    visual_direction: str
    cta_direction: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ProductReferenceScriptCreate(BaseModel):
    title: str = ""
    script_text: str = Field(..., min_length=1)
    format: Optional[str] = None
    notes: str = ""
    is_approved: bool = False


class ProductReferenceScriptUpdate(BaseModel):
    title: Optional[str] = None
    script_text: Optional[str] = None
    format: Optional[str] = None
    notes: Optional[str] = None
    is_approved: Optional[bool] = None


class ProductReferenceScriptOut(BaseModel):
    id: str
    product_id: str
    title: str
    script_text: str
    format: Optional[str] = None
    notes: str
    is_approved: bool
    created_at: datetime
    updated_at: datetime


class ProductContext(BaseModel):
    """The compact, pipeline-facing representation of a Product Library
    product — what actually gets threaded into Script generation / Asset
    Sourcing. Deliberately excludes raw reference-script text (too large to
    push into every LLM call) and internal fields (slug/status/timestamps).
    A handful of the most relevant approved reference scripts are included
    by title/summary only; script_service decides how much of that to use."""

    product_id: str
    name: str
    category: str
    short_description: str
    usp: str
    target_audience: str
    primary_problem: str
    positioning: str
    ingredients: list[str]
    benefits: list[str]
    approved_claims: list[str]
    prohibited_claims: list[str]
    mandatory_wording: str
    preferred_tone: str
    preferred_language: str
    cta_text: str
    winning_hooks: list[str]
    reference_script_excerpts: list[str] = Field(default_factory=list)
    primary_asset_url: Optional[str] = None

    never_say: str = ""
    preferred_visual_style: str = ""
    visual_exclusions: str = ""
    words_to_use: list[str] = Field(default_factory=list)
    words_to_avoid: list[str] = Field(default_factory=list)
    # Compact "name: description" lines — the full angle record (targeting/
    # messaging/visual/CTA direction) stays in the DB; only enough to steer
    # creative direction goes into the LLM-facing context.
    creative_angles: list[str] = Field(default_factory=list)
    # Product-specific Hook Studio hooks (Hook.product_id == this product),
    # text only — distinct from winning_hooks (freeform list on the product
    # record itself).
    approved_hooks: list[str] = Field(default_factory=list)
    has_real_product_asset: bool = False
