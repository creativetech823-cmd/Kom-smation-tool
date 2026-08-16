from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.library import (
    ContentAssetCreate,
    ContentAssetOut,
    ContentAssetUpdate,
    HistoryEventCreate,
    HistoryEventOut,
    HookListResult,
    HookOut,
    HookUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectStateUpdate,
    ProjectUpdate,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from app.services import library_service as svc

router = APIRouter(prefix="/library", tags=["library"])


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(status: Optional[str] = None, db: Session = Depends(get_db)) -> list[dict]:
    return [svc.project_to_out(db, p) for p in svc.list_projects(db, status)]


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = svc.create_project(db, payload.name, payload.description, payload.product_category)
    return svc.project_to_out(db, project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = svc.get_project(db, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return svc.project_to_out(db, project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> dict:
    project = svc.update_project(db, project_id, payload.model_dump(exclude_unset=True))
    if project is None:
        raise HTTPException(404, "Project not found")
    return svc.project_to_out(db, project)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    if not svc.delete_project(db, project_id):
        raise HTTPException(404, "Project not found")


@router.patch("/projects/{project_id}/state", response_model=ProjectOut)
def save_pipeline_state(project_id: str, payload: ProjectStateUpdate, db: Session = Depends(get_db)) -> dict:
    """Content Pipeline autosave — persists the full wizard snapshot + current
    stage so a browser refresh restores exactly where the user left off."""
    project = svc.save_pipeline_state(
        db, project_id, payload.pipeline_state, payload.pipeline_stage, payload.name, payload.product_category
    )
    if project is None:
        raise HTTPException(404, "Project not found")
    return svc.project_to_out(db, project)


# ---------------------------------------------------------------------------
# Content assets
# ---------------------------------------------------------------------------


@router.get("/assets", response_model=list[ContentAssetOut])
def list_assets(
    asset_type: Optional[str] = None,
    project_id: Optional[str] = None,
    favorite: Optional[bool] = None,
    q: Optional[str] = None,
    sort: str = "recent",
    db: Session = Depends(get_db),
) -> list[dict]:
    assets = svc.list_assets(db, asset_type, project_id, favorite, q, sort)
    return [svc.asset_to_out(db, a) for a in assets]


@router.post("/assets", response_model=ContentAssetOut)
def create_asset(payload: ContentAssetCreate, db: Session = Depends(get_db)) -> dict:
    asset = svc.create_asset(db, payload.model_dump())
    return svc.asset_to_out(db, asset)


@router.get("/assets/{asset_id}", response_model=ContentAssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)) -> dict:
    asset = svc.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    return svc.asset_to_out(db, asset)


@router.patch("/assets/{asset_id}", response_model=ContentAssetOut)
def update_asset(asset_id: str, payload: ContentAssetUpdate, db: Session = Depends(get_db)) -> dict:
    asset = svc.update_asset(db, asset_id, payload.model_dump(exclude_unset=True))
    if asset is None:
        raise HTTPException(404, "Asset not found")
    return svc.asset_to_out(db, asset)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, db: Session = Depends(get_db)) -> None:
    if not svc.delete_asset(db, asset_id):
        raise HTTPException(404, "Asset not found")


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


@router.get("/hooks", response_model=HookListResult)
def list_hooks(
    q: Optional[str] = None,
    category: Optional[str] = None,
    platform: Optional[str] = None,
    tone: Optional[str] = None,
    favorite: Optional[bool] = None,
    page: int = 1,
    page_size: int = 24,
    db: Session = Depends(get_db),
) -> dict:
    items, total = svc.list_hooks(db, q, category, platform, tone, favorite, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/hooks/{hook_id}", response_model=HookOut)
def get_hook(hook_id: str, db: Session = Depends(get_db)) -> object:
    hook = svc.get_hook(db, hook_id)
    if hook is None:
        raise HTTPException(404, "Hook not found")
    return hook


@router.patch("/hooks/{hook_id}", response_model=HookOut)
def update_hook(hook_id: str, payload: HookUpdate, db: Session = Depends(get_db)) -> object:
    hook = svc.update_hook(db, hook_id, payload.is_favorite)
    if hook is None:
        raise HTTPException(404, "Hook not found")
    return hook


@router.post("/hooks/{hook_id}/use", response_model=HookOut)
def use_hook(hook_id: str, db: Session = Depends(get_db)) -> object:
    hook = svc.use_hook(db, hook_id)
    if hook is None:
        raise HTTPException(404, "Hook not found")
    return hook


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    kind: Optional[str] = None,
    category: Optional[str] = None,
    mine: Optional[bool] = None,
    favorite: Optional[bool] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    return [svc.template_to_out(t) for t in svc.list_templates(db, kind, category, mine, favorite)]


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db)) -> dict:
    template = svc.get_template(db, template_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    return svc.template_to_out(template)


@router.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)) -> dict:
    try:
        template = svc.create_or_duplicate_template(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return svc.template_to_out(template)


@router.patch("/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: str, payload: TemplateUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        template = svc.update_template(db, template_id, payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if template is None:
        raise HTTPException(404, "Template not found")
    return svc.template_to_out(template)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: str, db: Session = Depends(get_db)) -> None:
    try:
        deleted = svc.delete_template(db, template_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not deleted:
        raise HTTPException(404, "Template not found")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/history", response_model=list[HistoryEventOut])
def list_history(project_id: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    events = svc.list_history(db, project_id, limit)
    return [svc.history_event_to_out(db, e) for e in events]


@router.post("/history", response_model=HistoryEventOut)
def create_history_event(payload: HistoryEventCreate, db: Session = Depends(get_db)) -> dict:
    event = svc.create_history_event(db, payload.event_type, payload.summary, payload.project_id, payload.asset_id)
    return svc.history_event_to_out(db, event)
