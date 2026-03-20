"""YouTube Shorts uploader via YouTube Data API v3."""

from __future__ import annotations

import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.pipeline.models import Account
from src.providers.base import UploadProvider

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader(UploadProvider):
    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        category_id: str = "22",
        privacy_status: str = "private",
        default_tags: list[str] | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.category_id = category_id
        self.privacy_status = privacy_status
        self.default_tags = default_tags or []

    def _get_credentials(self, account: Account | None = None) -> Credentials:
        """Load credentials from account or initiate OAuth flow."""
        if account and account.credentials_json:
            creds_data = json.loads(account.credentials_json)
            if "token" in creds_data:
                return Credentials.from_authorized_user_info(creds_data)

        # Fallback: OAuth flow (for initial setup)
        client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        return flow.run_local_server(port=0)

    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        account: Account | None = None,
    ) -> str:
        import asyncio

        return await asyncio.to_thread(
            self._upload_sync, video_path, title, description, tags, account
        )

    def _upload_sync(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        account: Account | None = None,
    ) -> str:
        credentials = self._get_credentials(account)
        youtube = build("youtube", "v3", credentials=credentials)

        all_tags = list(set(self.default_tags + tags))

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": all_tags,
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)

        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response["id"]
        return f"https://youtube.com/shorts/{video_id}"
