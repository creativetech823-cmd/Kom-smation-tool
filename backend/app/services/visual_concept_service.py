import base64
import hashlib
import io
import json
import logging
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import requests
from anthropic import Anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from PIL import Image

from app.config import settings
from app.models.product import (
    VisualConcept,
    VisualConceptDownloadInput,
    VisualConceptRegenerateInput,
    VisualConceptScoreInput,
    VisualConceptScores,
    VisualConceptsInput,
    VisualConceptsResult,
    VisualConceptStyleParams,
)
from app.services.claude_utils import extract_json_text
from app.services.compliance_rules import rules_for_category

logger = logging.getLogger("visual_concept_service")
_claude_client = Anthropic(api_key=settings.anthropic_api_key)

# Unlike the Anthropic/HF clients, google-genai's Client validates that the
# API key is non-empty at CONSTRUCTION time, not just on first call — so it
# can't be built eagerly at module import (the app must still start before a
# key is configured). Built lazily on first real use instead; an empty/
# placeholder key still fails naturally on the actual API call, which
# _classify_error turns into a clear "API key missing" message either way.
_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key or "missing-api-key")
    return _gemini_client


def _reset_gemini_client() -> None:
    """Discards the cached client so the next call builds a fresh one — used
    when the underlying httpx connection was torn down out from under us
    (e.g. a platform restart mid-request), which raises 'client has been
    closed' rather than a normal API error."""
    global _gemini_client
    _gemini_client = None

_IMAGE_SIZE_PREVIEW = "1K"
_IMAGE_SIZE_DOWNLOAD = "4K"


def _4k_canvas_for(aspect_ratio: str) -> tuple[int, int]:
    """The 4K-pixel-class canvas for this aspect ratio (3840 on the long edge,
    exactly 3840x2160 for 16:9). Gemini is asked to natively render at "4K"
    for downloads; this is a final correctness guarantee, not the primary
    resolution mechanism — a resize only happens if the native output doesn't
    already land exactly on this canvas."""
    try:
        w_ratio, h_ratio = (int(x) for x in aspect_ratio.split(":"))
    except ValueError:
        w_ratio, h_ratio = 9, 16
    if w_ratio >= h_ratio:
        width, height = 3840, round(3840 * h_ratio / w_ratio)
    else:
        height, width = 3840, round(3840 * w_ratio / h_ratio)
    return width - (width % 2), height - (height % 2)


# The 19 regeneration styles + 2 same-scene actions, per the requested style
# catalog. Used both as the style-preset menu and for "Generate Similar" /
# "Generate Different Angle" — all funnel through the same image-conditioned
# edit mechanism (see regenerate_visual_concept).
_VARIATION_STYLE_DIRECTIVES: dict[str, str] = {
    "photorealistic": "photorealistic, shot on a professional DSLR, natural realistic lighting and color",
    "luxury_product": "luxury product photography, premium minimal composition, elegant gold and black palette accents, high-end catalog styling",
    "studio_photography": "clean studio photography, seamless backdrop, professional softbox lighting, commercial product-shoot styling",
    "commercial_advertisement": "polished commercial advertisement styling, brand-campaign quality, crisp confident composition",
    "lifestyle": "natural lifestyle photography, candid in-context moment, authentic everyday setting",
    "fashion": "high-fashion editorial styling, glossy premium finish, dramatic pose and lighting",
    "apple_style": "Apple-campaign style — minimal, clean negative space, soft even lighting, premium restrained aesthetic",
    "nike_style": "Nike-campaign style — bold dynamic energy, dramatic contrast lighting, athletic intensity",
    "cinematic": "cinematic film-still composition, anamorphic lens flare, wide dynamic range, dramatic lighting",
    "moody": "moody dark tones, low-key dramatic lighting, high contrast shadows",
    "bollywood": "vibrant Bollywood commercial styling, saturated warm colors, expressive dramatic emotion",
    "documentary": "documentary realism, handheld authentic framing, natural available light",
    "meta_glasses_pov": "first-person POV as if shot on smart glasses, immersive point-of-view framing",
    "ugc": "authentic UGC selfie-style, casual off-the-cuff phone-camera look",
    "instagram_ad": "Instagram-native ad styling, vibrant punchy colors, thumb-stopping composition",
    "facebook_ad": "Facebook-native ad styling, clear bright product focus, broad-appeal commercial look",
    "luxury_cosmetic": "luxury cosmetic/beauty photography, soft glowing skin, elegant minimal props",
    "minimal": "minimalist composition, clean negative space, simple uncluttered background",
    "hyper_realistic": "hyper-realistic, extreme fine detail, visible skin pores, fabric texture, raw photo realism",
    "generate_similar": "a similar alternative take on the same scene — same subject, setting, and composition, only minor natural variation",
    "different_angle": "the exact same scene and subject, shot from a different camera angle and framing",
}

