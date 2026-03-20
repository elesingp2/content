"""Entry point for AI Content Farm."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

from src.config import AppConfig
from src.database import Database
from src.providers.factory import (
    get_script_provider,
    get_upload_provider,
    get_visual_provider,
    get_voice_provider,
)
from src.pipeline.engine import PipelineEngine
from src.bot.handlers import setup_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def init_db() -> Database:
    db = Database()
    await db.connect()
    return db


def main():
    config = AppConfig()

    if not config.settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    # Build Telegram app
    app = Application.builder().token(config.settings.telegram_bot_token).build()

    # Init providers
    script_prov = get_script_provider(config)
    voice_prov = get_voice_provider(config)
    visual_prov = get_visual_provider(config)
    upload_prov = get_upload_provider(config)

    # We need to init DB before running, use post_init hook
    async def post_init(application: Application):
        db = await init_db()
        application.bot_data["db"] = db
        engine = PipelineEngine(config, db, script_prov, voice_prov, visual_prov, upload_prov)
        application.bot_data["engine"] = engine
        setup_handlers(application, config, db, engine)
        logger.info("Bot initialized, providers: script=%s voice=%s visual=%s upload=%s",
                     config.script_provider, config.voice_provider,
                     config.visual_provider, config.upload_provider)

    async def post_shutdown(application: Application):
        db = application.bot_data.get("db")
        if db:
            await db.close()

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    logger.info("Starting AI Content Farm bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
