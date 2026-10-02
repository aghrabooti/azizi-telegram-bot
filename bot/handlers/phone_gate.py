"""Mandatory phone-number collection (the three-layer gate).

Lesson v1.4.1: making the phone optional, or guarding only one entry point,
means users slip into the menus and we lose the lead.  So:

(a) invalid **text** while waiting → error + ask again, никогда a menu;
(b) every **inline button** is intercepted in handler group ``-1`` (before all
    other handlers) → an old/forwarded button cannot bypass the gate;
(c) **non-text** messages (photo, sticker, voice) → ask again instead of
    staying silent.

The only accepted input is the native ``request_contact`` button, and the
contact must belong to the sender.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot import constants as C
from bot.config import content
from bot.handlers.common import remember_user, show_page, user_has_phone
from bot.keyboards.menus import contact_keyboard, remove_keyboard
from bot.services.analytics import KIND_CONTACT, track
from bot.services.database import get_db
from bot.services.navigation import render_static
from bot.utils.phone import mask_phone, normalize_phone

logger = logging.getLogger(__name__)


async def ask_for_phone(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        prefix: str | None = None) -> None:
    """Send (or re-send) the contact request with the native keyboard."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None:
        return
    name = (user.first_name if user and user.first_name else "دانش‌آموز").strip()
    body = content.text("phone.request", name=name)
    if prefix:
        body = f"{prefix}\n\n{body}"
    await context.bot.send_message(
        chat_id=chat.id,
        text=body,
        reply_markup=contact_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store a shared contact; accepts every international format."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or message.contact is None:
        return

    remember_user(update)
    contact = message.contact

    # A user can forward somebody else's contact card — not acceptable here.
    if contact.user_id is not None and contact.user_id != user.id:
        await message.reply_text(
            content.text("phone.foreign_contact"),
            reply_markup=contact_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    phone = normalize_phone(contact.phone_number)
    if phone is None:
        await message.reply_text(
            content.text("phone.invalid"),
            reply_markup=contact_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    get_db().set_phone(user.id, phone)
    track(user.id, KIND_CONTACT, "saved")
    logger.info("phone stored for user %s (%s)", user.id, mask_phone(phone))

    await message.reply_text(
        content.text("phone.saved", phone=phone),
        reply_markup=remove_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
    raise ApplicationHandlerStop


async def gate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Layer (a) + (c): nothing but a contact gets through without a phone."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    if message.contact is not None:  # handled by handle_contact
        return

    remember_user(update)
    if user_has_phone(update):
        return  # fall through to the normal handlers

    text = (message.text or "").strip()
    if text.startswith("/start"):
        await ask_for_phone(update, context)
    elif message.text is not None:
        # The user typed something instead of pressing the button.
        guess = normalize_phone(text)
        if guess:
            # typed a valid international number — accept it, same as a contact
            get_db().set_phone(user.id, guess)
            track(user.id, KIND_CONTACT, "typed")
            logger.info("phone typed by user %s (%s)", user.id, mask_phone(guess))
            await message.reply_text(
                content.text("phone.saved", phone=guess),
                reply_markup=remove_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            await show_page(update, context, render_static(C.PAGE_MAIN), force_new=True)
            raise ApplicationHandlerStop
        track(user.id, KIND_CONTACT, "invalid_text")
        await ask_for_phone(update, context, prefix=content.text("phone.invalid"))
    else:
        track(user.id, KIND_CONTACT, "non_text")
        await ask_for_phone(update, context, prefix=content.text("phone.not_text"))

    raise ApplicationHandlerStop


async def gate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Layer (b): registered in group -1, so no button escapes the gate."""
    query = update.callback_query
    if query is None:
        return
    remember_user(update)
    if user_has_phone(update):
        return

    track(update.effective_user.id if update.effective_user else None, KIND_CONTACT, "gate_button")
    try:
        await query.answer(content.text("phone.gate_callback"), show_alert=True)
    except Exception as exc:  # noqa: BLE001 - expired query ids are fine
        logger.debug("gate answer failed: %s", exc)
    await ask_for_phone(update, context)
    raise ApplicationHandlerStop
