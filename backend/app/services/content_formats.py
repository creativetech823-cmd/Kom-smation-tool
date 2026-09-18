"""Content Type / Format catalog — the concrete beat structure the script
prompt writes to for each (content_type, format) combination.

Mirrors frontend/lib/contentFormats.ts by hand, same convention as
creative_angles.py <-> creativeAngles.ts elsewhere in this codebase (plain
value/label pairs, no shared codegen). "video_ad" is deliberately absent from
_VIDEO_STRUCTURE_PROMPTS — it's the original default structure, handled by
script_service._structure_block, so existing behavior is unchanged when no
format (or "video_ad") is requested.
"""

VIDEO_FORMATS: list[dict[str, str]] = [
    {"value": "podcast", "label": "Podcast"},
    {"value": "whiteboard", "label": "Whiteboard"},
    {"value": "animation", "label": "Animation"},
    {"value": "video_ad", "label": "Video Ad"},
    {"value": "ugc_talking_head", "label": "UGC / Talking Head"},
    {"value": "explainer", "label": "Explainer"},
    {"value": "cinematic", "label": "Cinematic"},
    {"value": "product_showcase", "label": "Product Showcase"},
    {"value": "educational_video", "label": "Educational Video"},
    {"value": "social_media_reel", "label": "Social Media Reel"},
    {"value": "storytelling", "label": "Storytelling"},
    {"value": "testimonial", "label": "Testimonial"},
    {"value": "product_demo", "label": "Product Demo"},
]

STATIC_FORMATS: list[dict[str, str]] = [
    {"value": "instagram_post", "label": "Instagram Post"},
    {"value": "instagram_story", "label": "Instagram Story"},
    {"value": "carousel", "label": "Carousel"},
    {"value": "banner_ad", "label": "Banner Ad"},
    {"value": "product_advertisement", "label": "Product Advertisement"},
    {"value": "infographic", "label": "Infographic"},
    {"value": "quote_graphic", "label": "Quote / Text Graphic"},
    {"value": "educational_graphic", "label": "Educational Graphic"},
    {"value": "promotional_creative", "label": "Promotional Creative"},
    {"value": "thumbnail", "label": "Thumbnail"},
    {"value": "product_feature", "label": "Product Feature"},
]

_NO_SECTION_NOTE = 'Leave "section" as an empty string on every block — this format doesn\'t use the ad-structure sections.'

