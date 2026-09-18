from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.product_library import ProductContext


class SourceType(str, Enum):
    url = "url"
    description = "description"
    none = "none"


class ScriptLanguage(str, Enum):
    english = "english"
    hindi = "hindi"
    hinglish = "hinglish"
    marathi = "marathi"
    gujarati = "gujarati"
    tamil = "tamil"
    telugu = "telugu"
    bengali = "bengali"
    kannada = "kannada"
    malayalam = "malayalam"
    custom = "custom"


class ScriptSection(str, Enum):
    """Which beat of the 9-part ad structure a script line belongs to."""

    hook = "hook"
    problem = "problem"
    science = "science"
    story = "story"
    product_intro = "product_intro"
    ingredients = "ingredients"
    benefits = "benefits"
    objection_handling = "objection_handling"
    cta = "cta"


class ContentType(str, Enum):
    """What kind of creative is being produced — determines which format
    catalog applies and which downstream pipeline stages are relevant."""

    video = "video"
    static = "static"


class ScriptRegenerateScope(str, Enum):
    """Which part of an already-generated script a regeneration request targets."""

    full = "full"
    hook = "hook"
    cta = "cta"
    science = "science"
    story = "story"
    product_explanation = "product_explanation"
    emotional_tone = "emotional_tone"
    length = "length"
    specific_scene = "specific_scene"


class ReferenceKind(str, Enum):
    """What a reference material is, for card icon/label + extraction dispatch."""

    pdf = "pdf"
    docx = "docx"
    pptx = "pptx"
    doc = "doc"
    ppt = "ppt"
    txt = "txt"
    csv = "csv"
    xlsx = "xlsx"
    zip = "zip"
    image = "image"
    video = "video"
    audio = "audio"
    website = "website"
    google_drive = "google_drive"
    youtube = "youtube"
    dropbox = "dropbox"
    notion = "notion"


class ReferenceAnalysis(str, Enum):
    """Whether a reference material's content actually made it into the AI's context."""

    analyzed = "analyzed"
    coming_soon = "coming_soon"  # video/audio — stored + previewable, not analyzed yet
    not_supported = "not_supported"  # legacy .doc/.ppt — no extractor available
    failed = "failed"


class ReferenceMaterial(BaseModel):
    """One uploaded file or pasted link attached as supporting context for Stage 3."""

    id: str
    kind: ReferenceKind
    filename: Optional[str] = None
    source_url: Optional[str] = None
    stored_path: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    analysis: ReferenceAnalysis
    extracted_text: str = ""
    truncated: bool = False
    note: str = ""


class FetchUrlInput(BaseModel):
    url: str = Field(..., min_length=1)


class FetchUrlResult(BaseModel):
    raw_text: str
    title: str = ""
    char_count: int = 0
    truncated: bool = False


class AutoFillInput(BaseModel):
    raw_text: str = Field(..., min_length=1)
    source_url: Optional[str] = None


class AutoFillSuggestion(BaseModel):
    """A first-draft, editable product profile guessed from raw scraped/extracted text."""

    product_name: str = ""
    target_audience: str = ""
    source_description: str = ""
    product_category: str = ""
    brand: str = ""
    keywords: list[str] = Field(default_factory=list)
    key_benefits: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


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

    # Reference Materials (Step 1 upgrade) — client-cached URL fetch avoids
    # re-hitting Jina Reader at submit time, plus any attached reference files/links.
    source_url_raw_text: Optional[str] = None
    reference_materials: list[ReferenceMaterial] = Field(default_factory=list)


