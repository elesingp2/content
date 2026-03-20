"""Abstract base interfaces for all providers.

Each provider type has a simple interface. Swap implementations
by changing `providers.*` in config.yaml.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.pipeline.models import Account, Script


class ScriptProvider(ABC):
    """Generates a video script from an idea."""

    @abstractmethod
    async def generate_script(
        self,
        idea: str,
        product_name: str,
        product_tagline: str,
        product_description: str,
        product_cta: str,
        style: str = "engaging",
        tone: str = "confident",
        duration_seconds: int = 30,
        language: str = "en",
    ) -> Script:
        ...


class VoiceProvider(ABC):
    """Converts text to speech audio file."""

    @abstractmethod
    async def generate_voice(
        self,
        text: str,
        output_path: Path,
        voice_id: str = "",
    ) -> Path:
        """Returns path to generated audio file."""
        ...


class VisualProvider(ABC):
    """Fetches or generates visuals (stock footage, images)."""

    @abstractmethod
    async def get_visuals(
        self,
        keywords: list[str],
        count: int = 5,
        output_dir: Path | None = None,
        orientation: str = "portrait",
    ) -> list[Path]:
        """Returns paths to downloaded visual files."""
        ...


class UploadProvider(ABC):
    """Uploads video to a platform."""

    @abstractmethod
    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        account: Account | None = None,
    ) -> str:
        """Returns the published URL."""
        ...
