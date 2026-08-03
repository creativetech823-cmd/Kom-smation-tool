import uuid
from pathlib import Path

from huggingface_hub import InferenceClient

from app.config import settings
from app.models.product import MotionGenerationInput, MotionGenerationResult

_client = InferenceClient(provider=settings.hf_motion_provider, api_key=settings.huggingface_api_token)


def _motion_dir() -> Path:
    d = Path(settings.motion_output_dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_prompt(visual_tags: list[str]) -> str:
    subject = ", ".join(visual_tags) if visual_tags else "product advertisement scene"
    return f"{subject}, natural subtle motion, gentle camera movement, cinematic, high quality"


def generate_motion_clip(payload: MotionGenerationInput) -> MotionGenerationResult:
    """Stage 8.5 (optional) — animate a sourced still image into a short video
    clip via Hugging Face's free Inference Provider credits (Wan2.1 image-to-video)."""

    prompt = _build_prompt(payload.visual_tags)

    video_bytes = _client.image_to_video(
        payload.image_url,
        model=settings.hf_motion_model,
        prompt=prompt,
    )

    filename = f"{uuid.uuid4().hex[:12]}.mp4"
    video_path = _motion_dir() / filename
    video_path.write_bytes(video_bytes)

    return MotionGenerationResult(
        line_id=payload.line_id,
        video_path=str(video_path),
        prompt_used=prompt,
    )
