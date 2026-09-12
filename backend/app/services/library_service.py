"""Persistence layer for Projects, Content Assets, Hooks, Templates and
History — the data model backing the Content Management sidebar sections.

Every function here takes a SQLAlchemy Session as its first argument and
does plain ORM CRUD plus JSON (de)serialization for the `content_json` /
`config_json` text columns. Nothing here talks to the AI/media pipeline
services directly — the pipeline calls this layer from the frontend only
*after* an existing generation call has already succeeded.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models import ContentAsset, HistoryEvent, Hook, Project, Template


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _loads(text: Optional[str]) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _dumps(data: Optional[dict]) -> Optional[str]:
    if data is None:
        return None
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def _project_asset_count(db: Session, project_id: str) -> int:
    return db.query(ContentAsset).filter(ContentAsset.project_id == project_id).count()


def create_project(db: Session, name: str, description: str = "", product_category: str = "") -> Project:
    project = Project(name=name, description=description, product_category=product_category)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, status: Optional[str] = None) -> list[Project]:
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    return query.order_by(Project.updated_at.desc()).all()


def get_project(db: Session, project_id: str) -> Optional[Project]:
    return db.get(Project, project_id)


def update_project(db: Session, project_id: str, fields: dict) -> Optional[Project]:
    project = db.get(Project, project_id)
    if project is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(project, key, value)
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


def save_pipeline_state(
    db: Session,
    project_id: str,
    pipeline_state: dict,
    pipeline_stage: str,
    name: Optional[str] = None,
    product_category: Optional[str] = None,
) -> Optional[Project]:
    """Autosave from the Content Pipeline — always overwrites with the full
    current snapshot. `name`/`product_category` are set opportunistically
    (e.g. once the product is known) so the project reads well in the
    library, but never blanked out if not supplied."""
    project = db.get(Project, project_id)
    if project is None:
        return None
    project.pipeline_state = _dumps(pipeline_state)
    project.pipeline_stage = pipeline_stage
    if name:
        project.name = name
    if product_category:
        project.product_category = product_category
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str) -> bool:
    project = db.get(Project, project_id)
    if project is None:
        return False
    # Assets survive project deletion — detach them rather than cascade-delete.
    db.query(ContentAsset).filter(ContentAsset.project_id == project_id).update({"project_id": None})
    db.query(HistoryEvent).filter(HistoryEvent.project_id == project_id).update({"project_id": None})
    db.delete(project)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Content assets
# ---------------------------------------------------------------------------


def create_asset(db: Session, payload: dict) -> ContentAsset:
    content_json = _dumps(payload.pop("content_json", None))
    asset = ContentAsset(content_json=content_json, **payload)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_assets(
    db: Session,
    asset_type: Optional[str] = None,
    project_id: Optional[str] = None,
    favorite: Optional[bool] = None,
    q: Optional[str] = None,
    sort: str = "recent",
) -> list[ContentAsset]:
    query = db.query(ContentAsset)
    if asset_type:
        query = query.filter(ContentAsset.asset_type == asset_type)
    if project_id:
        query = query.filter(ContentAsset.project_id == project_id)
    if favorite is not None:
        query = query.filter(ContentAsset.is_favorite == favorite)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ContentAsset.title.like(like), ContentAsset.product_name.like(like)))
    if sort == "oldest":
        query = query.order_by(ContentAsset.created_at.asc())
    else:
        query = query.order_by(ContentAsset.created_at.desc())
    return query.all()


def get_asset(db: Session, asset_id: str) -> Optional[ContentAsset]:
    return db.get(ContentAsset, asset_id)


def update_asset(db: Session, asset_id: str, fields: dict) -> Optional[ContentAsset]:
    asset = db.get(ContentAsset, asset_id)
    if asset is None:
        return None
    if "content_json" in fields:
        asset.content_json = _dumps(fields.pop("content_json"))
    for key, value in fields.items():
        if value is not None:
            setattr(asset, key, value)
    asset.updated_at = _now()
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, asset_id: str) -> bool:
    asset = db.get(ContentAsset, asset_id)
    if asset is None:
        return False
    db.delete(asset)
    db.commit()
    return True


def asset_to_out(db: Session, asset: ContentAsset) -> dict:
    project_name = None
    if asset.project_id:
        project = db.get(Project, asset.project_id)
        project_name = project.name if project else None
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "asset_type": asset.asset_type.value if hasattr(asset.asset_type, "value") else asset.asset_type,
        "title": asset.title,
        "product_name": asset.product_name,
        "file_path": asset.file_path,
        "thumbnail_path": asset.thumbnail_path,
        "content_json": _loads(asset.content_json),
        "source_hook_id": asset.source_hook_id,
        "source_hook_text": asset.source_hook_text,
        "model_used": asset.model_used,
        "is_favorite": asset.is_favorite,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "project_name": project_name,
    }


def project_to_out(db: Session, project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "product_category": project.product_category,
        "status": project.status,
        "pipeline_state": _loads(project.pipeline_state),
        "pipeline_stage": project.pipeline_stage,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "asset_count": _project_asset_count(db, project.id),
    }


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def list_hooks(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    platform: Optional[str] = None,
    tone: Optional[str] = None,
    favorite: Optional[bool] = None,
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[Hook], int]:
    query = db.query(Hook)
    if q:
        query = query.filter(Hook.text.like(f"%{q}%"))
    if category:
        query = query.filter(Hook.category == category)
    if platform:
        query = query.filter(Hook.platform == platform)
    if tone:
        query = query.filter(Hook.tone == tone)
    if favorite is not None:
        query = query.filter(Hook.is_favorite == favorite)
    total = query.count()
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    items = query.order_by(Hook.category, Hook.text).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_hook(db: Session, hook_id: str) -> Optional[Hook]:
    return db.get(Hook, hook_id)


def update_hook(db: Session, hook_id: str, fields: dict) -> Optional[Hook]:
    hook = db.get(Hook, hook_id)
    if hook is None:
        return None
    if "text" in fields:
        stripped = (fields["text"] or "").strip()
        if not stripped:
            raise ValueError("Hook text cannot be empty")
        hook.text = stripped
    for key in ("category", "platform", "tone", "is_favorite"):
        if fields.get(key) is not None:
            setattr(hook, key, fields[key])
    db.commit()
    db.refresh(hook)
    return hook


def use_hook(db: Session, hook_id: str) -> Optional[Hook]:
    hook = db.get(Hook, hook_id)
    if hook is None:
        return None
    hook.usage_count += 1
    db.commit()
    db.refresh(hook)
    return hook


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def list_templates(
    db: Session,
    kind: Optional[str] = None,
    category: Optional[str] = None,
    mine: Optional[bool] = None,
    favorite: Optional[bool] = None,
) -> list[Template]:
    query = db.query(Template)
    if kind:
        query = query.filter(Template.kind == kind)
    if category:
        query = query.filter(Template.category == category)
    if mine is True:
        query = query.filter(Template.is_official.is_(False))
    elif mine is False:
        query = query.filter(Template.is_official.is_(True))
    if favorite is not None:
        query = query.filter(Template.is_favorite == favorite)
    return query.order_by(Template.is_official.desc(), Template.category, Template.name).all()


def get_template(db: Session, template_id: str) -> Optional[Template]:
    return db.get(Template, template_id)


def create_or_duplicate_template(db: Session, payload: dict) -> Template:
    duplicate_from = payload.get("duplicate_from")
    config_json = _dumps(payload.get("config_json"))

    if duplicate_from:
        source = db.get(Template, duplicate_from)
        if source is None:
            raise ValueError("Template to duplicate was not found")
        template = Template(
            name=f"{source.name} (Copy)",
            kind=source.kind,
            category=source.category,
            description=source.description,
            thumbnail_key=source.thumbnail_key,
            config_json=source.config_json,
            is_official=False,
        )
    else:
        if not payload.get("name") or not payload.get("kind"):
            raise ValueError("name and kind are required to create a template")
        template = Template(
            name=payload["name"],
            kind=payload["kind"],
            category=payload.get("category", ""),
            description=payload.get("description", ""),
            thumbnail_key=payload.get("thumbnail_key", ""),
            config_json=config_json,
            is_official=False,
        )

    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(db: Session, template_id: str, fields: dict) -> Optional[Template]:
    template = db.get(Template, template_id)
    if template is None:
        return None
    if template.is_official and any(v is not None for k, v in fields.items() if k != "is_favorite"):
        raise ValueError("Cannot edit an official template — duplicate it first")
    if "config_json" in fields:
        template.config_json = _dumps(fields.pop("config_json"))
    for key, value in fields.items():
        if value is not None:
            setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: str) -> bool:
    template = db.get(Template, template_id)
    if template is None:
        return False
    if template.is_official:
        raise ValueError("Cannot delete an official template")
    db.delete(template)
    db.commit()
    return True


def template_to_out(template: Template) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "kind": template.kind.value if hasattr(template.kind, "value") else template.kind,
        "category": template.category,
        "description": template.description,
        "thumbnail_key": template.thumbnail_key,
        "is_official": template.is_official,
        "config_json": _loads(template.config_json),
        "is_favorite": template.is_favorite,
        "created_at": template.created_at,
    }


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def create_history_event(
    db: Session,
    event_type: str,
    summary: str = "",
    project_id: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> HistoryEvent:
    event = HistoryEvent(event_type=event_type, summary=summary, project_id=project_id, asset_id=asset_id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_history(db: Session, project_id: Optional[str] = None, limit: int = 100) -> list[HistoryEvent]:
    query = db.query(HistoryEvent)
    if project_id:
        query = query.filter(HistoryEvent.project_id == project_id)
    limit = max(1, min(limit, 500))
    return query.order_by(HistoryEvent.created_at.desc()).limit(limit).all()


def history_event_to_out(db: Session, event: HistoryEvent) -> dict:
    project_name = None
    if event.project_id:
        project = db.get(Project, event.project_id)
        project_name = project.name if project else None
    return {
        "id": event.id,
        "event_type": event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        "summary": event.summary,
        "project_id": event.project_id,
        "asset_id": event.asset_id,
        "created_at": event.created_at,
        "project_name": project_name,
    }
