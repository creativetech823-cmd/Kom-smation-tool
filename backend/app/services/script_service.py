import json
import logging
import re

from pydantic import ValidationError

from app.config import settings
from app.models.product import (
    ContentType,
    GeneratedScript,
    ScriptGenerationInput,
    ScriptLanguage,
    ScriptRegenerateScope,
    ScriptSectionRegenerateInput,
)
from app.services import content_formats, script_length, script_quality
from app.services.compliance_rules import rules_for_category
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("script_service")

_MAX_TOKENS = 16000

_SECTION_PROSE: dict[str, str] = {
    "hook": (
        'Hook ("hook" field, section "hook") — a very strong attention-grabbing open: a question, '
        "a shocking fact, a fear, a POV moment, a snippet of conversation, curiosity, or a "
        "contradiction. It must be SPECIFIC to this exact situation/persona, never a generic "
        'template opener — avoid worn-out openers like "Are you tired of...", "Introducing...", '
        '"Did you know...", "In today\'s world..." unless you can make the specific wording genuinely '
        "surprising. A real viewer should not be able to guess what ad this hook is for."
    ),
    "problem": (
        'Problem (section "problem") — the user\'s pain, in their own words/frame. Do not mention '
        "the product yet."
    ),
    "science": (
        'Science / Psychology / Logic (section "science") — explain WHY the problem happens, '
        "briefly and credibly, in a way appropriate to the product's category (health, fitness, "
        "finance, beauty, lifestyle, tech, education, etc)."
    ),
    "story": (
        'Story / Emotional Build-up (section "story") — continue naturally into the human story. '
        "If the creative angle is storytelling, expand the story; if it's a doctor/expert angle, "
        "expand their explanation; if it's testimonial, tell the journey; if it's a conversation, "
        "write it as dialogue; if it's a POV format (e.g. Meta Glasses), keep first-person POV "
        "throughout this and every later beat."
    ),
    "product_intro": (
        'Product Introduction (section "product_intro") — introduce the product naturally, never '
        "like an ad read."
    ),
    "ingredients": (
        'Ingredients / Features (section "ingredients") — why each ingredient/feature matters, '
        "written conversationally, not like reading a label."
    ),
    "benefits": (
        'Benefits (section "benefits") — the clearest, most compelling benefit(s): immediate, '
        "emotional, or lifestyle, whichever lands hardest given the space available."
    ),
    "objection_handling": (
        'Objection Handling (section "objection_handling") — answer the single biggest doubt a '
        'real viewer would have ("is it safe?", "does it actually work?", "how is this different?") '
        "naturally, in-voice, not as a Q&A list."
    ),
    "cta": (
        'CTA ("cta" field, section "cta") — a close that feels earned by everything before it, not a '
        'reflexive "buy now"/"try it today"/"order now". Pick whichever style actually fits this '
        'story\'s tone and funnel stage: soft ("maybe this is the upgrade your routine was missing"), '
        'direct ("try the kit and make your next weekend count"), curiosity ("see what\'s inside"), or '
        'UGC-style ("if you\'re dealing with the same thing, it\'s worth checking out").'
    ),
}


def _structure_block(bucket: str) -> str:
    included = script_length.included_sections(bucket)
    numbered = "\n".join(f"{i}. {_SECTION_PROSE[section]}" for i, section in enumerate(included, start=1))
    return (
        "STRUCTURE — build the script across these beats, in order, tagging every body block with "
        "the matching \"section\" value. This duration is too short for the full nine-part "
        "structure, so ONLY these beats are used below — do not add any other section, and do not "
        "pad with extra blocks to fill space:\n"
        f"{numbered}\n\n"
        "FORMAT — cinematic blocks, not paragraphs: each beat is one or more short, punchy, "
        "individually timed script blocks (a sentence or two each), the way a real shooting script "
        "reads, never a wall of text in one block."
    )

_FIELDS_BLOCK = """For every single block (hook, each body block, and the CTA) produce ALL of these
fields:
- "text": the spoken/voiceover line, under the given character limit (for on-screen subtitle fit).
  Write in whatever language/voice is specified below — this is the one field that changes with it.
  Wrap 2-5 genuinely key words per full script (the product name at first mention, ingredient names
  with doses, standout numbers/stats) in **double asterisks** for bold emphasis — sparingly, not
  every line, only where a reader's eye should actually land.
- "on_screen_text": a short on-screen caption/text-overlay for this block — usually a compressed,
  punchier version of "text" (a few words to one short phrase), not just a copy of the full line.
- "visual_tags": concrete, literal visual search tags, ALWAYS IN ENGLISH regardless of the script's
  spoken language (these feed an English-language stock photo/video search, e.g. Pexels/Pixabay) —
  phrases that would actually return relevant results. Abstract or poetic phrasing is useless; tags
  must describe a literal, photographable scene or object (e.g. "green cardamom pods closeup",
  "worried father looking at phone", not "a wave of realization"). Never just translate the spoken
  line word-for-word — describe the actual VISUAL SCENE it implies, shaped as SCENE + SUBJECT +
  ACTION/EMOTION + CONTEXT (e.g. for "Roz ki thakaan ke baad bhi active rehna mushkil lagta hai" —
  not "tired" or "active rehna" but "Indian man tired after work at home" or "Indian office worker
  resting after long work day"). When the block's subject is a person, lifestyle moment, family,
  workplace, or home setting for an Indian audience, lead with an "Indian" (or "Indian man" / "Indian
  woman" / "Indian family" / "Indian office worker", etc.) modifier so search results reflect Indian
  people and settings rather than generic/Western stock imagery — but don't force it where it doesn't
  fit the subject (a closeup of cardamom pods or a product bottle doesn't need "Indian" in front of
  it; "ayurvedic herbs natural ingredients" already reads as intended without it). 1-3 tags per block.
- "scene_label": "Hook", "Scene 1", "Scene 2", ... or "CTA"
- "section": one of hook, problem, science, story, product_intro, ingredients, benefits,
  objection_handling, cta — whichever beat this block belongs to.
- "visual_direction": a director's note on blocking/action/framing for this block — richer prose
  than visual_tags, describing what happens on screen (e.g. "Father sits at the kitchen table,
  phone face down, staring at it for a long beat before picking it up"), but kept to one tight
  sentence (under ~25 words) — depth of detail, not length. Keep visual_tags and visual_direction
  distinct: visual_tags are literal stock-search phrases, visual_direction is cinematic direction.
- "camera_angle": a concrete shot type (e.g. "close-up", "over-the-shoulder", "wide establishing
  shot")
- "emotion": the emotional beat of this specific block
- "duration_seconds": a realistic on-screen duration for this block, as a number (typically 1.5-5).
- "b_roll": 0-2 short literal b-roll shot suggestions (English, like visual_tags) that could cut
  away to during this block.
- "sfx": one short sound-effect suggestion for this block if genuinely useful (e.g. "soft phone
  notification chime"), or an empty string if none needed.
- "ai_image_prompt": one concise, ready-to-use text-to-image generation prompt (under ~25 words)
  that would produce THIS block's key visual — derived directly from this block's own text and
  visual_direction, never a generic stock-photo scene unrelated to what's actually being said here.
  Where relevant to this exact beat, ground it in: subject, action, environment, product placement
  (only in beats where the product should actually be visible), emotion, composition, camera angle,
  lighting, and visual style. The product does not need to appear in every block — many blocks are
  the human situation with no product in frame, and that's expected, often stronger than forcing it
  into every scene.
- "ai_video_prompt": one concise, ready-to-use text-to-video/motion generation prompt (under ~25
  words) describing the motion/action for this block.

Also produce one top-level "bgm_suggestion": a short direction for background music (mood/genre/
tempo) that fits the situation's emotional arc across the whole ad."""