_SCENE_PLAN_SYSTEM_PROMPT = """You are an award-winning advertising creative director storyboarding
a premium ad campaign — the visual quality bar of Apple, Nike, Coca-Cola, A24, Netflix, or Google
Pixel campaigns. You are given a finished short-form ad script (hook, body, CTA), its persona,
emotion, creative angle, target duration, target audience, brand tone, and category compliance
rules. Create exactly 3 completely different image concepts for this campaign, in this order:

1. HOOK — the opening 3 seconds. Highest attention, scroll-stopping, cinematic lighting. Grounded
   in the actual hook line and persona given below.
2. MAIN SCENE — shows the product story and human emotion at the heart of the script's body.
   Grounded in the actual body of the script. Real, specific facial expressions and body language.
3. CTA — the product hero shot. Premium advertisement styling, brand colors, grounded in the
   script's CTA/resolution. Hopeful, bright, premium.

For each of the 3, write:
- "scene_title": a short evocative title
- "scene_label": exactly "hook", "emotional", or "transformation" respectively (internal labels —
  "emotional" means Main Scene, "transformation" means CTA/product hero shot)
- "prompt": ONE rich, specific, photorealistic-commercial-ad prompt (120-200 words) built from ALL
  of: the product, the target audience, the story, the selected creative angle, the script content,
  brand tone, scene/setting, lighting, camera (lens/shot type), mood, color grading, composition,
  and advertising style. Literally describe the subject(s), their expression/action, the setting/
  props, and the shot itself. Concrete photography/production-quality language: cinematic lighting,
  shallow depth of field, 85mm lens, studio color grading, ultra photorealistic, sharp focus,
  natural skin texture, subtle film grain, premium commercial advertising photography, award-
  winning commercial photography, ultra detailed. Must comply with the category compliance rules
  given below — never depict anything those rules prohibit. Ground every detail in the ACTUAL
  script, persona, and product given below — never generic stock-photo phrasing, never mention
  text/logos/watermarks appearing in the image itself.
- "negative_prompt": comma-separated list of things to avoid, e.g. "cartoon, illustration, plastic
  skin, deformed hands, extra fingers, low quality, blurry, watermark, text, logo, oversaturated"
- "style", "lighting", "camera", "mood", "background", "characters", "composition": short (3-8
  word) fragments breaking the prompt's key creative choices into separate fields, for later manual
  re-editing by the user.

Return ONLY valid JSON, no prose, no markdown fences, matching this exact shape:
{"concepts": [
  {"scene_title": string, "scene_label": "hook", "prompt": string, "negative_prompt": string, "style": string, "lighting": string, "camera": string, "mood": string, "background": string, "characters": string, "composition": string},
  {"scene_title": string, "scene_label": "emotional", ...same fields...},
  {"scene_title": string, "scene_label": "transformation", ...same fields...}
]}"""

_SCORE_SYSTEM_PROMPT = """You are an experienced advertising creative director evaluating one still
image from an ad campaign storyboard against the prompt that generated it. Score it 0-100 on each
axis:
- visual_impact: how scroll-stopping/attention-grabbing is this frame?
- ad_quality: does this look like a premium professional advertising campaign still?
- ctr_prediction: your best estimate of how well this would perform as a click/view-through hook
- emotion_score: how effectively does it convey the intended emotion?
- brand_match: how well does it fit the product/brand described in the prompt?
- photorealism: how photorealistic vs artificial/AI-looking does it look (penalize plastic skin,
  malformed hands, warped anatomy, obviously synthetic textures)?
Also give one short "notes" sentence with the single most useful improvement suggestion.

Return ONLY valid JSON, no prose, no markdown fences:
{"visual_impact": number, "ad_quality": number, "ctr_prediction": number, "emotion_score": number, "brand_match": number, "photorealism": number, "notes": string}"""