class StructuredProduct(BaseModel):
    """Stage 3 output — what every later stage consumes."""

    product_name: str
    target_audience: str
    ingredients: list[str] = Field(default_factory=list)
    usp: str = ""
    tone: str = ""
    key_benefits: list[str] = Field(default_factory=list)
    industry: str = ""
    pain_points: list[str] = Field(default_factory=list)
    marketing_angle: str = ""
    key_emotions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class StorySituation(BaseModel):
    """Stage 3.5 output item — a creative marketing angle, not a script.

    Represents a person, problem, context, or emotional journey that could
    become a script. Generated by an AI creative director from the structured
    product profile; the user picks one before Stage 6 writes an actual script.
    """

    id: str
    title: str
    description: str
    emotion: str
    persona: str
    marketing_angle: str
    category: str  # e.g. "Emotional", "Educational" — Gemini-generated, not an enum
    difficulty: str  # "easy" | "medium" | "hard" — production complexity
    estimated_length: str  # e.g. "15s" | "30s" | "60s"
    virality_score: float = Field(ge=0.0, le=10.0)
    # Creative Angle (execution style) — the HOW, distinct from marketing_angle
    # (the WHY/strategy). Labels drawn from creative_angles.CREATIVE_ANGLES.
    recommended_angles: list[str] = Field(default_factory=list)
    # Story-Ideas Creative DNA upgrade (2026-09-18 task) — additive fields,
    # all default-empty so any existing consumer of this model (older
    # persisted projects, tests) is unaffected. Populated by
    # story_situation_service.py's pool-generation + filtering pipeline.
    human_situation: str = ""  # the specific person/moment, distinct from the broader `description`
    behavioral_tension: str = ""  # the concrete, observable tension — never a category-level generality
    creative_mechanism: str = ""  # a label from creative_mechanism_catalog.CREATIVE_MECHANISMS
    creative_engine: str = ""  # one sentence: WHAT behavior + WHAT object/ritual + WHAT creative turn
    product_role: str = ""  # the specific job the product does inside this idea
    # True only when this candidate cleared every hard gate (product truth,
    # claim safety, category correctness, non-genericness, distinctiveness)
    # AND scored strongly — an AND of earned conditions, never a numeric
    # score threshold alone. See story_situation_service._is_strong_concept.
    strong_concept: bool = False


class StorySituationsInput(BaseModel):
    """Stage 3.5 input — ask Gemini for N diverse story situations for a product."""

    structured_product: StructuredProduct
    product_category: str = Field(..., min_length=1)
    # Story Ideas UI hard cap (2026-09-18 task, Part 12): one generation
    # never shows more than 6 cards. Default changed from 10 to 6 to match;
    # generate_situations() also hard-caps its return at 6 regardless of
    # what's requested here, so a caller passing a larger value still never
    # gets more than 6 back.
    count: int = 6
    exclude_titles: list[str] = Field(default_factory=list)
    script_language: ScriptLanguage = ScriptLanguage.hinglish
    # Set when the user selected an AyushWellness Product Library product —
    # richer grounding for the ProductCreativeContract built before story
    # discovery runs. None = the existing manual-product flow, unchanged.
    product_context: Optional[ProductContext] = None


class StorySituationsResult(BaseModel):
    situations: list[StorySituation] = Field(default_factory=list)
    # True when fewer than the requested (capped-at-6) concepts survived the
    # quality/safety gates even after bounded retries (Part 13) — the
    # frontend should show only the valid concepts and MAY surface this as a
    # "fewer strong concepts this time" note, never pad with weak filler.
    generation_shortfall: bool = False


class ScriptGenerationInput(BaseModel):
    """Stage 6 input — structured product data plus the chosen story situation.

    similar_past_winners is optional and stays empty until Stage 5 (retrieval)
    is wired up — Stage 6 works without it, just with less grounding.
    """

    structured_product: StructuredProduct
    selected_situation: StorySituation
    product_category: str = Field(..., min_length=1)
    platform: str = "instagram_reel"
    similar_past_winners: list[str] = Field(default_factory=list)
    max_line_chars: int = 90
    # Creative Angle (execution style) — a catalog label (e.g. "Meta Glasses
    # POV") or arbitrary custom instruction (e.g. "generate like a Netflix
    # documentary"). Empty = no specific execution style requested.
    creative_angle: str = Field("", max_length=300)
    # Spoken/on-screen script language — visual_tags always stay in English
    # (stock-footage search) regardless of this.
    script_language: ScriptLanguage = ScriptLanguage.english
    # Only used when script_language == custom — the free-text language name
    # to write in (e.g. "Punjabi", "Odia").
    custom_language: str = Field("", max_length=100)
    # Target video duration bucket (e.g. "30s", "60s"). Empty = derive from
    # selected_situation.estimated_length.
    target_duration: str = ""
    # A hook line picked from the Hooks library — when set, the script's hook
    # block should open with (or faithfully adapt) this exact line. Empty = AI
    # writes its own opening.
    selected_hook_text: str = Field("", max_length=500)
    # What's being produced (video vs. static creative) and in what format
    # (a content_formats.py catalog value, or a free label when the user
    # picked "Custom") — together these pick the beat structure the model
    # writes to. Empty format = the original default Video Ad structure.
    content_type: ContentType = ContentType.video
    format: str = Field("", max_length=100)
    format_description: str = Field("", max_length=500)
    # The requested voice/register (e.g. "Conversational", "Bold") — a free
    # label from the frontend's tone catalog, same free-string pattern as
    # creative_angle. Empty = no specific tone requested.
    tone: str = Field("", max_length=100)
    # Set only when this is a from-scratch "Entire Script" regenerate of an
    # already-generated script (not a first generation) — the previous
    # attempt's hook line, so the model is nudged toward a genuinely
    # different creative mechanism/story arc instead of reproducing the same
    # angle in different words. Empty on first generation.
    avoid_repeating_hook: str = Field("", max_length=500)
    # The previous attempt's self-reported creative_mechanism (e.g.
    # "curiosity_gap") — paired with avoid_repeating_hook so the model can
    # steer toward an actually different mechanism next time, not just
    # different wording for the same one. Empty on first generation.
    avoid_repeating_mechanism: str = Field("", max_length=50)
    # Set when the user selected an AyushWellness Product Library product
    # for this project — threads its approved knowledge/claims/tone/CTA into
    # the prompt. None = the existing manual-Product flow, unchanged.
    product_context: Optional[ProductContext] = None


