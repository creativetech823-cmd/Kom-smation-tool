from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AssetTypeLiteral = Literal["script", "image", "video", "voiceover", "render"]
TemplateKindLiteral = Literal["static", "video"]
HistoryEventTypeLiteral = Literal[
    "created_project",
    "generated_script",
    "generated_image",
    "generated_video",
    "generated_voiceover",
    "used_template",
    "used_hook",
    "edited_script",
    "exported_video",
    "deleted_content",
    "restored_content",
]


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    product_category: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    product_category: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str = ""
    product_category: str = ""
    status: str = "active"
    pipeline_state: Optional[dict] = None
    pipeline_stage: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    asset_count: int = 0


class ProjectStateUpdate(BaseModel):
    """Autosave payload from the Content Pipeline — always the full current
    snapshot (not a diff), so a save is safe to retry/replace wholesale."""

    pipeline_state: dict
    pipeline_stage: str = Field(..., min_length=1, max_length=40)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    product_category: Optional[str] = None


# ---------------------------------------------------------------------------
# Content assets
# ---------------------------------------------------------------------------


class ContentAssetCreate(BaseModel):
    project_id: Optional[str] = None
    asset_type: AssetTypeLiteral
    title: str = ""
    product_name: str = ""
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    content_json: Optional[dict] = None
    source_hook_id: Optional[str] = None
    source_hook_text: Optional[str] = None
    model_used: Optional[str] = None
    is_favorite: bool = False


class ContentAssetUpdate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = None
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    content_json: Optional[dict] = None
    is_favorite: Optional[bool] = None


class ContentAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: Optional[str] = None
    asset_type: str
    title: str = ""
    product_name: str = ""
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    content_json: Optional[dict] = None
    source_hook_id: Optional[str] = None
    source_hook_text: Optional[str] = None
    model_used: Optional[str] = None
    is_favorite: bool = False
    created_at: datetime
    updated_at: datetime
    project_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class HookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    text: str
    category: str
    platform: str
    tone: str
    usage_count: int = 0
    is_favorite: bool = False
    created_at: datetime


class HookUpdate(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    platform: Optional[str] = None
    tone: Optional[str] = None
    is_favorite: Optional[bool] = None


class HookListResult(BaseModel):
    items: list[HookOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TemplateCreate(BaseModel):
    name: Optional[str] = None
    kind: Optional[TemplateKindLiteral] = None
    category: str = ""
    description: str = ""
    thumbnail_key: str = ""
    config_json: Optional[dict] = None
    duplicate_from: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    config_json: Optional[dict] = None
    is_favorite: Optional[bool] = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    category: str = ""
    description: str = ""
    thumbnail_key: str = ""
    is_official: bool = False
    config_json: Optional[dict] = None
    is_favorite: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class HistoryEventCreate(BaseModel):
    event_type: HistoryEventTypeLiteral
    summary: str = ""
    project_id: Optional[str] = None
    asset_id: Optional[str] = None


class HistoryEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    summary: str = ""
    project_id: Optional[str] = None
    asset_id: Optional[str] = None
    created_at: datetime
    project_name: Optional[str] = None
