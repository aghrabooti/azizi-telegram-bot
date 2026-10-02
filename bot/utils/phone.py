"""Phone normalisation.

Rules (v1.4.1 lesson — a wrong regex here locks real users out):

* Anything already in international form (``+`` followed by 7..15 digits) is
  **kept exactly as sent**.  Telegram sends ``+98…`` for Iranian contacts and
  ``+49…``/``+971…`` for users abroad; all of them must be accepted.
* Iranian local formats are normalised to ``+98…``:
  ``09121234567``, ``9121234567``, ``989121234567``, ``0098912…`` and the same
  numbers written with Persian/Arabic digits.
* A local land-line without ``+`` and without a known country prefix is
  invalid — we cannot guess the country.
"""

from __future__ import annotations

import re

from bot.utils.text import to_en_digits

_NON_DIGITS = re.compile(r"[^\d+]")
_INTERNATIONAL = re.compile(r"^\+\d{7,15}$")
_IR_MOBILE_CORE = re.compile(r"^9\d{9}$")  # 9XXXXXXXXX


def normalize_phone(raw: str | None) -> str | None:
    """Return the phone in ``+<digits>`` form, or ``None`` when invalid."""
    if not raw:
        return None

    value = to_en_digits(str(raw)).strip()
    # Telegram sometimes sends "98912..." with no plus, people paste "(0912) 123-4567"
    value = value.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    value = _NON_DIGITS.sub("", value)
    if not value:
        return None

    # keep a leading + only if it is the very first character
    has_plus = value.startswith("+")
    digits = value.lstrip("+").replace("+", "")
    if not digits.isdigit():
        return None

    if has_plus:
        candidate = "+" + digits
        return candidate if _INTERNATIONAL.match(candidate) else None

    # ---- no plus: try to recognise an Iranian mobile number -----------------
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]

    if _IR_MOBILE_CORE.match(digits):
        return "+98" + digits

    # Unknown local format (land-line, partial number, …) → invalid.
    return None


def mask_phone(phone: str | None) -> str:
    """``+989121234567`` -> ``+9891*****567`` (for logs / shared screenshots)."""
    if not phone:
        return "—"
    if len(phone) <= 7:
        return phone[:2] + "***"
    return phone[:5] + "*" * (len(phone) - 8) + phone[-3:]
