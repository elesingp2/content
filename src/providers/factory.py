"""Provider factory — creates provider instances from config."""

from __future__ import annotations

from src.config import AppConfig
from src.providers.base import ScriptProvider, UploadProvider, VisualProvider, VoiceProvider


def get_script_provider(config: AppConfig) -> ScriptProvider:
    name = config.script_provider
    if name == "claude":
        from src.providers.script.claude import ClaudeScriptProvider

        return ClaudeScriptProvider(api_key=config.settings.anthropic_api_key)
    elif name == "openai":
        from src.providers.script.openai_provider import OpenAIScriptProvider

        return OpenAIScriptProvider(api_key=config.settings.openai_api_key)
    elif name == "openrouter":
        from src.providers.script.openai_provider import OpenAIScriptProvider

        return OpenAIScriptProvider(
            api_key=config.settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            model=config.settings.openrouter_model,
        )
    raise ValueError(f"Unknown script provider: {name}")


def get_voice_provider(config: AppConfig) -> VoiceProvider:
    name = config.voice_provider
    if name == "elevenlabs":
        from src.providers.voice.elevenlabs_provider import ElevenLabsVoiceProvider

        voice_cfg = config.voice_config.get("elevenlabs", {})
        return ElevenLabsVoiceProvider(
            api_key=config.settings.elevenlabs_api_key,
            default_voice_id=voice_cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
        )
    elif name == "google_tts":
        from src.providers.voice.google_tts_provider import GoogleTTSVoiceProvider

        voice_cfg = config.voice_config.get("google_tts", {})
        return GoogleTTSVoiceProvider(
            language=voice_cfg.get("language", "en"),
            slow=voice_cfg.get("slow", False),
        )
    raise ValueError(f"Unknown voice provider: {name}")


def get_visual_provider(config: AppConfig) -> VisualProvider:
    name = config.visual_provider
    if name == "pexels":
        from src.providers.visual.pexels import PexelsVisualProvider

        return PexelsVisualProvider(api_key=config.settings.pexels_api_key)
    raise ValueError(f"Unknown visual provider: {name}")


def get_upload_provider(config: AppConfig, platform: str | None = None) -> UploadProvider | None:
    name = platform or config.upload_provider
    if name == "none":
        return None
    if name == "youtube":
        from src.providers.upload.youtube import YouTubeUploader

        yt_cfg = config.youtube_config
        return YouTubeUploader(
            client_id=config.settings.youtube_client_id,
            client_secret=config.settings.youtube_client_secret,
            category_id=yt_cfg.get("category_id", "22"),
            privacy_status=yt_cfg.get("privacy_status", "private"),
            default_tags=yt_cfg.get("default_tags", []),
        )
    raise ValueError(f"Unknown upload provider: {name}")
