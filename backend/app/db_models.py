import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AssetType(str, enum.Enum):
    script = "script"
    image = "image"
    video = "video"
    voiceover = "voiceover"
    render = "render"


class TemplateKind(str, enum.Enum):
    static = "static"
    video = "video"


class HistoryEventType(str, enum.Enum):
    created_project = "created_project"
    generated_script = "generated_script"
    generated_image = "generated_image"
    generated_video = "generated_video"
    generated_voiceover = "generated_voiceover"
    used_template = "used_template"
    used_hook = "used_hook"
    edited_script = "edited_script"
    exported_video = "exported_video"
    deleted_content = "deleted_content"
    restored_content = "restored_content"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(32), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    product_category = Column(String(100), default="")
    status = Column(String(30), default="active")
    # Full serialized Content Pipeline wizard state (product/story/script/
    # assets/voiceover/render + edit history) for this project, so a browser
    # refresh mid-pipeline restores exactly where the user left off.
    pipeline_state = Column(Text, nullable=True)
    pipeline_stage = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    assets = relationship("ContentAsset", back_populates="project")


class ContentAsset(Base):
    __tablename__ = "content_assets"

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=True, index=True)
    asset_type = Column(SAEnum(AssetType), nullable=False, index=True)
    title = Column(String(300), default="")
    product_name = Column(String(300), default="")
    file_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    content_json = Column(Text, nullable=True)
    source_hook_id = Column(String(32), ForeignKey("hooks.id"), nullable=True)
    source_hook_text = Column(Text, nullable=True)
    model_used = Column(String(120), nullable=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_now, index=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="assets")


class Hook(Base):
    __tablename__ = "hooks"

    id = Column(String(32), primary_key=True, default=_uuid)
    text = Column(Text, nullable=False)
    category = Column(String(50), index=True)
    platform = Column(String(50), index=True)
    tone = Column(String(50), index=True)
    usage_count = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_now)
    # Nullable — most hooks stay global/unassociated. Set when a hook was
    # captured as a "winning hook" for a specific AyushWellness product.
    # Added after the table already existed in production DBs, so this
    # column also has an entry in app/db.py's run_lightweight_migrations().
    product_id = Column(String(32), ForeignKey("ayush_products.id"), nullable=True, index=True)


class Template(Base):
    __tablename__ = "templates"

    id = Column(String(32), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    kind = Column(SAEnum(TemplateKind), nullable=False, index=True)
    category = Column(String(100), default="", index=True)
    description = Column(Text, default="")
    thumbnail_key = Column(String(60), default="")
    is_official = Column(Boolean, default=False, index=True)
    config_json = Column(Text, nullable=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=_now)


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id = Column(String(32), primary_key=True, default=_uuid)
    event_type = Column(SAEnum(HistoryEventType), nullable=False)
    summary = Column(String(500), default="")
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=True, index=True)
    asset_id = Column(String(32), ForeignKey("content_assets.id"), nullable=True)
    created_at = Column(DateTime, default=_now, index=True)


# ---------------------------------------------------------------------------
# AyushWellness Product Library
# ---------------------------------------------------------------------------
#
# Additive feature: real product knowledge + real product assets that the
# Content Pipeline can optionally draw on instead of (never in place of) the
# existing manual Product step. Every array-shaped field (ingredients,
# benefits, approved_claims, ...) is stored as JSON text, matching the
# content_json/config_json convention used by ContentAsset/Template above —
# (de)serialized in product_library_service.py, never queried directly.


class ProductCategory(str, enum.Enum):
    """Extensible on purpose — the UI ships with two categories, but this is
    a plain string column (not a DB-level CHECK constraint) so a third
    category can be added later without a migration."""

    herbal_health = "herbal_health"
    nutraceuticals = "nutraceuticals"


class ProductAssetType(str, enum.Enum):
    """Two disjoint groups — see product_library_service.REAL_PRODUCT_ASSET_TYPES
    for the authoritative classification used everywhere primary-eligibility
    matters (header image, pipeline product context, asset sourcing).

    REAL PRODUCT (genuine photography of the actual product — eligible to
    become the primary/hero asset):
        product_image, product_packshot, product_lifestyle, ingredient_image

    REFERENCE MATERIAL (inspiration/context — never eligible to become
    primary, no matter how it was added):
        reference_image, advertisement, reference_video, other
    """

    product_image = "product_image"
    product_packshot = "product_packshot"
    product_lifestyle = "product_lifestyle"
    ingredient_image = "ingredient_image"
    reference_image = "reference_image"
    advertisement = "advertisement"
    reference_video = "reference_video"
    other = "other"