# The generation prompt's banned-phrase sentence is rendered FROM
# script_quality.BANNED_PHRASES (the same list the post-generation quality
# gate checks against) so the writer and the checker can't drift apart.
def _banned_phrases_prose() -> str:
    return ", ".join(f'"{p}"' for p in script_quality.BANNED_PHRASES)


def _core_principles_block() -> str:
    return f"""CORE WRITING PRINCIPLES (non-negotiable):
- Write like a human copywriter who actually gets this audience, not like an AI. Banned words/
  phrases (not exhaustive — the point is the pattern, not just this list): {_banned_phrases_prose()}.
  Generic openers like "are you tired of...", "in today's busy world...", "we all know...", "do you
  want to...", "have you ever wondered..." may be used ONLY when genuinely the sharpest option for
  this exact hook — never reach for them by default. If a line could appear in literally any ad for
  any product, rewrite it until it couldn't.
- Follow a real narrative arc for this exact story situation — do NOT default to a generic
  Problem -> Product -> Benefits -> CTA template every time. Let the persona, emotion, marketing
  angle, and chosen creative mechanism dictate the actual shape of the story; some situations open
  mid-scene, some open on a feeling, some open on someone else's voice. The structure beats above
  are the scaffolding, not a fill-in-the-blanks form.
- The product must feel like it belongs in this exact story, not like it was stuffed in because a
  product had to be mentioned somewhere. Build the situation so its entry feels inevitable — "of
  course this is what they'd reach for" — not announced. Never write a beat that exists only to
  name-drop the product.
- Turn features into benefits, not a feature dump: for anything you mention, think feature ->
  function -> consumer benefit -> human value, and write the human value the audience actually
  feels, not the ingredient label. Only make claims the given product info actually supports.
- Vary sentence rhythm on purpose — short punchy lines mixed with a longer thought that develops an
  idea, not every sentence the same length or shape. This is meant to be heard, not read as a
  paragraph. Avoid a run of same-shaped short declaratives back to back (e.g. "Energy low thi.
  Stamina low thi. Progress slow thi." reads like AI-generated bullet points, not speech) — break
  that pattern with a real question, a longer sentence that develops the thought, or a natural
  transition between beats.
- Use ONLY the product info you were actually given below (ingredients, doses, USP, benefits). Never
  invent a certification, clinical study, statistic, doctor endorsement, customer review/testimonial,
  award, or ingredient/dose that wasn't provided — if something is missing, write around it
  generically instead of making it up. This applies to the STORY, not just explicit claims: do not
  invent a specific concrete achievement (a race finished, a number on a scale, a health outcome) and
  present it as something the product caused — an aspirational story is fine, a fabricated result
  presented as fact is not. Frame the product's role as supporting/part of the routine/designed for
  this, not as the proven cause of an invented outcome.
- Write specifically for the given target audience — their real vocabulary, daily context, and
  concerns — not a generic "everyone" voice.
- Stay strictly inside the given persona, emotion, and marketing angle of the chosen story situation
  throughout every beat; don't let the script drift into a different, more generic angle halfway
  through.
- Make every visual beat concrete and photographable (a real scene, action, or object), never an
  abstract mood description that a camera or an image generator couldn't actually shoot.
- The CTA must feel earned by what came before it, matching the tone/format/funnel stage — not a
  reflexive "buy now"/"try it today"/"order now" by default. A soft, direct, curiosity-driven, or
  UGC-style close are all valid; pick whichever this exact story actually earns.
Before returning, silently self-check (never show this checking, never output it): would a
professional ad-agency creative director approve this, or does it read like generic AI marketing
copy? Is there ONE clear central idea, not several unrelated selling points mixed together? If
anything fails, rewrite it before returning — also check against the language rule below."""

# The prompt's mechanism list is rendered FROM script_quality.CREATIVE_MECHANISMS
# (the same list normalize_creative_mechanism() validates against post-hoc) so
# the writer's instructions and the checker's canonical set can't drift apart.
_MECHANISM_DESCRIPTIONS: dict[str, str] = {
    "confession": 'confession ("I used to think...")',
    "social_observation": 'social_observation ("you know that one friend who...")',
    "mini_story": "mini_story (setup -> tension -> realization -> resolution)",
    "problem_insight": "problem_insight (naming something the audience overlooked)",
    "question": "question (a genuinely intriguing one — this is a fallback, not a default; reach for it only when nothing sharper fits)",
}


def _creative_mechanisms_prose() -> str:
    return ", ".join(_MECHANISM_DESCRIPTIONS.get(m, m) for m in script_quality.CREATIVE_MECHANISMS)


def _creative_direction_block() -> str:
    return f"""CREATIVE STRATEGY — work through this silently before writing (never
show this reasoning, never output it as text; return only the final script JSON):
1. PRODUCT — what does it actually do, what makes it different, and which given benefit is
   strongest and most specific to this audience? Use only benefits/facts actually given below.
2. AUDIENCE — what does this persona want, fear, or get frustrated by? What situation puts them in
   the market for this right now?
3. HOOK — why would this exact person stop scrolling in the first 1-3 seconds? What curiosity gap,
   tension, surprising observation, or emotional trigger fits here?
4. CREATIVE MECHANISM — choose exactly ONE from this list: {_creative_mechanisms_prose()}.
   Decide the mechanism in this priority order, never picking one that doesn't actually fit just to
   be different: (1) if a specific hook line is given below, the mechanism it inherently implies
   wins — don't override a hook's own promise; (2) otherwise, whatever genuinely suits this exact
   product; (3) then the requested format; (4) then the audience; (5) then the tone; (6) only last,
   if a PREVIOUS ATTEMPT is noted below, prefer a mechanism different from it — but never force an
   unfitting one just to be different. Report your final choice, verbatim, as the top-level
   "creative_mechanism" JSON field — it MUST be exactly one of the snake_case labels above, nothing
   else (not a phrase, not a new word — pick the closest one from the list).
5. STORY ARC — pick the shape that fits the chosen mechanism, adapted freely into the STRUCTURE
   beats below (the arc is the internal logic; STRUCTURE is the JSON scaffolding it pours into):
   curiosity (hook -> unexpected observation -> tension -> reveal -> product -> benefit -> cta),
   story (hook -> situation -> problem -> emotional moment -> discovery -> product -> result -> cta),
   problem/insight (hook -> common belief -> why it's incomplete -> insight -> product -> why it
   fits -> cta), UGC (hook -> personal experience -> problem -> discovery -> product experience ->
   specific benefit -> recommendation), demonstration (hook -> show problem -> show process ->
   product -> result/benefit -> cta), or emotional (hook -> human moment -> emotional tension ->
   product enters naturally -> emotional payoff -> cta).
6. ONE IDEA — build the whole script around ONE central creative idea; never mix several unrelated
   selling points or emotional angles into the same script.
7. HOOK -> PAYOFF — if a specific hook line is given below, treat the promise/curiosity it opens as
   a contract with the viewer: the body must actually answer or resolve what the hook implied, in a
   way that couldn't be guessed from the hook alone. A viewer should never think "why did it start
   with that?"
8. CTA -> IDEA — the closing line should connect back to the ONE central creative idea from step 6,
   not just be a generic sign-off. A direct, plain call to action is correct when the story earns a
   direct close — don't force poetic phrasing where a direct CTA genuinely fits better.
Only after this reasoning, write the actual script — commit to the single strongest direction, do
not hedge between two ideas."""

