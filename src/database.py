"""SQLite database for ideas, accounts, and generation history."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite

from src.config import DB_PATH
from src.pipeline.models import Account, Idea, IdeaStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'youtube',
    credentials_json TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    voice_id TEXT NOT NULL DEFAULT '',
    content_language TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL DEFAULT 1,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    error_message TEXT NOT NULL DEFAULT '',
    script_json TEXT NOT NULL DEFAULT '{}',
    video_path TEXT NOT NULL DEFAULT '',
    published_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS generation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (idea_id) REFERENCES ideas(id)
);
"""


class Database:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # --- Accounts ---

    async def create_account(self, name: str, platform: str, credentials: dict) -> int:
        cursor = await self._db.execute(
            "INSERT INTO accounts (name, platform, credentials_json) VALUES (?, ?, ?)",
            (name, platform, json.dumps(credentials)),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_accounts(self, active_only: bool = True) -> list[Account]:
        query = "SELECT * FROM accounts"
        if active_only:
            query += " WHERE is_active = 1"
        cursor = await self._db.execute(query)
        rows = await cursor.fetchall()
        return [
            Account(
                id=r["id"],
                name=r["name"],
                platform=r["platform"],
                credentials_json=r["credentials_json"],
                is_active=bool(r["is_active"]),
                voice_id=r["voice_id"],
                content_language=r["content_language"],
                style=r["style"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def get_account(self, account_id: int) -> Account | None:
        cursor = await self._db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        r = await cursor.fetchone()
        if not r:
            return None
        return Account(
            id=r["id"],
            name=r["name"],
            platform=r["platform"],
            credentials_json=r["credentials_json"],
            is_active=bool(r["is_active"]),
            voice_id=r["voice_id"],
            content_language=r["content_language"],
            style=r["style"],
            created_at=r["created_at"],
        )

    # --- Ideas ---

    async def add_idea(self, text: str, account_id: int = 1) -> int:
        cursor = await self._db.execute(
            "INSERT INTO ideas (text, account_id) VALUES (?, ?)",
            (text, account_id),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_idea(self, idea_id: int) -> Idea | None:
        cursor = await self._db.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))
        r = await cursor.fetchone()
        if not r:
            return None
        return Idea(
            id=r["id"],
            account_id=r["account_id"],
            text=r["text"],
            status=IdeaStatus(r["status"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    async def get_ideas(
        self, status: IdeaStatus | None = None, account_id: int | None = None
    ) -> list[Idea]:
        query = "SELECT * FROM ideas WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)
        query += " ORDER BY created_at DESC"
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            Idea(
                id=r["id"],
                account_id=r["account_id"],
                text=r["text"],
                status=IdeaStatus(r["status"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def update_idea_status(
        self,
        idea_id: int,
        status: IdeaStatus,
        error_message: str = "",
        script_json: str = "",
        video_path: str = "",
        published_url: str = "",
    ):
        updates = ["status = ?", "updated_at = datetime('now')"]
        params: list = [status.value]
        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)
        if script_json:
            updates.append("script_json = ?")
            params.append(script_json)
        if video_path:
            updates.append("video_path = ?")
            params.append(video_path)
        if published_url:
            updates.append("published_url = ?")
            params.append(published_url)
        params.append(idea_id)
        await self._db.execute(
            f"UPDATE ideas SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self._db.commit()

    # --- Generation Log ---

    async def log_stage(
        self, idea_id: int, stage: str, status: str, duration_ms: int = 0, error: str = ""
    ):
        await self._db.execute(
            "INSERT INTO generation_log (idea_id, stage, status, duration_ms, error) VALUES (?, ?, ?, ?, ?)",
            (idea_id, stage, status, duration_ms, error),
        )
        await self._db.commit()
