import hashlib
import io
import json
import logging
import random
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
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
from app.services.compliance_rules import rules_for_category
from app.services.openrouter_utils import (
    call_openrouter_with_retry,
    generate_image,
    generate_text,
    image_part,
)

logger = logging.getLogger("visual_concept_service")

_IMAGE_SIZE_PREVIEW = "1K"
_IMAGE_SIZE_DOWNLOAD = "4K"


def _4k_canvas_for(aspect_ratio: str) -> tuple[int, int]:
    """The 4K-pixel-class canvas for this aspect ratio (3840 on the long edge,
    exactly 3840x2160 for 16:9). Gemini is asked to natively render at "4K"
    for downloads; this is a final correctness guarantee, not the primary
    resolution mechanism — a resize only happens if the native output doesn't
    already land exactly on this canvas."""
    try:
        w_ratio, h_ratio = (float(x) for x in aspect_ratio.split(":"))
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

_REALISM_DIRECTIVE = """REALISM & INDIAN CONTEXT (mandatory, applies to every generated image):
- If a person appears, they must look realistically Indian — natural Indian facial features, skin
  tones, hair, and body proportions — unless the concept explicitly calls for a different
  nationality. Never stereotypical or exaggerated "Indian" features. People must look like real
  photographs of real Indian people, NOT AI-generated characters: natural expressions, realistic
  skin texture and visible pores, natural hair, hands, eyes, and anatomy. Avoid plastic-looking
  skin, overly perfect symmetrical faces, distorted or extra-fingered hands, unnatural eyes, or
  artificial proportions.
- If the scene has a location (home, street, workplace, college, hospital, restaurant, shop, family
  setting), make it authentically and contemporarily Indian where appropriate — realistic Indian
  architecture, interiors, streets, vehicles, clothing, signage, and everyday objects, kept
  believable and current rather than stereotypical.
- Prioritize photorealism: this must look like professionally photographed commercial advertising
  photography — realistic lighting, natural shadows, real depth of field, believable reflections and
  materials, natural color grading. Never an illustration, 3D render, cartoon, CGI, or generic
  AI-art look. Avoid excessive cinematic effects, glowing edges, neon lighting, unrealistic bokeh, or
  artificial HDR unless explicitly requested.
- If a product is shown, its shape, packaging, branding, logo, typography, colors, and proportions
  must stay accurate to what's described or referenced — never invent or redesign the packaging;
  product placement should look natural and premium.
- If text is required in the image, it must be clean, correctly spelled, professionally positioned,
  and visually integrated, with a clear hierarchy between headline, supporting copy, CTA, and
  branding — never gibberish.
- Avoid: cartoon, illustration, 3D render, CGI, plastic skin, deformed or extra-fingered hands,
  warped anatomy, unnatural eyes, watermark, oversaturated colors, generic AI-art look.
The final image should look like something a professional Indian advertising agency could actually
publish directly in a social-media ad — photorealistic Indian commercial advertising photography,
premium brand design, natural human appearance, authentic Indian context, professional art
direction."""

_AD_CREATIVE_DIRECTIVE = """FINAL AD CREATIVE MODE (mandatory — never a plain photograph):
This request is for a finished advertisement, not a photograph. NEVER return a plain cinematic
photograph, plain lifestyle photograph, plain product photograph, generic portrait, generic UGC
photo, or any cinematic scene with no advertising design on it — a subject simply standing in an
environment with no ad layout is a FAILED result, no matter how well-lit or photorealistic. If a
design reference is supplied, treat it as the AD LAYOUT BLUEPRINT (headline placement, typography,
CTA placement/styling, logo/badge placement, color palette, spacing, card/container treatment) —
reproduce that design system around the new content, not just its photographic mood.
Render any headline, supporting message, CTA, or branding called for directly INSIDE the image,
using a real advertising hierarchy (brand/logo -> headline -> supporting message -> subject/
product -> benefit -> CTA, using only the layers this concept actually needs). All on-image text
must be exactly the real, correctly spelled copy specified in the prompt — never gibberish,
placeholder text, or duplicated text — legible, high-contrast, properly spaced, and kept clear of
faces, hands, and product labels.
The result must look like a professionally designed paid-social advertisement that could be
downloaded and posted directly to Instagram, Facebook, or Reels right now, with no further editing
needed in Canva or Figma. Photorealism alone is not the goal — a beautiful photograph integrated
into a finished, text-and-branding-complete advertising creative is the goal."""

