"""Keyboard construction (inline menus + the native contact request)."""

from bot.keyboards.builder import (
    STYLE_DANGER,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    SUPPORTS_BUTTON_STYLES,
    inline_button,
    inline_markup,
)
from bot.keyboards.menus import contact_keyboard, page_markup, remove_keyboard

__all__ = [
    "SUPPORTS_BUTTON_STYLES",
    "STYLE_PRIMARY",
    "STYLE_SUCCESS",
    "STYLE_DANGER",
    "inline_button",
    "inline_markup",
    "page_markup",
    "contact_keyboard",
    "remove_keyboard",
]
