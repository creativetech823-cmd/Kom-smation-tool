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