_JSON_SAFETY_BLOCK = """JSON SAFETY (strictly enforced): return ONLY a single valid JSON object, no
prose before or after, no markdown code fences. Every string value must have its double quotes
escaped as \\" and its line breaks escaped as \\n — never emit a raw, unescaped newline or double
quote inside a string value. Do not truncate — if you are running out of room, shorten remaining
blocks rather than cutting the response off mid-JSON."""

_SCRIPT_JSON_SHAPE = """{
  "hook": {"text": string, "on_screen_text": string, "visual_tags": [string], "scene_label": string, "section": string, "visual_direction": string, "camera_angle": string, "emotion": string, "duration_seconds": number, "b_roll": [string], "sfx": string, "ai_image_prompt": string, "ai_video_prompt": string},
  "body": [ ...same shape as hook... ],
  "cta": { ...same shape as hook... },
  "bgm_suggestion": string,
  "creative_mechanism": string
}"""

def _tone_block(tone: str) -> str:
    if not tone:
        return ""
    return (
        f'\nTONE (mandatory): write in a "{tone}" voice — let this genuinely shape word choice, '
        f"sentence rhythm, and register throughout every block, not just the adjectives used to "
        f"describe the product.\n"
    )


def _video_structure(bucket: str, format_value: str, format_description: str) -> str:
    """The default Video Ad structure unless a different video format was
    requested — "video_ad" itself and an empty/unrecognized format both fall
    through to the original duration-quota ad structure unchanged."""
    if format_value and format_value != "video_ad":
        structure = content_formats.video_structure_block(format_value, format_description)
        if structure:
            return structure
    return _structure_block(bucket)


def _system_prompt(bucket: str, format_value: str = "", format_description: str = "", tone: str = "") -> str:
    return (
        "You are a senior short-form video ad creative team in one — creative director, advertising "
        "strategist, senior copywriter, direct-response marketer, and visual storyteller — for a "
        "content factory pipeline, writing scripts as sharp and professional as a real D2C ad "
        "agency's shooting scripts, sized EXACTLY to fit the target duration below — never longer. "
        "Your job is to make the audience stop, watch, feel, understand, want, and act — not to "
        "write generic sentences about a product. You do NOT invent the creative situation itself — "
        "you are given ONE specific, already-chosen story situation (a persona, a conflict, an "
        "emotional arc) — but you choose HOW to tell it: the mechanism, the structure, the line-by-"
        "line execution. Stay faithful to the given persona, emotion, and marketing angle throughout.\n\n"
        + _creative_direction_block()
        + "\n\n"
        + _video_structure(bucket, format_value, format_description)
        + "\n\n"
        + _FIELDS_BLOCK
        + "\n\nYou MUST NOT make claims outside the approved category rules given to you — you are "
        "the first of two guardrail passes, so be conservative. If ingredient/USP data is missing, "
        "write generically rather than inventing specifics.\n\n"
        + _core_principles_block()
        + _tone_block(tone)
        + "\n\n"
        + _JSON_SAFETY_BLOCK
        + "\n\nReturn ONLY valid JSON, no prose, no markdown fences, matching this exact shape:\n"
        + _SCRIPT_JSON_SHAPE
    )


def _static_system_prompt(format_value: str, format_description: str, tone: str) -> str:
    return (
        "You are a senior creative director and copywriter for a content factory pipeline, writing "
        "static ad creative (a single graphic or a short slide set), as sharp and professional as a "
        "real D2C brand's in-house creative team — not a video script, no voiceover or camera work. "
        "You do NOT invent the creative situation itself — you are given ONE specific, already-"
        "chosen story situation (a persona, a conflict, an emotional arc) — but you choose HOW to "
        "distill it into the requested static format's copy plus a detailed image-generation prompt. "
        "Stay faithful to the given persona, emotion, and marketing angle throughout.\n\n"
        + _creative_direction_block()
        + "\n\n"
        + content_formats.static_structure_block(format_value, format_description)
        + "\n\n"
        + content_formats.STATIC_FIELDS_BLOCK
        + "\n\nYou MUST NOT make claims outside the approved category rules given to you — you are "
        "the first of two guardrail passes, so be conservative. If ingredient/USP data is missing, "
        "write generically rather than inventing specifics.\n\n"
        + _core_principles_block()
        + _tone_block(tone)
        + "\n\n"
        + _JSON_SAFETY_BLOCK
        + "\n\nReturn ONLY valid JSON, no prose, no markdown fences, matching this exact shape:\n"
        + _SCRIPT_JSON_SHAPE
    )

_REGEN_SYSTEM_PROMPT_PREFIX = """You are a senior short-form video ad copywriter/director for a
content factory pipeline. You are given a COMPLETE existing ad script as JSON, already broken into
a hook, body blocks, and a CTA, each tagged with a "section". Your job is to regenerate ONLY the
requested part below — every other block's every field must be copied back EXACTLY unchanged (same
text, same tags, same everything) — do not paraphrase, tidy up, or otherwise touch untouched
blocks. The rewritten part(s) must stay continuous with the surrounding, unchanged blocks (same
persona, same story so far, same product facts)."""

_FULL_REWRITE_PREFIX = """You are a senior short-form video ad copywriter/director for a content
factory pipeline. You are given the CURRENT version of an ad script as JSON (a hook, body blocks,
and a CTA, each tagged with a "section") and asked to rewrite it to meet a new requirement below
(a new length target and/or a specific creative instruction). Use the current script as your
reference for the story, persona, product facts, hook idea, and creative angle — keep all of that
the same — but you may freely rewrite, shorten, expand, split, or merge blocks as needed to
actually hit the new requirement. This is a full rewrite pass building on what's already there, not
an unrelated fresh script and not a copy-unless-asked pass."""