class ScriptLine(BaseModel):
    text: str
    on_screen_text: str = ""
    visual_tags: list[str] = Field(default_factory=list)
    scene_label: Optional[str] = None
    section: Optional[ScriptSection] = None
    visual_direction: Optional[str] = None
    camera_angle: Optional[str] = None
    emotion: Optional[str] = None
    lighting: Optional[str] = None
    transition_note: Optional[str] = None
    duration_seconds: Optional[float] = None
    b_roll: list[str] = Field(default_factory=list)
    sfx: Optional[str] = None
    ai_image_prompt: str = ""
    ai_video_prompt: str = ""

    @field_validator("section", mode="before")
    @classmethod
    def _blank_section_to_none(cls, v: object) -> object:
        """The model occasionally emits "" instead of omitting the field, or —
        for formats other than the default Video Ad structure, where it's
        told to leave this empty — invents an ad-structure-ish word anyway
        (e.g. "banter", "narration") that isn't a real ScriptSection value.
        Treat both the same as not tagging a section, rather than a
        validation error that would trigger a repair pass or fail outright."""
        if not v or (isinstance(v, str) and v not in {e.value for e in ScriptSection}):
            return None
        return v


class GeneratedScript(BaseModel):
    """Stage 6 output — consumed directly by Stage 7 (compliance) and Stage 8 (assets)."""

    hook: ScriptLine
    body: list[ScriptLine] = Field(default_factory=list)
    cta: ScriptLine
    situation: Optional[StorySituation] = None
    bgm_suggestion: str = ""
    creative_angle: str = ""
    script_language: ScriptLanguage = ScriptLanguage.english
    custom_language: str = ""
    target_duration: str = ""
    estimated_duration_seconds: float = 0.0
    content_type: ContentType = ContentType.video
    format: str = ""
    format_description: str = ""
    tone: str = ""
    # The creative mechanism the model reports having used (e.g.
    # "curiosity_gap", "mini_story") — internal bookkeeping so a later
    # regenerate can be steered away from repeating it. Never surfaced in
    # the UI. Empty on scripts generated before this field existed.
    creative_mechanism: str = ""
    # AHM Creative DNA pipeline artifacts (see script_service._run_creative_pre_stages) —
    # the specific human insight the story was built around, and which
    # creative_architecture.ARCHITECTURES key was selected to structure it.
    # Both additive/optional: empty on any script where pre-stage discovery
    # didn't run or failed (narrow regenerations, older scripts, or a
    # silent fallback) — never required, never surfaced as a hard gate.
    human_insight: str = ""
    creative_architecture: str = ""
    # Creative Breakdown / Quality Assessment (see app.services.creative_breakdown_service)
    # — deterministic renderings of the SAME creative-chain objects above
    # (territory/premise/Creative Director evaluation), never a fresh LLM
    # call. Plain dicts (via CreativeBreakdown.as_dict()/CreativeQualityAssessment.as_dict())
    # rather than a second Pydantic model, since these dataclasses are
    # already the canonical shape — this avoids maintaining two schemas for
    # the same data. None on any script where the creative pre-stage chain
    # didn't run (narrow regenerations, older scripts) or the gate never
    # produced an evaluation (deterministic issues caught first, or the
    # architecture stage itself failed) — never a hard requirement.
    creative_breakdown: Optional[dict] = None
    creative_quality_assessment: Optional[dict] = None

    @property
    def full_text(self) -> str:
        lines = [self.hook.text, *[line.text for line in self.body], self.cta.text]
        return "\n".join(lines)


