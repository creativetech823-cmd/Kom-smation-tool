import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from app.config import settings
from app.db import Base, SessionLocal, engine, run_lightweight_migrations
from app.routers import library, pipeline, product_library
from app.services.seed_data import seed_if_empty

# Render/uvicorn logging-visibility fix (2026-09-18 live production task) —
# the app never called logging.basicConfig() (or set any level) anywhere,
# so the root logger had no handler and Python's logging module fell back
# to its "handler of last resort," which only ever surfaces WARNING and
# above. Every logger.info() call in the app (not just the Story Ideas
# timing diagnostics) was therefore silently dropped in Render's logs —
# confirmed by the WARNING-level judge/enrichment-skip lines being visible
# while none of the [STORY_IDEAS] INFO lines ever appeared. uvicorn's own
# --log-level flag would only affect uvicorn's own loggers (uvicorn.access/
# uvicorn.error), not this app's loggers, so it can't fix this on its own.
# force=True guarantees this takes effect even if something else already
# attached a handler to the root logger before this module finishes
# importing. Level only — no new logging framework, no format/handler
# redesign.
logging.basicConfig(level=logging.INFO, force=True)

logger = logging.getLogger("app.main")

app = FastAPI(title="AI Content Factory Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    # Covers ngrok tunnel domains and Vercel preview/production deployments.
    allow_origin_regex=r"https://.*\.ngrok-free\.(app|dev)|https://.*\.ngrok\.(io|app)|https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(library.router)
app.include_router(product_library.router)

# StaticFiles(directory=...) raises RuntimeError at mount time (i.e. at
# import time, before the app can even start) if the directory doesn't
# already exist on disk. All of these are gitignored, generated-on-first-use
# output directories — present locally only because a prior dev run wrote
# something into them, but absent on a fresh clone (e.g. Render's build),
# which crashed the whole app before a single request could be served.
# Each service that actually writes into one of these (render_service,
# tts_service, motion_service, content_extraction_service,
# visual_concept_service) already creates it lazily via the same
# `settings.<x>_output_dir` value at write time — this just does the same
# `mkdir(parents=True, exist_ok=True)` up front, so the mount always has
# something to point at regardless of whether anything has been written yet.
for output_dir in (
    settings.renders_output_dir,
    settings.audio_output_dir,
    settings.motion_output_dir,
    settings.reference_uploads_dir,
    settings.visuals_output_dir,
    settings.product_uploads_dir,
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

app.mount("/renders", StaticFiles(directory=settings.renders_output_dir), name="renders")
app.mount("/audio", StaticFiles(directory=settings.audio_output_dir), name="audio")
app.mount("/motion", StaticFiles(directory=settings.motion_output_dir), name="motion")
app.mount("/reference-uploads", StaticFiles(directory=settings.reference_uploads_dir), name="reference_uploads")
app.mount("/visuals", StaticFiles(directory=settings.visuals_output_dir), name="visuals")
app.mount("/product-uploads", StaticFiles(directory=settings.product_uploads_dir), name="product_uploads")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    # Model-routing visibility (2026-09-18 GPT-5.6 Luna experiment, Part 15)
    # — never logs the API key, just which model/provider/reasoning-effort
    # every text stage will actually resolve to on this running instance.
    logger.info(
        "Provider: OpenRouter | Text Model: %s | Creative: %s | Final Script: %s | Validation: %s | "
        "Reasoning effort: %s | Image generation: %s",
        settings.openrouter_text_model, settings.creative_model, settings.final_script_model,
        settings.validation_model, settings.openrouter_reasoning_effort or "(none)",
        "enabled" if settings.image_generation_enabled else "disabled",
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": "openrouter",
        "text_model": settings.openrouter_text_model,
        "creative_model": settings.creative_model,
        "final_script_model": settings.final_script_model,
        "validation_model": settings.validation_model,
        "reasoning_effort": settings.openrouter_reasoning_effort,
        "image_generation_enabled": settings.image_generation_enabled,
    }