_SCOPE_GUIDANCE: dict[ScriptRegenerateScope, str] = {
    ScriptRegenerateScope.full: (
        "TASK: rewrite the ENTIRE script to meet the length target and/or instruction below, while "
        "keeping the same story, hook idea, persona, product facts, and creative angle as the "
        "current script — build on it, don't discard it."
    ),
    ScriptRegenerateScope.hook: (
        'TASK: regenerate ONLY the "hook" block — a genuinely different creative mechanism for the '
        "opening (see the mechanism list — pattern interrupt, curiosity gap, contrarian insight, "
        "relatable moment, confession, POV, social observation, etc. — pick one that isn't just a "
        "reworded version of the current hook's mechanism), still setting up a promise the "
        "unchanged body actually pays off. Leave every body block and the cta completely unchanged."
    ),
    ScriptRegenerateScope.cta: (
        'TASK: regenerate ONLY the "cta" block. Leave the hook and every body block completely '
        "unchanged."
    ),
    ScriptRegenerateScope.science: (
        'TASK: regenerate ONLY the body block(s) whose "section" is "science" (the '
        'why-this-happens explanation). If none are tagged "science", identify the block(s) that '
        "function as the explanatory/educational beat and rewrite those instead. Leave the hook, "
        "cta, and every other body block completely unchanged."
    ),
    ScriptRegenerateScope.story: (
        'TASK: regenerate ONLY the body block(s) whose "section" is "story" (the narrative/'
        'emotional throughline). If none are tagged "story", identify the block(s) that carry the '
        "story/emotional build-up and expand or rewrite those instead. Leave the hook, cta, and "
        "every other body block completely unchanged."
    ),
    ScriptRegenerateScope.product_explanation: (
        'TASK: regenerate ONLY the body block(s) whose "section" is "product_intro" or '
        '"ingredients". If none are tagged that way, identify the block(s) that introduce the '
        "product/ingredients and rewrite those instead. Leave the hook, cta, and every other body "
        "block completely unchanged."
    ),
    ScriptRegenerateScope.emotional_tone: (
        'TASK: rewrite the "text" and "on_screen_text" of EVERY block (hook, every body block, '
        "cta) to hit a noticeably stronger emotional register — lean harder into the feeling "
        "underneath the story — while keeping the exact same scene count, structure, section tags, "
        "camera_angle, and visual_direction as the original. Do not add or remove blocks."
    ),
    ScriptRegenerateScope.length: (
        "TASK: rewrite the ENTIRE script to be noticeably longer and richer than the current "
        "version — expand every beat with real substance, hit the new target word/block count "
        "below — while keeping the same story, hook, persona, product facts, and creative angle."
    ),
}


def _regen_system_prompt(
    scope: ScriptRegenerateScope,
    custom_instruction: str = "",
    content_type: ContentType = ContentType.video,
    tone: str = "",
    target_scene_label: str = "",
) -> str:
    if scope == ScriptRegenerateScope.specific_scene:
        label = target_scene_label or "the requested scene"
        task = (
            f'TASK: regenerate ONLY the body block whose "scene_label" is exactly "{label}" — a fresh '
            f"take on that one scene/beat. Leave the hook, cta, and every other body block completely "
            f"unchanged, including their scene_label values."
        )
    else:
        task = _SCOPE_GUIDANCE[scope]
    if custom_instruction:
        task += f"\nADDITIONAL INSTRUCTION: {custom_instruction}"
    is_full_rewrite = scope in (ScriptRegenerateScope.full, ScriptRegenerateScope.length)
    prefix = _FULL_REWRITE_PREFIX if is_full_rewrite else _REGEN_SYSTEM_PROMPT_PREFIX
    fields_block = content_formats.STATIC_FIELDS_BLOCK if content_type == ContentType.static else _FIELDS_BLOCK
    return (
        prefix
        + "\n\n"
        + task
        + "\n\n"
        + fields_block
        + "\n\n"
        + _core_principles_block()
        + _tone_block(tone)
        + "\n\n"
        + _JSON_SAFETY_BLOCK
        + "\n\nReturn the COMPLETE script (all blocks, changed and unchanged) as ONE valid JSON "
        "object, matching this exact shape:\n"
        + _SCRIPT_JSON_SHAPE
    )


def _angle_block(creative_angle: str) -> str:
    if not creative_angle:
        return ""
    return (
        f"\nCREATIVE ANGLE — EXECUTION STYLE (mandatory): \"{creative_angle}\"\n"
        f"This is not a tone tweak — it must fundamentally reshape HOW this story is told: the scene "
        f"structure, camera work, pacing, and dialogue style all need to concretely express this execution "
        f"style, while the underlying story situation (persona, conflict, emotional arc) stays the same. "
        f"Use your own knowledge of this format/style to interpret it concretely:\n"
        f"- If it names a filming format (e.g. \"Meta Glasses POV\", \"CCTV Footage\", \"Documentary\", "
        f"\"UGC\"), every camera_angle and visual_direction must literally reflect that format's real "
        f"visual grammar (POV = first-person, no cuts to a face unless a mirror/reflection; CCTV = fixed "
        f"wide angle, timestamp-style framing; documentary = handheld/interview cutaways, etc.).\n"
        f"- If it names a role (e.g. \"Doctor Testimonial\", \"Customer Testimonial\", \"Interview\"), "
        f"structure the script as that role speaking directly to camera, not third-person narration.\n"
        f"- If it references a known creator, brand, or production style (e.g. \"like an Apple commercial\", "
        f"\"like a Netflix documentary\", \"like [a named YouTuber]\"), emulate that style's real pacing, "
        f"line rhythm, and visual sensibility as best you can from what you know of it.\n"
        f"- Adjust the number and length of scenes if this execution style genuinely calls for a different "
        f"pace than a standard cut (e.g. a single unbroken POV take vs. a fast-cut viral-trend montage).\n"
    )


def _hook_block(selected_hook_text: str) -> str:
    if not selected_hook_text:
        return ""
    return (
        f"\nSELECTED HOOK LINE (mandatory) — open the \"hook\" block with this exact line, or a "
        f"light, faithful adaptation of it (translated/localized into the script's language if "
        f"needed, naturally connected to this exact product/audience) that keeps its core wording "
        f"and structure: \"{selected_hook_text}\"\n"
        f"This hook creates a specific promise or curiosity gap. Do not casually replace it, and do "
        f"not just paste it and then write unrelated product copy after it — the rest of the script "
        f"must actually pay off what it opened, specifically and concretely, not with generic copy "
        f"that could follow any hook. A viewer should never think \"why did it start with that?\"\n"
    )


# Keyword -> creative-emphasis note. Purely additive creative guidance, separate
# from compliance_rules.py's claim restrictions — keyed dynamically off whatever
# category string the user picked, so no single brand/category is hardcoded.
_CATEGORY_CREATIVE_NOTES: list[tuple[tuple[str, ...], str]] = [
    (
        ("ayur", "herbal", "natural remed"),
        "This is a herbal/Ayurvedic-style category — where the given product info actually supports "
        "it, traditional inspiration, ingredients, ritual/routine, sensory experience, and heritage "
        "are natural angles. Never invent a tradition, lineage, or heritage detail that wasn't given.",
    ),
    (
        ("skin", "beauty", "hair", "personal care", "face care"),
        "This is a skincare/personal-care-style category — routine, texture, sensory experience, "
        "confidence, and specific skin/hair concerns are natural angles. Never make a medical claim "
        "about treating or curing a skin condition.",
    ),
    (
        ("health", "wellness", "fitness", "nutrition", "supplement"),
        "This is a healthcare/wellness-style category — be especially careful: never diagnose, never "
        "promise a cure, never guarantee a medical outcome, never invent clinical proof. Lean on "
        "lifestyle, routine, and confidence framing instead of medical claims.",
    ),
    (
        ("food", "beverage", "tea", "drink"),
        "This is a food/beverage-style category — sensory experience (taste, aroma, the ritual of "
        "consumption), routine, and lifestyle fit are natural angles.",
    ),
]


