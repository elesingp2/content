"""Data models for the content pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class IdeaStatus(str, Enum):
    QUEUED = "queued"
    SCRIPTING = "scripting"
    VOICING = "voicing"
    VISUALS = "visuals"
    ASSEMBLING = "assembling"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class Idea:
    id: int | None = None
    account_id: int = 1  # Multi-account support
    text: str = ""
    status: IdeaStatus = IdeaStatus.QUEUED
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Script:
    idea_id: int = 0
    hook: str = ""  # First 3 seconds — attention grabber
    body: str = ""  # Main content
    cta: str = ""  # Call to action (product plug)
    full_text: str = ""  # Combined for TTS
    hashtags: list[str] = field(default_factory=list)
    title: str = ""  # Video title for upload
    description: str = ""  # Video description


@dataclass
class GeneratedContent:
    """Result of the full pipeline for one idea."""

    idea_id: int = 0
    account_id: int = 1
    script: Script | None = None
    voice_path: Path | None = None  # Path to audio file
    visual_paths: list[Path] = field(default_factory=list)  # Stock footage/images
    video_path: Path | None = None  # Final assembled video
    subtitle_path: Path | None = None  # SRT file
    duration_seconds: float = 0.0
    published_url: str = ""


@dataclass
class Account:
    """Represents a social media account for multi-account support."""

    id: int | None = None
    name: str = ""  # Display name
    platform: str = ""  # youtube | tiktok | reels
    credentials_json: str = ""  # Encrypted JSON with tokens/keys
    is_active: bool = True
    created_at: str = ""

    # Per-account overrides
    voice_id: str = ""  # Override default voice
    content_language: str = ""  # Override default language
    style: str = ""  # Override default style