_VIDEO_STRUCTURE_PROMPTS: dict[str, str] = {
    "podcast": (
        "STRUCTURE — write this as a natural two-person podcast conversation, not an ad, using the "
        'field convention HOST: / GUEST: / INTERRUPTION: / REACTION: / CAMERA-VISUAL:. Alternating '
        'blocks between a Host and a Guest (the guest can be an expert, the founder, or a satisfied '
        'customer, whichever fits the story situation). Tag every block\'s "scene_label" with exactly '
        '"Host" or "Guest" (never both in one block), and write "text" as `Host: "..."` or '
        '`Guest: "..."` accordingly — real conversational rhythm, questions, half-finished thoughts '
        'picked back up, not two monologues taking turns; the Host draws the story out with real '
        'curiosity, the Guest answers like a real person, not a spokesperson reading talking points. '
        'When one talks over or cuts off the other, note it in "action" (e.g. "Host cuts in before '
        'Guest finishes."). Use "reaction" for a genuine reaction beat (a laugh, a pause, a surprised '
        '"wait, really?") where one happens. "visual_direction" covers the camera/visual setup for '
        'that block (mostly static two-shot/single-shot — only note it when something genuinely '
        'changes); leave "camera_angle" empty unless a specific shot genuinely matters. '
        + _NO_SECTION_NOTE
    ),
    "whiteboard": (
        'STRUCTURE — a whiteboard-explainer video: number each beat "Scene 1", "Scene 2", ... in '
        '"scene_label". For every scene, "visual_direction" describes exactly what\'s being drawn/'
        'revealed on the whiteboard right now (a sketch, a diagram, an arrow, a crossed-out word — '
        'concrete enough that an illustrator could draw it), and "text" is the narration spoken over '
        "it. Keep narration and drawing tightly synced — one clear idea being drawn per scene. "
        + _NO_SECTION_NOTE
    ),
    "animation": (
        'STRUCTURE — an animated explainer/story, using the field convention SCENE: / VISUAL: / '
        'CHARACTER ACTION: / DIALOGUE-VO: / ANIMATION BEAT: / TRANSITION:. Number each beat "Scene 1", '
        '"Scene 2", ... in "scene_label" (the SCENE marker). "visual_direction" is the VISUAL (what\'s '
        'animated on screen — characters, setting, concrete enough for an animator/image generator to '
        'build); "action" is the CHARACTER ACTION (the specific animated motion/behavior — a gesture, a '
        'transformation, an object moving); "text" is the DIALOGUE/VO (a character line, or plain '
        'voiceover narration if no character is speaking); "transition_note" is the TRANSITION into the '
        'next scene (a cut, a morph, a wipe — empty if it\'s a plain cut); "on_screen_text" is any '
        'on-screen caption/label for that scene (empty if none needed). Treat any distinct beat of '
        'motion within a scene as its own ANIMATION BEAT via "action", not folded silently into '
        '"visual_direction". ' + _NO_SECTION_NOTE
    ),
    "ugc_talking_head": (
        "STRUCTURE — a single person talking directly to camera, phone-shot UGC style, using the field "
        'convention SHOT: / PERSON TO CAMERA: / ACTION: / REACTION: / CUTAWAY:. Mostly one continuous '
        'voice (don\'t invent a second speaker), broken into short "scene_label" beats ("Scene 1", '
        '"Scene 2", ...) only where the framing/setting genuinely changes. "visual_direction" is the '
        'SHOT (the framing/setting for this beat); "text" is what they say direct-to-camera (PERSON TO '
        'CAMERA — no `Character:` prefix needed, it\'s always the same person); "action" is what they '
        'physically do while talking (e.g. picks up the product, checks their phone); "reaction" is '
        'used only for a genuine own-reaction beat (a laugh, a pause, catching themselves); use it for '
        'a CUTAWAY beat (a quick insert shot — the product close-up, a text overlay, a b-roll moment) '
        'by describing it in "visual_direction" for that block and leaving "text" empty. "camera_angle" '
        'should reflect handheld, close, selfie-style framing (e.g. "handheld selfie, arm\'s length"), '
        "never a polished multi-camera studio setup. " + _NO_SECTION_NOTE
    ),
    "explainer": (
        'STRUCTURE — a clear, educational explainer: number each beat "Scene 1", "Scene 2", ... in '
        '"scene_label", building one idea at a time in a logical teaching order (context -> concept -> '
        'how it works -> why it matters), each with concrete "visual_direction" that could illustrate '
        "the idea just explained. " + _NO_SECTION_NOTE
    ),
    "cinematic": (
        'STRUCTURE — a cinematic, film-like piece: the beat order for every scene is VISUAL -> ACTION '
        '-> REACTION -> DIALOGUE -> (pause) -> CUT -> next beat, never VO explanation -> VO explanation '
        '-> product explanation -> marketing statement -> CTA. Number each beat "Scene 1", "Scene 2", '
        '... in "scene_label" (naming the location/situation, e.g. "Scene 1 — Office Break Room"), '
        'each with a strong, specific "camera_angle" and richly visual "visual_direction" (lighting, '
        'blocking, framing) — this format lives or dies on the visuals, so make every scene\'s '
        'direction genuinely shootable and distinct, not interchangeable. "action" is the physical '
        'behavior driving the beat; "reaction" is another character\'s response where one exists; '
        '"text" (DIALOGUE) should be sparse and used only where a real person would actually speak — '
        'sparse VO is allowed only when it genuinely improves the film, never as a default narration '
        'track explaining what\'s already visible. Let the visuals carry the weight. ' + _NO_SECTION_NOTE
    ),
    "product_showcase": (
        'STRUCTURE — a product-focused showcase, using the field convention SHOT: / PRODUCT VISUAL: / '
        'ACTION: / VOICEOVER: / PRODUCT DETAIL: / TRANSITION:. Number each beat "Scene 1", "Scene 2", '
        '... in "scene_label" (the SHOT), each spotlighting one concrete feature/angle/use-case of the '
        'product (not the customer\'s life story) — a real product-demo video\'s actual shot list. '
        '"visual_direction" is the PRODUCT VISUAL (exactly what\'s shown of the product in that shot); '
        '"action" is a hand/product ACTION if one is happening (e.g. "hand opens the pack, tips it '
        'into the palm"); "text" is the VOICEOVER; "on_screen_text" carries the PRODUCT DETAIL (a spec/'
        'ingredient/feature callout as on-screen text, empty if this shot has none); "transition_note" '
        "is the cut/move into the next shot. " + _NO_SECTION_NOTE
    ),
    "educational_video": (
        "STRUCTURE — this must genuinely teach something useful and stand on its own even if the "
        'viewer never buys anything, not become a generic advertisement wearing an educational hat, '
        'using the field convention HOOK: / VISUAL: / SPEAKER: / EXPLANATION: / DEMONSTRATION: / '
        'PAYOFF: / CTA:. The opening "hook" block is the HOOK. For each body beat, tag "scene_label" '
        'with whichever of "Visual", "Speaker", "Explanation", or "Demonstration" best names what that '
        'beat actually is, in a logical teaching order (context -> concept -> how it works -> why it '
        'matters); "visual_direction" is always the VISUAL for that beat; "text" carries either the '
        'SPEAKER\'s line or the EXPLANATION content depending on which the beat is; "action" carries a '
        'concrete DEMONSTRATION step when one is happening (a hand showing how something works), '
        'grounded in real, specific, correct information, not filler. The final body beat (or the '
        '"cta" block, whichever fits) is the PAYOFF — what the viewer should walk away understanding. '
        'Weave the product in naturally only where it genuinely fits, never forced into every beat. '
        + _NO_SECTION_NOTE
    ),
    "social_media_reel": (
        'STRUCTURE — a fast, native-feeling short-form reel: number each beat "Scene 1", "Scene 2", ... '
        'in "scene_label", very fast cuts, high energy, hooks the scroll within the first line. Favor '
        'punchy on-screen text ("on_screen_text") since viewers often watch muted. ' + _NO_SECTION_NOTE
    ),
    "storytelling": (
        'STRUCTURE — a narrative-driven story: number each beat "Scene 1", "Scene 2", ... in '
        '"scene_label", following a real story arc (setup -> tension/conflict -> turn -> resolution) '
        "with the product woven into the resolution, not bolted onto the end. Lean fully into "
        "storytelling technique (specific sensory detail, a real character, a real stake) rather than "
        "summarizing the story in the abstract. " + _NO_SECTION_NOTE
    ),
    "testimonial": (
        'STRUCTURE — a real-customer testimonial: mostly one continuous voice (don\'t invent a second '
        'speaker) speaking in first person about their own genuine experience with the product, broken '
        'into short "scene_label" beats ("Scene 1", "Scene 2", ...) only where the framing/setting '
        "genuinely changes. Write it the way a real customer actually talks — specific, personal, a "
        "little imperfect — not polished ad copy in disguise; never invent specific clinical/medical "
        "results the product profile doesn't support. \"camera_angle\" should reflect an unpolished, "
        'handheld or simple sit-down setup, never a studio production. ' + _NO_SECTION_NOTE
    ),
    "product_demo": (
        'STRUCTURE — a feature-by-feature product demo (distinct from Product Showcase\'s broader '
        'lifestyle/angle spotlighting: this is a literal, step-by-step walkthrough of how the product '
        'is used): number each beat "Scene 1", "Scene 2", ... in "scene_label", each one showing a '
        'single concrete step or feature in the order a real user would actually encounter it (unbox/'
        'setup -> core use -> secondary features -> result). "visual_direction" should describe exactly '
        "what hands/product are doing on screen in that step, concrete enough to shoot or generate an "
        "image from. " + _NO_SECTION_NOTE
    ),
}

