"""Button helper.

Two hard-won rules are encoded here:

1. **Every** callback button gets a style, ``primary`` by default.  A button
   with no style renders as a washed-out grey box in Telegram clients released
   after 2026-02-09 — users think it is disabled.
2. Telegram accepts exactly three style values: ``primary`` / ``success`` /
   ``danger``.  Anything else (``positive``, ``destructive``, …) is a 400 from
   the API, which in practice means "the whole menu never appears".

Older python-telegram-bot releases do not have the ``style`` parameter at all.
We detect that at import time (:data:`SUPPORTS_BUTTON_STYLES`) and silently
build style-less buttons instead of crashing — the bot must keep working on
whatever version the host has installed.
"""

from __future__ import annotations

import inspect
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton

logger = logging.getLogger(__name__)

STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"
ALLOWED_STYLES = frozenset({STYLE_PRIMARY, STYLE_SUCCESS, STYLE_DANGER})

#: True when the installed python-telegram-bot exposes InlineKeyboardButton(style=…)
SUPPORTS_BUTTON_STYLES = "style" in inspect.signature(InlineKeyboardButton.__init__).parameters
SUPPORTS_REPLY_BUTTON_STYLES = "style" in inspect.signature(KeyboardButton.__init__).parameters

_warned = False


def _style_mode() -> str:
    from bot.config.settings import settings

    return settings.button_style_mode


def resolve_style(style: str | None) -> str | None:
    """Return a style Telegram accepts, or ``None`` when styles are disabled."""
    global _warned
    mode = _style_mode()
    if mode == "off":
        return None
    if style is None:
        style = STYLE_PRIMARY
    style = str(style).strip().lower()
    if style not in ALLOWED_STYLES:
        logger.warning(
            "invalid button style %r (allowed: %s) — falling back to %s",
            style,
            ", ".join(sorted(ALLOWED_STYLES)),
            STYLE_PRIMARY,
        )
        style = STYLE_PRIMARY
    if not SUPPORTS_BUTTON_STYLES:
        if mode == "native" and not _warned:
            logger.warning(
                "BUTTON_STYLE_MODE=native but python-telegram-bot has no `style` "
                "parameter — buttons will be classic/blue. Upgrade to >= 22.7."
            )
            _warned = True
        return None
    return style


def inline_button(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    style: str | None = STYLE_PRIMARY,
) -> InlineKeyboardButton:
    """Build one inline button; styled by default (never washed-out grey)."""
    if callback_data is None and url is None:
        raise ValueError("inline_button needs either callback_data or url")
    resolved = resolve_style(style)
    kwargs: dict[str, object] = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
        encoded = callback_data.encode("utf-8")
        if len(encoded) > 64:
            raise ValueError(f"callback_data too long ({len(encoded)} bytes): {callback_data!r}")
    if url is not None:
        kwargs["url"] = url
    if resolved is not None:
        kwargs["style"] = resolved
    return InlineKeyboardButton(text, **kwargs)


def inline_markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)


def reply_button(text: str, *, request_contact: bool = False, style: str | None = STYLE_PRIMARY):
    resolved = resolve_style(style) if SUPPORTS_REPLY_BUTTON_STYLES else None
    kwargs: dict[str, object] = {}
    if request_contact:
        kwargs["request_contact"] = True
    if resolved is not None:
        kwargs["style"] = resolved
    return KeyboardButton(text, **kwargs)