def _visuals_dir() -> Path:
    d = Path(settings.visuals_output_dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_bytes(data: bytes, ext: str = "png") -> str:
    """Raw passthrough save — no re-encode, used for preview generations."""
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    path = _visuals_dir() / filename
    path.write_bytes(data)
    return str(path)


def _save_pil_image(image: Image.Image, ext: str = "png") -> str:
    ext = ext.lower()
    fmt = {"jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP", "png": "PNG"}.get(ext, "PNG")
    if fmt == "JPEG" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    filename = f"{uuid.uuid4().hex[:12]}.{'jpg' if fmt == 'JPEG' else ext}"
    path = _visuals_dir() / filename
    save_kwargs = {"quality": 92} if fmt in ("JPEG", "WEBP") else {}
    image.save(path, format=fmt, **save_kwargs)
    return str(path)


def _image_dims(data: bytes) -> str:
    try:
        with Image.open(io.BytesIO(data)) as img:
            return f"{img.width}x{img.height}"
    except Exception:
        return ""


def _build_full_prompt(concept: VisualConcept) -> str:
    sp = concept.style_params
    extra_fields = {
        "Style": sp.style,
        "Lighting": sp.lighting,
        "Camera": sp.camera,
        "Mood": sp.mood,
        "Background": sp.background,
        "Characters": sp.characters,
        "Composition": sp.composition,
        "Brand colors": sp.brand_colors,
        "Logo placement": sp.logo_placement,
        "Product position": sp.product_position,
    }
    extras = ". ".join(f"{k}: {v.strip()}" for k, v in extra_fields.items() if v.strip())
    base = concept.prompt.strip().rstrip(".")
    return f"{base}. {extras}." if extras else f"{base}."


# ---------------------------------------------------------------------------
# Gemini calls
# ---------------------------------------------------------------------------

_image_cache: dict[str, tuple[bytes, str, float]] = {}


def _cache_key(mode: str, prompt_or_instruction: str, aspect_ratio: str, seed: int | None, image_hash: str = "") -> str:
    raw = f"{mode}|{aspect_ratio}|{seed}|{image_hash}|{prompt_or_instruction}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _classify_error(e: Exception | None) -> str:
    """A short, specific, user-displayable reason — never a generic 'Network
    Error' unless the failure is genuinely a connection-level problem."""
    if e is None:
        return "Unknown error — no attempts were made."
    if not settings.gemini_api_key:
        return "API key missing — no GEMINI_API_KEY configured on the backend."
    if isinstance(e, genai_errors.APIError):
        code = getattr(e, "code", None)
        message = getattr(e, "message", None) or str(e)
        if code == 429:
            return f"Gemini quota exceeded. {message}"[:300]
        if code in (401, 403):
            return f"API key invalid or lacks permission. {message}"[:300]
        if code == 400:
            return f"Invalid request to Gemini: {message}"[:300]
        if code and code >= 500:
            return f"Gemini service error (HTTP {code}): {message}"[:300]
        return f"Gemini returned HTTP {code}: {message}"[:300]
    name = type(e).__name__
    msg = str(e)
    if "timeout" in name.lower() or "timeout" in msg.lower():
        return "Gemini timeout — the request took too long. Try again."
    if any(term in name for term in ("Connect", "DNS", "Network", "Socket")):
        return f"Network error reaching Gemini: {msg[:200]}"
    return f"Invalid response from Gemini ({name}): {msg[:200]}"


def _extract_image_bytes(response: genai_types.GenerateContentResponse) -> bytes:
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content else None
        for part in parts or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data
    raise RuntimeError("Invalid response — Gemini didn't return an image (no inline image data in any candidate).")


def _generate_image(prompt: str, aspect_ratio: str, seed: int | None = None, image_size: str = _IMAGE_SIZE_PREVIEW) -> tuple[bytes, str, float]:
    t0 = time.time()
    config = genai_types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=genai_types.ImageConfig(aspect_ratio=aspect_ratio, image_size=image_size),
        seed=seed,
    )
    response = _get_gemini_client().models.generate_content(model=settings.gemini_image_model, contents=[prompt], config=config)
    data = _extract_image_bytes(response)
    return data, settings.gemini_image_model, time.time() - t0


