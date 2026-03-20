"""Pexels stock footage/image provider."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from src.providers.base import VisualProvider


class PexelsVisualProvider(VisualProvider):
    BASE_URL = "https://api.pexels.com"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_visuals(
        self,
        keywords: list[str],
        count: int = 5,
        output_dir: Path | None = None,
        orientation: str = "portrait",
    ) -> list[Path]:
        if output_dir is None:
            output_dir = Path("output/visuals")
        output_dir.mkdir(parents=True, exist_ok=True)

        query = " ".join(keywords[:3])
        headers = {"Authorization": self.api_key}

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            # Try video first, fallback to photos
            paths = await self._fetch_videos(client, query, count, output_dir, orientation)
            if not paths:
                paths = await self._fetch_photos(client, query, count, output_dir, orientation)

        return paths

    async def _fetch_videos(
        self,
        client: httpx.AsyncClient,
        query: str,
        count: int,
        output_dir: Path,
        orientation: str,
    ) -> list[Path]:
        resp = await client.get(
            f"{self.BASE_URL}/videos/search",
            params={"query": query, "per_page": count, "orientation": orientation},
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        videos = data.get("videos", [])
        paths = []

        for i, video in enumerate(videos[:count]):
            # Get the HD or SD video file
            video_files = video.get("video_files", [])
            # Prefer HD portrait
            chosen = None
            for vf in video_files:
                if vf.get("quality") == "hd" and vf.get("height", 0) > vf.get("width", 0):
                    chosen = vf
                    break
            if not chosen and video_files:
                chosen = video_files[0]
            if not chosen:
                continue

            url = chosen["link"]
            ext = url.split("?")[0].rsplit(".", 1)[-1] if "." in url.split("?")[0] else "mp4"
            file_path = output_dir / f"visual_{i}.{ext}"

            dl_resp = await client.get(url, follow_redirects=True)
            if dl_resp.status_code == 200:
                file_path.write_bytes(dl_resp.content)
                paths.append(file_path)

        return paths

    async def _fetch_photos(
        self,
        client: httpx.AsyncClient,
        query: str,
        count: int,
        output_dir: Path,
        orientation: str,
    ) -> list[Path]:
        resp = await client.get(
            f"{self.BASE_URL}/v1/search",
            params={"query": query, "per_page": count, "orientation": orientation},
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        photos = data.get("photos", [])
        paths = []

        for i, photo in enumerate(photos[:count]):
            url = photo.get("src", {}).get("large2x", photo.get("src", {}).get("original", ""))
            if not url:
                continue

            file_path = output_dir / f"photo_{i}.jpg"
            dl_resp = await client.get(url, follow_redirects=True)
            if dl_resp.status_code == 200:
                file_path.write_bytes(dl_resp.content)
                paths.append(file_path)

        return paths
