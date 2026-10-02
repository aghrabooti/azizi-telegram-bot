"""Turn rendered pages (plain data) into Telegram keyboards."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import content
from bot.keyboards.builder import inline_button, reply_button
from bot.services.navigation import Button, Page


def page_markup(page: Page) -> InlineKeyboardMarkup:
    rows = [
        [
            inline_button(
                button.text,
                callback_data=button.callback,
                url=button.url,
                style=button.style,
            )
            for button in row
        ]
        for row in page.rows
    ]
    return InlineKeyboardMarkup(rows)


def buttons_markup(rows: list[list[Button]]) -> InlineKeyboardMarkup:
    return page_markup(Page(id="adhoc", title="", text="", rows=rows))


def contact_keyboard() -> ReplyKeyboardMarkup:
    """The only way into the bot: the native "share my contact" button.

    There is deliberately no "later" / "skip" button — the phone number is
    required for consulting and sales follow-up.
    """
    return ReplyKeyboardMarkup(
        [[reply_button(content.text("phone.button"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=content.text("phone.button"),
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
