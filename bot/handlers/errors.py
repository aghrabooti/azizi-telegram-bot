"""Global error handler — a crash must never leave the user without feedback."""

from __future__ import annotations

import html
import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.config import content
from bot.config.settings import settings
from bot.services.analytics import KIND_ERROR, track
from bot.utils.logging import redact

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    logger.error("unhandled error: %s", error, exc_info=error)

    if isinstance(update, Update):
        user = update.effective_user
        track(user.id if user else None, KIND_ERROR, type(error).__name__)
        try:
            if update.callback_query is not None:
                await update.callback_query.answer(
                    content.text("error.generic"), show_alert=True
                )
            elif update.effective_message is not None:
                await update.effective_message.reply_text(content.text("error.generic"))
        except TelegramError:
            pass

    # Notify the first admin with a short, token-free traceback.
    if not settings.admin_ids:
        return
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    snippet = html.escape(redact(tb)[-1200:])
    try:
        await context.bot.send_message(
            chat_id=settings.admin_ids[0],
            text=f"⚠️ <b>خطا در ربات</b>\n<pre>{snippet}</pre>",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        pass
