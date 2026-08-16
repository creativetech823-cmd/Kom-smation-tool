from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, SessionLocal, engine, run_lightweight_migrations
from app.routers import library, pipeline
from app.services.seed_data import seed_if_empty

app = FastAPI(title="AI Content Factory Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",],
    # Covers ngrok tunnel domains and Vercel preview/production deployments.
    allow_origin_regex=r"https://.*\.ngrok-free\.(app|dev)|https://.*\.ngrok\.(io|app)|https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(library.router)
app.mount("/renders", StaticFiles(directory="renders"), name="renders")
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/motion", StaticFiles(directory="motion"), name="motion")
app.mount("/reference-uploads", StaticFiles(directory="reference_uploads"), name="reference_uploads")
app.mount("/visuals", StaticFiles(directory="visuals"), name="visuals")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
