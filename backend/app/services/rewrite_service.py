from app.config import settings
from app.models.product import RewriteDirective, RewriteLineInput, RewriteLineResult, ScriptLanguage
from app.services.gemini_utils import call_gemini_with_retry, generate_text

_DIRECTIVE_GUIDANCE: dict[RewriteDirective, str] = {
    RewriteDirective.improve: "Tighten and sharpen this line — better rhythm, clearer meaning, "
    "no wasted words. Keep the same intent and claims, just make it read better.",
    RewriteDirective.make_viral: "Rewrite this line to be more scroll-stopping and shareable — "
    "punchier, more surprising, more likely to make someone stop scrolling. Keep it truthful "
    "to the original meaning, don't add claims that weren't there.",
    RewriteDirective.make_emotional: "Rewrite this line to hit harder emotionally — lean into "
    "the feeling underneath it (relief, pride, hope, worry, etc.) without becoming melodramatic "
    "or adding claims that weren't in the original.",
    RewriteDirective.increase_conversion: "Rewrite this line to be more persuasive and "
    "action-driving, as if written by a direct-response copywriter — sharper benefit framing, "
    "more urgency where appropriate. Do not add guarantees or claims the original didn't make.",
    RewriteDirective.rewrite: "Write a fresh alternative take on this line — same core idea and "
    "intent, different words and phrasing than the original.",
    RewriteDirective.make_shorter: "Cut this line down substantially — keep only the essential "
    "words, same core meaning, noticeably fewer words than the original.",
    RewriteDirective.make_longer: "Expand this line with more substance and detail — same core "
    "idea, but noticeably more words, without padding or repeating itself.",
    RewriteDirective.more_cinematic: "Rewrite this line with a more cinematic, visual quality — "
    "the kind of line that conjures a strong mental image, as if narrating a scene.",
    RewriteDirective.more_conversational: "Rewrite this line to sound like natural, casual spoken "
    "conversation — the way a real person would actually say it out loud, not written copy.",
    RewriteDirective.more_scientific: "Rewrite this line with a more credible, evidence-grounded "
    "register — precise, educational phrasing, without inventing any new facts or figures.",
    RewriteDirective.more_persuasive: "Rewrite this line to be more compelling and convincing — "
    "sharper benefit framing and urgency, without adding claims the original didn't make.",
    RewriteDirective.simplify: "Rewrite this line in plainer, simpler language — shorter words, "
    "no jargon, easy for anyone to understand instantly.",
    RewriteDirective.professional_tone: "Rewrite this line in a more polished, professional "
    "register — credible and composed, without becoming stiff or corporate-sounding.",
    RewriteDirective.funny: "Rewrite this line with a light, funny, self-aware tone — genuinely "
    "amusing, not just adding a random joke, and still true to the original meaning.",
    RewriteDirective.fear_based: "Rewrite this line to lean into the fear/stakes of NOT acting — "
    "what's lost or at risk — without becoming manipulative or making claims the original didn't.",
    RewriteDirective.doctor_style: "Rewrite this line as a doctor/medical expert would say it — "
    "calm, credible, clinical-but-warm authority, first person if natural.",
    RewriteDirective.storytelling_style: "Rewrite this line as part of a personal narrative being "
    "told — first-person, reflective, like someone recounting their own experience.",
    RewriteDirective.ugc_style: "Rewrite this line the way a real person would say it in a casual "
    "selfie-style UGC video — unpolished, authentic, off-the-cuff phrasing.",
    RewriteDirective.podcast_style: "Rewrite this line the way it would sound in a relaxed podcast "
    "conversation — thinking-out-loud, conversational asides, unhurried.",
    RewriteDirective.meta_glasses_pov: "Rewrite this line for a first-person POV format (like Meta "
    "Glasses footage) — as if the speaker is narrating their own point of view in the moment.",
}

_SYSTEM_PROMPT = """You are a script-line editor for a short-form video ad content factory.
You rewrite exactly ONE line of dialogue/on-screen text at a time, according to a given
directive. You MUST preserve the line's original meaning, claims, and any product facts it
contains — you are a rewrite pass, not a new-claim generator, and this feeds a
compliance-sensitive pipeline. Never introduce a claim, statistic, or promise that wasn't
already in the original line.

If a maximum character count is given, the rewritten line must fit within it.

Return ONLY the rewritten line of text — no prose, no quotes, no markdown, no explanation."""

_TRANSLATE_SYSTEM_PROMPT = """You are a script-line translator for a short-form video ad content
factory. You translate exactly ONE line of dialogue/on-screen text into the requested language,
preserving its exact meaning and any product claims/figures — never add, remove, or soften claims.
Keep it natural, spoken-register phrasing in the target language, not a stiff literal translation.
Preserve any **double-asterisk** bold markers around the same key words/concepts they wrapped in
the original.

Return ONLY the translated line — no prose, no quotes, no markdown fences, no explanation."""

_LANGUAGE_NAME = {"english": "English", "hindi": "Hindi (Devanagari script)", "hinglish": "Hinglish (Hindi sentence structure in Roman/Latin script)"}


def _build_user_message(payload: RewriteLineInput) -> str:
    char_limit = f"\nMax characters: {payload.max_chars}" if payload.max_chars else ""

    if payload.directive == RewriteDirective.translate:
        target = _LANGUAGE_NAME.get((payload.target_language or ScriptLanguage.english).value, "English")
        return f"Translate this line into {target}:\n\n{payload.text}{char_limit}"

    guidance = _DIRECTIVE_GUIDANCE[payload.directive]
    return f"Directive: {guidance}\n\nOriginal line:\n{payload.text}{char_limit}"


def rewrite_line(payload: RewriteLineInput) -> RewriteLineResult:
    """AI quick-action — rewrite (or translate) one script line's text per a directive, nothing else."""

    system = _TRANSLATE_SYSTEM_PROMPT if payload.directive == RewriteDirective.translate else _SYSTEM_PROMPT

    text = call_gemini_with_retry(
        lambda: generate_text(
            system_instruction=system,
            contents=[_build_user_message(payload)],
            model=settings.gemini_text_model,
            max_output_tokens=512,
        ),
        label="rewrite_line",
    )

    rewritten = text.strip().strip('"')
    return RewriteLineResult(text=rewritten)
