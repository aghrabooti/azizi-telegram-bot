"""Shared helpers for handlers (rendering, user bookkeeping, guards)."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.config.settings import settings
from bot.keyboards.menus import page_markup
from bot.services.analytics import KIND_PAGE, track
from bot.services.database import get_db
from bot.services.navigation import Page

logger = logging.getLogger(__name__)

#: key used in ``context.user_data`` to remember what the bot is waiting for
AWAIT_KEY = "awaiting"


def remember_user(update: Update) -> None:
    user = update.effective_user
    if user is None:
        return
    try:
        get_db().upsert_user(user.id, user.username, user.first_name, user.last_name)
    except Exception as exc:  # noqa: BLE001 - never break a flow on bookkeeping
        logger.warning("cannot upsert user %s: %s", user.id, exc)


def user_has_phone(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    try:
        return get_db().has_phone(user.id)
    except Exception as exc:  # noqa: BLE001
        logger.error("phone lookup failed for %s: %s", user.id, exc)
        # Fail closed: without a phone number we do not let anybody in.
        return False


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and settings.is_admin(user.id))


async def show_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: Page,
    *,
    force_new: bool = False,
    track_view: bool = True,
) -> None:
    """Render *page* — editing the same message when it came from a button."""
    user = update.effective_user
    if track_view:
        track(user.id if user else None, KIND_PAGE, page.id)

    markup = page_markup(page)
    query = update.callback_query
    if query is not None and not force_new:
        try:
            await query.edit_message_text(
                page.text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return
            logger.info("edit failed (%s) — sending a new message", exc)

    chat = update.effective_chat
    if chat is None:  # pragma: no cover
        return
    await context.bot.send_message(
        chat_id=chat.id,
        text=page.text,
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def answer(update: Update, text: str | None = None, *, alert: bool = False) -> None:
    query = update.callback_query
    if query is None:
        return
    try:
        await query.answer(text=text, show_alert=alert)
    except BadRequest as exc:  # query too old
        logger.debug("callback answer failed: %s", exc)


def set_awaiting(context: ContextTypes.DEFAULT_TYPE, value: Any) -> None:
    if context.user_data is None:  # pragma: no cover
        return
    if value is None:
        context.user_data.pop(AWAIT_KEY, None)
    else:
        context.user_data[AWAIT_KEY] = value


def get_awaiting(context: ContextTypes.DEFAULT_TYPE) -> Any:
    if context.user_data is None:  # pragma: no cover
        return None
    return context.user_data.get(AWAIT_KEY)
