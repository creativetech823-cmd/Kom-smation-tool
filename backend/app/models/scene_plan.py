"""ScenePlan — the professional motion/scene architecture that sits between
a finished script (+ its sourced assets) and Remotion.

Deliberately a render-time Pydantic structure, NOT a persisted DB table —
it's fully derivable from data that already exists (GeneratedScript's
per-line camera_angle/emotion/section/visual_direction, the resolved
SelectedAsset per line, measured voiceover duration, and an optional
Product Library context), so persisting it would just be a stale copy of
data that already lives elsewhere. See scene_plan_service.py for the
deterministic builder — no LLM call is used to produce this.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScenePurpose(str, Enum):
    HOOK = "HOOK"
    PROBLEM = "PROBLEM"
    TENSION = "TENSION"
    AGITATION = "AGITATION"
    SOLUTION = "SOLUTION"
    PRODUCT_REVEAL = "PRODUCT_REVEAL"
    INGREDIENT = "INGREDIENT"
    BENEFIT = "BENEFIT"
    PROOF = "PROOF"
    TRANSFORMATION = "TRANSFORMATION"
    CTA = "CTA"


class MotionPreset(str, Enum):
    CINEMATIC = "CINEMATIC"
    UGC = "UGC"
    ENERGETIC = "ENERGETIC"
    PREMIUM = "PREMIUM"
    PRODUCT_HERO = "PRODUCT_HERO"
    INGREDIENT_EXPLAINER = "INGREDIENT_EXPLAINER"
    HOOK_IMPACT = "HOOK_IMPACT"
    CTA = "CTA"


class CameraMotion(str, Enum):
    slow_zoom_in = "slowZoomIn"
    slow_zoom_out = "slowZoomOut"
    pan_left = "panLeft"
    pan_right = "panRight"
    push_in = "pushIn"
    pull_out = "pullOut"
    product_reveal = "productReveal"
    static_hold = "staticHold"


class TextAnimation(str, Enum):
    word_reveal = "wordReveal"
    fade_through = "fadeThrough"
    slide_up = "slideUp"
    badge = "badge"
    subtitle = "subtitle"  # the existing, unchanged bottom-subtitle treatment


class TransitionStyle(str, Enum):
    crossfade = "crossfade"
    hard_cut = "hardCut"


# Sound-design architecture only — no audio files are bundled or generated.
# This is metadata so a future mixing pass (or a human editor) knows what
# mood/cue each scene calls for; Remotion does not read or play these yet.
MUSIC_MOOD_BY_PURPOSE: dict[ScenePurpose, str] = {
    ScenePurpose.HOOK: "tense_minimal",
    ScenePurpose.PROBLEM: "tense_minimal",
    ScenePurpose.TENSION: "tense_minimal",
    ScenePurpose.AGITATION: "tense_building",
    ScenePurpose.SOLUTION: "hopeful_lift",
    ScenePurpose.PRODUCT_REVEAL: "hopeful_lift",
    ScenePurpose.INGREDIENT: "warm_organic",
    ScenePurpose.BENEFIT: "warm_organic",
    ScenePurpose.PROOF: "warm_organic",
    ScenePurpose.TRANSFORMATION: "uplifting",
    ScenePurpose.CTA: "uplifting_resolve",
}

SFX_CUE_BY_PURPOSE: dict[ScenePurpose, Optional[str]] = {
    ScenePurpose.HOOK: "whoosh_in",
    ScenePurpose.PROBLEM: None,
    ScenePurpose.TENSION: None,
    ScenePurpose.AGITATION: "riser",
    ScenePurpose.SOLUTION: None,
    ScenePurpose.PRODUCT_REVEAL: "chime_reveal",
    ScenePurpose.INGREDIENT: None,
    ScenePurpose.BENEFIT: None,
    ScenePurpose.PROOF: None,
    ScenePurpose.TRANSFORMATION: "swell",
    ScenePurpose.CTA: "button_tap",
}


# Which MotionPreset each ScenePurpose gets by default — the Creative
# Director's only real "decision"; everything else is mechanical.
PURPOSE_TO_PRESET: dict[ScenePurpose, MotionPreset] = {
    ScenePurpose.HOOK: MotionPreset.HOOK_IMPACT,
    ScenePurpose.PROBLEM: MotionPreset.CINEMATIC,
    ScenePurpose.TENSION: MotionPreset.CINEMATIC,
    ScenePurpose.AGITATION: MotionPreset.ENERGETIC,
    ScenePurpose.SOLUTION: MotionPreset.CINEMATIC,
    ScenePurpose.PRODUCT_REVEAL: MotionPreset.PRODUCT_HERO,
    ScenePurpose.INGREDIENT: MotionPreset.INGREDIENT_EXPLAINER,
    ScenePurpose.BENEFIT: MotionPreset.PREMIUM,
    ScenePurpose.PROOF: MotionPreset.PREMIUM,
    ScenePurpose.TRANSFORMATION: MotionPreset.CINEMATIC,
    ScenePurpose.CTA: MotionPreset.CTA,
}


class VideoScene(BaseModel):
    scene_id: str
    order: int
    duration_seconds: float

    purpose: ScenePurpose
    script_text: str
    voiceover_text: Optional[str] = None
    on_screen_text: str = ""
    visual_description: str = ""

    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_product_asset: bool = False

    visual_style: MotionPreset
    camera_motion: CameraMotion
    text_animation: TextAnimation
    transition: TransitionStyle = TransitionStyle.crossfade

    emphasis: list[str] = Field(default_factory=list)
    is_cta: bool = False
    is_product_reveal: bool = False

    # Sound-design metadata only (see MUSIC_MOOD_BY_PURPOSE/SFX_CUE_BY_PURPOSE) —
    # not consumed by Remotion today, no audio files are bundled or generated.
    music_mood: str = ""
    sfx_cue: Optional[str] = None

    metadata: dict = Field(default_factory=dict)


class ScenePlan(BaseModel):
    product_name: str
    scenes: list[VideoScene]
    total_duration_seconds: float
    used_product_context: bool = False
