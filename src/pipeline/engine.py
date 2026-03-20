"""Pipeline engine — orchestrates content generation from idea to video."""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.config import AppConfig, OUTPUT_DIR
from src.database import Database
from src.pipeline.models import GeneratedContent, IdeaStatus, Script
from src.providers.base import ScriptProvider, UploadProvider, VisualProvider, VoiceProvider
from src.video.assembler import VideoAssembler


class PipelineEngine:
    def __init__(
        self,
        config: AppConfig,
        db: Database,
        script_provider: ScriptProvider,
        voice_provider: VoiceProvider,
        visual_provider: VisualProvider,
        upload_provider: UploadProvider,
    ):
        self.config = config
        self.db = db
        self.script = script_provider
        self.voice = voice_provider
        self.visual = visual_provider
        self.upload = upload_provider
        self.assembler = VideoAssembler(config.video)

    async def generate(self, idea_id: int, voice_id: str = "") -> GeneratedContent:
        """Run the full pipeline for an idea. Returns GeneratedContent with video_path set."""
        idea = await self.db.get_idea(idea_id)
        if not idea:
            raise ValueError(f"Idea {idea_id} not found")

        content = GeneratedContent(idea_id=idea_id, account_id=idea.account_id)
        work_dir = OUTPUT_DIR / str(idea_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Script
        await self.db.update_idea_status(idea_id, IdeaStatus.SCRIPTING)
        t0 = time.monotonic()
        try:
            content.script = await self.script.generate_script(
                idea=idea.text,
                product_name=self.config.product.name,
                product_tagline=self.config.product.tagline,
                product_description=self.config.product.description,
                product_cta=self.config.product.cta,
                style=self.config.content.style,
                tone=self.config.content.tone,
                duration_seconds=self.config.content.duration_seconds,
                language=self.config.content.language,
            )
            await self.db.log_stage(idea_id, "script", "ok", int((time.monotonic() - t0) * 1000))
            await self.db.update_idea_status(
                idea_id, IdeaStatus.VOICING, script_json=json.dumps({
                    "hook": content.script.hook,
                    "body": content.script.body,
                    "cta": content.script.cta,
                    "title": content.script.title,
                })
            )
        except Exception as e:
            await self.db.log_stage(idea_id, "script", "error", error=str(e))
            await self.db.update_idea_status(idea_id, IdeaStatus.FAILED, error_message=str(e))
            raise

        # Stage 2: Voice
        t0 = time.monotonic()
        try:
            content.voice_path = await self.voice.generate_voice(
                text=content.script.full_text,
                output_path=work_dir / "voice.mp3",
                voice_id=voice_id,
            )
            await self.db.log_stage(idea_id, "voice", "ok", int((time.monotonic() - t0) * 1000))
        except Exception as e:
            await self.db.log_stage(idea_id, "voice", "error", error=str(e))
            await self.db.update_idea_status(idea_id, IdeaStatus.FAILED, error_message=str(e))
            raise

        # Stage 3: Visuals
        await self.db.update_idea_status(idea_id, IdeaStatus.VISUALS)
        t0 = time.monotonic()
        try:
            keywords = content.script.hashtags[:5] or idea.text.split()[:5]
            content.visual_paths = await self.visual.get_visuals(
                keywords=keywords,
                count=5,
                output_dir=work_dir / "visuals",
            )
            await self.db.log_stage(idea_id, "visuals", "ok", int((time.monotonic() - t0) * 1000))
        except Exception as e:
            await self.db.log_stage(idea_id, "visuals", "error", error=str(e))
            # Non-fatal: we can use color background
            content.visual_paths = []

        # Stage 4: Assembly
        await self.db.update_idea_status(idea_id, IdeaStatus.ASSEMBLING)
        t0 = time.monotonic()
        try:
            content.video_path = await self.assembler.assemble(
                audio_path=content.voice_path,
                visual_paths=content.visual_paths,
                output_path=work_dir / "final.mp4",
                subtitle_text=content.script.full_text,
            )
            await self.db.log_stage(idea_id, "assembly", "ok", int((time.monotonic() - t0) * 1000))
            await self.db.update_idea_status(
                idea_id, IdeaStatus.REVIEW, video_path=str(content.video_path)
            )
        except Exception as e:
            await self.db.log_stage(idea_id, "assembly", "error", error=str(e))
            await self.db.update_idea_status(idea_id, IdeaStatus.FAILED, error_message=str(e))
            raise

        return content

    async def publish(self, idea_id: int, content: GeneratedContent, account=None) -> str:
        """Upload approved video to platform."""
        await self.db.update_idea_status(idea_id, IdeaStatus.UPLOADING)
        try:
            url = await self.upload.upload(
                video_path=content.video_path,
                title=content.script.title,
                description=content.script.description,
                tags=content.script.hashtags,
                account=account,
            )
            await self.db.update_idea_status(
                idea_id, IdeaStatus.PUBLISHED, published_url=url
            )
            content.published_url = url
            return url
        except Exception as e:
            await self.db.update_idea_status(idea_id, IdeaStatus.FAILED, error_message=str(e))
            raise