def _edit_image(image_bytes: bytes, instruction: str, aspect_ratio: str, image_size: str = _IMAGE_SIZE_PREVIEW) -> tuple[bytes, str, float]:
    """Image-conditioned edit — the current image + a natural-language
    instruction, used for Edit Prompt, style presets, Generate Similar, and
    Generate Different Angle, so edits actually preserve the rest of the
    scene instead of regenerating a whole new one from scratch."""
    t0 = time.time()
    config = genai_types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=genai_types.ImageConfig(aspect_ratio=aspect_ratio, image_size=image_size),
    )
    contents = [instruction, genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png")]
    response = _get_gemini_client().models.generate_content(model=settings.gemini_image_model, contents=contents, config=config)
    data = _extract_image_bytes(response)
    return data, settings.gemini_image_model, time.time() - t0


def _call_with_retry(fn: Callable[[], tuple[bytes, str, float]], *, label: str, max_attempts: int = 3) -> tuple[bytes, str, float]:
    """Retries transient failures (quota/server/timeout) with backoff before
    giving up. The user only ever sees an error after every attempt fails."""
    last_error: Exception | None = None
    t_start = time.time()
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        logger.info("[%s] Calling Gemini (attempt %d/%d) model=%s", label, attempt, max_attempts, settings.gemini_image_model)
        t0 = time.time()
        try:
            data, model, _elapsed = fn()
            logger.info("[%s] Status: success — model=%s bytes=%d response_time=%.1fs", label, model, len(data), time.time() - t0)
            return data, model, time.time() - t_start
        except Exception as e:
            last_error = e
            code = getattr(e, "code", None)
            logger.warning(
                "[%s] Status: failed — attempt=%d code=%s response_time=%.1fs error=%s",
                label, attempt, code, time.time() - t0, e,
            )
            message = str(e).lower()
            client_closed = "client has been closed" in message
            transient = code in (429, 500, 502, 503) or "timeout" in message or client_closed
            if not transient or attempt == max_attempts:
                break
            if client_closed:
                _reset_gemini_client()
            time.sleep(min(2**attempt, 8))

    reason = _classify_error(last_error)
    if attempt > 1:
        reason = f"Retry failed after {attempt} attempts. {reason}"
    logger.error("[%s] All attempts failed. Final reason: %s", label, reason)
    raise RuntimeError(reason)


def _generate_cached(prompt: str, aspect_ratio: str, seed: int | None, label: str) -> tuple[bytes, str, float]:
    key = _cache_key("gen", prompt, aspect_ratio, seed)
    cached = _image_cache.get(key)
    if cached:
        logger.info("[%s] Cache hit — reusing existing image, no Gemini call.", label)
        return cached
    result = _call_with_retry(lambda: _generate_image(prompt, aspect_ratio, seed), label=label)
    _image_cache[key] = result
    return result


def _edit_cached(image_bytes: bytes, instruction: str, aspect_ratio: str, label: str) -> tuple[bytes, str, float]:
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    key = _cache_key("edit", instruction, aspect_ratio, None, image_hash)
    cached = _image_cache.get(key)
    if cached:
        logger.info("[%s] Cache hit — reusing existing image, no Gemini call.", label)
        return cached
    result = _call_with_retry(lambda: _edit_image(image_bytes, instruction, aspect_ratio), label=label)
    _image_cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Scene planning (Claude — unchanged provider, richer context)
# ---------------------------------------------------------------------------


def _flatten_script_text(script) -> str:
    lines = [script.hook, *script.body, script.cta]
    return "\n".join(f"[{line.section or '-'}] {line.text}" for line in lines)


def _build_plan_user_message(payload: VisualConceptsInput) -> str:
    p = payload.structured_product
    s = payload.situation
    rules = rules_for_category(payload.product_category or p.industry or "general")
    rules_block = "\n".join(f"- {r}" for r in rules)
    return (
        f"Product: {p.product_name}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Target audience: {p.target_audience}\n"
        f"Brand tone: {p.tone or 'unspecified'}\n"
        f"Story persona: {s.persona}\n"
        f"Emotion: {s.emotion}\n"
        f"Creative angle: {payload.creative_angle or 'none specified'}\n"
        f"Target duration: {payload.script.target_duration or s.estimated_length or 'unspecified'}\n\n"
        f"Category compliance rules (do not depict anything these prohibit):\n{rules_block}\n\n"
        f"Full script:\n{_flatten_script_text(payload.script)}"
    )


def plan_visual_concepts(payload: VisualConceptsInput) -> list[VisualConcept]:
    logger.info("Preparing prompt... understanding story — product=%s situation=%s", payload.structured_product.product_name, payload.situation.title)
    response = _claude_client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=4096,
        system=_SCENE_PLAN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_plan_user_message(payload)}],
        extra_body={"thinking": {"type": "disabled"}},
    )
    try:
        data = json.loads(extract_json_text(response.content))
    except json.JSONDecodeError as e:
        logger.error("Claude returned malformed JSON while planning visual concepts.")
        raise ValueError("Claude returned malformed JSON while planning visual concepts.") from e

    labels = ["hook", "emotional", "transformation"]
    concepts: list[VisualConcept] = []
    for i, item in enumerate(data.get("concepts", [])[:3]):
        concepts.append(
            VisualConcept(
                id=uuid.uuid4().hex[:10],
                scene_number=i + 1,
                scene_title=item.get("scene_title") or f"Scene {i + 1}",
                scene_label=item.get("scene_label") or labels[i],
                creative_angle=payload.creative_angle,
                prompt=item.get("prompt", ""),
                style_params=VisualConceptStyleParams(
                    style=item.get("style", ""),
                    lighting=item.get("lighting", ""),
                    camera=item.get("camera", ""),
                    mood=item.get("mood", ""),
                    background=item.get("background", ""),
                    characters=item.get("characters", ""),
                    composition=item.get("composition", ""),
                    negative_prompt=item.get("negative_prompt", ""),
                ),
            )
        )
    logger.info("Generated %d scene prompt(s): %s", len(concepts), [c.scene_label.value for c in concepts])
    return concepts


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def _render_concept(concept: VisualConcept) -> VisualConcept:
    label = f"Generating Concept {concept.scene_number} ({concept.scene_label.value})"
    prompt = _build_full_prompt(concept)
    seed = random.randint(1, 2_000_000_000)
    data, model, elapsed = _generate_cached(prompt, concept.aspect_ratio, seed, label)
    concept.image_path = _save_bytes(data)
    concept.seed = seed
    concept.resolution = _image_dims(data)
    concept.generation_time_seconds = round(elapsed, 1)
    concept.used_model = model
    logger.info("[%s] Saved successfully. -> %s", label, concept.image_path)
    return concept


