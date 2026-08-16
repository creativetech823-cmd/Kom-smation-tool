import uuid
from pathlib import Path

from gtts import gTTS
from mutagen.mp3 import MP3

from app.config import settings
from app.models.product import VoiceoverLine, VoiceoverResult
from app.services.openrouter_utils import call_openrouter_with_retry, generate_text

_TRANSLATE_SYSTEM_PROMPT = """You convert a short video-ad script line into natural, conversational
spoken Hindi (Devanagari script) — the way a voiceover artist would actually say it, not a stiff
literal translation. The input may already be English, Hindi, or Hinglish (Roman-script Hindi) —
if it's already Hindi/Hinglish, normalize it into clean Devanagari rather than passing through
informal Roman spelling; if it's English, translate it. Keep brand/product names unchanged. Return
ONLY the Hindi text, nothing else — no quotes, no explanation, no romanization, no markdown."""


def _translate_to_hindi(text: str) -> str:
    # Script text may contain **bold** markdown emphasis (Step 3 Hinglish/Hindi
    # copy) — strip it before translation so the ** characters don't confuse
    # the model or leak into the spoken output.
    plain_text = text.replace("**", "")
    result = call_openrouter_with_retry(
        lambda: generate_text(
            system_instruction=_TRANSLATE_SYSTEM_PROMPT,
            contents=[plain_text],
            model=settings.openrouter_text_model,
            max_output_tokens=512,
        ),
        label="translate_to_hindi",
    )
    return result.strip().strip('"').replace("**", "")


def _audio_dir() -> Path:
    d = Path(settings.audio_output_dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def synthesize_voiceover(line: VoiceoverLine) -> VoiceoverResult:
    """Stage 9 (voiceover) — translate a script line to Hindi and synthesize
    spoken audio for it via gTTS (free, no API key required)."""

    hindi_text = _translate_to_hindi(line.text)

    filename = f"{uuid.uuid4().hex[:12]}.mp3"
    audio_path = _audio_dir() / filename
    gTTS(text=hindi_text, lang="hi").save(str(audio_path))

    duration_seconds = MP3(str(audio_path)).info.length

    return VoiceoverResult(
        line_id=line.line_id,
        hindi_text=hindi_text,
        audio_path=str(audio_path),
        duration_seconds=round(duration_seconds, 2),
    )
