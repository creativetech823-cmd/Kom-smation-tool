from fastapi import APIRouter, HTTPException

from app.models.product import (
    AssetSourcingInput,
    ComplianceCheckInput,
    ComplianceResult,
    GeneratedScript,
    MotionGenerationInput,
    MotionGenerationResult,
    ProductInput,
    RenderInput,
    RenderResult,
    RewriteLineInput,
    RewriteLineResult,
    ScriptGenerationInput,
    SelectedAsset,
    SourceType,
    StorySituationsInput,
    StorySituationsResult,
    StructuredProduct,
    VoiceoverInput,
    VoiceoverResult,
)
from app.services.asset_service import source_asset_for_line
from app.services.claude_service import structure_product
from app.services.compliance_service import audit_script
from app.services.motion_service import generate_motion_clip
from app.services.render_service import render_video
from app.services.rewrite_service import rewrite_line
from app.services.script_service import generate_script
from app.services.story_situation_service import generate_situations
from app.services.tts_service import synthesize_voiceover

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _validate_input(payload: ProductInput) -> None:
    """Stage 1 gate — block generation on genuinely empty input."""
    if payload.source_type == SourceType.url and not payload.source_url:
        raise HTTPException(400, "source_url is required when source_type is 'url'")

    if payload.source_type == SourceType.description and not payload.source_description:
        raise HTTPException(400, "source_description is required when source_type is 'description'")

    if payload.source_type == SourceType.none:
        if not payload.manual_ingredients or not payload.manual_usp:
            raise HTTPException(
                400,
                "No source provided — manual_ingredients and manual_usp are required "
                "to proceed without a URL or description.",
            )


def _resolve_raw_text(payload: ProductInput) -> str:
    """Stage 2 (scraping) is not wired up yet — URL sources fall back to
    whatever manual context is available until Jina Reader is integrated."""
    if payload.source_type == SourceType.description:
        return payload.source_description or ""
    if payload.source_type == SourceType.url:
        raise HTTPException(
            501,
            "URL scraping (Stage 2 / Jina Reader) is not implemented yet — "
            "submit source_type='description' or 'none' for now.",
        )
    return ""


@router.post("/structure", response_model=StructuredProduct)
def structure(payload: ProductInput) -> StructuredProduct:
    """Stage 1 + Stage 3 — validate input, then structure it via Claude."""
    _validate_input(payload)
    raw_text = _resolve_raw_text(payload)
    try:
        return structure_product(payload, raw_text=raw_text)
    except ValueError as e:
        raise HTTPException(502, str(e))


@router.post("/story-situations", response_model=StorySituationsResult)
def story_situations(payload: StorySituationsInput) -> StorySituationsResult:
    """Stage 3.5 — structured product -> diverse story-situation options for the user to pick from."""
    return generate_situations(payload)


@router.post("/generate-script", response_model=GeneratedScript)
def generate(payload: ScriptGenerationInput) -> GeneratedScript:
    """Stage 6 — structured product -> hook/body/CTA + visual search tags."""
    return generate_script(payload)


@router.post("/rewrite-line", response_model=RewriteLineResult)
def rewrite_line_endpoint(payload: RewriteLineInput) -> RewriteLineResult:
    """AI quick-action — rewrite one script line's text per a directive."""
    return rewrite_line(payload)


@router.post("/compliance-audit", response_model=ComplianceResult)
def compliance_audit(payload: ComplianceCheckInput) -> ComplianceResult:
    """Stage 7 — independent compliance pass over a finished script."""
    return audit_script(payload)


@router.post("/source-asset", response_model=SelectedAsset)
def source_asset(payload: AssetSourcingInput) -> SelectedAsset:
    """Stage 8 — search Pexels/Pixabay for one script line's visual tags,
    auto-broadening on zero results, then Claude Vision picks the best match."""
    return source_asset_for_line(payload)


@router.post("/generate-motion", response_model=MotionGenerationResult)
def generate_motion(payload: MotionGenerationInput) -> MotionGenerationResult:
    """Stage 8.5 (optional) — animate a sourced image into a short motion
    clip via Hugging Face's free-tier Inference Provider credits."""
    try:
        return generate_motion_clip(payload)
    except Exception as e:
        raise HTTPException(502, f"Motion generation failed: {e}")


@router.post("/voiceover", response_model=list[VoiceoverResult])
def voiceover(payload: VoiceoverInput) -> list[VoiceoverResult]:
    """Stage 9 (voiceover) — translate each line to Hindi and synthesize
    spoken audio via gTTS, one file per line."""
    return [synthesize_voiceover(line) for line in payload.lines]


@router.post("/render", response_model=RenderResult)
def render(payload: RenderInput) -> RenderResult:
    """Stage 9 — inject script lines + assets into the Remotion template
    and render a finished MP4."""
    try:
        return render_video(payload)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
