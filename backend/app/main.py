from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import pipeline

app = FastAPI(title="AI Content Factory Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    # Covers ngrok's free-tier tunnel domains, so a tunneled frontend can call this API.
    allow_origin_regex=r"https://.*\.ngrok-free\.app|https://.*\.ngrok\.(io|app)",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.mount("/renders", StaticFiles(directory="renders"), name="renders")
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.mount("/motion", StaticFiles(directory="motion"), name="motion")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