def _category_creative_note(category: str) -> str:
    key = (category or "").lower()
    for keywords, note in _CATEGORY_CREATIVE_NOTES:
        if any(k in key for k in keywords):
            return note
    return ""


_VOICE_STRUCTURE_GUIDE = """
Write like a native Hindi-speaking D2C copywriter, not a translator — the way real ad scripts for
brands like this actually sound. Structurally (regardless of script):
- Open the hook as a relatable rhetorical question or observation the audience has genuinely had.
- Break thoughts into short, punchy beats (roughly one idea per line) rather than long sentences —
  natural spoken pauses, not paragraphs. This creates rhythm when read aloud.
- It's fine (often good) to use a "problem reframe" beat — restating what the problem ISN'T before
  landing what it actually IS — when it genuinely fits, not as a forced formula every time.
- When introducing ingredients or specifics, use the pattern: name the ingredient/spec, its
  dose/detail if known, then the one-line benefit.
- Land the CTA/closing on a short, rhythmic brand line — often 2-3 short parallel phrases — rather
  than a generic "buy now."
"""

_NO_TRANSLATION_NOTE = (
    "Write directly and natively in this language/register from the first draft — do NOT compose the "
    "script in English and then translate it. A translated line always reads stiff and gives itself "
    "away; a native line uses the sentence rhythm, idiom, and word choices a real Indian speaker of "
    "this register would reach for unprompted.\n"
)

def _native_script_block(language_label: str, script_name: str, example: str) -> str:
    return (
        f"\nSCRIPT LANGUAGE (mandatory, strictly enforced): Write every \"text\" field ENTIRELY in "
        f"native {script_name} script — every word, not just some. Do NOT write in Roman/Latin "
        f"letters, even for common code-switched words — transliterate them into {script_name} too. "
        f"The only exception is the product/brand name itself, which may stay in Roman script if "
        f"that's how it's branded. This must read like natural conversational spoken {language_label} "
        f"a voiceover artist would say, not a stiff formal translation. Example of the register (not "
        f"the content): \"{example}\"\n"
        + _NO_TRANSLATION_NOTE
        + _VOICE_STRUCTURE_GUIDE
    )


_LANGUAGE_BLOCKS: dict[ScriptLanguage, str] = {
    ScriptLanguage.english: "",
    ScriptLanguage.hindi: (
        "\nSCRIPT LANGUAGE (mandatory, strictly enforced): Write every \"text\" field ENTIRELY in "
        "Devanagari script (हिंदी) — every word, not just some. Do NOT write in Roman/Latin letters at "
        "all, even for common code-switched words — transliterate them into Devanagari too (e.g. write "
        "\"स्ट्रेस\" not \"stress\", \"रूटीन\" not \"routine\"). The only exception is the product/brand "
        "name itself, which may stay in Roman script if that's how it's branded. This must read like "
        "natural conversational spoken Hindi a voiceover artist would say, not a stiff formal "
        "translation. Example of the register (not the content) — a line should look like this shape: "
        "\"क्या आपको भी लगता है कि यह सिर्फ एक ट्रेंड है?\" and an ingredient beat like "
        "\"**अश्वगंधा — 250 mg**, जो तनाव को नियंत्रित करने में मदद करता है।\"\n"
        + _NO_TRANSLATION_NOTE
        + _VOICE_STRUCTURE_GUIDE
    ),
    ScriptLanguage.hinglish: (
        "\nSCRIPT LANGUAGE (mandatory — this is the default voice of the whole pipeline): Write every "
        "\"text\" field in natural spoken Hinglish, the way an urban Indian actually talks day to day — "
        "Hindi sentence structure and vocabulary in ROMAN (Latin) script, code-switching to English for "
        "words that Indian audiences naturally say in English (e.g. \"stress\", \"routine\", \"habit\", "
        "\"cycle\", \"support\", \"confidence\"). This is NOT English text with a few Hindi words "
        "sprinkled in — the sentence structure itself must be Hindi. There is no fixed ratio of "
        "Hindi-to-English words — let it land wherever sounds natural for this specific line, the same "
        "way a real person code-switches without thinking about it; some lines may lean almost fully "
        "Hindi, others may lean more English, and that variation is correct, not a mistake. Example of "
        "the register (not the content): \"Kabhi socha hai ki yeh sirf ek trend hai?\" and an ingredient "
        "beat like \"**Ashwagandha — 250 mg**, jo stress ko manage karne mein support karta hai.\"\n"
        + _NO_TRANSLATION_NOTE
        + _VOICE_STRUCTURE_GUIDE
    ),
    ScriptLanguage.marathi: _native_script_block("Marathi", "Devanagari", "तुला पण असंच वाटतं का की हा फक्त एक ट्रेंड आहे?"),
    ScriptLanguage.gujarati: _native_script_block("Gujarati", "Gujarati", "શું તમને પણ લાગે છે કે આ ફક્ત એક ટ્રેન્ડ છે?"),
    ScriptLanguage.tamil: _native_script_block("Tamil", "Tamil", "இது ஒரு ட்ரெண்ட் மட்டும்தான் என்று உங்களுக்கும் தோன்றுகிறதா?"),
    ScriptLanguage.telugu: _native_script_block("Telugu", "Telugu", "ఇది కేవలం ఒక ట్రెండ్ అని మీకు కూడా అనిపిస్తుందా?"),
    ScriptLanguage.bengali: _native_script_block("Bengali", "Bengali", "তোমারও কি মনে হয় এটা শুধু একটা ট্রেন্ড?"),
    ScriptLanguage.kannada: _native_script_block("Kannada", "Kannada", "ಇದು ಕೇವಲ ಒಂದು ಟ್ರೆಂಡ್ ಅಂತ ನಿಮಗೂ ಅನಿಸುತ್ತಾ?"),
    ScriptLanguage.malayalam: _native_script_block("Malayalam", "Malayalam", "ഇത് വെറും ഒരു ട്രെൻഡ് ആണെന്ന് നിങ്ങൾക്കും തോന്നുന്നുണ്ടോ?"),
}


def _language_block(language: ScriptLanguage) -> str:
    return _LANGUAGE_BLOCKS.get(language, "")


def _custom_language_block(custom_language: str) -> str:
    if not custom_language:
        return ""
    return (
        f"\nSCRIPT LANGUAGE (mandatory): Write every \"text\" field natively in {custom_language} — "
        f"native script and phrasing for that language, not a translation from English. Only the "
        f"product/brand name may stay in Roman script if that's how it's branded.\n"
        + _NO_TRANSLATION_NOTE
    )


