"""Digit/number/text helpers (Persian friendly)."""

from __future__ import annotations

import html

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"

_TO_EN = {ord(fa): en for fa, en in zip(FA_DIGITS, EN_DIGITS)}
_TO_EN.update({ord(ar): en for ar, en in zip(AR_DIGITS, EN_DIGITS)})
_TO_FA = {ord(en): fa for en, fa in zip(EN_DIGITS, FA_DIGITS)}


def to_en_digits(value: str) -> str:
    """Convert Persian/Arabic digits to ASCII digits."""
    return value.translate(_TO_EN)


def fa_digits(value: str | int) -> str:
    """Convert ASCII digits to Persian digits."""
    return str(value).translate(_TO_FA)


def group_thousands(amount: int) -> str:
    return f"{amount:,}".replace(",", "٬")


def format_price(amount: int | float | None, *, free_label: str, unknown_label: str,
                 toman_template: str) -> str:
    """Format a price exactly like the website does (Persian digits + ٬)."""
    if amount is None:
        return unknown_label
    try:
        value = int(round(float(amount)))
    except (TypeError, ValueError):
        return unknown_label
    if value <= 0:
        return free_label
    return toman_template.format(amount=fa_digits(group_thousands(value)))


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def esc(value: object) -> str:
    """HTML-escape a value for parse_mode=HTML messages."""
    return html.escape(str(value), quote=False)


def shorten(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
