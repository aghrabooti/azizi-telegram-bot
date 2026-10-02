"""Free-text routing: whatever the user types lands here (after the gate)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot import constants as C
from bot.handlers import admin as admin_handlers
from bot.handlers.anonymous import on_admin_reply_shortcut, on_anon_message
from bot.handlers.common import remember_user, show_page
from bot.services.navigation import render_static

logger = logging.getLogger(__name__)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)

    # 1) an admin replying (Reply) to an anonymous-message notification
    if await on_admin_reply_shortcut(update, context):
        return
    # 2) admin flows: live content editing, panel reply
    if await admin_handlers.handle_admin_text(update, context):
        return
    # 3) the user is composing an anonymous message
    if await on_anon_message(update, context):
        return
    # 4) anything else: show the menu instead of staying silent
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_handlers.handle_admin_document(update, context)


async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photos, stickers, voice… from a user who already has a phone number."""
    remember_user(update)
    if await on_anon_message(update, context):
        return
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