def _context_block(payload, target_duration: str, target_word_count: int | None = None) -> str:
    """Situation/product/rules/angle/language/length context shared by both a
    fresh generation and a targeted regeneration."""
    p = payload.structured_product
    s = payload.selected_situation
    rules = rules_for_category(payload.product_category)
    rules_block = "\n".join(f"- {r}" for r in rules)

    winners = getattr(payload, "similar_past_winners", None)
    winners_block = "\n".join(f"- {w}" for w in winners) if winners else "(none available yet)"

    current_script = getattr(payload, "current_script", None)
    current_word_count = (
        script_length.count_words(
            {
                "hook": current_script.hook.model_dump(),
                "body": [line.model_dump() for line in current_script.body],
                "cta": current_script.cta.model_dump(),
            }
        )
        if current_script
        else None
    )

    category_note = _category_creative_note(payload.product_category)
    category_note_block = f"\nCategory creative note: {category_note}\n" if category_note else ""

    format_label = payload.format.replace("_", " ").title() if payload.format else "default"
    format_desc_note = f' — "{payload.format_description}"' if payload.format == "custom" and payload.format_description else ""
    length_line = (
        script_length.static_length_directive(target_word_count, current_word_count)
        if payload.content_type == ContentType.static
        else script_length.length_directive(target_duration, target_word_count, current_word_count)
    )

    return (
        f"Chosen story situation (the creative brief — bring THIS to life):\n"
        f"Title: {s.title}\n"
        f"Description: {s.description}\n"
        f"Emotion: {s.emotion}\n"
        f"Persona: {s.persona}\n"
        f"Marketing angle: {s.marketing_angle}\n"
        f"Category: {s.category}\n"
        f"Content type: {payload.content_type.value}\n"
        f"Format: {format_label}{format_desc_note}\n"
        f"{_hook_block(getattr(payload, 'selected_hook_text', ''))}"
        f"{_angle_block(payload.creative_angle)}"
        f"{_custom_language_block(getattr(payload, 'custom_language', '')) if payload.script_language == ScriptLanguage.custom else _language_block(payload.script_language)}\n"
        f"{length_line}"
        f"Platform: {payload.platform}\n"
        f"Max characters per line: {payload.max_line_chars}\n\n"
        f"Product: {p.product_name}\n"
        f"Target audience: {p.target_audience}\n"
        f"Ingredients: {', '.join(p.ingredients) or 'unknown'}\n"
        f"USP: {p.usp or 'unknown'}\n"
        f"Tone: {p.tone or 'unspecified'}\n"
        f"Key benefits: {', '.join(p.key_benefits) or 'unknown'}\n\n"
        f"Category compliance rules (do not violate these):\n{rules_block}\n"
        f"{category_note_block}\n"
        f"Similar past-winning scripts for reference (style/structure inspiration only, "
        f"do not copy claims):\n{winners_block}"
        f"{_product_library_block(getattr(payload, 'product_context', None))}"
    )


def _product_library_block(ctx) -> str:
    """AyushWellness Product Library context — additive, empty string when no
    Product Library product is selected (every existing caller/script stays
    byte-for-byte unchanged). Approved claims are the ONLY claims the model
    may use; prohibited claims are an explicit denylist. Reference scripts
    are style/strategy inspiration only — the model is told explicitly not
    to copy them verbatim, same convention as similar_past_winners above."""
    if ctx is None:
        return ""
    lines = [
        "\n\nAYUSHWELLNESS PRODUCT LIBRARY CONTEXT (this is the real, approved product — ground the "
        "script in this, not invented details):",
        f"Product: {ctx.name} ({ctx.category})",
    ]
    if ctx.usp:
        lines.append(f"USP: {ctx.usp}")
    if ctx.target_audience:
        lines.append(f"Target audience: {ctx.target_audience}")
    if ctx.primary_problem:
        lines.append(f"Primary problem it solves: {ctx.primary_problem}")
    if ctx.positioning:
        lines.append(f"Positioning: {ctx.positioning}")
    if ctx.ingredients:
        lines.append(f"Ingredients: {', '.join(ctx.ingredients)}")
    if ctx.benefits:
        lines.append(f"Benefits: {', '.join(ctx.benefits)}")
    if ctx.preferred_tone:
        lines.append(f"Preferred tone: {ctx.preferred_tone}")
    if ctx.cta_text:
        lines.append(f"Preferred CTA: {ctx.cta_text}")
    if ctx.winning_hooks:
        lines.append("Winning hooks from past creative (style reference only, do not reuse verbatim):")
        lines.extend(f"  - {h}" for h in ctx.winning_hooks)
    if ctx.approved_claims:
        lines.append(
            "APPROVED CLAIMS — the ONLY claims about this product's efficacy you may make "
            "(reword naturally, but never claim more than these say):"
        )
        lines.extend(f"  - {c}" for c in ctx.approved_claims)
    if ctx.prohibited_claims:
        lines.append("PROHIBITED CLAIMS — never say or imply any of these, in any wording:")
        lines.extend(f"  - {c}" for c in ctx.prohibited_claims)
    if ctx.mandatory_wording:
        lines.append(f"Mandatory wording (must appear somewhere in the script): {ctx.mandatory_wording}")
    if ctx.reference_script_excerpts:
        lines.append(
            "Approved reference script excerpts — STYLE/PACING/TONE reference only. Learn the voice, "
            "hook pattern, and structure. Do NOT copy sentences, claims, or the exact creative idea "
            "verbatim — write an original script:"
        )
        for excerpt in ctx.reference_script_excerpts:
            lines.append(f'  """{excerpt}"""')
    return "\n".join(lines)


def _call_llm(system: str, user_message: str, max_tokens: int) -> str:
    return call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=system,
            contents=[user_message],
            model=settings.openrouter_text_model,
            max_output_tokens=max_tokens,
            json_mode=True,
        ),
        label="script_service",
    )


def _parse_script_json(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw_text)
        return json.loads(cleaned)


_REPAIR_SYSTEM_PROMPT = """You are a strict JSON repair tool. You will be given a piece of text
that was supposed to be a single valid JSON object but failed to parse, plus the parser error. Fix
it and return ONLY the corrected, complete, valid JSON object — no prose, no markdown fences, no
explanation. Preserve all the original content and structure as closely as possible; only fix
syntax problems (unescaped quotes/newlines, trailing commas, truncation, etc.). If the JSON was cut
off mid-object, complete it sensibly rather than leaving it truncated."""


def _repair_json(broken_text: str, error_message: str, max_tokens: int) -> dict:
    user_message = f"Parser error: {error_message}\n\nBroken JSON:\n{broken_text}"
    raw = _call_llm(_REPAIR_SYSTEM_PROMPT, user_message, max_tokens)
    return _parse_script_json(raw)


