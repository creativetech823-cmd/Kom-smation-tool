"""Creative diversity memory — tracks the creative territory (premise,
insight, architecture, visual device, emotional engine, narrative device)
chosen by each FRESH script generation for a given product, so the NEXT
independent generate_script() call for the SAME product can see what was
already used and deliberately diverge.

Why this exists: the pipeline already had avoid_repeating_hook/
avoid_repeating_mechanism, but those only thread forward on an explicit
"regenerate this existing script" request — a brand-new generate_script()
call (the common case: a user opens the product again later, or a batch
process requests several independent concepts) starts with a blank slate
every time. Live testing showed independent fresh calls for the same brief
reliably converge on the same "safest" creative device as a result. This
module is the missing persistent memory that makes fresh generation
diversity-aware too, reusing the existing SQLite DB (app/db.py) rather than
adding a second store.

Never raises: any DB failure here degrades to "no history available" (the
caller proceeds exactly as if this were the first generation for that
product) rather than failing generation.
"""

import hashlib
import logging

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.db_models import CreativeConceptRecord

logger = logging.getLogger("creative_memory_service")

# How many recent generations' territory to surface to the next premise/
# architecture selection call, and how many rows to retain per product
# before pruning older ones — small on purpose: this is meant to steer away
# from the last few concepts, not build a permanent creative archive.
RECENT_LIMIT = 5
RETAIN_LIMIT = 20


def product_key(product_id: str, product_name: str, product_category: str) -> str:
    """A stable identity for "this product" across generations. A Product
    Library selection already has a real product_id — use it directly. A
    manually-entered product has none, so derive a stable signature from its
    name+category instead (same product typed the same way on a later visit
    resolves to the same key; a different product does not)."""
    if product_id:
        return f"lib:{product_id}"
    signature = f"{product_name.strip().lower()}|{product_category.strip().lower()}"
    return "manual:" + hashlib.sha1(signature.encode("utf-8")).hexdigest()[:24]


def recent_concepts(key: str, limit: int = RECENT_LIMIT) -> list[dict]:
    """Most recent generations' territory for this product, newest first.
    Returns [] on any failure or when this is genuinely the first
    generation — both are the same "no history" case to every caller."""
    if not key:
        return []
    try:
        with SessionLocal() as db:
            rows = db.execute(
                select(CreativeConceptRecord)
                .where(CreativeConceptRecord.product_key == key)
                .order_by(CreativeConceptRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "architecture_key": r.architecture_key,
                    "creative_device": r.creative_device,
                    "visual_device": r.visual_device,
                    "emotional_engine": r.emotional_engine,
                    "narrative_device": r.narrative_device,
                    "insight_statement": r.insight_statement,
                    "premise_statement": r.premise_statement,
                    "territory_name": getattr(r, "territory_name", "") or "",
                    "human_tension": getattr(r, "human_tension", "") or "",
                    "creative_question": getattr(r, "creative_question", "") or "",
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("Failed to read creative concept history for %s: %s", key, e)
        return []


def record_concept(
    key: str,
    *,
    architecture_key: str = "",
    creative_device: str = "",
    visual_device: str = "",
    emotional_engine: str = "",
    narrative_device: str = "",
    insight_statement: str = "",
    premise_statement: str = "",
    territory_name: str = "",
    human_tension: str = "",
    creative_question: str = "",
) -> None:
    """Persists this generation's chosen territory, then prunes old rows
    for this product beyond RETAIN_LIMIT. Never raises — a failure to
    record is a missed future diversity signal, not a reason to fail the
    generation that already succeeded."""
    if not key:
        return
    try:
        with SessionLocal() as db:
            db.add(
                CreativeConceptRecord(
                    product_key=key,
                    architecture_key=architecture_key,
                    creative_device=creative_device,
                    visual_device=visual_device,
                    emotional_engine=emotional_engine,
                    narrative_device=narrative_device,
                    insight_statement=insight_statement,
                    premise_statement=premise_statement,
                    territory_name=territory_name,
                    human_tension=human_tension,
                    creative_question=creative_question,
                )
            )
            db.commit()

            stale_ids = db.execute(
                select(CreativeConceptRecord.id)
                .where(CreativeConceptRecord.product_key == key)
                .order_by(CreativeConceptRecord.created_at.desc())
                .offset(RETAIN_LIMIT)
            ).scalars().all()
            if stale_ids:
                db.execute(delete(CreativeConceptRecord).where(CreativeConceptRecord.id.in_(stale_ids)))
                db.commit()
    except Exception as e:
        logger.warning("Failed to record creative concept history for %s: %s", key, e)


def recent_territories_prompt_block(concepts: list[dict]) -> str:
    """Territory-LEVEL rendering (territory_name/human_tension/
    creative_question) for creative_territory_service — one abstraction
    level above recent_territory_prompt_block below, which renders
    premise/device-level history for creative_premise_service. Skips any
    record from before territory tracking existed (empty territory_name)."""
    named = [c for c in concepts if c.get("territory_name")]
    if not named:
        return ""
    lines = [
        "RECENTLY USED TERRITORIES for this exact product (from other recent generations — a new "
        "candidate that is the same underlying lens as any of these, with only the character/setting/"
        "device/wording changed, is NOT a new territory; per the same-idea-different-clothes test, "
        "score its distance_from_recent low):"
    ]
    for i, c in enumerate(named, start=1):
        lines.append(
            f"  {i}. \"{c['territory_name']}\" — tension: {c.get('human_tension') or 'n/a'}; "
            f"question: {c.get('creative_question') or 'n/a'}"
        )
    return "\n".join(lines)


def recent_territory_prompt_block(concepts: list[dict]) -> str:
    """Renders recent territory as a prompt block for premise generation —
    shared helper so the wording is consistent wherever this is injected."""
    if not concepts:
        return ""
    lines = [
        "RECENTLY USED CREATIVE TERRITORY for this exact product (from other recent generations — do "
        "NOT propose a candidate that is really the same underlying idea as any of these with different "
        "wording, a different character, or a different object standing in for the same device; "
        "deliberately pull from a genuinely different creative engine instead):"
    ]
    for i, c in enumerate(concepts, start=1):
        lines.append(
            f"  {i}. Architecture: {c.get('architecture_key') or 'n/a'}; device: {c.get('creative_device') or 'n/a'}; "
            f"visual device: {c.get('visual_device') or 'n/a'}; emotional engine: {c.get('emotional_engine') or 'n/a'}; "
            f"narrative device: {c.get('narrative_device') or 'n/a'}; premise: "
            f"{(c.get('premise_statement') or '')[:200]}"
        )
    return "\n".join(lines)
