"""Inline navigation: static pages, catalog browsing, expired buttons."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot import constants as C
from bot.config import content
from bot.handlers.common import answer, remember_user, set_awaiting, show_page
from bot.services.catalog import get_catalog
from bot.services.navigation import (
    UnknownPage,
    parse_catalog,
    render_catalog_fields,
    render_catalog_list,
    render_catalog_types,
    render_static,
)

logger = logging.getLogger(__name__)


async def on_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    remember_user(update)
    set_awaiting(context, None)
    await answer(update)

    page_id = query.data.split(":", 1)[1]
    try:
        page = render_static(page_id)
    except UnknownPage:
        await answer(update, content.text("error.expired"), alert=True)
        return
    await show_page(update, context, page)


async def on_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    remember_user(update)
    set_awaiting(context, None)
    await answer(update)

    try:
        type_code, grade, field_code, page_number = parse_catalog(query.data)
    except (UnknownPage, IndexError, ValueError):
        await answer(update, content.text("error.expired"), alert=True)
        return

    if grade is None:
        await show_page(update, context, render_catalog_types(type_code))
        return
    if field_code is None:
        await show_page(update, context, render_catalog_fields(type_code, grade))
        return

    snapshot = await get_catalog().get_async()
    if not snapshot.ok:
        logger.warning("catalog unavailable: %s", snapshot.error)
    page = render_catalog_list(type_code, grade, field_code, page_number or 1, snapshot)
    await show_page(update, context, page)


async def on_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Page counters etc. — acknowledge so the client stops the spinner."""
    await answer(update)


async def on_unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any callback from an old build: tell the user instead of going silent."""
    query = update.callback_query
    logger.info("unknown callback: %r", query.data if query else None)
    await answer(update, content.text("error.expired"), alert=True)
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