def generate_visual_concepts(payload: VisualConceptsInput) -> VisualConceptsResult:
    """Storyboard section — plan 3 distinct scene concepts from the finished
    script, then render all 3 concurrently (each Gemini call is blocking)."""
    concepts = plan_visual_concepts(payload)
    with ThreadPoolExecutor(max_workers=3) as executor:
        rendered = list(executor.map(_render_concept, concepts))
    logger.info("Done. Visual concepts generation complete — %d image(s) saved.", len(rendered))
    return VisualConceptsResult(concepts=rendered)


def regenerate_visual_concept(payload: VisualConceptRegenerateInput) -> VisualConcept:
    """Regenerate one concept:
    - a style preset / "Generate Similar" / "Generate Different Angle"
      (`variation_style` set), or a manual prompt edit (`is_manual_edit`) —
      image-conditioned EDIT of the current image, so the rest of the scene
      is preserved.
    - a plain "Regenerate" click (neither set) — a fresh text-to-image
      re-roll with a new seed."""
    concept = payload.concept.model_copy(deep=True)
    label = f"regenerate scene {concept.scene_number}"
    current_bytes = None
    if concept.image_path and Path(concept.image_path).exists():
        current_bytes = Path(concept.image_path).read_bytes()

    if payload.variation_style and current_bytes:
        directive = _VARIATION_STYLE_DIRECTIVES.get(payload.variation_style, payload.variation_style.replace("_", " "))
        data, model, elapsed = _edit_cached(current_bytes, directive, concept.aspect_ratio, label)
        seed = concept.seed
    elif payload.is_manual_edit and current_bytes:
        instruction = f"Apply this creative direction to the image: {concept.prompt}"
        data, model, elapsed = _edit_cached(current_bytes, instruction, concept.aspect_ratio, label)
        seed = concept.seed
    else:
        prompt = _build_full_prompt(concept)
        seed = random.randint(1, 2_000_000_000)
        data, model, elapsed = _generate_cached(prompt, concept.aspect_ratio, seed, label)

    concept.image_path = _save_bytes(data)
    concept.seed = seed
    concept.resolution = _image_dims(data)
    concept.generation_time_seconds = round(elapsed, 1)
    concept.used_model = model
    concept.scores = None
    if payload.as_new_variation:
        concept.id = uuid.uuid4().hex[:10]
    logger.info("[%s] Saved successfully. -> %s", label, concept.image_path)
    return concept


