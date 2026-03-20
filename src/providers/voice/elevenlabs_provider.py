"""ElevenLabs TTS provider."""

from __future__ import annotations

from pathlib import Path

from elevenlabs import AsyncElevenLabs

from src.providers.base import VoiceProvider

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel


class ElevenLabsVoiceProvider(VoiceProvider):
    def __init__(self, api_key: str, default_voice_id: str = DEFAULT_VOICE_ID):
        self.client = AsyncElevenLabs(api_key=api_key)
        self.default_voice_id = default_voice_id

    async def generate_voice(
        self,
        text: str,
        output_path: Path,
        voice_id: str = "",
    ) -> Path:
        vid = voice_id or self.default_voice_id
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_generator = await self.client.text_to_speech.convert(
            voice_id=vid,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        with open(output_path, "wb") as f:
            async for chunk in audio_generator:
                f.write(chunk)

        return output_path
