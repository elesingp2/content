"""Google TTS (gTTS) provider — free, no API key needed."""

from __future__ import annotations

import asyncio
from pathlib import Path

from gtts import gTTS

from src.providers.base import VoiceProvider


class GoogleTTSVoiceProvider(VoiceProvider):
    def __init__(self, language: str = "en", slow: bool = False):
        self.language = language
        self.slow = slow

    async def generate_voice(
        self,
        text: str,
        output_path: Path,
        voice_id: str = "",
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lang = voice_id or self.language

        # gTTS is synchronous, run in thread
        def _generate():
            tts = gTTS(text=text, lang=lang, slow=self.slow)
            tts.save(str(output_path))

        await asyncio.to_thread(_generate)
        return output_path