class AyushProduct(Base):
    __tablename__ = "ayush_products"

    id = Column(String(32), primary_key=True, default=_uuid)
    name = Column(String(300), nullable=False)
    slug = Column(String(320), unique=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # ProductCategory value; plain string, see above
    status = Column(String(20), default="active", index=True)  # active | archived

    short_description = Column(Text, default="")
    description = Column(Text, default="")
    product_url = Column(String(500), nullable=True)
    price = Column(String(50), nullable=True)  # free-text ("₹299") — not used in arithmetic anywhere

    # BASIC INFO — identity fields beyond name/category, added for the
    # multi-product catalog (subcategory/brand/SKU distinguish product
    # variants like "... New - Ziplock Big Pouches" from the base product).
    display_name = Column(String(300), default="")  # shown in UI when set; falls back to name
    subcategory = Column(String(200), default="")
    brand = Column(String(200), default="")
    sku = Column(String(100), default="")

    # PRODUCT PAGE / WEBSITE — product_url above is the primary store link;
    # these cover the additional reference/marketplace links a product may have.
    marketplace_urls = Column(Text, nullable=True)  # JSON list[str]
    landing_page_url = Column(String(500), nullable=True)

    # PRODUCT KNOWLEDGE
    target_audience = Column(Text, default="")
    primary_problem = Column(Text, default="")
    positioning = Column(Text, default="")
    usp = Column(Text, default="")
    ingredients = Column(Text, nullable=True)  # JSON list[str]
    benefits = Column(Text, nullable=True)  # JSON list[str]
    usage = Column(Text, default="")  # "how to use"
    how_it_works = Column(Text, default="")
    who_is_it_for = Column(Text, default="")
    cautions = Column(Text, default="")

    # CLAIMS — the only claim vocabulary Script generation is allowed to draw
    # on for this product; prohibited_claims are an explicit denylist passed
    # into the compliance-aware script prompt, never silently dropped.
    approved_claims = Column(Text, nullable=True)  # JSON list[str]
    prohibited_claims = Column(Text, nullable=True)  # JSON list[str]
    mandatory_wording = Column(Text, default="")
    # Brand-voice guardrail distinct from prohibited_claims: things that are
    # not compliance violations but simply shouldn't be said about this
    # product (off-brand, off-strategy) — e.g. "don't call it a cure-all".
    never_say = Column(Text, default="")

    # TARGET CUSTOMER — beyond target_audience/pain_points/emotional_triggers.
    secondary_target_audience = Column(Text, default="")
    customer_objections = Column(Text, nullable=True)  # JSON list[str]
    buying_triggers = Column(Text, nullable=True)  # JSON list[str]
    awareness_level = Column(String(200), default="")

    # CREATIVE KNOWLEDGE
    pain_points = Column(Text, nullable=True)  # JSON list[str]
    emotional_triggers = Column(Text, nullable=True)  # JSON list[str]
    advertising_angles = Column(Text, nullable=True)  # JSON list[str]
    preferred_tone = Column(String(200), default="")
    preferred_language = Column(String(50), default="")
    cta_text = Column(Text, default="")
    winning_hooks = Column(Text, nullable=True)  # JSON list[str] — freeform, distinct from the Hook table
    creative_notes = Column(Text, default="")
    # BRAND / CREATIVE DIRECTION — feeds visual-tag generation and asset ranking.
    brand_personality = Column(Text, default="")
    words_to_use = Column(Text, nullable=True)  # JSON list[str]
    words_to_avoid = Column(Text, nullable=True)  # JSON list[str]
    visual_style = Column(Text, default="")
    visual_exclusions = Column(Text, default="")  # things that should NOT appear visually

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    assets = relationship("ProductAsset", back_populates="product")
    reference_scripts = relationship("ProductReferenceScript", back_populates="product")
    creative_angles = relationship("ProductCreativeAngle", back_populates="product")


class ProductAsset(Base):
    __tablename__ = "product_assets"

    id = Column(String(32), primary_key=True, default=_uuid)
    product_id = Column(String(32), ForeignKey("ayush_products.id"), nullable=False, index=True)
    asset_type = Column(SAEnum(ProductAssetType), nullable=False, index=True)

    # Nullable so a "reference ad" / "reference video" can be a bare external
    # URL (e.g. a competitor ad or YouTube link) with no uploaded file — see
    # source_url below. An uploaded asset still requires file_path; enforced
    # in product_library_service, not at the column level.
    file_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    title = Column(String(300), default="")
    description = Column(Text, default="")
    tags = Column(Text, nullable=True)  # JSON list[str]
    # Free-text lifecycle marker per the spec's "Reference / Approved /
    # Primary / Inspiration" states — deliberately not an enum: these are
    # curatorial labels a user assigns, not states the system enforces.
    reference_state = Column(String(20), nullable=True)

    # Reference-material fields — only meaningful for asset_type in
    # (advertisement, reference_video), left blank for plain product photos.
    # Consolidated into one style_notes field (rather than separate
    # hook_style/visual_style/editing_style/cta_style columns) since these
    # are always authored together as free-form curator notes, not queried
    # individually.
    source_url = Column(String(1000), nullable=True)  # external reference URL when there's no uploaded file
    learning_notes = Column(Text, default="")  # what the AI/creative team should learn from this reference
    style_notes = Column(Text, default="")  # hook/visual/editing/CTA style observations

    sort_order = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime, default=_now, index=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    product = relationship("AyushProduct", back_populates="assets")


class ProductCreativeAngle(Base):
    """A user-authored advertising angle for one product (e.g. "Tobacco-free
    alternative", "Daily habit reset") — distinct from winning_hooks (single
    lines) and advertising_angles (a freeform list on AyushProduct): an angle
    here carries its own targeting/messaging/visual direction so it can be
    picked as a structured creative brief, not just a label."""

    __tablename__ = "product_creative_angles"

    id = Column(String(32), primary_key=True, default=_uuid)
    product_id = Column(String(32), ForeignKey("ayush_products.id"), nullable=False, index=True)

    name = Column(String(300), nullable=False)
    description = Column(Text, default="")
    target_audience = Column(Text, default="")
    emotional_direction = Column(Text, default="")
    approved_messaging = Column(Text, default="")
    restricted_messaging = Column(Text, default="")
    visual_direction = Column(Text, default="")
    cta_direction = Column(Text, default="")

    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    product = relationship("AyushProduct", back_populates="creative_angles")


class ProductReferenceScript(Base):
    __tablename__ = "product_reference_scripts"

    id = Column(String(32), primary_key=True, default=_uuid)
    product_id = Column(String(32), ForeignKey("ayush_products.id"), nullable=False, index=True)
    title = Column(String(300), default="")
    script_text = Column(Text, nullable=False)
    format = Column(String(50), nullable=True)
    notes = Column(Text, default="")
    is_approved = Column(Boolean, default=False, index=True)

    # Real-reference import metadata (2026-09-19 task) — all nullable/blank
    # for user-authored rows, populated only by
    # reference_script_service.import_calender_references(). reference_key
    # is the stable idempotency key AND the join key to
    # creative_reference_dna.REFERENCE_RECORDS.video_id (the structured
    # hook_device/human_insight/proof_device/payoff DNA lives there — one
    # source of truth, deliberately not duplicated into columns here).
    source_document = Column(String(300), nullable=True)
    reference_key = Column(String(64), nullable=True, index=True)
    creative_direction = Column(String(100), nullable=True)
    creative_mechanism = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    product = relationship("AyushProduct", back_populates="reference_scripts")


class CreativeConceptRecord(Base):
    """One row per fresh script generation's chosen creative territory —
    the "creative diversity memory" premise generation and architecture
    selection consult before the NEXT fresh generation for the same
    product, so independent generate_script() calls (not just an explicit
    regenerate) stop converging on the same device. Deliberately not tied
    to ayush_products via a FK: a manually-entered product (no Product
    Library entry) still needs this tracked, keyed by a stable signature
    derived from product name + category instead (see
    creative_memory_service.product_key())."""

    __tablename__ = "creative_concept_records"

    id = Column(String(32), primary_key=True, default=_uuid)
    product_key = Column(String(200), nullable=False, index=True)
    architecture_key = Column(String(64), default="")
    creative_device = Column(Text, default="")
    visual_device = Column(Text, default="")
    emotional_engine = Column(Text, default="")
    narrative_device = Column(Text, default="")
    insight_statement = Column(Text, default="")
    premise_statement = Column(Text, default="")
    # Territory-level fields (creative_territory_service) — one abstraction
    # level above premise/device: the underlying human/behavioural lens, not
    # the specific situation or execution. Added after this table already
    # shipped — see db.run_lightweight_migrations().
    territory_name = Column(Text, default="")
    human_tension = Column(Text, default="")
    creative_question = Column(Text, default="")
    created_at = Column(DateTime, default=_now, index=True)