def _generate_with_recovery(
    system: str,
    user_message: str,
    max_tokens: int,
    target_duration: str,
    target_word_count: int | None = None,
    content_type: ContentType = ContentType.video,
) -> dict:
    """Attempt 1 -> silent retry (attempt 2) -> repair pass -> only then raise.
    The caller (and therefore the user) only ever sees an error if all three
    recovery stages fail."""
    data: dict | None = None
    last_raw = ""
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            last_raw = _call_llm(system, user_message, max_tokens)
            candidate = _parse_script_json(last_raw)
            GeneratedScript(**candidate)
            data = candidate
            break
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            last_error = e
            logger.warning("Script generation attempt %d produced invalid JSON: %s", attempt, e)

    if data is None:
        try:
            data = _repair_json(last_raw, str(last_error), max_tokens)
            GeneratedScript(**data)
        except Exception as e:
            logger.warning("Script JSON repair pass also failed: %s", e)
            raise ValueError(
                "Gemini returned malformed JSON while writing the script, even after an automatic "
                "retry and repair pass. Please try again in a moment."
            ) from e

    # Static creative has its own tight, format-specific word ceilings baked into
    # content_formats.py's structure prompts, not the video WPM/duration-bucket
    # system — skip the correction pass for a FRESH static generation (no
    # explicit target). But when the Script Length control set an explicit
    # target_word_count on a static creative, still correct toward it below,
    # same as video.
    if content_type == ContentType.static and not target_word_count:
        return data

    if target_word_count:
        # A precise numeric target (length-adjustment controls) — tolerance is
        # tight, since "barely moved from the current length" must be caught,
        # not just catastrophic failures.
        word_lo, word_hi = max(10, target_word_count - 10), target_word_count + 10
        correction_floor, correction_ceiling = word_lo * 0.9, word_hi * 1.15
    else:
        # A duration bucket's published range (fresh generation) — deliberately
        # a FLAT word margin around the range, not a percentage of it. A
        # percentage multiplier scales the same way the range itself does, so
        # at wide high-tier ranges (e.g. Very Long's 160-230) it silently
        # created a huge absolute floor gap (was 0.75x -> 120, well below the
        # stated 160 minimum) that never got caught by the correction pass
        # below — exactly why fresh Very Long generations could undershoot to
        # ~148 words and be accepted as "close enough". A flat margin keeps
        # the same absolute slack regardless of bucket size, matching the
        # already-working stepper (target_word_count) branch above.
        word_lo, word_hi = script_length.target_word_minimum(target_duration), script_length.target_word_maximum(target_duration)
        correction_floor, correction_ceiling = word_lo - 10, word_hi + 20

    words = script_length.count_words(data)
    if words < correction_floor or words > correction_ceiling:
        fit_note = "fit the spoken runtime" if content_type != ContentType.static else "fit the target copy length"
        direction = (
            f"far too short ({words} words; target is {word_lo}-{word_hi})"
            if words < correction_floor
            else f"far too long ({words} words; target is {word_lo}-{word_hi}) — this must actually "
            f"{fit_note}, cut it down substantially by removing or merging blocks"
        )
        try:
            corrected_raw = _call_llm(
                system,
                user_message
                + f"\n\nIMPORTANT: your previous attempt was {direction}. Rewrite it to actually hit "
                "the target word count — but by adding genuinely NEW story beats (situation, "
                "consequence, tension, insight, turning point, experience, payoff — whichever the "
                "brief above calls for), never by repeating a point in different words, adding a "
                "generic motivational line, repeating the product name, or padding with filler "
                "adjectives. Preserve the same story, hook, and structure; develop it further.",
                max_tokens,
            )
            corrected_data = _parse_script_json(corrected_raw)
            GeneratedScript(**corrected_data)
            data = corrected_data
        except Exception as e:
            logger.warning("Length-correction regeneration failed, keeping prior script: %s", e)

    return data


def _finish(data: dict, payload, target_duration: str) -> GeneratedScript:
    # Normalize against the canonical mechanism list here — the one choke
    # point every generation/regeneration path passes through — so an
    # off-list value the model happens to self-report (e.g. "transformation"
    # instead of "before_after") never reaches GeneratedScript, and
    # therefore never reaches a later avoid_repeating_mechanism either.
    data = {**data, "creative_mechanism": script_quality.normalize_creative_mechanism(data.get("creative_mechanism", ""))}
    return GeneratedScript(
        **data,
        situation=payload.selected_situation,
        creative_angle=payload.creative_angle,
        script_language=payload.script_language,
        custom_language=payload.custom_language,
        target_duration=target_duration,
        estimated_duration_seconds=script_length.estimate_seconds(script_length.count_words(data)),
        content_type=payload.content_type,
        format=payload.format,
        format_description=payload.format_description,
        tone=payload.tone,
    )


def _rewrite_for_quality(
    data: dict,
    payload,
    target_duration: str,
    target_word_count: int | None,
    reason: str,
    content_type: ContentType,
) -> dict:
    """The quality gate's one allowed rewrite pass. Reuses the same
    full-rewrite scaffolding as a normal "full" regenerate — same prefix and
    scope guidance ("keep the same story/hook/persona/product facts, build
    on it"), so a selected Hooks-library hook or the current creative
    direction is preserved by default; the `reason` argument is what
    actually steers the fix, and only overrides that default when the
    flagged issue is specifically about the hook itself."""
    context = _context_block(payload, target_duration, target_word_count)
    current_script_json = json.dumps(data, ensure_ascii=False)
    user_message = (
        f"{context}\n\n"
        f"Current script (JSON) — this is what was generated; follow the TASK above to fix it:\n"
        f"{current_script_json}"
    )
    system = _regen_system_prompt(ScriptRegenerateScope.full, reason, content_type, getattr(payload, "tone", ""))
    return _generate_with_recovery(
        system, user_message, _MAX_TOKENS, target_duration, target_word_count, content_type
    )


def _apply_quality_gate(
    data: dict,
    payload,
    target_duration: str,
    target_word_count: int | None,
    content_type: ContentType,
    run_semantic_check: bool,
) -> dict:
    """Draft -> Quality Gate -> (rewrite once if weak) -> Final script. Layer
    1 (banned-phrase/structural/product-relevance checks) is free and always
    runs; Layer 2 (one small LLM eval) only runs when Layer 1 is clean AND
    the caller opts in — reserved for the broad generation paths (fresh
    generation, full/length regenerate), skipped for narrow single-block
    regenerates (Improve Hook/CTA/etc) to avoid an extra call on every
    click. At most one rewrite pass total. Never raises — any failure here
    falls back to the original draft so the user always gets a script."""
    try:
        issues = script_quality.deterministic_issues(data, payload)
        if not issues and run_semantic_check:
            issues = script_quality.llm_quality_issues(data, payload)
        if not issues:
            return data
        logger.info("Quality gate flagged %s — attempting one rewrite pass", issues)
        reason = script_quality.rewrite_reason(issues)
        return _rewrite_for_quality(data, payload, target_duration, target_word_count, reason, content_type)
    except Exception as e:
        logger.warning("Quality gate rewrite failed, keeping original draft: %s", e)
        return data


