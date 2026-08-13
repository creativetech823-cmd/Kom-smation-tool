import logging
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.product import (
    AssetSourcingInput,
    AutoFillInput,
    AutoFillSuggestion,
    ComplianceCheckInput,
    ComplianceResult,
    FetchUrlInput,
    FetchUrlResult,
    GeneratedScript,
    MotionGenerationInput,
    MotionGenerationResult,
    ProductInput,
    ReferenceAnalysis,
    ReferenceMaterial,
    RenderInput,
    RenderResult,
    RewriteLineInput,
    RewriteLineResult,
    ScriptGenerationInput,
    ScriptSectionRegenerateInput,
    SelectedAsset,
    SourceType,
    StorySituationsInput,
    StorySituationsResult,
    StructuredProduct,
    VoiceoverInput,
    VoiceoverResult,
)
from app.services.asset_service import source_asset_for_line
from app.services.autofill_service import suggest_product_fields
from app.services.claude_service import structure_product
from app.services.compliance_service import audit_script
from app.services.content_extraction_service import (
    ExtractionError,
    classify_link_kind,
    extract_from_upload,
    fetch_url_as_text,
)
from app.services.motion_service import generate_motion_clip
from app.services.render_service import render_video
from app.services.rewrite_service import rewrite_line
from app.services.script_service import generate_script, regenerate_script_section
from app.services.story_situation_service import generate_situations
from app.services.tts_service import synthesize_voiceover

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger("pipeline")

_MAX_CONTEXT_CHARS = 60_000


def _validate_input(payload: ProductInput) -> None:
    """Stage 1 gate — block generation on genuinely empty input."""
    if payload.source_type == SourceType.url and not payload.source_url:
        raise HTTPException(400, "source_url is required when source_type is 'url'")

    if payload.source_type == SourceType.description and not payload.source_description:
        raise HTTPException(400, "source_description is required when source_type is 'description'")

    if payload.source_type == SourceType.none:
        has_manual = payload.manual_ingredients and payload.manual_usp
        has_reference = any(m.analysis == ReferenceAnalysis.analyzed for m in payload.reference_materials)
        if not has_manual and not has_reference:
            raise HTTPException(
                400,
                "No source provided — manual_ingredients + manual_usp, or at least one analyzed "
                "reference material, are required to proceed without a URL or description.",
            )


def _build_context_text(payload: ProductInput) -> str:
    """Stage 2 — combine the primary source (description/URL) with every
    successfully analyzed reference material into one context blob for
    Stage 3 (structure_product)."""
    if payload.source_type == SourceType.description:
        primary = payload.source_description or ""
    elif payload.source_type == SourceType.url:
        if payload.source_url_raw_text:
            primary = payload.source_url_raw_text
        elif payload.source_url:
            try:
                primary, _title = fetch_url_as_text(payload.source_url)
            except ExtractionError as e:
                raise HTTPException(502, str(e))
            except Exception as e:
                logger.exception("Unhandled error fetching source_url in _build_context_text")
                raise HTTPException(502, f"Couldn't fetch that website: {e}")
        else:
            primary = ""
    else:
        primary = ""

    reference_blocks = [
        f"--- Reference: {m.filename or m.source_url or m.id} ({m.kind.value}) ---\n{m.extracted_text}"
        for m in payload.reference_materials
        if m.analysis == ReferenceAnalysis.analyzed and m.extracted_text.strip()
    ]
    combined = "\n\n".join(block for block in [primary, *reference_blocks] if block)
    return combined[:_MAX_CONTEXT_CHARS]


@router.post("/structure", response_model=StructuredProduct)
def structure(payload: ProductInput) -> StructuredProduct:
    """Stage 1 + Stage 3 — validate input, then structure it via Claude."""
    _validate_input(payload)
    raw_text = _build_context_text(payload)
    try:
        return structure_product(payload, raw_text=raw_text)
    except ValueError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        logger.exception("Unhandled error in structure_product")
        raise HTTPException(502, f"Couldn't structure this product: {e}")


@router.post("/fetch-url", response_model=FetchUrlResult)
def fetch_url(payload: FetchUrlInput) -> FetchUrlResult:
    """Website URL source — fetch + clean a page's content (YouTube gets its
    caption transcript instead) for staged-progress preview and auto-fill."""
    try:
        raw_text, title = fetch_url_as_text(payload.url)
    except ExtractionError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        logger.exception("Unhandled error in fetch_url_as_text for url=%r", payload.url)
        raise HTTPException(502, f"Couldn't fetch that website: {e}")
    return FetchUrlResult(
        raw_text=raw_text,
        title=title,
        char_count=len(raw_text),
        truncated=len(raw_text) >= 200_000,
    )


@router.post("/autofill-product", response_model=AutoFillSuggestion)
def autofill_product(payload: AutoFillInput) -> AutoFillSuggestion:
    """Guess editable product fields from raw extracted text, before the
    user has necessarily entered a product name or target audience."""
    try:
        return suggest_product_fields(payload)
    except ValueError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        logger.exception("Unhandled error in suggest_product_fields")
        raise HTTPException(502, f"Couldn't analyze that content: {e}")


@router.post("/reference-materials/upload", response_model=ReferenceMaterial)
async def upload_reference_material(file: UploadFile = File(...)) -> ReferenceMaterial:
    """Reference Materials — upload + extract one file (PDF/DOCX/PPTX/TXT/CSV/
    XLSX/ZIP/image analyzed; legacy doc/ppt and video/audio stored only)."""
    try:
        return await extract_from_upload(file)
    except ExtractionError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Unhandled error extracting upload filename=%r", file.filename)
        raise HTTPException(502, f"Couldn't process that file: {e}")


