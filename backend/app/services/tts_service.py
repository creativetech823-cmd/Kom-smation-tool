import uuid
from pathlib import Path

from anthropic import Anthropic
from gtts import gTTS
from mutagen.mp3 import MP3

from app.config import settings
from app.models.product import VoiceoverLine, VoiceoverResult

_client = Anthropic(api_key=settings.anthropic_api_key)

_TRANSLATE_SYSTEM_PROMPT = """You translate short video-ad script lines from English into natural,
conversational spoken Hindi (Devanagari script) — the way a voiceover artist would actually say it,
not a stiff literal translation. Keep brand/product names unchanged. Return ONLY the Hindi
translation text, nothing else — no quotes, no explanation, no romanization."""


def _translate_to_hindi(text: str) -> str:
    response = _client.messages.create(
        model=settings.claude_compliance_model,
        max_tokens=256,
        system=_TRANSLATE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    text_block = next(b for b in response.content if b.type == "text")
    return text_block.text.strip().strip('"')


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
