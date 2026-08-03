from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    url = "url"
    description = "description"
    none = "none"


class ProductInput(BaseModel):
    """Stage 1 — what the user submits via the form."""

    product_name: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    source_type: SourceType
    source_url: Optional[str] = None
    source_description: Optional[str] = None

    # Manual fallback fields, required only when source_type == none
    manual_ingredients: Optional[str] = None
    manual_usp: Optional[str] = None


class StructuredProduct(BaseModel):
    """Stage 3 output — what every later stage consumes."""

    product_name: str
    target_audience: str
    ingredients: list[str] = Field(default_factory=list)
    usp: str = ""
    tone: str = ""
    key_benefits: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ScriptGenerationInput(BaseModel):
    """Stage 6 input — structured product data plus platform context.

    similar_past_winners is optional and stays empty until Stage 5 (retrieval)
    is wired up — Stage 6 works without it, just with less grounding.
    """

    structured_product: StructuredProduct
    product_category: str = Field(..., min_length=1)
    platform: str = "instagram_reel"
    similar_past_winners: list[str] = Field(default_factory=list)
    max_line_chars: int = 90


class ScriptLine(BaseModel):
    text: str
    visual_tags: list[str] = Field(default_factory=list)


class GeneratedScript(BaseModel):
    """Stage 6 output — consumed directly by Stage 7 (compliance) and Stage 8 (assets)."""

    hook: ScriptLine
    body: list[ScriptLine] = Field(default_factory=list)
    cta: ScriptLine

    @property
    def full_text(self) -> str:
        lines = [self.hook.text, *[line.text for line in self.body], self.cta.text]
        return "\n".join(lines)


class AssetSourcingInput(BaseModel):
    """Stage 8 input — one entry per script line, each with its own visual tags."""

    line_id: str = Field(..., description="e.g. 'hook', 'body_0', 'cta' — ties the asset back to a script line")
    visual_tags: list[str] = Field(..., min_length=1)


class AssetCandidate(BaseModel):
    source: str  # "pexels" | "pixabay"
    url: str
    thumbnail_url: str
    width: int
    height: int


class SelectedAsset(BaseModel):
    line_id: str
    tag_used: str
    broadened: bool = False
    candidate: Optional[AssetCandidate] = None
    reasoning: str = ""


class MotionGenerationInput(BaseModel):
    """Stage 8.5 (optional) — animate one sourced image into a short video clip."""

    line_id: str
    image_url: str = Field(..., min_length=1)
    visual_tags: list[str] = Field(default_factory=list)


class MotionGenerationResult(BaseModel):
    line_id: str
    video_path: str
    prompt_used: str


class VoiceoverLine(BaseModel):
    line_id: str
    text: str


class VoiceoverInput(BaseModel):
    lines: list[VoiceoverLine] = Field(..., min_length=1)


class VoiceoverResult(BaseModel):
    line_id: str
    hindi_text: str
    audio_path: str
    duration_seconds: float


class RenderLine(BaseModel):
    text: str
    image_url: str
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    min_duration_seconds: Optional[float] = None


class RenderInput(BaseModel):
    """Stage 9 input — script lines already paired with their chosen assets."""

    product_name: str = Field(..., min_length=1)
    lines: list[RenderLine] = Field(..., min_length=1)
    seconds_per_line: float = 3.0


class RenderResult(BaseModel):
    output_path: str
    duration_seconds: float


class ComplianceCheckInput(BaseModel):
    """Stage 7 input — the final script text plus category context.

    Independent from whatever produced the script (Stage 6 today, anything
    else later) — this stage only ever sees the finished text.
    """

    script_text: str = Field(..., min_length=1)
    product_category: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)


class ComplianceViolation(BaseModel):
    phrase: str
    reason: str
    severity: str  # "blocker" | "warning"


class ComplianceResult(BaseModel):
    """Stage 7 output — pass/fail gate before a script can reach rendering."""

    passed: bool
    violations: list[ComplianceViolation] = Field(default_factory=list)
    notes: str = ""