_CUSTOM_VIDEO_STRUCTURE = (
    "STRUCTURE — the user has described a custom format below; interpret it using your own knowledge "
    'of how that kind of video is actually made (its real pacing, shot pattern, and voice) and number '
    'each beat "Scene 1", "Scene 2", ... in "scene_label" accordingly. ' + _NO_SECTION_NOTE + "\n"
    'CUSTOM FORMAT REQUESTED: "{description}"'
)

STATIC_FIELDS_BLOCK = """For every block (hook, each body block, and the CTA) produce these fields —
this is a STATIC graphic, not a video, so there is no spoken voiceover, camera work, or duration:
- "text": the actual copy for this block (see STRUCTURE below for what each block should contain).
  Wrap 2-4 genuinely key words per full creative (the product name at first mention, a standout
  number/stat) in **double asterisks** for bold emphasis — sparingly.
- "on_screen_text": usually identical to "text" for static content (it IS the on-screen text) unless
  a shorter, punchier compressed version reads better on a graphic — in that case use the compressed
  version here.
- "scene_label": the field label for this block, exactly as given in STRUCTURE below (e.g. "Headline",
  "Primary Copy", "Supporting Copy", "Design Notes", or a slide label like "Slide 2 — Problem").
- "visual_direction": design direction for this specific block if it has one (e.g. layout notes, where
  this text sits relative to the subject) — one tight sentence, or empty if not applicable to this
  block.
- "ai_image_prompt": on the block that carries the creative's main visual (usually the hook block,
  unless STRUCTURE below says otherwise) — one detailed, ready-to-use text-to-image generation prompt
  (30-60 words) describing the full visual: subject, background, composition, lighting, mood, style.
  This is the single most important field for static content — it must be specific and shootable, not
  vague. Empty string on blocks that don't carry a distinct visual.
- "section": leave as an empty string on every block.
- Leave "visual_tags", "camera_angle", "duration_seconds", "b_roll", "sfx", "ai_video_prompt",
  "action", and "reaction" at their defaults (empty/unused) — none of these apply to static content.

Also produce a top-level "bgm_suggestion": always an empty string for static content."""