class ScriptSectionRegenerateInput(BaseModel):
    """Targeted regeneration — take an already-generated script and rewrite
    only the requested part, leaving everything else untouched."""

    structured_product: StructuredProduct
    selected_situation: StorySituation
    product_category: str = Field(..., min_length=1)
    platform: str = "instagram_reel"
    max_line_chars: int = 90
    creative_angle: str = Field("", max_length=300)
    script_language: ScriptLanguage = ScriptLanguage.english
    custom_language: str = Field("", max_length=100)
    target_duration: str = ""
    # See ScriptGenerationInput.selected_hook_text — only meaningful for a
    # full/fresh regeneration; the frontend omits it for scoped regenerations
    # (e.g. "CTA only") to avoid contradicting "leave the hook unchanged".
    selected_hook_text: str = Field("", max_length=500)
    current_script: GeneratedScript
    scope: ScriptRegenerateScope = ScriptRegenerateScope.full
    # Free text appended to the scope's guidance — powers one-click actions like
    # "Add More Science" or "Remove Repetition" without needing a new enum value.
    custom_instruction: str = ""
    # Precise numeric word-count target — used by Shorten/Extend/slider controls
    # to override the bucket's normal range with an exact goal.
    target_word_count: Optional[int] = None
    content_type: ContentType = ContentType.video
    format: str = Field("", max_length=100)
    format_description: str = Field("", max_length=500)
    tone: str = Field("", max_length=100)
    # Only used when scope == specific_scene — the exact scene_label of the
    # single body block to regenerate; every other block (including hook/cta)
    # is left untouched.
    target_scene_label: str = Field("", max_length=100)
    product_context: Optional[ProductContext] = None


class AssetSourcingInput(BaseModel):
    """Stage 8 input — one entry per script line, each with its own visual tags."""

    line_id: str = Field(..., description="e.g. 'hook', 'body_0', 'cta' — ties the asset back to a script line")
    visual_tags: list[str] = Field(..., min_length=1)
    # Optional and additive — URLs already selected for OTHER lines in this
    # same script, so this line can avoid picking a duplicate. Only
    # meaningful when the caller actually knows prior selections (e.g.
    # regenerating one line's asset after the rest already loaded); the
    # initial parallel batch load has nothing to pass here, which is fine.
    exclude_urls: list[str] = Field(default_factory=list)
    # Optional, additive — existing ScriptLine metadata for THIS line, used
    # to deterministically decide whether the scene needs the actual product
    # (section == product_intro/benefits/cta), an ingredient shot (section
    # == ingredients), or a generic lifestyle/stock photo (everything else).
    # None on every existing caller — behavior is byte-for-byte unchanged
    # unless both this and product_context are supplied.
    section: Optional[str] = None
    # Set only when a Product Library product is selected for this project —
    # its primary asset gets first refusal on product/ingredient-shaped
    # scenes, ahead of Pexels/Pixabay. None = existing stock-only behavior.
    product_context: Optional[ProductContext] = None


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
    # True when candidate is None because Pexels/Pixabay rejected our API key
    # (a configuration problem), not because a genuine search found nothing —
    # lets the frontend tell the two apart instead of showing "No match
    # found" for both.
    provider_error: bool = False


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
    # Optional, additive — the SAME creative metadata ScriptLine already
    # produces (see ScriptSection/ScriptLine above), just no longer dropped
    # before reaching render. None on every existing caller: the scene
    # planner falls back to position-based heuristics (first=HOOK,
    # last=CTA) when these are absent, so old requests keep working exactly
    # as before, just with a slightly less-informed scene plan.
    section: Optional[str] = None
    scene_label: Optional[str] = None
    on_screen_text: Optional[str] = None
    visual_direction: Optional[str] = None
    camera_angle: Optional[str] = None
    emotion: Optional[str] = None
    # True when image_url/video_url is a real, approved Product Library
    # asset (not stock) — lets the scene planner apply product-hero
    # treatment and the renderer preserve the asset exactly, unmodified.
    is_product_asset: bool = False


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

    structured_product is optional and additive (Compliance V2) — when given,
    it lets the audit distinguish a claim that's actually supported by the
    supplied product data from one the script invented. Old callers that omit
    it still work; the audit just has less grounding to work with.
    """

    script_text: str = Field(..., min_length=1)
    product_category: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    structured_product: Optional[StructuredProduct] = None


class ComplianceViolation(BaseModel):
    phrase: str
    reason: str
    severity: str  # "blocker" | "warning"
    # Compliance V2 additions — both optional so older responses/consumers
    # that don't know about them still validate fine.
    claim_type: str = ""  # e.g. "GUARANTEED_OUTCOME", "AUTHORITY_CLAIM" — internal taxonomy label
    suggested_fix: str = ""


class ComplianceResult(BaseModel):
    """Stage 7 output — pass/fail gate before a script can reach rendering."""

    passed: bool
    violations: list[ComplianceViolation] = Field(default_factory=list)
    notes: str = ""


class RewriteDirective(str, Enum):
    """A single AI quick-action a user can apply to one script line's text."""

    improve = "improve"
    make_viral = "make_viral"
    make_emotional = "make_emotional"
    increase_conversion = "increase_conversion"
    rewrite = "rewrite"
    make_shorter = "make_shorter"
    make_longer = "make_longer"
    more_cinematic = "more_cinematic"
    more_conversational = "more_conversational"
    more_scientific = "more_scientific"
    more_persuasive = "more_persuasive"
    simplify = "simplify"
    professional_tone = "professional_tone"
    funny = "funny"
    fear_based = "fear_based"
    doctor_style = "doctor_style"
    storytelling_style = "storytelling_style"
    ugc_style = "ugc_style"
    podcast_style = "podcast_style"
    meta_glasses_pov = "meta_glasses_pov"
    translate = "translate"


