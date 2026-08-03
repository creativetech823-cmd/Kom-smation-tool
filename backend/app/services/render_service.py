import json
import subprocess
import uuid
from pathlib import Path

from app.config import settings
from app.models.product import RenderInput, RenderResult


def _remotion_dir() -> Path:
    return (Path(__file__).resolve().parent.parent.parent / settings.remotion_project_dir).resolve()


def render_video(payload: RenderInput) -> RenderResult:
    """Stage 9 — inject script lines + assets into the ProductAdMold Remotion
    template and render a finished MP4."""

    remotion_dir = _remotion_dir()
    output_dir = Path(settings.renders_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex[:12]
    output_path = output_dir / f"{job_id}.mp4"
    props_path = remotion_dir / f".props-{job_id}.json"

    def _line_props(line):
        entry = {"text": line.text, "imageUrl": line.image_url}
        if line.video_url:
            entry["videoUrl"] = line.video_url
        if line.audio_url:
            entry["audioUrl"] = line.audio_url
        if line.min_duration_seconds:
            entry["durationSeconds"] = max(payload.seconds_per_line, line.min_duration_seconds)
        return entry

    props = {
        "productName": payload.product_name,
        "secondsPerLine": payload.seconds_per_line,
        "lines": [_line_props(line) for line in payload.lines],
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

    duration_seconds = sum(
        max(payload.seconds_per_line, line.min_duration_seconds or 0) for line in payload.lines
    )
    return RenderResult(output_path=str(output_path), duration_seconds=duration_seconds)