_STATIC_STRUCTURE_PROMPTS: dict[str, str] = {
    "instagram_post": (
        'STRUCTURE: hook = "Headline" (short, scroll-stopping, carries the main ai_image_prompt); body '
        '= ["Primary Copy" (the core message/benefit), "Supporting Copy" (one supporting detail or '
        'proof point, optional — omit by leaving text empty if the post is stronger without it)]; cta '
        '= the call to action. Keep every field concise — this is copy that sits ON an image, not an '
        "article; a real Instagram post's text is a handful of short lines, not paragraphs."
    ),
    "instagram_story": (
        'STRUCTURE: hook = "Headline" (very short — a story is glanced at for 2-3 seconds, carries the '
        'main ai_image_prompt); body = ["Supporting Copy" (one short line, optional)]; cta = a single, '
        "punchy tap-through call to action. Full-bleed vertical (9:16) visual thinking in the image "
        "prompt. Extremely minimal text — shorter than an Instagram Post."
    ),
    "carousel": (
        'STRUCTURE: this is a multi-slide carousel — hook = "Slide 1 — Hook"; body = ["Slide 2 — '
        'Problem", "Slide 3 — Insight", "Slide 4 — Solution", "Slide 5 — Benefits"] (each its own body '
        'block, each with its own ai_image_prompt since every slide is a separate image); cta = "Slide '
        '6 — CTA". Each slide\'s "text" is short (one idea per slide, a sentence or a short phrase) — a '
        "real carousel is skimmed slide by slide, not read like a page. Keep the visual style/subject "
        "consistent across every slide's ai_image_prompt so the carousel feels like one cohesive set."
    ),
    "banner_ad": (
        'STRUCTURE: hook = "Headline" (very short, high-impact, carries the main ai_image_prompt); body '
        '= ["Supporting Copy" (one short line, optional — many effective banners have none, leave text '
        'empty if so)]; cta = a short, direct button-style call to action (2-4 words, e.g. "Shop Now"). '
        "Banners are seen for a split second — every word must earn its place; when in doubt, cut."
    ),
    "product_advertisement": (
        'STRUCTURE: hook = "Headline" (the core promise/hook, carries the main ai_image_prompt centered '
        'on the product); body = ["Primary Copy" (the key benefit/USP), "Supporting Copy" (a supporting '
        'detail or proof point, optional)]; cta = the call to action. The ai_image_prompt should put the '
        "product itself front and center, styled like real commercial product photography."
    ),
    "infographic": (
        'STRUCTURE: hook = "Headline" (the topic/claim this infographic proves, carries the main '
        'ai_image_prompt — an overall layout/background concept, not a single scene); body = 2-4 blocks '
        'each labeled "Data Point 1", "Data Point 2", etc. — each a genuinely distinct fact/step/stat '
        'drawn from the real product info given below (never invent a statistic that wasn\'t given); '
        'cta = the closing call to action. Each data point\'s "text" is short enough to sit as a label '
        "next to an icon/chart, not a paragraph."
    ),
    "quote_graphic": (
        'STRUCTURE: hook = "Quote" (the single strong, quotable line — this IS the whole creative, make '
        'it genuinely worth screenshotting; carries the main ai_image_prompt, usually a clean, minimal '
        'background that won\'t compete with the text); body = [] (leave empty — a quote graphic has no '
        'body copy); cta = a minimal attribution/brand line, not a hard sales pitch.'
    ),
    "educational_graphic": (
        'STRUCTURE: hook = "Headline" (the thing being taught, carries the main ai_image_prompt); body '
        '= 2-4 blocks labeled "Point 1", "Point 2", etc. — real, specific, correct educational content '
        'drawn from the given product info, not filler; cta = a soft closing line (this format teaches '
        "first, sells second — the cta should feel like a natural next step, not a hard pitch)."
    ),
    "promotional_creative": (
        'STRUCTURE: hook = "Headline" (the offer/promotion itself, carries the main ai_image_prompt); '
        'body = ["Primary Copy" (what the offer actually is / why it matters), "Supporting Copy" (terms/'
        'urgency detail, optional)]; cta = a direct, urgency-driven call to action.'
    ),
    "thumbnail": (
        'STRUCTURE: hook = "Headline" (extremely short — 3-6 words max, the kind of bold text that '
        'wins the click in a crowded feed, carries the main ai_image_prompt with a high-contrast, '
        'expressive composition); body = [] (leave empty); cta = "" (thumbnails don\'t carry a CTA).'
    ),
    "product_feature": (
        'STRUCTURE: hook = "Headline" (names the one specific feature being spotlighted, carries the '
        'main ai_image_prompt showing that feature in use/detail); body = ["Primary Copy" (how this '
        'feature works and why it matters)]; cta = the call to action. Stay tightly focused on ONE '
        "feature — this is not a general product ad."
    ),
}

