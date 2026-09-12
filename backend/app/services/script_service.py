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
from app.services import content_formats, script_length
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
        'CTA ("cta" field, section "cta") — a strong close: not "buy now" but a transformation-'
        'framed call (e.g. "Start your recovery today", "Choose better, starting now").'
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
  "worried father looking at phone", not "a wave of realization"). 1-3 tags per block.
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
  that would produce this block's key visual.
- "ai_video_prompt": one concise, ready-to-use text-to-video/motion generation prompt (under ~25
  words) describing the motion/action for this block.

Also produce one top-level "bgm_suggestion": a short direction for background music (mood/genre/
tempo) that fits the situation's emotional arc across the whole ad."""

_CORE_PRINCIPLES_BLOCK = """CORE WRITING PRINCIPLES (non-negotiable):
- Write like a human copywriter who actually gets this audience, not like an AI. Never use
  corporate/AI-ish filler ("in today's fast-paced world", "unlock the power of", "game-changer",
  "revolutionize", "elevate your", "unleash", "seamlessly", "journey to a better you"). If a line
  could appear in literally any ad for any product, rewrite it until it couldn't.
- Follow a real narrative arc for this exact story situation — do NOT default to a generic
  Problem -> Product -> Benefits -> CTA template. Let the persona, emotion, and marketing angle
  given to you dictate the actual shape of the story; some situations open mid-scene, some open on
  a feeling, some open on someone else's voice. The structure beats above are the scaffolding, not
  a fill-in-the-blanks form.
- Use ONLY the product info you were actually given below (ingredients, doses, USP, benefits). Never
  invent a certification, clinical study, statistic, doctor endorsement, or ingredient/dose that
  wasn't provided — if something is missing, write around it generically instead of making it up.
- Write specifically for the given target audience — their real vocabulary, daily context, and
  concerns — not a generic "everyone" voice.
- Stay strictly inside the given persona, emotion, and marketing angle of the chosen story situation
  throughout every beat; don't let the script drift into a different, more generic angle halfway
  through.
- Make every visual beat concrete and photographable (a real scene, action, or object), never an
  abstract mood description that a camera or an image generator couldn't actually shoot.
Before finalizing, silently check your own output against every rule above and the language rule
below — fix anything that fails before returning."""

_JSON_SAFETY_BLOCK = """JSON SAFETY (strictly enforced): return ONLY a single valid JSON object, no
prose before or after, no markdown code fences. Every string value must have its double quotes
escaped as \\" and its line breaks escaped as \\n — never emit a raw, unescaped newline or double
quote inside a string value. Do not truncate — if you are running out of room, shorten remaining
blocks rather than cutting the response off mid-JSON."""

