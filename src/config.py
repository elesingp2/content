"""Application configuration with environment and YAML config support."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
DB_PATH = ROOT_DIR / "db.sqlite"
OUTPUT_DIR = ROOT_DIR / "output"
ASSETS_DIR = ROOT_DIR / "assets"


class Settings(BaseSettings):
    """Environment-based settings (secrets)."""

    telegram_bot_token: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    pexels_api_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    admin_user_ids: str = ""  # Comma-separated

    model_config = {"env_file": str(ROOT_DIR / ".env"), "env_file_encoding": "utf-8"}

    @property
    def admin_ids(self) -> list[int]:
        if not self.admin_user_ids:
            return []
        return [int(x.strip()) for x in self.admin_user_ids.split(",") if x.strip()]


class ProductConfig:
    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.tagline: str = data.get("tagline", "")
        self.description: str = data.get("description", "")
        self.url: str = data.get("url", "")
        self.cta: str = data.get("cta", "")


class ContentConfig:
    def __init__(self, data: dict):
        self.language: str = data.get("language", "en")
        self.duration_seconds: int = data.get("duration_seconds", 30)
        self.style: str = data.get("style", "engaging")
        self.tone: str = data.get("tone", "confident")


class VideoConfig:
    def __init__(self, data: dict):
        self.width: int = data.get("width", 1080)
        self.height: int = data.get("height", 1920)
        self.fps: int = data.get("fps", 30)
        self.font_size: int = data.get("font_size", 60)
        self.font_color: str = data.get("font_color", "white")
        self.subtitle_bg_color: str = data.get("subtitle_bg_color", "black")
        self.subtitle_bg_opacity: float = data.get("subtitle_bg_opacity", 0.7)


class AppConfig:
    """Full application config from YAML + env."""

    def __init__(self):
        self.settings = Settings()
        self._raw = self._load_yaml()
        self.product = ProductConfig(self._raw.get("product", {}))
        self.content = ContentConfig(self._raw.get("content", {}))
        self.video = VideoConfig(self._raw.get("video", {}))
        self.providers_config = self._raw.get("providers", {})
        self.voice_config = self._raw.get("voice", {})
        self.youtube_config = self._raw.get("youtube", {})

    def _load_yaml(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return yaml.safe_load(f) or {}
        return {}

    @property
    def script_provider(self) -> str:
        return self.providers_config.get("script", "claude")

    @property
    def voice_provider(self) -> str:
        return self.providers_config.get("voice", "elevenlabs")

    @property
    def visual_provider(self) -> str:
        return self.providers_config.get("visual", "pexels")

    @property
    def upload_provider(self) -> str:
        return self.providers_config.get("upload", "youtube")