class RewriteLineInput(BaseModel):
    text: str = Field(..., min_length=1)
    directive: RewriteDirective
    max_chars: Optional[int] = None
    # Only used when directive == translate.
    target_language: Optional[ScriptLanguage] = None


class RewriteLineResult(BaseModel):
    text: str


class GenerateAlternativesResult(BaseModel):
    alternatives: list[str] = Field(default_factory=list)


class ScriptSuggestionCategory(str, Enum):
    """The AI-suggestions panel's critique lens — mirrors how a professional
    short-form script editor actually evaluates a script."""

    hook = "hook"
    opening_line = "opening_line"
    emotional_impact = "emotional_impact"
    clarity = "clarity"
    flow = "flow"
    storytelling = "storytelling"
    product_integration = "product_integration"
    cta = "cta"
    repetition = "repetition"
    length = "length"
    natural_hinglish = "natural_hinglish"
    brand_mention = "brand_mention"
    audience_relevance = "audience_relevance"
    virality = "virality"


class ScriptSuggestionCard(BaseModel):
    """One concrete, ready-to-apply improvement — grounded in the actual
    script, not a generic tip. Applying a card is a pure text swap on
    `line_id` (no further AI call) whenever `current_text`/`suggested_text`
    are set; `suggested_scope` is only a fallback for the rare suggestion
    that genuinely needs a whole-section regenerate (e.g. severe pacing
    mismatch) rather than a single-line fix."""

    id: str
    category: ScriptSuggestionCategory
    title: str
    why: str
    line_id: Optional[str] = None
    current_text: Optional[str] = None
    suggested_text: Optional[str] = None
    suggested_scope: Optional[ScriptRegenerateScope] = None
    instruction: Optional[str] = None

    @field_validator("line_id", "current_text", "suggested_text", "suggested_scope", "instruction", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        return v or None


class SmartScriptSuggestionsResult(BaseModel):
    """Full AI Suggestions panel payload for one analysis pass."""

    status: Literal["strong", "needs_work"] = "needs_work"
    headline: str = ""
    cards: list[ScriptSuggestionCard] = Field(default_factory=list)
    optional_ideas: list[str] = Field(default_factory=list)


class ScriptSuggestionsInput(BaseModel):
    script: GeneratedScript
    structured_product: Optional[StructuredProduct] = None
    target_duration: str = ""


class ScriptCommandSelection(BaseModel):
    """An explicit user text selection within one line — powers
    "Improve selection" in the structured whole-script editor."""

    line_id: str
    selected_text: str = Field(..., min_length=1)


class ScriptCommandInput(BaseModel):
    """A free-form natural-language instruction from the AI Suggestions
    panel's "Tell AI what you want to change" box — interpreted against the
    live script and (usually) turned into a single targeted line patch."""

    structured_product: StructuredProduct
    script: GeneratedScript
    product_category: str = ""
    creative_angle: str = ""
    instruction: str = Field(..., min_length=1, max_length=500)
    selection: Optional[ScriptCommandSelection] = None


class ScriptCommandResult(BaseModel):
    """A previewable, applicable patch — never silently overwrites the
    script. The frontend shows before/after and only commits on user
    confirmation."""

    is_full_rewrite: bool = False
    title: str
    why: str
    line_id: Optional[str] = None
    current_text: Optional[str] = None
    suggested_text: Optional[str] = None
    full_script_after: Optional[GeneratedScript] = None


class VisualSceneLabel(str, Enum):
    hook = "hook"
    emotional = "emotional"
    transformation = "transformation"
    product_shot = "product_shot"
    social_proof = "social_proof"
    testimonial = "testimonial"
    ugc = "ugc"
    lifestyle = "lifestyle"


class VisualConceptStyleParams(BaseModel):
    """Fields exposed in the "Edit Prompt" modal — merged into the final
    generation prompt when non-empty."""

    style: str = ""
    lighting: str = ""
    camera: str = ""
    mood: str = ""
    background: str = ""
    characters: str = ""
    composition: str = ""
    brand_colors: str = ""
    logo_placement: str = ""
    product_position: str = ""
    negative_prompt: str = ""


class VisualConceptScores(BaseModel):
    """Gemini Vision's assessment of a rendered concept — an AI judgment call
    against stated creative criteria, not a validated ad-industry metric."""

    visual_impact: int = 0
    ad_quality: int = 0
    ctr_prediction: int = 0
    emotion_score: int = 0
    brand_match: int = 0
    photorealism: int = 0
    notes: str = ""


class VisualConcept(BaseModel):
    id: str
    scene_number: int
    scene_title: str
    scene_label: VisualSceneLabel
    creative_angle: str = ""
    aspect_ratio: str = "9:16"
    prompt: str
    style_params: VisualConceptStyleParams = Field(default_factory=VisualConceptStyleParams)
    image_path: str = ""
    scores: Optional[VisualConceptScores] = None
    favorite: bool = False
    seed: Optional[int] = None
    resolution: str = ""
    generation_time_seconds: float = 0.0
    used_model: str = ""
    # "pending" — planned, image not yet requested. "generating" — render in
    # flight. "completed" — image_path is a real rendered image. "failed" —
    # see `error`. Defaults to "pending" so forgetting to advance it on a new
    # code path fails loudly (a stuck "pending" card) rather than silently
    # claiming a finished image that doesn't exist.
    status: Literal["pending", "generating", "completed", "failed"] = "pending"
    error: Optional[str] = None

    @field_validator("scene_label", mode="before")
    @classmethod
    def _blank_scene_label_to_hook(cls, v: object) -> object:
        return v or "hook"


class VisualConceptsInput(BaseModel):
    structured_product: StructuredProduct
    script: GeneratedScript
    situation: StorySituation
    creative_angle: str = ""
    product_category: str = ""


class VisualConceptsResult(BaseModel):
    concepts: list[VisualConcept] = Field(default_factory=list)


class VisualConceptRegenerateInput(BaseModel):
    structured_product: StructuredProduct
    script: GeneratedScript
    situation: StorySituation
    creative_angle: str = ""
    concept: VisualConcept
    variation_style: Optional[str] = None
    as_new_variation: bool = False
    # True when the user edited the prompt/style fields directly (Edit Prompt
    # modal) — routes through image-conditioned editing instead of a fresh
    # from-scratch generation, same as variation_style.
    is_manual_edit: bool = False


class VisualConceptScoreInput(BaseModel):
    concept: VisualConcept


class VisualConceptDownloadInput(BaseModel):
    concept: VisualConcept
    format: str = "png"


class TestImageResult(BaseModel):
    """Diagnostic — isolates whether a failure is in the HF pipeline itself
    vs. the script-to-image flow around it."""

    image_path: str
    used_model: str = ""
    elapsed_seconds: float = 0.0


class VisualConceptDebugInfo(BaseModel):
    """Static config + a live connectivity check — fast, no image generation."""

    api_key_loaded: bool
    model: str
    api_url: str
    internet_access: bool
    image_generation_enabled: bool = True


class StaticVisualInput(BaseModel):
    """One-off image render for a static creative's ai_image_prompt — the
    static-content equivalent of a video VisualConcept, without the scene
    planning/scoring/style-param editing machinery those carry."""

    prompt: str = Field(..., min_length=1)
    aspect_ratio: str = "1:1"


class StaticVisualResult(BaseModel):
    image_path: str
    used_model: str = ""
    elapsed_seconds: float = 0.0
    seed: Optional[int] = None