_SCENE_PLAN_SYSTEM_PROMPT = """You are an award-winning advertising creative director producing
FINAL, COMPLETE, READY-TO-PUBLISH STATIC AD CREATIVES — the visual and design quality bar of
Apple, Nike, Coca-Cola, A24, Netflix, or Google Pixel paid-social campaigns. You are given a
finished short-form ad script (hook, body, CTA), its persona, emotion, creative angle, target
duration, target audience, brand tone, product info, script language, and category compliance
rules. Create exactly 3 completely different FINISHED AD CREATIVES for this campaign, in this
order — NOT 5, exactly 3:

1. HOOK / PROBLEM — the opening 3 seconds. Highest attention, scroll-stopping. Grounded in the
   actual hook line and persona given below — the relatable situation/problem the script opens on.
2. TURNING POINT / PRODUCT — the product story and human emotion at the heart of the script's
   body: the moment the product enters the person's situation. Grounded in the actual body of the
   script. Real, specific facial expressions and body language.
3. OUTCOME / CTA — the product hero moment. Premium advertisement styling, brand colors, grounded
   in the script's CTA/resolution. Hopeful, bright, premium.

CRITICAL RULE — NEVER a plain photograph: each of the 3 is a COMPLETE AD CREATIVE, not a bare
cinematic/lifestyle/product photograph. A beautiful photograph with no advertising design on it is
a FAILED output, no matter how well-lit or well-composed it is. Every concept must read as a
finished advertisement someone could download and post directly to Instagram/Facebook/Reels right
now — headline, supporting copy, and CTA rendered directly inside the image using a real
advertising hierarchy, not left for the user to add in Canva/Figma afterward. Not every concept
needs every layer (brand/logo, headline, supporting message, CTA), but every concept must feel
intentionally designed as an ad, never as a raw scene.

AD COPY SOURCE (critical): the actual on-image headline/supporting-line/CTA wording you specify in
each "prompt" must be adapted from the REAL script lines and product info given below — never
invented generic ad-speak. Keep it short and punchy (a headline is a few words, not a sentence).
Write this on-image copy in the script's actual language (see "Script language" below) — if it is
Hinglish, write natural spoken Hinglish in Roman script (Hindi sentence structure, natural
English code-switching, e.g. "Exam kal hai. Aaj raat sleep compromise mat karo." — never a stiff
mechanical translation); if Hindi, natural Devanagari; if English, natural native-level English.

REFERENCE-DESIGN NOTE: when reference images are supplied at generation time, they define the ad's
LAYOUT and DESIGN SYSTEM (headline placement, typography, CTA styling, badge/logo placement,
color palette, spacing, card treatment) — so write each "prompt" assuming that design language will
be applied, describing WHAT text/copy/branding this specific concept needs and where it belongs in
the hierarchy (brand/logo -> headline -> supporting message -> subject/product -> benefit -> CTA),
not a from-scratch layout invention.

For each of the 3, write:
- "scene_title": a short evocative title
- "scene_label": exactly "hook", "emotional", or "transformation" respectively (internal labels —
  "hook" means Hook/Problem, "emotional" means Turning Point/Product, "transformation" means
  Outcome/CTA)
- "prompt": ONE rich, specific ad-creative prompt (120-220 words), detailed enough to hand directly
  to an image-generation model with zero further interpretation, describing BOTH the photography
  (subject(s) and their specific expression/action, props, lighting, camera/lens, mood, color
  grading, composition) AND the advertising design layer (the exact headline text, supporting
  copy, CTA text, and branding to render inside the image, and where each belongs). Concrete
  photography/production-quality language: cinematic lighting, shallow depth of field, 85mm lens,
  studio color grading, ultra photorealistic, sharp focus, natural skin texture, subtle film grain,
  premium commercial advertising photography, ultra detailed — combined with concrete graphic-
  design language: headline typography, CTA button/badge styling, logo placement, negative space,
  text-to-image ratio. Must comply with the category compliance rules given below — never depict
  or claim anything those rules prohibit. Ground every detail in the ACTUAL script, persona, and
  product given below — never generic stock-photo phrasing (e.g. not "student studying", but the
  specific late-night scene the script actually describes) and never gibberish/placeholder text —
  every word of on-image copy must be real, spelled correctly, and mean something. Keep any
  specified text placement away from faces, hands, and product labels. If the concept includes a
  person, describe them as realistically Indian (natural Indian features, skin tone, hair, and
  clothing appropriate to the context — never stereotypical) unless the product/brief genuinely
  calls for a different nationality; if the concept includes a location, ground it in an authentic,
  contemporary Indian setting (home, street, workplace, shop, etc.) with real Indian architecture,
  interiors, and everyday detail, unless the brief says otherwise.
- "negative_prompt": comma-separated list of things to avoid, e.g. "plain photograph with no ad
  design, cartoon, illustration, plastic skin, deformed hands, extra fingers, low quality, blurry,
  watermark, gibberish text, misspelled text, oversaturated"
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
    full = f"{base}. {extras}." if extras else f"{base}."
    negative = sp.negative_prompt.strip()
    return f"{full} Avoid: {negative}." if negative else full


# ---------------------------------------------------------------------------
# OpenRouter calls
# ---------------------------------------------------------------------------

_image_cache: dict[str, tuple[bytes, str, float]] = {}


def _cache_key(mode: str, prompt_or_instruction: str, aspect_ratio: str, seed: int | None, image_hash: str = "") -> str:
    raw = f"{mode}|{aspect_ratio}|{seed}|{image_hash}|{prompt_or_instruction}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Reference-image conditioning — every fresh generation is grounded in
# whatever image(s) sit in settings.references_dir (see references/README.md),
# sent to Gemini as actual image input alongside the prompt, not just
# described in text.
# ---------------------------------------------------------------------------

_REFERENCE_IMAGE_EXTENSIONS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _references_dir() -> Path:
    d = Path(settings.references_dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _natural_sort_key(path: Path) -> list:
    """Numeric-aware sort so `i2.jpeg` sorts before `i11.jpeg` (plain string
    sort would put i10-i19 before i2-i9)."""
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", path.stem)]


def _reference_paths() -> list[Path]:
    """Filename sort order determines primary (first) vs. supporting
    references — e.g. `01-hero.jpg`, `02-detail.jpg`."""
    files = (p for p in _references_dir().iterdir() if p.is_file() and p.suffix.lower() in _REFERENCE_IMAGE_EXTENSIONS)
    return sorted(files, key=_natural_sort_key)


def _load_reference_images() -> list[bytes]:
    return [p.read_bytes() for p in _reference_paths()]


def _references_signature() -> str:
    """Cheap fingerprint (paths + mtimes, no content hashing) of the
    references folder's current contents, so swapping reference images
    invalidates the image cache instead of silently reusing a stale render."""
    sig = "|".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in _reference_paths())
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16]


def _build_reference_conditioned_prompt(new_request: str, reference_count: int) -> str:
    multi_note = (
        "\nMultiple reference images are attached — use the first as the primary reference for "
        "layout and overall design direction; treat the rest as supporting references for specific "
        "characteristics only. Do not randomly mix unrelated elements between them."
        if reference_count > 1
        else ""
    )
    return f"""REFERENCE IMAGE — DESIGN BLUEPRINT (not just photographic inspiration):