@router.post("/reference-materials/url", response_model=ReferenceMaterial)
def add_reference_material_url(payload: FetchUrlInput) -> ReferenceMaterial:
    """Reference Materials — attach a pasted link (website, YouTube, or any
    publicly accessible Drive/Dropbox/Notion URL) as a reference material."""
    kind = classify_link_kind(payload.url)
    material_id = uuid4().hex[:12]
    try:
        raw_text, _title = fetch_url_as_text(payload.url)
    except ExtractionError as e:
        return ReferenceMaterial(
            id=material_id,
            kind=kind,
            source_url=payload.url,
            analysis=ReferenceAnalysis.failed,
            note=str(e),
        )
    except Exception as e:
        logger.exception("Unhandled error fetching reference url=%r", payload.url)
        return ReferenceMaterial(
            id=material_id,
            kind=kind,
            source_url=payload.url,
            analysis=ReferenceAnalysis.failed,
            note=f"Couldn't fetch that link: {e}",
        )
    truncated = len(raw_text) > 40_000
    return ReferenceMaterial(
        id=material_id,
        kind=kind,
        source_url=payload.url,
        analysis=ReferenceAnalysis.analyzed,
        extracted_text=raw_text[:40_000],
        truncated=truncated,
    )


@router.post("/story-situations", response_model=StorySituationsResult)
def story_situations(payload: StorySituationsInput) -> StorySituationsResult:
    """Stage 3.5 — structured product -> diverse story-situation options for the user to pick from."""
    try:
        return generate_situations(payload)
    except Exception as e:
        logger.exception("Unhandled error in generate_situations")
        raise HTTPException(502, f"Couldn't generate story ideas: {e}")


@router.post("/generate-script", response_model=GeneratedScript)
def generate(payload: ScriptGenerationInput) -> GeneratedScript:
    """Stage 6 — structured product -> hook/body/CTA + visual search tags."""
    try:
        return generate_script(payload)
    except Exception as e:
        logger.exception("Unhandled error in generate_script")
        raise HTTPException(502, f"Couldn't generate the script: {e}")


@router.post("/regenerate-script-section", response_model=GeneratedScript)
def regenerate_script(payload: ScriptSectionRegenerateInput) -> GeneratedScript:
    """Stage 6 (targeted) — rewrite only one part of an already-generated
    script (hook, CTA, science section, etc.), leaving the rest untouched."""
    try:
        return regenerate_script_section(payload)
    except Exception as e:
        logger.exception("Unhandled error in regenerate_script_section")
        raise HTTPException(502, f"Couldn't regenerate that part of the script: {e}")


@router.post("/rewrite-line", response_model=RewriteLineResult)
def rewrite_line_endpoint(payload: RewriteLineInput) -> RewriteLineResult:
    """AI quick-action — rewrite one script line's text per a directive."""
    try:
        return rewrite_line(payload)
    except Exception as e:
        logger.exception("Unhandled error in rewrite_line")
        raise HTTPException(502, f"Couldn't rewrite that line: {e}")


@router.post("/compliance-audit", response_model=ComplianceResult)
def compliance_audit(payload: ComplianceCheckInput) -> ComplianceResult:
    """Stage 7 — independent compliance pass over a finished script."""
    try:
        return audit_script(payload)
    except Exception as e:
        logger.exception("Unhandled error in audit_script")
        raise HTTPException(502, f"Couldn't run the compliance check: {e}")


@router.post("/source-asset", response_model=SelectedAsset)
def source_asset(payload: AssetSourcingInput) -> SelectedAsset:
    """Stage 8 — search Pexels/Pixabay for one script line's visual tags,
    auto-broadening on zero results, then Claude Vision picks the best match."""
    try:
        return source_asset_for_line(payload)
    except Exception as e:
        logger.exception("Unhandled error in source_asset_for_line")
        raise HTTPException(502, f"Couldn't source an asset: {e}")


@router.post("/generate-motion", response_model=MotionGenerationResult)
def generate_motion(payload: MotionGenerationInput) -> MotionGenerationResult:
    """Stage 8.5 (optional) — animate a sourced image into a short motion
    clip via Hugging Face's free-tier Inference Provider credits."""
    try:
        return generate_motion_clip(payload)
    except Exception as e:
        logger.exception("Unhandled error in generate_motion_clip")
        raise HTTPException(502, f"Motion generation failed: {e}")


@router.post("/voiceover", response_model=list[VoiceoverResult])
def voiceover(payload: VoiceoverInput) -> list[VoiceoverResult]:
    """Stage 9 (voiceover) — translate each line to Hindi and synthesize
    spoken audio via gTTS, one file per line."""
    try:
        return [synthesize_voiceover(line) for line in payload.lines]
    except Exception as e:
        logger.exception("Unhandled error in synthesize_voiceover")
        raise HTTPException(502, f"Couldn't generate voiceover: {e}")


@router.post("/render", response_model=RenderResult)
def render(payload: RenderInput) -> RenderResult:
    """Stage 9 — inject script lines + assets into the Remotion template
    and render a finished MP4."""
    try:
        return render_video(payload)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.exception("Unhandled error in render_video")
        raise HTTPException(500, f"Render failed: {e}")