_SCRIPT_JSON_SHAPE = """{
  "hook": {"text": string, "on_screen_text": string, "visual_tags": [string], "scene_label": string, "section": string, "visual_direction": string, "camera_angle": string, "emotion": string, "duration_seconds": number, "b_roll": [string], "sfx": string, "ai_image_prompt": string, "ai_video_prompt": string},
  "body": [ ...same shape as hook... ],
  "cta": { ...same shape as hook... },
  "bgm_suggestion": string
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
        "You are a senior short-form video ad copywriter/director for a content factory pipeline, "
        "writing scripts as sharp and professional as a real D2C ad agency's shooting scripts, "
        "sized EXACTLY to fit the target duration below — never longer. You do NOT invent the "
        "creative — you are given ONE specific, already-chosen story situation (a persona, a "
        "conflict, an emotional arc) and your job is to write the complete script, in the requested "
        "format, that brings that exact situation to life, at the correct length for its runtime. "
        "Stay faithful to the given persona, emotion, and marketing angle throughout.\n\n"
        + _video_structure(bucket, format_value, format_description)
        + "\n\n"
        + _FIELDS_BLOCK
        + "\n\nYou MUST NOT make claims outside the approved category rules given to you — you are "
        "the first of two guardrail passes, so be conservative. If ingredient/USP data is missing, "
        "write generically rather than inventing specifics.\n\n"
        + _CORE_PRINCIPLES_BLOCK
        + _tone_block(tone)
        + "\n\n"
        + _JSON_SAFETY_BLOCK
        + "\n\nReturn ONLY valid JSON, no prose, no markdown fences, matching this exact shape:\n"
        + _SCRIPT_JSON_SHAPE
    )


def _static_system_prompt(format_value: str, format_description: str, tone: str) -> str:
    return (
        "You are a senior creative copywriter/art director for a content factory pipeline, writing "
        "static ad creative (a single graphic or a short slide set), as sharp and professional as a "
        "real D2C brand's in-house creative team — not a video script, no voiceover or camera work. "
        "You do NOT invent the creative — you are given ONE specific, already-chosen story situation "
        "(a persona, a conflict, an emotional arc) and your job is to distill it into the requested "
        "static format's copy plus a detailed image-generation prompt. Stay faithful to the given "
        "persona, emotion, and marketing angle throughout.\n\n"
        + content_formats.static_structure_block(format_value, format_description)
        + "\n\n"
        + content_formats.STATIC_FIELDS_BLOCK
        + "\n\nYou MUST NOT make claims outside the approved category rules given to you — you are "
        "the first of two guardrail passes, so be conservative. If ingredient/USP data is missing, "
        "write generically rather than inventing specifics.\n\n"
        + _CORE_PRINCIPLES_BLOCK
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
        'TASK: regenerate ONLY the "hook" block — a fresh angle/wording for the opening. Leave '
        "every body block and the cta completely unchanged."
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
        + _CORE_PRINCIPLES_BLOCK
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
        f"needed) that keeps its core wording and structure: \"{selected_hook_text}\"\n"
    )


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

    format_label = payload.format.replace("_", " ").title() if payload.format else "default"
    format_desc_note = f' — "{payload.format_description}"' if payload.format == "custom" and payload.format_description else ""
    length_line = (
        ""
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
        f"Category compliance rules (do not violate these):\n{rules_block}\n\n"
        f"Similar past-winning scripts for reference (style/structure inspiration only, "
        f"do not copy claims):\n{winners_block}"
    )


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
    # system — skip the video length-correction pass entirely for it.
    if content_type == ContentType.static:
        return data

    if target_word_count:
        # A precise numeric target (length-adjustment controls) — tolerance is
        # tight, since "barely moved from the current length" must be caught,
        # not just catastrophic failures.
        word_lo, word_hi = max(10, target_word_count - 10), target_word_count + 10
        tol_lo, tol_hi = 0.9, 1.15
    else:
        word_lo, word_hi = script_length.target_word_minimum(target_duration), script_length.target_word_maximum(target_duration)
        tol_lo, tol_hi = 0.75, 1.3

    words = script_length.count_words(data)
    if words < word_lo * tol_lo or words > word_hi * tol_hi:
        direction = (
            f"far too short ({words} words; target is {word_lo}-{word_hi})"
            if words < word_lo
            else f"far too long ({words} words; target is {word_lo}-{word_hi}) — this must actually "
            "fit the spoken runtime, cut it down substantially by removing or merging blocks"
        )
        try:
            corrected_raw = _call_llm(
                system,
                user_message
                + f"\n\nIMPORTANT: your previous attempt was {direction}. Rewrite it to actually "
                "hit the target word count while preserving the same story, hook, and structure.",
                max_tokens,
            )
            corrected_data = _parse_script_json(corrected_raw)
            GeneratedScript(**corrected_data)
            data = corrected_data
        except Exception as e:
            logger.warning("Length-correction regeneration failed, keeping prior script: %s", e)

    return data


def _finish(data: dict, payload, target_duration: str) -> GeneratedScript:
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


def _generate_full_script(
    payload,
    target_duration: str,
    target_word_count: int | None = None,
    custom_instruction: str = "",
) -> GeneratedScript:
    user_message = _context_block(payload, target_duration, target_word_count)
    if custom_instruction:
        user_message += f"\n\nADDITIONAL INSTRUCTION: {custom_instruction}\n"
    if payload.content_type == ContentType.static:
        system = _static_system_prompt(payload.format, payload.format_description, payload.tone)
    else:
        system = _system_prompt(target_duration, payload.format, payload.format_description, payload.tone)
    data = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, target_duration, target_word_count, payload.content_type
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
    return _generate_full_script(payload, target_duration)


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
        return _generate_full_script(payload, target_duration)

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

    return _finish(data, payload, length_target)