The attached image is the primary design reference. Analyze it carefully before generating the
image.{multi_note}

The reference(s) are finished advertising creatives. They define the expected FINAL OUTPUT FORMAT,
DESIGN LANGUAGE, COMPOSITION, TYPOGRAPHY, INFORMATION HIERARCHY, AND AD STRUCTURE for the new
image — not merely a photographic mood board. Do NOT simply copy the reference's photographic
subject (its specific people, product, or scene). DO reproduce its design system on the NEW
story/product content described in NEW REQUEST below.

EXTRACT AND REPRODUCE from the reference:
Overall advertising layout, text placement, headline hierarchy, typography style, CTA placement
and styling, brand/logo placement, badges, labels, visual hierarchy, image-to-text ratio, negative
space, card/container treatment, borders, shadows, gradients, color palette, composition, spacing,
and the general premium social-media-ad structure.

If the reference is a finished static advertisement containing IMAGE + HEADLINE + SUPPORTING TEXT
+ CTA + BRANDING, the generated result must also contain IMAGE + HEADLINE + SUPPORTING TEXT + CTA
+ BRANDING, applied to the new concept — it must NOT collapse down to just a bare image with no ad
design on it. Any on-image text must be exactly the wording specified in NEW REQUEST — real,
correctly spelled advertising copy, never gibberish, placeholder text, or a copy of the reference's
own wording.

NEW REQUEST:
{new_request}

MODIFICATIONS:
Apply the new story/product content and any copy specified above within the reference's design
system. Keep the layout, typography, and structural design language consistent with the reference
wherever this new concept's content allows.

