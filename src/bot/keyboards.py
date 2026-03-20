"""Inline keyboards for Telegram bot."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def review_keyboard(idea_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publish", callback_data=f"approve:{idea_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{idea_id}"),
        ],
        [
            InlineKeyboardButton("🔄 Regenerate", callback_data=f"regen:{idea_id}"),
        ],
    ])


def account_select_keyboard(accounts: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"acc:{acc_id}")]
        for acc_id, name in accounts
    ]
    return InlineKeyboardMarkup(buttons)