def _apply_narrow_quality_gate(
    data: dict,
    payload: ScriptSectionRegenerateInput,
    target_duration: str,
    target_word_count: int | None,
    content_type: ContentType,
) -> dict:
    """The narrow-scope counterpart to _apply_quality_gate: cheap,
    deterministic-only checks on JUST the block(s) this scope is allowed to
    touch (Improve Hook only checks the hook, Improve CTA only the cta,
    etc.) — never the whole script. If something's wrong, ONE targeted
    rewrite using that SAME scope (never scope=full), so the fix can't
    spill into blocks the current edit wasn't meant to touch. No LLM eval
    layer here — deliberately cheap, matching the existing "no extra API
    call on every narrow click" design. Never raises."""
    try:
        changed_text = script_quality.scope_changed_text(data, payload.scope, payload.target_scene_label)
        if not changed_text.strip():
            return data
        issues = script_quality.text_issues(changed_text)
        if "unsupported_claim" in issues and script_quality.claim_grounded_in_product_data(payload):
            issues = [i for i in issues if i != "unsupported_claim"]
        if not issues:
            return data
        logger.info("Narrow quality gate flagged %s on scope=%s — targeted rewrite", issues, payload.scope)
        reason = script_quality.rewrite_reason(issues)
        context = _context_block(payload, target_duration, target_word_count)
        current_script_json = json.dumps(data, ensure_ascii=False)
        user_message = (
            f"{context}\n\n"
            f"Current script (JSON) — this is what was just generated; follow the TASK above to fix "
            f"it:\n{current_script_json}"
        )
        system = _regen_system_prompt(payload.scope, reason, content_type, payload.tone, payload.target_scene_label)
        rewritten = _generate_with_recovery(
            system, user_message, _MAX_TOKENS, target_duration, target_word_count, content_type
        )
        # The rewrite prompt says "leave every other block unchanged", but a
        # targeted-fix instruction can still make the model drift and touch
        # more than it was asked to — enforce the contract deterministically
        # rather than trusting compliance alone.
        return script_quality.enforce_narrow_scope(data, rewritten, payload.scope, payload.target_scene_label)
    except Exception as e:
        logger.warning("Narrow quality gate rewrite failed, keeping original draft: %s", e)
        return data


def _generate_full_script(
    payload,
    target_duration: str,
    target_word_count: int | None = None,
    custom_instruction: str = "",
    avoid_repeating_hook: str = "",
    avoid_repeating_mechanism: str = "",
) -> GeneratedScript:
    user_message = _context_block(payload, target_duration, target_word_count)
    if avoid_repeating_hook:
        mechanism_note = (
            f' (creative mechanism: "{avoid_repeating_mechanism}")' if avoid_repeating_mechanism else ""
        )
        user_message += (
            f"\n\nThis is a RE-generation from scratch — the previous attempt's hook was: "
            f"\"{avoid_repeating_hook}\"{mechanism_note}. Per the priority order in CREATIVE STRATEGY "
            f"step 4 above, prefer a genuinely different creative mechanism and story arc this time — "
            f"NOT just different wording for the same mechanism (e.g. \"Nobody tells you...\" -> "
            f"\"Here's what nobody tells you...\" is NOT a different mechanism, it's the same "
            f"curiosity_gap reworded). Only repeat the previous mechanism if the selected hook below "
            f"genuinely requires it or no other mechanism actually fits this product/format/audience. "
            f"Same product, same story situation, same format/tone/language/duration — a meaningfully "
            f"different creative idea.\n"
        )
    if custom_instruction:
        user_message += f"\n\nADDITIONAL INSTRUCTION: {custom_instruction}\n"
    if payload.content_type == ContentType.static:
        system = _static_system_prompt(payload.format, payload.format_description, payload.tone)
    else:
        system = _system_prompt(target_duration, payload.format, payload.format_description, payload.tone)
    data = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, target_duration, target_word_count, payload.content_type
    )
    data = _apply_quality_gate(
        data, payload, target_duration, target_word_count, payload.content_type, run_semantic_check=True
    )
    return _finish(data, payload, target_duration)


def generate_script(payload: ScriptGenerationInput) -> GeneratedScript:
    """Stage 6 — chosen story situation (+ optional creative execution angle,
    content type, format, and tone) -> a full structured script or static
    creative, sized to the target duration (video) or format (static)."""

    target_duration = (
        ""
        if payload.content_type == ContentType.static
        else script_length.resolve_target_duration(payload.selected_situation.estimated_length, payload.target_duration)
    )
    return _generate_full_script(
        payload,
        target_duration,
        avoid_repeating_hook=getattr(payload, "avoid_repeating_hook", ""),
        avoid_repeating_mechanism=getattr(payload, "avoid_repeating_mechanism", ""),
    )


def regenerate_script_section(payload: ScriptSectionRegenerateInput) -> GeneratedScript:
    """Targeted regeneration — rewrite only the requested part of an
    already-generated script, leaving every other block untouched."""

    target_duration = (
        ""
        if payload.content_type == ContentType.static
        else script_length.resolve_target_duration(payload.selected_situation.estimated_length, payload.target_duration)
    )

    # A "pure" full regenerate (no explicit length/instruction override — the
    # RegenerateMenu's "Entire Script" option) intentionally starts fresh from
    # the situation. Every other case — including full/length WITH a
    # target_word_count or custom_instruction, i.e. the Shorten/Extend/one-click
    # controls — must build on the CURRENT script, not discard it.
    is_pure_full = (
        payload.scope == ScriptRegenerateScope.full
        and not payload.target_word_count
        and not payload.custom_instruction
    )
    if is_pure_full:
        previous_hook = (payload.current_script.hook.text or "").strip() if payload.current_script else ""
        previous_mechanism = (
            (payload.current_script.creative_mechanism or "").strip() if payload.current_script else ""
        )
        return _generate_full_script(
            payload,
            target_duration,
            avoid_repeating_hook=previous_hook,
            avoid_repeating_mechanism=previous_mechanism,
        )

    length_target = (
        script_length.bump_bucket(target_duration)
        if payload.scope == ScriptRegenerateScope.length and not payload.target_word_count
        else target_duration
    )
    context = _context_block(payload, length_target, payload.target_word_count)
    current_script_json = payload.current_script.model_dump_json(exclude={"situation"})
    user_message = (
        f"{context}\n\n"
        f"Current script (JSON) — this is what exists right now; follow the TASK above to update "
        f"it:\n{current_script_json}"
    )
    system = _regen_system_prompt(
        payload.scope, payload.custom_instruction, payload.content_type, payload.tone, payload.target_scene_label
    )
    data = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, length_target, payload.target_word_count, payload.content_type
    )
    # Quality gate only runs for the broad rewrite scopes (full/length) —
    # its rewrite pass always targets the WHOLE script, which is correct
    # there but would break a narrow scope's "leave every other block
    # untouched" contract (e.g. flagging a pre-existing issue in a body
    # block that an Improve-Hook/CTA-only edit was never meant to touch).
    if payload.scope in (ScriptRegenerateScope.full, ScriptRegenerateScope.length):
        data = _apply_quality_gate(
            data, payload, length_target, payload.target_word_count, payload.content_type, run_semantic_check=True
        )
    else:
        data = _apply_narrow_quality_gate(data, payload, length_target, payload.target_word_count, payload.content_type)

    return _finish(data, payload, length_target)
