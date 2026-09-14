import json
import subprocess
import uuid
from pathlib import Path

from app.config import settings
from app.models.product import RenderInput, RenderResult
from app.models.scene_plan import ScenePlan, VideoScene
from app.services.scene_plan_service import build_scene_plan


def _remotion_dir() -> Path:
    return (Path(__file__).resolve().parent.parent.parent / settings.remotion_project_dir).resolve()


def _resolve_url(url: str | None) -> str | None:
    """Remotion's headless-Chrome render process fetches URLs over real
    HTTP — a relative URL from our own /product-uploads static mount (a
    Product Library asset) needs to become absolute before Remotion can
    fetch it. Pexels/Pixabay/gTTS-audio URLs are already absolute and pass
    through unchanged."""
    if url and url.startswith("/"):
        return settings.backend_base_url.rstrip("/") + url
    return url


def _scene_props(scene: VideoScene) -> dict:
    entry = {
        "sceneId": scene.scene_id,
        "order": scene.order,
        "durationSeconds": scene.duration_seconds,
        "purpose": scene.purpose.value,
        "text": scene.script_text,
        "onScreenText": scene.on_screen_text,
        "imageUrl": _resolve_url(scene.image_url),
        "isProductAsset": scene.is_product_asset,
        "visualStyle": scene.visual_style.value,
        "cameraMotion": scene.camera_motion.value,
        "textAnimation": scene.text_animation.value,
        "transition": scene.transition.value,
        "emphasis": scene.emphasis,
        "isCta": scene.is_cta,
        "isProductReveal": scene.is_product_reveal,
        # Sound-design architecture only — Remotion does not play these yet;
        # exposed so a future mixing pass has the per-scene mood/cue to work from.
        "musicMood": scene.music_mood,
        "sfxCue": scene.sfx_cue,
    }
    video_url = _resolve_url(scene.video_url)
    if video_url:
        entry["videoUrl"] = video_url
    audio_url = _resolve_url(scene.audio_url)
    if audio_url:
        entry["audioUrl"] = audio_url
    return entry


def render_video(payload: RenderInput) -> RenderResult:
    """Stage 9 — build a ScenePlan from the script lines + resolved assets
    (see scene_plan_service.build_scene_plan — deterministic, no LLM call),
    then render it through the ProductAdMold Remotion composition.

    Backward compatible by construction: build_scene_plan() already handles
    both a RenderInput with the newer optional section/emotion/etc fields
    populated AND an older/external caller that only ever sent
    text/image_url — either way this function always ends up with a
    complete ScenePlan to hand to Remotion."""

    scene_plan: ScenePlan = build_scene_plan(payload)

    remotion_dir = _remotion_dir()
    output_dir = Path(settings.renders_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex[:12]
    output_path = output_dir / f"{job_id}.mp4"
    props_path = remotion_dir / f".props-{job_id}.json"

    props = {
        "productName": scene_plan.product_name,
        "scenes": [_scene_props(s) for s in scene_plan.scenes],
    }
    props_path.write_text(json.dumps(props), encoding="utf-8")

    try:
        result = subprocess.run(
            [
                "npx",
                "remotion",
                "render",
                "src/index.ts",
                "ProductAdMold",
                str(output_path),
                f"--props={props_path}",
            ],
            cwd=str(remotion_dir),
            capture_output=True,
            text=True,
            timeout=300,
            shell=True,
        )
    finally:
        props_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Remotion render failed:\n{result.stdout}\n{result.stderr}")

    return RenderResult(output_path=str(output_path), duration_seconds=scene_plan.total_duration_seconds)