VISUAL CONSISTENCY:
The final image should look as if it was designed by the same art director / ad agency that
created the reference image — same design system, new campaign content.

QUALITY:
Generate a highly detailed, polished, photorealistic, commercially usable finished advertisement
with realistic lighting, natural materials, accurate proportions, clean edges, high-quality
textures, and legible, correctly spelled, well-hierarchized typography.

IMPORTANT:
Do not output a plain photograph with no advertising design on it — that is a failed result
regardless of photographic quality. Do not ignore the reference's design system. Do not
unnecessarily change the layout, typography treatment, or overall design language it establishes."""


def _aspect_instruction(aspect_ratio: str, image_size: str) -> str:
    """OpenRouter's chat-completions image endpoint has no dedicated aspect
    ratio / resolution config (unlike Gemini's native ImageConfig) — folded
    into the prompt text instead."""
    resolution = (
        "the highest available native resolution — target 4K, at least 3840px on the long edge"
        if image_size == _IMAGE_SIZE_DOWNLOAD
        else "high native resolution"
    )
    return (
        f"\n\nRender this image in a strict {aspect_ratio} aspect ratio, at {resolution}. Fill "
        "the entire frame — no borders, letterboxing, or padding."
    )


def _generate_image(prompt: str, aspect_ratio: str, seed: int | None = None, image_size: str = _IMAGE_SIZE_PREVIEW) -> tuple[bytes, str, float]:
    t0 = time.time()
    reference_images = _load_reference_images()
    base_prompt = (
        _build_reference_conditioned_prompt(prompt, len(reference_images)) if reference_images else prompt
    )
    full_prompt = (
        base_prompt
        + _aspect_instruction(aspect_ratio, image_size)
        + "\n\n"
        + _AD_CREATIVE_DIRECTIVE
        + "\n\n"
        + _REALISM_DIRECTIVE
    )
    data = generate_image(
        full_prompt,
        model=settings.openrouter_image_model,
        seed=seed,
        reference_images=reference_images or None,
    )
    return data, settings.openrouter_image_model, time.time() - t0


def _edit_image(image_bytes: bytes, instruction: str, aspect_ratio: str, image_size: str = _IMAGE_SIZE_PREVIEW) -> tuple[bytes, str, float]:
    """Image-conditioned edit — the current image + a natural-language
    instruction, used for Edit Prompt, style presets, Generate Similar, and
    Generate Different Angle, so edits actually preserve the rest of the
    scene instead of regenerating a whole new one from scratch."""
    t0 = time.time()
    full_instruction = (
        instruction
        + _aspect_instruction(aspect_ratio, image_size)
        + "\n\n"
        + _AD_CREATIVE_DIRECTIVE
        + "\n\n"
        + _REALISM_DIRECTIVE
    )
    data = generate_image(full_instruction, model=settings.openrouter_image_model, reference_images=[image_bytes])
    return data, settings.openrouter_image_model, time.time() - t0


def _generate_cached(prompt: str, aspect_ratio: str, seed: int | None, label: str) -> tuple[bytes, str, float]:
    key = _cache_key("gen", prompt, aspect_ratio, seed, _references_signature())
    cached = _image_cache.get(key)
    if cached:
        logger.info("[%s] Cache hit — reusing existing image, no OpenRouter call.", label)
        return cached
    result = call_openrouter_with_retry(lambda: _generate_image(prompt, aspect_ratio, seed), label=label)
    _image_cache[key] = result
    return result


def _edit_cached(image_bytes: bytes, instruction: str, aspect_ratio: str, label: str) -> tuple[bytes, str, float]:
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    key = _cache_key("edit", instruction, aspect_ratio, None, image_hash)
    cached = _image_cache.get(key)
    if cached:
        logger.info("[%s] Cache hit — reusing existing image, no OpenRouter call.", label)
        return cached
    result = call_openrouter_with_retry(lambda: _edit_image(image_bytes, instruction, aspect_ratio), label=label)
    _image_cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Scene planning (text generation, richer context)
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
        f"Product / brand name: {p.product_name}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n"
        f"Target audience: {p.target_audience}\n"
        f"Brand tone: {p.tone or 'unspecified'}\n"
        f"Story persona: {s.persona}\n"
        f"Emotion: {s.emotion}\n"
        f"Creative angle: {payload.creative_angle or 'none specified'}\n"
        f"Target duration: {payload.script.target_duration or s.estimated_length or 'unspecified'}\n"
        f"Script language (write all on-image ad copy natively in this register): "
        f"{payload.script.script_language.value}\n\n"
        f"Category compliance rules (do not depict or claim anything these prohibit):\n{rules_block}\n\n"
        f"Full script (source the on-image headline/copy/CTA wording from these actual lines, "
        f"adapted and shortened for an image, not invented):\n{_flatten_script_text(payload.script)}"
    )


def plan_visual_concepts(payload: VisualConceptsInput) -> list[VisualConcept]:
    logger.info("Preparing prompt... understanding story — product=%s situation=%s", payload.structured_product.product_name, payload.situation.title)
    text = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_SCENE_PLAN_SYSTEM_PROMPT,
            contents=[_build_plan_user_message(payload)],
            model=settings.openrouter_text_model,
            max_output_tokens=6144,
            json_mode=True,
        ),
        label="plan_visual_concepts",
    )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Gemini returned malformed JSON while planning visual concepts.")
        raise ValueError("Gemini returned malformed JSON while planning visual concepts.") from e

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
    concept.status = "completed"
    concept.error = None
    logger.info("[%s] Saved successfully. -> %s", label, concept.image_path)
    return concept


def generate_visual_concepts(payload: VisualConceptsInput) -> VisualConceptsResult:
    """Storyboard section — plan 3 distinct scene concepts from the finished
    script, then render all 3 concurrently (each OpenRouter call is
    blocking)."""
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
    concept.status = "completed"
    concept.error = None
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

    try:
        text = call_openrouter_with_retry(
            lambda: generate_text(
                system_instruction=_SCORE_SYSTEM_PROMPT,
                contents=[
                    f"Intended prompt: {concept.prompt}",
                    image_part(path.read_bytes(), media_type),
                ],
                model=settings.openrouter_text_model,
                max_output_tokens=1024,
                json_mode=True,
            ),
            label="score_visual_concept",
        )
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return VisualConceptScores(notes="Scoring failed — malformed response.")
    return VisualConceptScores(**data)


def render_download(payload: VisualConceptDownloadInput) -> str:
    """A fresh, native 4K render (same prompt/seed, requested at Gemini's "4K"
    image_size) — not an upscale of the small preview. Resized only if the
    native output doesn't already land exactly on the target canvas."""
    concept = payload.concept
    prompt = _build_full_prompt(concept)
    data, _model, _elapsed = call_openrouter_with_retry(
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


def generate_static_visual(prompt: str, aspect_ratio: str = "1:1") -> dict:
    """One-off image render for a static creative's ai_image_prompt — reuses
    the same generation/quality pipeline as a video VisualConcept (reference
    conditioning, ad-creative/realism directives, retry) without the scene
    planning, scoring, or style-param editing machinery those carry."""
    seed = random.randint(1, 2_000_000_000)
    data, model, elapsed = _generate_cached(prompt, aspect_ratio, seed, "static_visual")
    path = _save_bytes(data)
    logger.info("[static_visual] Saved successfully. -> %s", path)
    return {"image_path": path, "used_model": model, "elapsed_seconds": round(elapsed, 1), "seed": seed}


def generate_test_image() -> dict:
    """Diagnostic — isolates whether a failure is in the OpenRouter image
    pipeline itself or in the script-to-image flow around it. Fixed, simple
    prompt so results are comparable across runs."""
    prompt = "A photorealistic apple on a wooden table, cinematic lighting."
    logger.info(
        "[test] API Key Loaded: %s | Model: %s",
        "YES" if settings.openrouter_api_key else "NO",
        settings.openrouter_image_model,
    )
    data, model, elapsed = call_openrouter_with_retry(lambda: _generate_image(prompt, "1:1"), label="test")
    path = _save_bytes(data)
    logger.info("[test] Saved successfully. -> %s", path)
    return {"image_path": path, "used_model": model, "elapsed_seconds": round(elapsed, 1)}


def get_debug_info() -> dict:
    """Static config + a real connectivity check — fast, no image generation."""
    api_key_loaded = bool(settings.openrouter_api_key)
    internet_access = False
    try:
        resp = requests.head("https://openrouter.ai/api/v1/models", timeout=5)
        internet_access = resp.status_code < 500
    except Exception as e:
        logger.warning("[debug] Connectivity check failed: %s", e)
    return {
        "api_key_loaded": api_key_loaded,
        "model": settings.openrouter_image_model,
        "api_url": "https://openrouter.ai/api/v1",
        "internet_access": internet_access,
    }
