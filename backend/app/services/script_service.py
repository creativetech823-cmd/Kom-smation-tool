import json
import logging
import re
import time
from dataclasses import dataclass

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
from app.services import (
    architecture_validation_service,
    beat_outline_service,
    claim_safety_service,
    creative_architecture,
    creative_breakdown_service,
    creative_insight_service,
    creative_memory_service,
    creative_premise_service,
    creative_reference_dna,
    creative_territory_service,
    hook_generation_service,
    product_context_service,
    product_context_validator,
)
from app.services import openrouter_utils
from app.services.compliance_rules import rules_for_category
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

logger = logging.getLogger("script_service")

_MAX_TOKENS = 16000

_SECTION_PROSE: dict[str, str] = {
    "hook": (
        'HOOK ("hook" field, section "hook") — open on a SCENE, not a statement: a specific moment '
        "already in motion (a line of dialogue, a physical action, a reaction, a POV beat) that a "
        "camera could start rolling on. It must be SPECIFIC to this exact situation/persona, never a "
        'generic template opener — avoid worn-out openers like "Are you tired of...", "Introducing...", '
        '"Did you know...", "In today\'s world..." and never a line that EXPLAINS the ad\'s theme or '
        "insight (that's a tagline, not a hook). A real viewer should not be able to guess what ad "
        "this hook is for, and should see/hear something happening, not be told what the ad is about."
    ),
    "problem": (
        'PROBLEM (section "problem") — SHOW the tension through a concrete behavior, moment, or '
        "exchange the character is actually in — not a sentence explaining that they have a problem. "
        "Do not mention the product yet."
    ),
    "science": (
        'SCIENCE / PSYCHOLOGY / LOGIC (section "science") — where a brief explanation genuinely earns '
        "its place, keep it to one plain, credible line grounded in the product's category (health, "
        "fitness, finance, beauty, lifestyle, tech, education, etc) — never a string of abstract "
        "reasoning; if the point can instead be shown through a character's behavior or reaction "
        "rather than stated, show it."
    ),
    "story": (
        'STORY / ESCALATION (section "story") — continue the SCENE from the problem beat: what the '
        "character DOES, what changes, what someone else notices or says — a real event, not a "
        "restated feeling. If the creative angle is storytelling, escalate the situation; if it's a "
        "doctor/expert angle, show the actual consultation moment, not a summary of it; if it's "
        "testimonial, show the specific remembered moment, not a general account; if it's a "
        "conversation, write real back-and-forth dialogue between named characters; if it's a POV "
        "format (e.g. Meta Glasses), keep first-person POV throughout this and every later beat."
    ),
    "product_intro": (
        'PRODUCT INTEGRATION (section "product_intro") — the product enters through a physical action '
        "(a character reaches for it, uses it, someone else notices it) inside the scene already "
        "happening — never a cutaway to introduce the product as new information. If the story's "
        "creative mechanism (an object, a ritual, a device) is the natural way the product would "
        "enter, use it here."
    ),
    "ingredients": (
        'INGREDIENTS / FEATURES (section "ingredients") — only the ONE (at most two) ingredient/'
        "feature this specific creative idea actually needs, folded into the scene's action or "
        "dialogue (a character mentions it, notices it on the pack, a beat shows it), never a list "
        "read aloud. Do not enumerate every given ingredient."
    ),
    "benefits": (
        'BENEFITS (section "benefits") — show the benefit through what changes in the character\'s '
        "behavior, expression, or situation, not a stated claim about what the product does. Pick "
        "whichever benefit lands hardest given the space available."
    ),
    "objection_handling": (
        'OBJECTION HANDLING (section "objection_handling") — answer the single biggest doubt a real '
        'viewer would have ("is it safe?", "does it actually work?", "how is this different?") through '
        "a natural line of dialogue or a small demonstrated moment, in-voice — never as a stated Q&A."
    ),
    "cta": (
        'CTA ("cta" field, section "cta") — a close that feels earned by everything before it and, '
        "where the story has a memorable device or dynamic (an object, a ritual, a relationship), "
        "connects back to it rather than closing generically — not a reflexive \"buy now\"/\"try it "
        'today\"/"order now". Pick whichever style actually fits this story\'s tone and funnel stage: '
        'soft ("maybe this is the upgrade your routine was missing"), direct ("try the kit and make '
        'your next weekend count"), curiosity ("see what\'s inside"), or UGC-style ("if you\'re '
        'dealing with the same thing, it\'s worth checking out").'
    ),
}


def _structure_block(bucket: str, has_outline: bool = False) -> str:
    included = script_length.included_sections(bucket)
    numbered = "\n".join(f"{i}. {_SECTION_PROSE[section]}" for i, section in enumerate(included, start=1))
    if has_outline:
        return (
            "SECTION TAGGING — the APPROVED BEAT OUTLINE below (not this list) determines the actual "
            "sequence, number, and content of beats. This list only exists so every block can still "
            "carry a \"section\" tag for the editing UI — after you've written each of the outline's "
            "beats, tag it with whichever of these values fits best; do NOT force a "
            "problem→science→story→product_intro→ingredients→benefits→objection_handling ordering "
            "if the outline's actual causal sequence differs, do NOT insert a beat just to use an "
            "unused tag, and it's fine for a tag to be skipped entirely or for one outline beat to "
            "span more than one block of the same tag:\n"
            f"{numbered}\n\n"
            "FORMAT — cinematic blocks, not paragraphs: each outline beat becomes one or more short, "
            "punchy, individually timed script blocks (a sentence or two each), the way a real "
            "shooting script reads, never a wall of text in one block."
        )
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
- "text": the DIALOGUE — the actual spoken line, under the given character limit (for on-screen
  subtitle fit). When a character is speaking, write it as `Character: "line"` (name or role, e.g.
  `Boss: "Rule sabke liye hai."`) so it reads as real dialogue, not narration; when this beat is pure
  voiceover with no character speaking, write the line plain with no name prefix. A beat with no
  dialogue at all (pure visual/action) leaves this empty rather than inventing a line to fill it.
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
- "scene_label": "HOOK" for the opening block, "SCENE 1 — [LOCATION / SITUATION]", "SCENE 2 —
  [LOCATION / SITUATION]", ... for each body beat that's a distinct scene (name the actual location/
  situation, e.g. "SCENE 1 — OFFICE BREAK ROOM", never a bare "Scene 1"), "PRODUCT INTEGRATION" for
  the beat where the product physically enters the story, "PAYOFF" for the final story beat, or "CTA"
  for the closing block. Every block gets exactly one of these — never leave it as a generic "Scene N"
  with no location/situation named.
- "section": one of hook, problem, science, story, product_intro, ingredients, benefits,
  objection_handling, cta — whichever beat this block belongs to (internal bookkeeping only; this
  never appears on screen and is separate from scene_label above).
