"""/start, /menu, /help, /id."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot import constants as C
from bot.handlers.common import remember_user, set_awaiting, show_page, user_has_phone
from bot.handlers.phone_gate import ask_for_phone
from bot.services.analytics import KIND_COMMAND, track
from bot.services.navigation import render_static

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)
    set_awaiting(context, None)
    user = update.effective_user
    track(user.id if user else None, KIND_COMMAND, "/start")

    if not user_has_phone(update):
        await ask_for_phone(update, context)
        return
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)
    set_awaiting(context, None)
    user = update.effective_user
    track(user.id if user else None, KIND_COMMAND, "/menu")
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)
    user = update.effective_user
    track(user.id if user else None, KIND_COMMAND, "/help")
    await show_page(update, context, render_static(C.PAGE_HELP), force_new=True)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prints the numeric Telegram id — needed to fill ADMIN_IDS in .env."""
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    await message.reply_text(
        f"🆔 آیدی عددی شما: <code>{user.id}</code>",
        parse_mode=ParseMode.HTML,
    )