_CUSTOM_STATIC_STRUCTURE = (
    "STRUCTURE — the user has described a custom static format below; interpret it using your own "
    'knowledge of how that kind of creative is actually laid out and choose sensible "scene_label" '
    'values for hook/body/cta accordingly (e.g. "Headline", "Body Copy", "Design Notes"). '
    'CUSTOM FORMAT REQUESTED: "{description}"'
)


def video_structure_block(format_value: str, format_description: str) -> str:
    """The STRUCTURE prompt fragment for a video format other than the
    default "video_ad" (which stays on script_service._structure_block).
    Empty string if format_value doesn't match a known/custom format —
    callers should fall back to the default ad structure in that case."""
    if format_value == "custom":
        return _CUSTOM_VIDEO_STRUCTURE.format(description=format_description or "no description given")
    return _VIDEO_STRUCTURE_PROMPTS.get(format_value, "")


_STATIC_ASPECT_RATIOS: dict[str, str] = {
    "instagram_post": "1:1",
    "instagram_story": "9:16",
    "carousel": "1:1",
    "banner_ad": "16:9",
    "product_advertisement": "4:5",
    "infographic": "4:5",
    "quote_graphic": "1:1",
    "educational_graphic": "4:5",
    "promotional_creative": "4:5",
    "thumbnail": "16:9",
    "product_feature": "4:5",
}


def static_aspect_ratio(format_value: str) -> str:
    """The sensible canvas shape for a given static format — falls back to a
    square 1:1 for "custom" or anything unrecognized."""
    return _STATIC_ASPECT_RATIOS.get(format_value, "1:1")


def static_structure_block(format_value: str, format_description: str) -> str:
    """The STRUCTURE prompt fragment for a static format. Falls back to
    "instagram_post" (a sensible general default) if format_value is empty
    or unrecognized."""
    if format_value == "custom":
        return _CUSTOM_STATIC_STRUCTURE.format(description=format_description or "no description given")
    return _STATIC_STRUCTURE_PROMPTS.get(format_value, _STATIC_STRUCTURE_PROMPTS["instagram_post"])