- "visual_direction": the VISUAL — what the camera literally sees in this beat (setting, framing,
  who/what is in frame), richer prose than visual_tags (e.g. "Father sits at the kitchen table, phone
  face down"), one tight sentence (under ~25 words). Keep visual_tags and visual_direction distinct:
  visual_tags are literal stock-search phrases, visual_direction is cinematic direction.
- "action": the ACTION — what a character PHYSICALLY DOES in this beat, a concrete behavior a camera
  could film (e.g. "His hand moves toward his usual pocket. He stops halfway."), never an abstract
  internal state ("he realizes he should change"). Empty string only if this exact beat is pure
  dialogue/reaction with genuinely no distinct physical action worth noting.
- "reaction": the REACTION — what another character does, notices, or how they respond, if this beat
  has one (e.g. "The worker notices and raises an eyebrow."). Empty string when there's no second
  character or nothing to react to in this beat — do not invent a reaction that isn't needed.
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
- If a PRODUCT CREATIVE CONTRACT is given below, it is immutable factual grounding, not a creative
  starting point. Your job is to make the idea more cinematic, memorable, emotionally sharp, humorous,
  surprising, or visually interesting — never to redefine what the product fundamentally is, who it's
  for, or how it's actually used/consumed. Do not reinterpret the product based on an ambiguous word in
  its name (creative freedom applies to HOW the story is told, never WHAT the product is).
- If a WINNING REFERENCE / STRUCTURAL REFERENCE block is given below (hook device, human insight,
  proof device, payoff, etc. from real prior ad scripts), treat it as the LEVEL of creative thinking
  and the underlying PATTERN to match — never text to copy. Do not reuse its wording, its specific
  characters, its specific setting, or its specific lines; build an ORIGINAL situation for THIS exact
  story that earns the same kind of hook device, the same caliber of human insight, and the same kind
  of earned payoff. If the actual advertising IDEA here would feel weaker than that reference's, the
  concept needs more work before it's ready to write, not just prettier sentences.
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
- SHOW, DON'T EXPLAIN (hard rule): if something can be communicated through action, expression,
  reaction, a prop, the environment, movement, dialogue, or silence, show it that way instead of
  stating it as a line of narration. A line like "Aadat sirf packet nahi; woh reach, break aur
  familiar taste ka poora ritual hai" is an EXPLANATION, not a story — the same idea shown through
  behavior (the break bell rings, his hand moves toward the usual pocket, he stops, looks at it,
  puts it back, reaches for the other pocket instead) is what this script must do. The viewer should
  understand the insight from what happens, never from being told it in a sentence.
- CREATIVE MECHANISM MUST DRIVE THE STORY, not just be mentioned in the title: if the chosen
  mechanism were removed, the story should materially change. A two-pocket idea must become the
  actual physical device the character's hand keeps reaching toward/away from — not a line
  describing that there are two pockets.
- NO CONCEPT-EXPLANATION DIALOGUE: a character is a person, not a creative strategist reciting the
  ad's own insight. Avoid lines like "Haath purana soche, choice nayi ho" or "ye sirf ek habit nahi,
  ek ritual hai" — dialogue exists for a character to react, tease, question, interrupt, hesitate,
  notice something, make a mistake, or reveal who they are, never to explain the ad's message
  directly. Before keeping any major dialogue line, ask: would a real person actually say this exact
  sentence in this exact moment? If it sounds like a slogan, a philosophical statement, or a
  motivational quote, rewrite it as something a specific person would actually blurt out.
- PRODUCT INTEGRATION stays physical and natural: a character reaches for it, uses it, someone else
  notices it — never a paragraph of product information inserted because the data exists. Do not
  convert given ingredients into a recited list ("Ingredient 1... Ingredient 2...") inside the story.
- IF the concept has a memorable device, relationship, or dynamic (named in the story situation's
  title — a recurring object, a two-choice contrast, a specific relationship dynamic), the PAYOFF
  must connect back to that specific device/dynamic — never a generic closing beat that could belong
  to any unrelated ad for this brand.
Before returning, silently self-check (never show this checking, never output it) against this exact
list — rewrite anything that fails before returning:
1. Does the creative mechanism actually drive the scenes, not just appear in the title?
2. Could a director shoot every important beat exactly as written, without inventing what happens?
3. Does the dialogue sound like real people talking, not a creative strategist explaining the idea?
4. Is the product integrated through physical action, not a paragraph of product information?
5. Is there a genuine turn/payoff, and does it connect back to the story's memorable device?
6. Is the selected FORMAT's actual writing convention visibly reflected, not just mentioned?
7. Does the script rely on behavior and action rather than explanation and narration?
8. Is the title/creative device memorable and actually delivered, not just named?
9. Could this exact script work unchanged for 20 unrelated brands? If yes, make it more specific.
10. Does it avoid inventing any product/health claim not explicitly given below?
Also silently check the actual dialogue for a warning pattern: lines built from stems like "aadat...",
"ye sirf...", "iska matlab...", "yahi...", "ab samajh...", "choice badal...", "habit ko support...",
"familiar...", "refreshing...", "ritual...", "direction..." are not automatically forbidden, but if
the script is DOMINATED by lines like these, it has drifted into explanation — rewrite the story as
action + reaction + dialogue + visual instead. Would a professional ad-agency creative director
approve this, or does it read like generic AI marketing copy? Is there ONE clear central idea, not
several unrelated selling points mixed together? If anything fails, rewrite it before returning —
also check against the language rule below."""

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


def _creative_direction_block(has_outline: bool = False) -> str:
    if has_outline:
        return f"""CREATIVE STRATEGY — the CREATIVE PREMISE, ARCHITECTURE, and APPROVED BEAT OUTLINE
given below have ALREADY made these decisions. Do NOT re-derive a different hook idea, mechanism, or
story arc, and do NOT quietly drift the outline's specific situation back toward a safer, more
generic version of itself. Your job here is EXECUTION, not re-invention:
1. Read the premise, the architecture's required beats/prohibited patterns, and the outline's beats
   as a single locked plan.
2. Write each outline beat as real, specific dialogue/narration/action — turn the outline's
   structural description of "what happens" into the actual spoken lines and visuals, in this exact
   product/audience's voice, without adding filler or generic advertising language to fill space.
3. Still report which single label from this list your execution actually reads as, verbatim, in the
   top-level "creative_mechanism" JSON field (it must describe what you actually wrote, not restart
   the creative decision): {_creative_mechanisms_prose()}.
4. HOOK -> PAYOFF — the approved hook opened a specific promise or curiosity gap; the body must
   actually resolve it specifically, in a way that couldn't be guessed from the hook alone.
5. CTA -> IDEA — the closing line must connect back to the outline's payoff beat and the premise's
   actual idea, not a generic sign-off that could close any script in this category.
Only after this, write the actual script — do not hedge between the given plan and a different one."""
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
  "hook": {"text": string, "on_screen_text": string, "visual_tags": [string], "scene_label": string, "section": string, "visual_direction": string, "action": string, "reaction": string, "camera_angle": string, "emotion": string, "duration_seconds": number, "b_roll": [string], "sfx": string, "ai_image_prompt": string, "ai_video_prompt": string},
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


def _video_structure(bucket: str, format_value: str, format_description: str, has_outline: bool = False) -> str:
    """The default Video Ad structure unless a different video format was
    requested — "video_ad" itself and an empty/unrecognized format both fall
    through to the original duration-quota ad structure unchanged."""
    if format_value and format_value != "video_ad":
        structure = content_formats.video_structure_block(format_value, format_description)
        if structure:
            return structure
    return _structure_block(bucket, has_outline)


def _system_prompt(bucket: str, format_value: str = "", format_description: str = "", tone: str = "", has_outline: bool = False) -> str:
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
        + _creative_direction_block(has_outline)
        + "\n\n"
        + _video_structure(bucket, format_value, format_description, has_outline)
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


def _static_system_prompt(format_value: str, format_description: str, tone: str, has_outline: bool = False) -> str:
    return (
        "You are a senior creative director and copywriter for a content factory pipeline, writing "
        "static ad creative (a single graphic or a short slide set), as sharp and professional as a "
        "real D2C brand's in-house creative team — not a video script, no voiceover or camera work. "
        "You do NOT invent the creative situation itself — you are given ONE specific, already-"
        "chosen story situation (a persona, a conflict, an emotional arc) — but you choose HOW to "
        "distill it into the requested static format's copy plus a detailed image-generation prompt. "
        "Stay faithful to the given persona, emotion, and marketing angle throughout.\n\n"
        + _creative_direction_block(has_outline)
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
- Ingredients exist to serve the STORY, not to be enumerated. Before naming any ingredient, ask: does
  THIS premise/creative idea actually need this specific ingredient named, or is a general phrase
  ("natural ingredients", "a herbal blend") enough here? Most scripts should name at most ONE, maybe
  two, ingredients — whichever one the premise's own logic makes relevant (e.g. the one the visual
  device shows, the one the payoff turns on) — never all of the given ones back-to-back. When an
  ingredient does earn a mention, the chain is: name it -> the one relevant property (not a definition)
  -> why THIS property matters to what just happened in the story, in the same breath, not as a
  separate label-then-benefit line. Do NOT write a line-per-ingredient pattern (ingredient, ingredient,
  ingredient, then benefit, benefit) even if several are given — that reads as a label being read
  aloud, not a story.
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


def _approved_concept_block(s) -> str:
    """The Story Idea's own creative_mechanism/creative_engine/hook fields,
    rendered DIRECTLY into the writer-facing brief. Fix for a traced bug: the
    writer previously only ever saw title/description/emotion/persona/
    marketing_angle/category here — creative_mechanism, creative_engine,
    product_role, human_situation, behavioral_tension, and the Hooks Menu
    hook_type/hook_mechanism/hook_execution fields reached the writer only
    INDIRECTLY (via premise generation re-deriving them from
    pre.situation_block, a separate, lossy path that only runs for a FRESH
    generation and never for regenerate_script_section at all) — so the
    writer was reconstructing the concept from a thinner summary than what
    was actually approved. Every line here is conditional on the field
    actually being set, so an older situation predating these fields renders
    exactly as before (empty string, no change)."""
    lines = []
    if getattr(s, "creative_mechanism", ""):
        lines.append(f"Approved creative mechanism: {s.creative_mechanism}")
    if getattr(s, "creative_engine", ""):
        lines.append(f"Approved creative engine (the specific behavior + object/ritual + turn — execute THIS, do not substitute a different one): {s.creative_engine}")
    if getattr(s, "human_situation", ""):
        lines.append(f"Human situation: {s.human_situation}")
    if getattr(s, "behavioral_tension", ""):
        lines.append(f"Behavioral tension: {s.behavioral_tension}")
    if getattr(s, "product_role", ""):
        lines.append(f"Product's role in this idea: {s.product_role}")
    if getattr(s, "hook_type", ""):
        lines.append(f"Approved hook tactic: {s.hook_type}")
        if getattr(s, "hook_mechanism", ""):
            lines.append(f"Why this tactic fits: {s.hook_mechanism}")
        if getattr(s, "hook_execution", ""):
            lines.append(f"Approved hook execution (the actual opening scene/action/dialogue — adapt to this exact product/language, do not flatten into a generic spoken line): {s.hook_execution}")
    return ("\n" + "\n".join(lines) + "\n") if lines else ""


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
        f"{_approved_concept_block(s)}"
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
    if ctx.never_say:
        lines.append(f"NEVER SAY (brand-voice guardrail, distinct from the claims above): {ctx.never_say}")
    if ctx.words_to_use:
        lines.append(f"Words/phrases to favor: {', '.join(ctx.words_to_use)}")
    if ctx.words_to_avoid:
        lines.append(f"Words/phrases to avoid: {', '.join(ctx.words_to_avoid)}")
    if ctx.creative_angles:
        lines.append("Approved creative angles for this product (pick the one that fits the chosen format/situation):")
        lines.extend(f"  - {a}" for a in ctx.creative_angles)
    if ctx.approved_hooks:
        lines.append("Product-specific approved hooks (style reference only, do not reuse verbatim unless one is explicitly selected as the opening hook elsewhere in this prompt):")
        lines.extend(f"  - {h}" for h in ctx.approved_hooks)
    if ctx.preferred_visual_style:
        lines.append(f"Preferred visual style (for visual_direction/ai_image_prompt fields): {ctx.preferred_visual_style}")
    if ctx.visual_exclusions:
        lines.append(f"Visual exclusions (never depict): {ctx.visual_exclusions}")
    if ctx.reference_script_excerpts:
        lines.append(
            "Approved reference script excerpts — STYLE/PACING/TONE reference only. Learn the voice, "
            "hook pattern, and structure. Do NOT copy sentences, claims, or the exact creative idea "
            "verbatim — write an original script:"
        )
        for excerpt in ctx.reference_script_excerpts:
            lines.append(f'  """{excerpt}"""')
    return "\n".join(lines)


def _call_llm(system: str, user_message: str, max_tokens: int, model: str, label: str = "script_service") -> str:
    return call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=system,
            contents=[user_message],
            model=model,
            max_output_tokens=max_tokens,
            json_mode=True,
            label=label,
        ),
        label=label,
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


def _repair_json(broken_text: str, error_message: str, max_tokens: int, model: str) -> dict:
    user_message = f"Parser error: {error_message}\n\nBroken JSON:\n{broken_text}"
    raw = _call_llm(_REPAIR_SYSTEM_PROMPT, user_message, max_tokens, model, label="script_json_repair")
    return _parse_script_json(raw)


def _generate_with_recovery(
    system: str,
    user_message: str,
    max_tokens: int,
    target_duration: str,
    target_word_count: int | None = None,
    content_type: ContentType = ContentType.video,
    model: str = "",
    label: str = "script_service",
) -> dict:
    """Attempt 1 -> silent retry (attempt 2) -> repair pass -> only then raise.
    The caller (and therefore the user) only ever sees an error if all three
    recovery stages fail.

    `model` selects which routing tier (Option C) this particular call uses —
    callers decide (final-script tier for a fresh write or a gate-triggered
    rewrite, creative tier for a narrow single-block edit); an empty string
    falls back to final_script_model, since every existing caller of this
    function IS producing/rewriting a full script."""
    model = model or settings.final_script_model
    data: dict | None = None
    last_raw = ""
    last_error: Exception | None = None

    got_any_text = False
    for attempt in (1, 2):
        try:
            last_raw = _call_llm(system, user_message, max_tokens, model, label=label)
            got_any_text = True
            candidate = _parse_script_json(last_raw)
            GeneratedScript(**candidate)
            data = candidate
            break
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            last_error = e
            logger.warning("Script generation attempt %d produced invalid JSON: %s", attempt, e)
        except (openrouter_utils.OpenRouterError, ValueError) as e:
            # Phase 2 fix: previously this exact exception type (raised by
            # call_openrouter_with_retry once its own attempts are exhausted
            # — e.g. every retry came back as an empty/malformed response)
            # was NOT caught here at all, so it propagated straight past
            # this function's own attempt-2 and repair-pass logic, aborting
            # generation on the very first failure. The "existing retry+
            # repair mechanism" was never actually reached for this failure
            # shape before this fix.
            last_error = e
            logger.warning("Script generation attempt %d got no usable response: %s", attempt, e)

    if data is None:
        if not got_any_text or not last_raw.strip():
            # Nothing was ever returned to repair — asking the model to
            # "fix" an empty string wastes a call for no possible benefit.
            # Fail cleanly and honestly instead.
            logger.warning("Both generation attempts returned no usable text — skipping the repair pass (nothing to repair).")
            raise ValueError(
                "Gemini returned no usable content after 2 attempts. This is usually a transient "
                "provider issue — please try again in a moment."
            ) from last_error
        try:
            data = _repair_json(last_raw, str(last_error), max_tokens, model)
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
                model,
                label=label,
            )
            corrected_data = _parse_script_json(corrected_raw)
            GeneratedScript(**corrected_data)
            data = corrected_data
        except Exception as e:
            logger.warning("Length-correction regeneration failed, keeping prior script: %s", e)

    return data


def _finish(
    data: dict,
    payload,
    target_duration: str,
    human_insight: str = "",
    creative_architecture_key: str = "",
    creative_breakdown: "creative_breakdown_service.CreativeBreakdown | None" = None,
    creative_quality_assessment: "creative_breakdown_service.CreativeQualityAssessment | None" = None,
) -> GeneratedScript:
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
        human_insight=human_insight,
        creative_architecture=creative_architecture_key,
        creative_breakdown=creative_breakdown.as_dict() if creative_breakdown is not None else None,
        creative_quality_assessment=creative_quality_assessment.as_dict() if creative_quality_assessment is not None else None,
    )


def _rewrite_for_quality(
    data: dict,
    payload,
    target_duration: str,
    target_word_count: int | None,
    reason: str,
    content_type: ContentType,
    creative_context_block: str = "",
) -> dict:
    """The quality/architecture gates' one allowed rewrite pass. Reuses the
    same full-rewrite scaffolding as a normal "full" regenerate — same
    prefix and scope guidance ("keep the same story/hook/persona/product
    facts, build on it"), so a selected Hooks-library hook or the current
    creative direction is preserved by default; the `reason` argument is
    what actually steers the fix, and only overrides that default when the
    flagged issue is specifically about the hook itself.

    `creative_context_block` re-attaches the approved premise/architecture/
    beat outline (when a fresh generation produced one) so a rewrite
    triggered by e.g. "architecture_abandoned" has the actual outline to
    snap back to, instead of only a vague reason string — without this, the
    rewrite pass has no memory of what the approved plan even was."""
    context = _context_block(payload, target_duration, target_word_count)
    if creative_context_block:
        context += f"\n\n{creative_context_block}"
    current_script_json = json.dumps(data, ensure_ascii=False)
    user_message = (
        f"{context}\n\n"
        f"Current script (JSON) — this is what was generated; follow the TASK above to fix it:\n"
        f"{current_script_json}"
    )
    system = _regen_system_prompt(ScriptRegenerateScope.full, reason, content_type, getattr(payload, "tone", ""))
    # The "necessary final rewrite" (Option C §8) — only reached when a
    # quality/architecture gate actually flagged something, never on every
    # generation — so this uses the final_script tier (Pro), same as the
    # original write.
    _rewrite_start = time.monotonic()
    logger.info("[GENERATE_SCRIPT] rewrite start model=%s", settings.final_script_model)
    result = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, target_duration, target_word_count, content_type,
        model=settings.final_script_model, label="gate_rewrite",
    )
    logger.info("[GENERATE_SCRIPT] rewrite complete elapsed=%.1fs", time.monotonic() - _rewrite_start)
    return result


def _rewrite_context_for_issues(pre: "CreativePreStageResult | None", issues: list[str]) -> str:
    """Decides how much of the creative pre-stage context survives into a
    quality/architecture-gate rewrite, based on WHAT was flagged — never
    just "escalated or not":
    - territory_mismatch/same_idea_different_clothes: the TERRITORY itself
      is the problem (never expressed, or indistinguishable from a recent
      one) — drop everything (territory+premise+outline) and instead tell
      the rewrite which territories (including the one that just failed)
      to avoid, so it picks a genuinely different lens.
    - other 3+-issue escalation: the EXECUTION is the problem, not the
      lens — keep the territory as context (it wasn't at fault) but drop
      the premise/outline specifics, so the rewrite finds a new situation
      inside the same approved territory rather than blindly patching or
      discarding something that wasn't flagged.
    - <3 issues, no territory problem: ordinary targeted patch — keep the
      full pre-stage context exactly as before this function existed.
    Returns "" when pre is None (the narrow/no-pre-stages callers).

    The Product Creative Contract is the one exception to all of the above:
    it is PRODUCT TRUTH, never something a rewrite is allowed to lose track
    of regardless of which branch fires — a territory-escalation rewrite
    that forgets the product's real category could "successfully" pick a
    fresh territory that's just as category-wrong as the one it replaced.
    It is always prepended, on every branch."""
    if pre is None:
        return ""
    contract_block = pre.contract.prompt_block() if pre.contract is not None else ""

    if script_quality.is_territory_weak(issues):
        recent = list(creative_memory_service.recent_concepts(pre.memory_key)) if pre.memory_key else []
        if pre.territory is not None:
            recent = recent + [{
                "territory_name": pre.territory.territory_name,
                "human_tension": pre.territory.human_tension,
                "creative_question": pre.territory.creative_question,
            }]
        block = creative_memory_service.recent_territories_prompt_block(recent)
        if not block:
            return contract_block
        return (
            f"{contract_block}\n\n{block}\n\nThe previous attempt's territory did not survive into the "
            "script (or was too close to a recent one) — pick a genuinely different underlying creative "
            "territory for this rewrite, not just a different execution of the same one, while staying "
            "inside the Product Creative Contract above."
        )
    if script_quality.is_premise_escalation(issues):
        territory_part = pre.territory.prompt_block() if pre.territory is not None else ""
        return f"{contract_block}\n\n{territory_part}" if territory_part else contract_block
    # pre.prompt_block already starts with the contract block (it's always
    # blocks[0] — see _run_creative_pre_stages), so no duplication here.
    return pre.prompt_block


def _claim_safety_inputs(payload) -> "tuple[str, list[str], list[str]]":
    """product_name, ingredients, approved_claims — from the Product
    Library context when a library product was selected, falling back to
    the manually-structured product otherwise. Mirrors _brief_fields'
    preference order. An empty approved_claims list is the correct,
    default-safe result when neither source gives one — never invented."""
    ctx = getattr(payload, "product_context", None)
    p = payload.structured_product
    if ctx is not None:
        return ctx.name, list(getattr(ctx, "ingredients", []) or p.ingredients), list(getattr(ctx, "approved_claims", []) or [])
    return p.product_name, list(p.ingredients or []), []


def _apply_claim_safety_gate(
    data: dict,
    payload,
    target_duration: str,
    target_word_count: int | None,
    content_type: ContentType,
) -> "tuple[dict, claim_safety_service.ClaimSafetyResult]":
    """The "Meri Maa Ki Dua" regression fix — a HARD pre-gate, run BEFORE
    the quality/architecture gates (and therefore before either can spend
    its own one rewrite on something else while an unsupported claim or
    coercive framing survives untouched). An unsupported efficacy claim —
    explicit, implied, or told through story/metaphor — or emotionally
    coercive framing is never just one score among many that strong writing
    elsewhere can outweigh: it forces exactly one rewrite with the specific
    defect named, then the SAME check runs again on the rewritten draft
    (bounded — no infinite loop, matching every other re-verification in
    this pipeline) so a rewrite can never quietly reintroduce or leave
    unresolved the exact thing it was told to fix.

    Returns (data, result) — result is the FINAL claim-safety verdict for
    whatever draft is actually being returned, so callers can refuse to
    ever present a still-failing script as "passed" (see
    creative_breakdown_service.build_creative_quality_assessment's
    claim_safety_override)."""
    product_name, ingredients, approved_claims = _claim_safety_inputs(payload)
    text = " ".join(script_quality._block_texts(data))
    result = claim_safety_service.check_claim_safety_and_coercion(
        text, product_name=product_name, ingredients=ingredients, approved_claims=approved_claims,
    )
    if result.passed:
        return data, result
    reason_parts = []
    if result.unsupported:
        reason_parts.append(
            f"it contains an unsupported {'implied/narrative' if result.claim_type == 'implied_narrative' else 'explicit'} "
            f"efficacy/outcome claim (\"{result.evidence}\") that isn't covered by any approved claim given — remove or "
            "soften it to a general, non-outcome statement (name the ingredient/experience without promising a result)"
        )
    if result.emotional_coercion:
        coercion_detail = result.coercion_reason or "guilt, devotional pressure, or family-approval-tied-to-purchase framing"
        reason_parts.append(
            f"it relies on emotionally coercive framing ({coercion_detail}) — rewrite the family/relationship beat so "
            "it reflects genuine warmth or care, never guilt, shame, or a prayer/blessing framed as caused by the purchase"
        )
    reason = "Rewrite this script because " + "; and because ".join(reason_parts) + "."
    logger.info("Claim-safety hard gate failed (%s) — attempting one bounded rewrite", result.claim_type or "coercion")
    rewritten = _rewrite_for_quality(data, payload, target_duration, target_word_count, reason, content_type)
    recheck_text = " ".join(script_quality._block_texts(rewritten))
    recheck = claim_safety_service.check_claim_safety_and_coercion(
        recheck_text, product_name=product_name, ingredients=ingredients, approved_claims=approved_claims,
    )
    if not recheck.passed:
        logger.warning(
            "Claim-safety hard gate still fails after the one allowed rewrite (%s) — bounded failure, "
            "keeping the rewritten draft but marking it as NOT passed", recheck.claim_type or "coercion"
        )
    return rewritten, recheck


def _apply_quality_gate(
    data: dict,
    payload,
    target_duration: str,
    target_word_count: int | None,
    content_type: ContentType,
    run_semantic_check: bool,
    pre: "CreativePreStageResult | None" = None,
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
        context = _rewrite_context_for_issues(pre, issues)
        return _rewrite_for_quality(
            data, payload, target_duration, target_word_count, reason, content_type, context
        )
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
        # A single-block edit (Improve Hook/CTA/etc) — cheap, frequent, and
        # not the "final script"/"necessary rewrite" Option C reserves Pro
        # for, so this stays on the creative (Flash) tier.
        rewritten = _generate_with_recovery(
            system, user_message, _MAX_TOKENS, target_duration, target_word_count, content_type,
            model=settings.creative_model, label="narrow_regenerate",
        )
        # The rewrite prompt says "leave every other block unchanged", but a
        # targeted-fix instruction can still make the model drift and touch
        # more than it was asked to — enforce the contract deterministically
        # rather than trusting compliance alone.
        return script_quality.enforce_narrow_scope(data, rewritten, payload.scope, payload.target_scene_label)
    except Exception as e:
        logger.warning("Narrow quality gate rewrite failed, keeping original draft: %s", e)
        return data


def _story_situation_block(situation) -> str:
    """Renders the user's chosen Story Situation card as prompt text —
    shared by premise generation (Phase 3C grounding fix) and the post-
    script Creative Director gate (title/story integrity check). Empty when
    no situation is given (defensive; every real caller has one).

    Hooks Menu task addition: when the situation carries a hook_type (the
    Story Idea already committed to a specific hook TACTIC, separate from
    the creative mechanism), that's rendered too — this single block already
    reaches both premise generation and the Creative Director gate, so no
    extra plumbing was needed to make either one hook-tactic-aware."""
    if situation is None:
        return ""
    title = getattr(situation, "title", "") or ""
    if not title:
        return ""
    hook_type = getattr(situation, "hook_type", "") or ""
    hook_lines = (
        f"\nApproved hook tactic: {hook_type}\n"
        f"Why this tactic fits: {getattr(situation, 'hook_mechanism', '') or ''}\n"
        f"Approved hook execution (the opening scene/action/dialogue to actually write, adapted to "
        f"this exact product/language — not replaced with a generic spoken line): "
        f"{getattr(situation, 'hook_execution', '') or ''}"
        if hook_type else ""
    )
    return (
        f"Title: {title}\n"
        f"Description: {getattr(situation, 'description', '') or ''}\n"
        f"Persona: {getattr(situation, 'persona', '') or ''}\n"
        f"Emotion: {getattr(situation, 'emotion', '') or ''}\n"
        f"Marketing angle: {getattr(situation, 'marketing_angle', '') or ''}"
        f"{hook_lines}"
    )


def _brief_fields(payload) -> tuple[str, str, str, str, list[str], str]:
    """product_name, category, target_audience, usp, benefits, primary_problem —
    preferring the richer Product Library context when a library product is
    selected, falling back to the manually structured product otherwise."""
    ctx = getattr(payload, "product_context", None)
    p = payload.structured_product
    if ctx is not None:
        return (
            ctx.name,
            ctx.category or payload.product_category,
            ctx.target_audience or p.target_audience,
            ctx.usp or p.usp,
            list(ctx.benefits) or list(p.key_benefits),
            ctx.primary_problem,
        )
    return (p.product_name, payload.product_category, p.target_audience, p.usp, list(p.key_benefits), "")


@dataclass
class CreativePreStageResult:
    prompt_block: str = ""
    payload: object = None
    insight_statement: str = ""
    architecture: "creative_architecture.Architecture | None" = None
    outline: "beat_outline_service.BeatOutline | None" = None
    premise: "creative_premise_service.CreativePremise | None" = None
    territory: "creative_territory_service.CreativeTerritory | None" = None
    contract: "product_context_service.ProductCreativeContract | None" = None
    reference_dna_notes: str = ""
    product_name: str = ""
    target_audience: str = ""
    memory_key: str = ""
    recent_territories_block: str = ""
    situation_block: str = ""


def _run_creative_pre_stages(payload, target_duration: str) -> CreativePreStageResult:
    """Human insight discovery -> architecture selection -> hook generation/
    evaluation -> BEAT OUTLINE generation + validation (Parts 3, 1, 4, then
    the outline-enforcement upgrade) — runs once, before the main generation
    call, ONLY for a fresh/from-scratch script (see _generate_full_script's
    two callers). Never raises: any failure at any stage returns a
    default-valued CreativePreStageResult(payload=payload) unchanged, so
    generation always proceeds exactly as it did before this pipeline
    existed — the outline (and everything after it) is additive, not a hard
    dependency for generation to succeed at all."""
    try:
        product_name, category, target_audience, usp, benefits, primary_problem = _brief_fields(payload)

        # PRODUCT TRUTH — established BEFORE any creative generation, per the
        # hierarchy PRODUCT TRUTH -> AUDIENCE TRUTH -> BEHAVIOURAL TRUTH ->
        # CREATIVE TERRITORY -> STORYTELLING DEVICE -> SCRIPT. This is fixed
        # factual grounding (derived from the given brief, the Product
        # Library record when one is selected, and reference-DNA category
        # association — never invented from the product name alone) that
        # every downstream stage receives and is instructed to treat as
        # immutable, so a creative pass can change HOW the story is told but
        # never WHAT the product fundamentally is.
        contract = product_context_service.build_product_creative_contract(
            product_name=product_name, category=category, target_audience=target_audience,
            usp=usp, benefits=benefits, primary_problem=primary_problem,
            product_context=getattr(payload, "product_context", None),
        )
        contract_block = contract.prompt_block()

        # CREATIVE DIVERSITY MEMORY — what recent FRESH generations for this
        # exact product already used, so this call can diverge from it
        # rather than converging on the same "safest" device every time (the
        # gap the pre-existing avoid_repeating_hook/mechanism never covered,
        # since that only threads forward on an explicit regenerate of an
        # existing script, not a brand-new generate_script() call).
        ctx = getattr(payload, "product_context", None)
        memory_key = creative_memory_service.product_key(
            getattr(ctx, "product_id", "") or "", product_name, category
        )
        recent_concepts = creative_memory_service.recent_concepts(memory_key)
        recent_architectures = [c["architecture_key"] for c in recent_concepts if c.get("architecture_key")]
        recent_territory_block = creative_memory_service.recent_territory_prompt_block(recent_concepts)
        recent_territories_block = creative_memory_service.recent_territories_prompt_block(recent_concepts)

        insight = creative_insight_service.discover_insight(
            product_name=product_name,
            category=category,
            target_audience=target_audience,
            usp=usp,
            benefits=benefits,
            primary_problem=primary_problem,
            contract_block=contract_block,
        )
        insight_statement = insight.insight_statement if insight else ""

        # CREATIVE TERRITORY — decided BEFORE architecture/premise: the
        # underlying human/behavioural LENS this ad will explore (one level
        # more abstract than a premise). Uses only the category-agnostic
        # anti-pattern notes here (not the architecture-specific reference
        # notes below) since architecture hasn't been chosen yet — the full
        # mechanism-specific reference notes still flow into premise
        # generation once architecture is known.
        territory = creative_territory_service.generate_and_select_territory(
            product_name=product_name,
            category=category,
            target_audience=target_audience,
            usp=usp,
            benefits=benefits,
            insight_block=insight.prompt_block() if insight else "",
            reference_dna_notes=creative_reference_dna.anti_pattern_notes(),
            recent_territory_block=recent_territories_block,
            recent_concepts=recent_concepts,
            contract=contract,
            contract_block=contract_block,
        )
        territory_block = territory.prompt_block() if territory else ""

        available_proof = ", ".join(benefits) or usp
        architecture = creative_architecture.select_architecture(
            product_category=category,
            target_audience=target_audience,
            objective=f"{payload.content_type.value} ad on {payload.platform}",
            available_proof=available_proof,
            tone=payload.tone,
            platform=payload.platform,
            insight_statement=insight_statement,
            recently_used_architectures=recent_architectures,
            territory_context=territory_block,
            contract_block=contract_block,
        )

        # brief_text is checked (in addition to the coarse product_category
        # string) so a product whose real audience/brief genuinely describes
        # a tobacco/gutka/pan-masala switching situation isn't misclassified
        # as an unrelated category just because its stored category label
        # (e.g. the Product Library's "herbal_health") doesn't say so.
        brief_text = " ".join([product_name, target_audience, usp, " ".join(benefits)])
        ref_notes = creative_reference_dna.relevant_notes(architecture.key, category, brief_text=brief_text)
        # Winning-reference-DNA fix (2026-09-18 task) — mechanism_notes()
        # already existed, fully implemented, but was never actually called
        # anywhere in the pipeline (confirmed by inspection): the chosen
        # Story Idea may have already committed to a specific creative_
        # mechanism_catalog label (Story Ideas pool generation reports one
        # per candidate), and this codebase's own real prior AayushWellness
        # Herbal Masala reference scripts ("Calender Video August" —
        # CAL1/CAL3/CAL4/CAL5 in creative_reference_dna.py) are keyed by
        # that exact mechanism vocabulary, not by architecture — CAL1/CAL3
        # have no architecture at all, so relevant_notes() alone could
        # never surface them regardless of which architecture was selected.
        # Merging both keeps the existing architecture-keyed structural
        # notes AND adds the specific product-proven example for the
        # already-chosen mechanism, without changing relevant_notes()'s own
        # behavior, category-transfer labeling, or any other caller.
        selected_mechanism = getattr(payload.selected_situation, "creative_mechanism", "") or ""
        if selected_mechanism:
            mechanism_ref_notes = creative_reference_dna.mechanism_notes(
                selected_mechanism, category, brief_text=brief_text
            )
            if mechanism_ref_notes:
                ref_notes = f"{ref_notes}\n{mechanism_ref_notes}" if ref_notes else mechanism_ref_notes

        # CREATIVE PREMISE — dramatizes the approved territory (when one was
        # selected) into one specific situation; the missing link between the
        # insight/territory (a lens) and the beat outline (a structure).
        # Generates several genuinely distinct candidate premises, self-
        # scores them, and keeps only the strongest — never exposed to the
        # user, never shown as 10 scripts.
        #
        # situation_block (Phase 3C root-cause fix): the user's OWN chosen
        # Story Situation card. Before this, premise/territory/outline
        # generation ran completely disconnected from it — the premise
        # invented its own unrelated "situation" field, and the writer was
        # then told the (situation-blind) premise/outline had "ALREADY made
        # these decisions", so a card titled e.g. "Doctor ki Advice, Healthy
        # Life" could produce a script with no doctor in it at all. Grounding
        # premise generation in the actual chosen card closes that gap.
        situation_block = _story_situation_block(payload.selected_situation)
        premise = creative_premise_service.generate_and_select_premise(
            product_name=product_name,
            category=category,
            target_audience=target_audience,
            usp=usp,
            benefits=benefits,
            insight_block=insight.prompt_block() if insight else "",
            architecture_name=architecture.name,
            architecture_purpose=architecture.creative_purpose,
            reference_dna_notes=ref_notes,
            recent_territory_block=recent_territory_block,
            territory_block=territory_block,
            contract=contract,
            contract_block=contract_block,
            situation_block=situation_block,
        )

        # PRODUCT TRUTH goes first — every stage below builds inside it, per
        # the PRODUCT TRUTH -> AUDIENCE TRUTH -> ... -> SCRIPT hierarchy.
        blocks = [contract_block]
        if insight is not None:
            blocks.append(insight.prompt_block())
        if territory is not None:
            blocks.append(territory.prompt_block())
        if ref_notes:
            blocks.append(ref_notes)
        if premise is not None:
            blocks.append(premise.prompt_block())

        # Only generate a machine hook if the user hasn't already picked one
        # from the Hooks library — a human-selected hook always wins.
        selected_hook_text = getattr(payload, "selected_hook_text", "")
        if not selected_hook_text:
            reveal_early = "early" in architecture.product_reveal_logic.lower() or "immediate" in architecture.product_reveal_logic.lower()
            language_label = payload.script_language.value if hasattr(payload.script_language, "value") else str(payload.script_language)
            hook = hook_generation_service.generate_and_select_hook(
                product_name=product_name,
                category=category,
                target_audience=target_audience,
                insight_block=insight.prompt_block() if insight else "",
                architecture_hook_pattern=architecture.hook_pattern,
                product_reveal_early=reveal_early,
                language=language_label,
                premise_block=premise.prompt_block() if premise else "",
                contract_block=contract_block,
                # Hooks Menu task — the chosen Story Idea may have already
                # committed to a specific hook TACTIC; execute it rather
                # than freely re-deriving a new one. Empty on any situation
                # predating this field (existing behavior unchanged).
                hook_type=getattr(payload.selected_situation, "hook_type", "") or "",
                hook_mechanism=getattr(payload.selected_situation, "hook_mechanism", "") or "",
                hook_execution=getattr(payload.selected_situation, "hook_execution", "") or "",
            )
            if hook is not None:
                payload = payload.model_copy(update={"selected_hook_text": hook.text})
                selected_hook_text = hook.text

        # BEAT OUTLINE — the story blueprint the writing call must follow,
        # now built from (and validated against) the selected premise, not
        # just the raw insight. Falls back to architecture.prompt_block()
        # alone (the previous, advisory-only behavior) if outline
        # generation/validation never produces a usable outline —
        # generation still proceeds either way.
        outline, remaining_outline_issues = beat_outline_service.generate_and_validate_outline(
            architecture=architecture,
            hook=selected_hook_text,
            human_insight=insight_statement,
            product_name=product_name,
            category=category,
            target_audience=target_audience,
            target_duration_bucket=target_duration,
            premise=premise,
            contract=contract,
        )
        if outline is not None and outline.beats:
            blocks.append(outline.prompt_block())
            if remaining_outline_issues:
                logger.info(
                    "Beat outline used despite unresolved issues after max attempts: %s", remaining_outline_issues
                )
        else:
            blocks.append(architecture.prompt_block())

        return CreativePreStageResult(
            prompt_block="\n\n".join(blocks),
            payload=payload,
            insight_statement=insight_statement,
            architecture=architecture,
            outline=outline,
            premise=premise,
            territory=territory,
            contract=contract,
            reference_dna_notes=ref_notes,
            product_name=product_name,
            target_audience=target_audience,
            memory_key=memory_key,
            recent_territories_block=recent_territories_block,
            situation_block=situation_block,
        )
    except Exception as e:
        logger.warning("Creative pre-stages (insight/architecture/hook/outline) failed, proceeding without them: %s", e)
        return CreativePreStageResult(payload=payload)


def _apply_architecture_gate(
    data: dict,
    pre: CreativePreStageResult,
    payload,
    target_duration: str,
    target_word_count: int | None,
    content_type: ContentType,
) -> "tuple[dict, architecture_validation_service.ScriptExecutionEvaluation | None]":
    """Post-script validation (Parts 5-7 of the outline-enforcement upgrade)
    — runs ONLY when an architecture was actually selected (i.e. the
    creative pre-stages succeeded). Cheap deterministic checks first (hook
    intact, product-reveal timing, beat count), then ONE combined LLM call
    covering architecture compliance + the "creative director" evaluation +
    the strengthened competitor-swappable test. At most one targeted
    rewrite, same "never raises, fall back to draft" convention as
    _apply_quality_gate. Runs AFTER (not instead of) the existing quality
    gate — a script only reaches here once the generic checks already
    passed.

    Returns (data, evaluation) — evaluation is the full
    ScriptExecutionEvaluation (scores/announcement_mode/abstract_copy_risk),
    not just its .issues, whenever the LLM evaluation call actually ran; it
    reflects whichever draft is actually being returned (the post-rewrite
    re-check's evaluation when a rewrite happened, the original evaluation
    otherwise). None when no evaluation call ran at all (no architecture,
    or deterministic checks already caught something first) — this is the
    ONLY change from the prior version, which called the exact same
    evaluate_script_execution() function via a .issues-only wrapper and
    discarded everything else; no algorithm/scoring/prompt change."""
    if pre.architecture is None:
        return data, None
    try:
        territory_block = pre.territory.prompt_block() if pre.territory is not None else ""
        contract_block = pre.contract.prompt_block() if pre.contract is not None else ""
        issues = architecture_validation_service.validate_script_against_outline_deterministic(
            data, pre.outline, pre.architecture, pre.product_name, pre.contract
        )
        evaluation = None
        if not issues:
            evaluation = architecture_validation_service.evaluate_script_execution(
                data, pre.outline, pre.architecture, pre.product_name, pre.target_audience, pre.reference_dna_notes,
                territory_block, pre.recent_territories_block, contract_block,
                situation_block=pre.situation_block,
                content_type=content_type.value if hasattr(content_type, "value") else str(content_type),
                format_value=payload.format,
            )
            issues = evaluation.issues
        if not issues:
            return data, evaluation
        logger.info("Architecture/creative-director gate flagged %s — attempting one targeted rewrite", issues)
        reason = script_quality.rewrite_reason(issues)
        context = _rewrite_context_for_issues(pre, issues)
        rewritten = _rewrite_for_quality(
            data, payload, target_duration, target_word_count, reason, content_type, context
        )
        # Bounded re-verification (Phase 3C Part 17): confirm the ONE allowed
        # rewrite actually fixed what was flagged, rather than accepting it
        # unconditionally. Deliberately does NOT trigger a second rewrite
        # either way — a still-failing re-check is logged as a bounded
        # failure and the rewritten draft is still returned (strictly better
        # odds than the pre-rewrite draft, never worse), matching "maximum
        # retries must remain bounded, no infinite loops, do not silently
        # downgrade from Pro".
        recheck_evaluation = None
        try:
            recheck_evaluation = architecture_validation_service.evaluate_script_execution(
                rewritten, pre.outline, pre.architecture, pre.product_name, pre.target_audience,
                pre.reference_dna_notes, territory_block, pre.recent_territories_block, contract_block,
                situation_block=pre.situation_block,
                content_type=content_type.value if hasattr(content_type, "value") else str(content_type),
                format_value=payload.format,
            )
            recheck_issues = recheck_evaluation.issues
            if recheck_issues:
                logger.warning(
                    "Architecture/creative-director gate still flags %s after the one allowed rewrite — "
                    "bounded failure, keeping the rewritten draft (no further retry)", recheck_issues
                )
            else:
                logger.info("Architecture/creative-director gate re-check passed after rewrite")
        except Exception as e:
            logger.warning("Post-rewrite re-check failed, keeping rewritten draft: %s", e)
        # recheck_evaluation (the state of the draft actually being
        # returned) takes priority; falls back to the pre-rewrite
        # `evaluation` only if the re-check itself failed to run.
        return rewritten, (recheck_evaluation or evaluation)
    except Exception as e:
        logger.warning("Architecture gate failed, keeping prior draft: %s", e)
        return data, None


def _generate_full_script(
    payload,
    target_duration: str,
    target_word_count: int | None = None,
    custom_instruction: str = "",
    avoid_repeating_hook: str = "",
    avoid_repeating_mechanism: str = "",
) -> GeneratedScript:
    # Pipeline cost/token observability (Option C §12-13) — tracks every
    # OpenRouter call made anywhere in this one generation (insight through
    # final rewrite) via a context-local accumulator, logged as one summary
    # line at the end regardless of how generation turns out. Purely
    # diagnostic — never affects the returned script.
    openrouter_utils.start_usage_tracking()
    try:
        return _generate_full_script_tracked(
            payload, target_duration, target_word_count, custom_instruction,
            avoid_repeating_hook, avoid_repeating_mechanism,
        )
    finally:
        summary = openrouter_utils.get_usage_summary()
        logger.info("pipeline_cost_summary %s", summary)
        openrouter_utils.stop_usage_tracking()


def _generate_full_script_tracked(
    payload,
    target_duration: str,
    target_word_count: int | None = None,
    custom_instruction: str = "",
    avoid_repeating_hook: str = "",
    avoid_repeating_mechanism: str = "",
) -> GeneratedScript:
    # [GENERATE_SCRIPT] stage timing (2026-09-18 task — timeout fix
    # follow-up, renamed from [SCRIPT_GENERATION]) — observability only,
    # matching the Story Ideas [STORY_IDEAS] convention; never affects
    # timeout/retry behavior. Logs stage name, elapsed seconds, and (where
    # safe) model name only — never prompts, product descriptions, or
    # script content. A retry's own attempt number is already logged by
    # call_openrouter_with_retry itself ("[label] attempt=N/M failed...",
    # openrouter_utils.py) — not duplicated here.
    _script_gen_start = time.monotonic()
    logger.info("[GENERATE_SCRIPT] start")
    pre = _run_creative_pre_stages(payload, target_duration)
    payload = pre.payload
    logger.info(
        "[GENERATE_SCRIPT] creative planning complete elapsed=%.1fs",
        time.monotonic() - _script_gen_start,
    )
    user_message = _context_block(payload, target_duration, target_word_count)
    if pre.prompt_block:
        user_message += f"\n\n{pre.prompt_block}"
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
    has_outline = pre.outline is not None and bool(pre.outline.beats)
    if payload.content_type == ContentType.static:
        system = _static_system_prompt(payload.format, payload.format_description, payload.tone, has_outline)
    else:
        system = _system_prompt(target_duration, payload.format, payload.format_description, payload.tone, has_outline)
    # THE main final script-writing call (Option C §5B) — the highest-value,
    # lowest-volume call in the pipeline, using the structured context
    # already produced (insight/territory/architecture/premise/hook/outline)
    # rather than a generic "write an ad" prompt.
    logger.info(
        "[GENERATE_SCRIPT] final script start model=%s elapsed=%.1fs",
        settings.final_script_model, time.monotonic() - _script_gen_start,
    )
    data = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, target_duration, target_word_count, payload.content_type,
        model=settings.final_script_model, label="final_script_write",
    )
    logger.info(
        "[GENERATE_SCRIPT] final script complete elapsed=%.1fs", time.monotonic() - _script_gen_start,
    )
    # Claim-safety/coercion HARD gate — runs FIRST, before the quality and
    # architecture gates get their own one rewrite each, so neither can
    # spend its shot on something else while an unsupported claim or
    # coercive framing survives untouched.
    logger.info("[GENERATE_SCRIPT] claim safety gate start elapsed=%.1fs", time.monotonic() - _script_gen_start)
    data, claim_safety_result = _apply_claim_safety_gate(
        data, payload, target_duration, target_word_count, payload.content_type
    )
    logger.info("[GENERATE_SCRIPT] claim safety gate complete elapsed=%.1fs", time.monotonic() - _script_gen_start)
    logger.info("[GENERATE_SCRIPT] quality gate start elapsed=%.1fs", time.monotonic() - _script_gen_start)
    data = _apply_quality_gate(
        data, payload, target_duration, target_word_count, payload.content_type, run_semantic_check=True,
        pre=pre,
    )
    logger.info("[GENERATE_SCRIPT] quality gate complete elapsed=%.1fs", time.monotonic() - _script_gen_start)
    logger.info("[GENERATE_SCRIPT] architecture gate start elapsed=%.1fs", time.monotonic() - _script_gen_start)
    data, evaluation = _apply_architecture_gate(data, pre, payload, target_duration, target_word_count, payload.content_type)
    logger.info(
        "[GENERATE_SCRIPT] validation complete elapsed=%.1fs", time.monotonic() - _script_gen_start,
    )
    architecture_key = pre.architecture.key if pre.architecture else ""
    # Creative Breakdown / Quality Assessment — deterministic renderers,
    # ZERO additional LLM calls: `evaluation` is the SAME evaluation object
    # the architecture gate above already computed (and previously
    # discarded down to .issues); pre.contract/territory/premise were
    # already sitting in scope. Both builders degrade to honest "not
    # available" lines rather than inventing anything when a piece is
    # missing (e.g. evaluation is None because deterministic issues caught
    # something before the LLM call ever ran).
    breakdown = creative_breakdown_service.build_creative_breakdown(
        contract=pre.contract, insight_statement=pre.insight_statement, territory=pre.territory,
        premise=pre.premise, selected_hook_text=payload.selected_hook_text, architecture=pre.architecture,
        evaluation=evaluation,
    )
    quality_assessment = creative_breakdown_service.build_creative_quality_assessment(
        contract=pre.contract, premise=pre.premise, evaluation=evaluation,
        claim_safety_result=claim_safety_result,
    )
    result = _finish(
        data, payload, target_duration, pre.insight_statement, architecture_key,
        creative_breakdown=breakdown, creative_quality_assessment=quality_assessment,
    )
    # Record this generation's territory AFTER it actually succeeded, so the
    # NEXT independent fresh generation for this product can diverge from
    # it. Never raises (creative_memory_service is fail-open internally).
    if pre.memory_key and pre.premise is not None:
        creative_memory_service.record_concept(
            pre.memory_key,
            architecture_key=architecture_key,
            creative_device=pre.premise.creative_device,
            visual_device=pre.premise.visual_device,
            emotional_engine=pre.premise.emotional_engine,
            narrative_device=pre.premise.narrative_device,
            insight_statement=pre.insight_statement,
            premise_statement=pre.premise.statement,
            territory_name=pre.territory.territory_name if pre.territory else "",
            human_tension=pre.territory.human_tension if pre.territory else "",
            creative_question=pre.territory.creative_question if pre.territory else "",
        )
    logger.info("[GENERATE_SCRIPT] complete elapsed=%.1fs", time.monotonic() - _script_gen_start)
    return result


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
    # A user-initiated "Entire Script"/"Shorten"/"Extend" (full/length scope)
    # is a whole-script rewrite of the same weight as the final script write
    # or a gate-triggered rewrite, so it uses the same final_script tier; a
    # single-block edit (hook/cta/science/story/etc) stays on the cheaper
    # creative tier, matching the narrow quality-gate rewrite above.
    is_broad_scope = payload.scope in (ScriptRegenerateScope.full, ScriptRegenerateScope.length)
    data = _generate_with_recovery(
        system, user_message, _MAX_TOKENS, length_target, payload.target_word_count, payload.content_type,
        model=settings.final_script_model if is_broad_scope else settings.creative_model,
        label="regenerate_full_or_length" if is_broad_scope else "narrow_regenerate",
    )
    # Quality gate only runs for the broad rewrite scopes (full/length) —
    # its rewrite pass always targets the WHOLE script, which is correct
    # there but would break a narrow scope's "leave every other block
    # untouched" contract (e.g. flagging a pre-existing issue in a body
    # block that an Improve-Hook/CTA-only edit was never meant to touch).
    if payload.scope in (ScriptRegenerateScope.full, ScriptRegenerateScope.length):
        # Claim-safety/coercion HARD gate — was previously only wired into
        # the fresh-generation path (_generate_full_script_tracked), so any
        # broad regenerate (Shorten/Extend/"Entire Script" combined with an
        # instruction — i.e. anything except a "pure" full regenerate, which
        # routes through _generate_full_script instead) could reintroduce or
        # rewrite in an unsupported claim with NO check at all. Runs first,
        # same ordering as the fresh-generation path, so the quality gate's
        # own rewrite can't spend its shot on something else while an
        # unsupported claim survives untouched.
        data, _claim_safety_result = _apply_claim_safety_gate(
            data, payload, length_target, payload.target_word_count, payload.content_type
        )
        data = _apply_quality_gate(
            data, payload, length_target, payload.target_word_count, payload.content_type, run_semantic_check=True
        )
    else:
        data = _apply_narrow_quality_gate(data, payload, length_target, payload.target_word_count, payload.content_type)

    return _finish(data, payload, length_target)
