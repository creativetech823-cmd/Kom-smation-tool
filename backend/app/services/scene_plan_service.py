"""Scene Plan builder — the "Creative Director" layer between a finished,
asset-resolved script and Remotion.

Deliberately NOT an LLM call: script_service.py already produces real
creative-director-quality metadata per block (section, camera_angle,
emotion, visual_direction) — the gap this module closes is that none of it
used to reach Remotion. This is a deterministic mapper, not a second
generation pass, per the explicit "avoid a second LLM call" requirement.

The single entry point, build_scene_plan(), works for BOTH old and new
callers of RenderInput: when a RenderLine carries the newer optional
section/emotion/camera_angle fields (populated by the current frontend), the
purpose classification uses them directly; when it doesn't (an older
request, or any external caller that only ever sent text/image_url), the
same function falls back to simple position-based heuristics (first=HOOK,
last=CTA) — so there's exactly one code path, not a separate "legacy
adapter" that has to be kept in sync with a "new" one.
"""

import re

from app.models.product import RenderInput
from app.models.scene_plan import (
    MUSIC_MOOD_BY_PURPOSE,
    PURPOSE_TO_PRESET,
    SFX_CUE_BY_PURPOSE,
    CameraMotion,
    MotionPreset,
    ScenePlan,
    ScenePurpose,
    TextAnimation,
    TransitionStyle,
    VideoScene,
)

_SECTION_TO_PURPOSE: dict[str, ScenePurpose] = {
    "hook": ScenePurpose.HOOK,
    "problem": ScenePurpose.PROBLEM,
    "story": ScenePurpose.TENSION,
    "science": ScenePurpose.PROOF,
    "product_intro": ScenePurpose.PRODUCT_REVEAL,
    "ingredients": ScenePurpose.INGREDIENT,
    "benefits": ScenePurpose.BENEFIT,
    "objection_handling": ScenePurpose.PROOF,
    "cta": ScenePurpose.CTA,
}

# Deterministic, index-cycled variety for scenes that don't have a more
# specific motion — real movement instead of the old "always zoom in".
_CINEMATIC_CYCLE = [
    CameraMotion.slow_zoom_in,
    CameraMotion.pan_left,
    CameraMotion.slow_zoom_out,
    CameraMotion.pan_right,
]
_ENERGETIC_CYCLE = [CameraMotion.pan_left, CameraMotion.pan_right, CameraMotion.push_in]

_EMPHASIS_RE = re.compile(r"\*\*(.+?)\*\*")


def _extract_emphasis(text: str) -> list[str]:
    """Script generation already marks 2-5 key words per line with
    **double asterisks** for bold emphasis — reuse that existing signal
    for kinetic-text word emphasis instead of re-deriving it."""
    return _EMPHASIS_RE.findall(text or "")


def _classify_purpose(index: int, total: int, section: str | None, seen_problem_before: bool) -> ScenePurpose:
    if index == total - 1:
        return ScenePurpose.CTA
    if index == 0 and not section:
        return ScenePurpose.HOOK
    normalized = (section or "").lower()
    if normalized in _SECTION_TO_PURPOSE:
        purpose = _SECTION_TO_PURPOSE[normalized]
        # A second (or later) "problem" beat reads as escalation, not a
        # fresh problem statement — classify it as agitation instead.
        if purpose is ScenePurpose.PROBLEM and seen_problem_before:
            return ScenePurpose.AGITATION
        return purpose
    # No section metadata at all (an older/external caller) — alternate
    # between the two most common generic beats rather than defaulting
    # everything to the same purpose.
    return ScenePurpose.PROBLEM if index % 2 == 1 else ScenePurpose.BENEFIT


def _camera_motion_for(purpose: ScenePurpose, preset: MotionPreset, index: int) -> CameraMotion:
    if preset is MotionPreset.HOOK_IMPACT:
        return CameraMotion.push_in
    if preset is MotionPreset.PRODUCT_HERO:
        return CameraMotion.product_reveal
    if preset is MotionPreset.CTA:
        return CameraMotion.slow_zoom_in
    if preset is MotionPreset.INGREDIENT_EXPLAINER:
        return CameraMotion.pan_left if index % 2 == 0 else CameraMotion.pan_right
    if preset is MotionPreset.ENERGETIC:
        return _ENERGETIC_CYCLE[index % len(_ENERGETIC_CYCLE)]
    return _CINEMATIC_CYCLE[index % len(_CINEMATIC_CYCLE)]


def _text_animation_for(purpose: ScenePurpose) -> TextAnimation:
    if purpose is ScenePurpose.HOOK:
        return TextAnimation.word_reveal
    if purpose in (ScenePurpose.PRODUCT_REVEAL, ScenePurpose.CTA, ScenePurpose.INGREDIENT):
        return TextAnimation.badge
    if purpose is ScenePurpose.AGITATION:
        return TextAnimation.fade_through
    return TextAnimation.subtitle


def build_scene_plan(payload: RenderInput) -> ScenePlan:
    scenes: list[VideoScene] = []
    total = len(payload.lines)
    seen_problem = False
    total_duration = 0.0

    for index, line in enumerate(payload.lines):
        section = line.section
        purpose = _classify_purpose(index, total, section, seen_problem)
        if purpose is ScenePurpose.PROBLEM:
            seen_problem = True

        preset = PURPOSE_TO_PRESET[purpose]
        # An actual Product Library asset always gets the product-hero
        # treatment, even on a scene the section-based classifier didn't
        # already flag as PRODUCT_REVEAL (e.g. a "benefits" line whose
        # visual_tags explicitly named the product — see asset_service.py).
        if line.is_product_asset and preset is not MotionPreset.PRODUCT_HERO:
            preset = MotionPreset.PRODUCT_HERO
            if purpose not in (ScenePurpose.CTA,):
                purpose = ScenePurpose.PRODUCT_REVEAL

        duration = max(payload.seconds_per_line, line.min_duration_seconds or 0.0)
        total_duration += duration

        scenes.append(
            VideoScene(
                scene_id=line.scene_label or f"scene_{index}",
                order=index,
                duration_seconds=duration,
                purpose=purpose,
                script_text=line.text,
                voiceover_text=line.text,
                on_screen_text=line.on_screen_text or "",
                visual_description=line.visual_direction or "",
                image_url=line.image_url,
                video_url=line.video_url,
                audio_url=line.audio_url,
                is_product_asset=line.is_product_asset,
                visual_style=preset,
                camera_motion=_camera_motion_for(purpose, preset, index),
                text_animation=_text_animation_for(purpose),
                transition=TransitionStyle.crossfade,
                emphasis=_extract_emphasis(line.text),
                is_cta=purpose is ScenePurpose.CTA,
                is_product_reveal=purpose is ScenePurpose.PRODUCT_REVEAL or line.is_product_asset,
                music_mood=MUSIC_MOOD_BY_PURPOSE.get(purpose, ""),
                sfx_cue=SFX_CUE_BY_PURPOSE.get(purpose),
                metadata={"camera_angle": line.camera_angle or "", "emotion": line.emotion or ""},
            )
        )

    return ScenePlan(
        product_name=payload.product_name,
        scenes=scenes,
        total_duration_seconds=total_duration,
        used_product_context=any(s.is_product_asset for s in scenes),
    )
