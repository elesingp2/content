"""Telegram bot handlers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import AppConfig
from src.database import Database
from src.pipeline.engine import PipelineEngine
from src.pipeline.models import GeneratedContent, IdeaStatus
from src.bot.keyboards import review_keyboard

logger = logging.getLogger(__name__)

# In-memory cache for generated content awaiting review
_pending_review: dict[int, GeneratedContent] = {}


def is_admin(config: AppConfig):
    """Decorator-like check for admin access."""
    def check(user_id: int) -> bool:
        return not config.settings.admin_ids or user_id in config.settings.admin_ids
    return check


def setup_handlers(app: Application, config: AppConfig, db: Database, engine: PipelineEngine):
    """Register all bot handlers."""
    admin_check = is_admin(config)

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        await update.message.reply_text(
            "🎬 AI Content Farm\n\n"
            "Commands:\n"
            "/newidea <text> — add idea\n"
            "/ideas — list queued ideas\n"
            "/generate <id> — generate video\n"
            "/accounts — list accounts\n"
            "/status — pipeline status"
        )

    async def cmd_newidea(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        text = " ".join(ctx.args) if ctx.args else ""
        if not text:
            await update.message.reply_text("Usage: /newidea <your idea text>")
            return
        # Default account_id=1, can be extended with /newidea @account_name idea
        account_id = 1
        idea_id = await db.add_idea(text, account_id=account_id)
        await update.message.reply_text(f"✅ Idea #{idea_id} added:\n{text}")

    async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        ideas = await db.get_ideas(status=IdeaStatus.QUEUED)
        if not ideas:
            await update.message.reply_text("No ideas in queue.")
            return
        lines = [f"#{i.id} — {i.text[:60]}" for i in ideas[:20]]
        await update.message.reply_text("📋 Queued ideas:\n\n" + "\n".join(lines))

    async def cmd_generate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /generate <idea_id>")
            return
        try:
            idea_id = int(ctx.args[0])
        except ValueError:
            await update.message.reply_text("Invalid idea ID.")
            return

        idea = await db.get_idea(idea_id)
        if not idea:
            await update.message.reply_text(f"Idea #{idea_id} not found.")
            return

        msg = await update.message.reply_text(f"⏳ Generating video for idea #{idea_id}...")

        try:
            content = await engine.generate(idea_id)
            _pending_review[idea_id] = content

            # Send video preview for review
            if content.video_path and content.video_path.exists():
                script_preview = (
                    f"📝 Script:\n"
                    f"Hook: {content.script.hook}\n\n"
                    f"Body: {content.script.body}\n\n"
                    f"CTA: {content.script.cta}\n\n"
                    f"Title: {content.script.title}\n"
                    f"Tags: {', '.join(content.script.hashtags)}"
                )
                await update.message.reply_text(script_preview)

                with open(content.video_path, "rb") as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"🎬 Preview for idea #{idea_id}",
                        reply_markup=review_keyboard(idea_id),
                    )
            else:
                await msg.edit_text(f"❌ Video generation failed for idea #{idea_id}")
        except Exception as e:
            logger.exception(f"Generation failed for idea #{idea_id}")
            await msg.edit_text(f"❌ Error: {e}")

    async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        statuses = {}
        for status in IdeaStatus:
            ideas = await db.get_ideas(status=status)
            if ideas:
                statuses[status.value] = len(ideas)
        if not statuses:
            await update.message.reply_text("No ideas in the system.")
            return
        lines = [f"{s}: {c}" for s, c in statuses.items()]
        await update.message.reply_text("📊 Status:\n" + "\n".join(lines))

    async def cmd_accounts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        accounts = await db.get_accounts()
        if not accounts:
            await update.message.reply_text("No accounts configured.\nUse /addaccount <name> <platform>")
            return
        lines = [f"#{a.id} {a.name} ({a.platform}) {'✅' if a.is_active else '❌'}" for a in accounts]
        await update.message.reply_text("👥 Accounts:\n" + "\n".join(lines))

    async def cmd_addaccount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not admin_check(update.effective_user.id):
            return
        if len(ctx.args) < 2:
            await update.message.reply_text("Usage: /addaccount <name> <platform>\nPlatforms: youtube, tiktok, reels")
            return
        name, platform = ctx.args[0], ctx.args[1]
        acc_id = await db.create_account(name, platform, {})
        await update.message.reply_text(f"✅ Account #{acc_id} '{name}' ({platform}) created.")

    async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        action, idea_id_str = data.split(":", 1)
        idea_id = int(idea_id_str)

        if action == "approve":
            content = _pending_review.get(idea_id)
            if not content:
                await query.edit_message_caption("❌ Content not found. Regenerate first.")
                return
            await query.edit_message_caption("⏳ Publishing...")
            try:
                url = await engine.publish(idea_id, content)
                await query.edit_message_caption(f"✅ Published!\n{url}")
                _pending_review.pop(idea_id, None)
            except Exception as e:
                await query.edit_message_caption(f"❌ Upload failed: {e}")

        elif action == "reject":
            await db.update_idea_status(idea_id, IdeaStatus.REJECTED)
            _pending_review.pop(idea_id, None)
            await query.edit_message_caption("❌ Rejected. Idea returned to pool.")

        elif action == "regen":
            await query.edit_message_caption("⏳ Regenerating...")
            try:
                content = await engine.generate(idea_id)
                _pending_review[idea_id] = content
                if content.video_path and content.video_path.exists():
                    with open(content.video_path, "rb") as f:
                        await query.message.reply_video(
                            video=f,
                            caption=f"🎬 New version for idea #{idea_id}",
                            reply_markup=review_keyboard(idea_id),
                        )
            except Exception as e:
                await query.message.reply_text(f"❌ Regen failed: {e}")

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("newidea", cmd_newidea))
    app.add_handler(CommandHandler("ideas", cmd_ideas))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("addaccount", cmd_addaccount))
    app.add_handler(CallbackQueryHandler(callback_handler))