def score_visual_concept(payload: VisualConceptScoreInput) -> VisualConceptScores:
    concept = payload.concept
    path = Path(concept.image_path)
    if not path.exists():
        return VisualConceptScores(notes="Image file not found — couldn't score.")

    ext = path.suffix.lstrip(".").lower()
    media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
    b64_data = base64.b64encode(path.read_bytes()).decode("ascii")

    response = _claude_client.messages.create(
        model=settings.claude_structuring_model,
        max_tokens=512,
        system=_SCORE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Intended prompt: {concept.prompt}"},
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
                ],
            }
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    try:
        data = json.loads(extract_json_text(response.content))
    except json.JSONDecodeError:
        return VisualConceptScores(notes="Scoring failed — malformed response.")
    return VisualConceptScores(**data)


def render_download(payload: VisualConceptDownloadInput) -> str:
    """A fresh, native 4K render (same prompt/seed, requested at Gemini's "4K"
    image_size) — not an upscale of the small preview. Resized only if the
    native output doesn't already land exactly on the target canvas."""
    concept = payload.concept
    prompt = _build_full_prompt(concept)
    data, _model, _elapsed = _call_with_retry(
        lambda: _generate_image(prompt, concept.aspect_ratio, seed=concept.seed, image_size=_IMAGE_SIZE_DOWNLOAD),
        label="download",
    )
    image = Image.open(io.BytesIO(data))
    canvas = _4k_canvas_for(concept.aspect_ratio)
    if image.size != canvas:
        image = image.resize(canvas, Image.LANCZOS)

    ext = payload.format.lower()
    if ext not in ("png", "jpeg", "jpg", "webp"):
        ext = "png"
    path = _save_pil_image(image, ext=ext)
    logger.info("[download] Saved successfully. -> %s", path)
    return path


def generate_test_image() -> dict:
    """Diagnostic — isolates whether a failure is in the Gemini pipeline
    itself or in the script-to-image flow around it. Fixed, simple prompt so
    results are comparable across runs."""
    prompt = "A photorealistic apple on a wooden table, cinematic lighting."
    logger.info(
        "[test] API Key Loaded: %s | Model: %s",
        "YES" if settings.gemini_api_key else "NO",
        settings.gemini_image_model,
    )
    data, model, elapsed = _call_with_retry(lambda: _generate_image(prompt, "1:1"), label="test")
    path = _save_bytes(data)
    logger.info("[test] Saved successfully. -> %s", path)
    return {"image_path": path, "used_model": model, "elapsed_seconds": round(elapsed, 1)}


def get_debug_info() -> dict:
    """Static config + a real connectivity check — fast, no image generation."""
    api_key_loaded = bool(settings.gemini_api_key)
    internet_access = False
    try:
        resp = requests.head("https://generativelanguage.googleapis.com", timeout=5)
        internet_access = resp.status_code < 500
    except Exception as e:
        logger.warning("[debug] Connectivity check failed: %s", e)
    return {
        "api_key_loaded": api_key_loaded,
        "model": settings.gemini_image_model,
        "api_url": "https://generativelanguage.googleapis.com",
        "internet_access": internet_access,
    }
