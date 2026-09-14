"""Scene Plan builder tests — deterministic Creative Director mapper.
Covers: valid ScenePlan from a script, scene ordering, scene durations,
product-reveal scenes referencing the product asset, and backward
compatibility (old RenderInput with no section/emotion metadata still
produces a sensible plan)."""

from app.models.product import RenderInput, RenderLine
from app.models.scene_plan import MotionPreset, ScenePurpose
from app.services.scene_plan_service import build_scene_plan


def _line(text, section=None, **overrides):
    defaults = dict(text=text, image_url="http://x/img.jpg", section=section)
    defaults.update(overrides)
    return RenderLine(**defaults)


# --- 15. script produces valid ScenePlan ---
def test_build_scene_plan_produces_valid_plan():
    payload = RenderInput(
        product_name="Test Product",
        seconds_per_line=3.0,
        lines=[
            _line("Hook line", section="hook"),
            _line("Problem line", section="problem"),
            _line("CTA line", section="cta"),
        ],
    )
    plan = build_scene_plan(payload)
    assert plan.product_name == "Test Product"
    assert len(plan.scenes) == 3
    assert plan.total_duration_seconds == 9.0


# --- 16. scene ordering valid ---
def test_scene_ordering_matches_input_order():
    payload = RenderInput(
        product_name="P",
        lines=[_line("A", section="hook"), _line("B", section="problem"), _line("C", section="cta")],
    )
    plan = build_scene_plan(payload)
    assert [s.order for s in plan.scenes] == [0, 1, 2]
    assert [s.script_text for s in plan.scenes] == ["A", "B", "C"]


# --- 17. scene durations valid ---
def test_scene_duration_respects_voiceover_floor():
    payload = RenderInput(
        product_name="P",
        seconds_per_line=3.0,
        lines=[
            _line("Short", section="hook", min_duration_seconds=1.0),  # below floor -> uses seconds_per_line
            _line("Long voiceover", section="cta", min_duration_seconds=7.5),  # above floor -> uses actual duration
        ],
    )
    plan = build_scene_plan(payload)
    assert plan.scenes[0].duration_seconds == 3.0
    assert plan.scenes[1].duration_seconds == 7.5
    assert plan.total_duration_seconds == 10.5


def test_purpose_classification_from_section_metadata():
    payload = RenderInput(
        product_name="P",
        lines=[
            _line("hook", section="hook"),
            _line("problem", section="problem"),
            _line("agitation", section="problem"),  # 2nd problem beat -> AGITATION
            _line("science", section="science"),
            _line("story", section="story"),
            _line("intro", section="product_intro"),
            _line("ingredients", section="ingredients"),
            _line("benefits", section="benefits"),
            _line("objection", section="objection_handling"),
            _line("cta", section="cta"),
        ],
    )
    plan = build_scene_plan(payload)
    purposes = [s.purpose for s in plan.scenes]
    assert purposes == [
        ScenePurpose.HOOK,
        ScenePurpose.PROBLEM,
        ScenePurpose.AGITATION,
        ScenePurpose.PROOF,
        ScenePurpose.TENSION,
        ScenePurpose.PRODUCT_REVEAL,
        ScenePurpose.INGREDIENT,
        ScenePurpose.BENEFIT,
        ScenePurpose.PROOF,
        ScenePurpose.CTA,
    ]


# --- 18. product-reveal scene can reference product asset ---
def test_product_asset_line_gets_product_hero_treatment():
    payload = RenderInput(
        product_name="P",
        lines=[
            _line("hook", section="hook"),
            _line("Benefit callout showing the pack", section="benefits", is_product_asset=True),
            _line("cta", section="cta"),
        ],
    )
    plan = build_scene_plan(payload)
    benefit_scene = plan.scenes[1]
    assert benefit_scene.is_product_asset is True
    assert benefit_scene.visual_style == MotionPreset.PRODUCT_HERO
    assert benefit_scene.is_product_reveal is True
    assert plan.used_product_context is True


def test_no_product_assets_means_used_product_context_false():
    payload = RenderInput(product_name="P", lines=[_line("a", section="hook"), _line("b", section="cta")])
    plan = build_scene_plan(payload)
    assert plan.used_product_context is False


# --- 19. backward-compatible render props convert to ScenePlan ---
def test_legacy_render_input_without_section_metadata_still_produces_plan():
    """The exact shape old callers already send — no section/emotion/etc,
    just text + image_url — must still produce a sensible plan."""
    payload = RenderInput(
        product_name="Legacy Product",
        lines=[
            RenderLine(text="Still starting your day the hard way?", image_url="http://x/1.jpg"),
            RenderLine(text="Meet the product that changes that.", image_url="http://x/2.jpg"),
        ],
    )
    plan = build_scene_plan(payload)
    assert len(plan.scenes) == 2
    # Last line always becomes CTA regardless of missing metadata.
    assert plan.scenes[-1].purpose == ScenePurpose.CTA
    assert all(s.image_url for s in plan.scenes)


def test_emphasis_extracted_from_bold_markdown():
    payload = RenderInput(
        product_name="P",
        lines=[_line("Try **Aayush Wellness** today for real **energy**.", section="cta")],
    )
    plan = build_scene_plan(payload)
    assert plan.scenes[0].emphasis == ["Aayush Wellness", "energy"]


# --- sound design architecture (metadata only, no audio files) ---
def test_sound_design_metadata_assigned_per_purpose():
    payload = RenderInput(
        product_name="P",
        lines=[
            _line("hook", section="hook"),
            _line("intro", section="product_intro"),
            _line("cta", section="cta"),
        ],
    )
    plan = build_scene_plan(payload)
    assert plan.scenes[0].music_mood == "tense_minimal"
    assert plan.scenes[0].sfx_cue == "whoosh_in"
    assert plan.scenes[1].music_mood == "hopeful_lift"
    assert plan.scenes[1].sfx_cue == "chime_reveal"
    assert plan.scenes[2].music_mood == "uplifting_resolve"
