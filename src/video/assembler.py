"""Video assembler — combines audio, visuals, and subtitles into a vertical video."""

from __future__ import annotations

import asyncio
import math
import subprocess
import tempfile
from pathlib import Path

from src.config import VideoConfig


class VideoAssembler:
    """Assembles final vertical video from components using FFmpeg."""

    def __init__(self, config: VideoConfig):
        self.config = config

    async def assemble(
        self,
        audio_path: Path,
        visual_paths: list[Path],
        output_path: Path,
        subtitle_text: str = "",
    ) -> Path:
        """Assemble video from audio + visuals + subtitles.

        Strategy:
        - If we have video clips: concatenate them, loop if needed to match audio duration
        - If we have images: create slideshow with Ken Burns effect
        - Overlay subtitles word-by-word (animated)
        - Mix with audio track
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_duration = await self._get_duration(audio_path)

        # Determine if visuals are videos or images
        video_exts = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
        has_videos = any(p.suffix.lower() in video_exts for p in visual_paths)

        if has_videos:
            video_bg = await self._create_video_background(visual_paths, audio_duration)
        else:
            video_bg = await self._create_image_slideshow(visual_paths, audio_duration)

        # Create subtitle file if text provided
        srt_path = None
        if subtitle_text:
            srt_path = output_path.with_suffix(".srt")
            self._generate_srt(subtitle_text, audio_duration, srt_path)

        # Final assembly: background + audio + subtitles
        await self._final_compose(video_bg, audio_path, srt_path, output_path)

        # Cleanup temp files
        if video_bg != output_path and video_bg.exists():
            video_bg.unlink()
        if srt_path and srt_path.exists():
            srt_path.unlink()

        return output_path

    async def _get_duration(self, audio_path: Path) -> float:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())

    async def _create_video_background(
        self, visual_paths: list[Path], target_duration: float
    ) -> Path:
        """Concatenate video clips and loop/trim to match audio duration."""
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        w, h = self.config.width, self.config.height

        # Filter to only video files
        video_exts = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
        videos = [p for p in visual_paths if p.suffix.lower() in video_exts]
        if not videos:
            return await self._create_color_background(target_duration)

        # Create concat file
        concat_path = Path(tempfile.mktemp(suffix=".txt"))
        with open(concat_path, "w") as f:
            for v in videos:
                f.write(f"file '{v}'\n")

        # Concatenate, scale to vertical, and trim to target duration
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-stream_loop", "-1",  # Loop if too short
            "-t", str(target_duration),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
            "-r", str(self.config.fps),
            "-an",  # No audio from clips
            "-c:v", "libx264", "-preset", "fast",
            str(tmp),
        ]

        await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, check=True
        )
        concat_path.unlink()
        return tmp

    async def _create_image_slideshow(
        self, image_paths: list[Path], target_duration: float
    ) -> Path:
        """Create a slideshow from images with crossfade transitions."""
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        w, h = self.config.width, self.config.height

        if not image_paths:
            return await self._create_color_background(target_duration)

        duration_per_image = target_duration / len(image_paths)

        # Build filter complex for slideshow with zoom effect
        inputs = []
        filter_parts = []
        for i, img in enumerate(image_paths):
            inputs.extend(["-loop", "1", "-t", str(duration_per_image), "-i", str(img)])
            # Scale and add slight zoom (Ken Burns)
            zoom = f"zoompan=z='min(zoom+0.001,1.3)':d={int(duration_per_image * self.config.fps)}:s={w}x{h}:fps={self.config.fps}"
            filter_parts.append(f"[{i}]{zoom}[v{i}]")

        # Concatenate all
        concat_inputs = "".join(f"[v{i}]" for i in range(len(image_paths)))
        filter_parts.append(f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[out]")

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264", "-preset", "fast",
            "-t", str(target_duration),
            str(tmp),
        ]

        await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, check=True
        )
        return tmp

    async def _create_color_background(self, duration: float) -> Path:
        """Fallback: solid dark background."""
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        w, h = self.config.width, self.config.height

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=0x1a1a2e:s={w}x{h}:d={duration}:r={self.config.fps}",
            "-c:v", "libx264", "-preset", "fast",
            str(tmp),
        ]
        await asyncio.to_thread(subprocess.run, cmd, capture_output=True, check=True)
        return tmp

    def _generate_srt(self, text: str, duration: float, output_path: Path):
        """Generate SRT subtitle file with word-by-word timing."""
        words = text.split()
        if not words:
            return

        time_per_word = duration / len(words)
        # Group words into chunks of 4-6 for readability
        chunk_size = 5
        chunks = [words[i : i + chunk_size] for i in range(0, len(words), chunk_size)]

        lines = []
        for i, chunk in enumerate(chunks):
            start = i * chunk_size * time_per_word
            end = min((i * chunk_size + len(chunk)) * time_per_word, duration)
            start_str = self._format_srt_time(start)
            end_str = self._format_srt_time(end)
            text_line = " ".join(chunk)
            lines.append(f"{i + 1}\n{start_str} --> {end_str}\n{text_line}\n")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    async def _final_compose(
        self,
        video_path: Path,
        audio_path: Path,
        srt_path: Path | None,
        output_path: Path,
    ):
        """Compose final video: background + audio + optional subtitles."""
        font_size = self.config.font_size
        font_color = self.config.font_color

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
        ]

        if srt_path and srt_path.exists():
            # Burn subtitles into video
            sub_style = (
                f"FontSize={font_size},"
                f"PrimaryColour=&H00FFFFFF,"
                f"BackColour=&H80000000,"
                f"BorderStyle=4,"
                f"Outline=0,"
                f"Shadow=0,"
                f"MarginV=80,"
                f"Alignment=2"
            )
            cmd.extend([
                "-vf", f"subtitles={srt_path}:force_style='{sub_style}'",
            ])

        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ])

        await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, check=True
        )
